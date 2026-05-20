import asyncio
from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import Frame, TextFrame, TextStreamFrame
from openai import AsyncAzureOpenAI
from uuid import uuid4
import os
import time


class SimpleAzureLLM(PipelineComponent):
    
    def __init__(self,
        model:str = "gpt-4o",
        endpoint:str = None,
        api_version:str = None,
        api_key:str = None,
        name: str = "SimpleAzureLLM", queue_size: int = 100):
        super().__init__(name, queue_size)
        self.model = model
        if not all([endpoint, api_version, api_key]):
            print("⚠️ Credentials not provided, attemping to load from .env file...")
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("OPENAI_API_VERSION")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            if not all([endpoint, api_version, api_key]):
                raise ValueError("Credentials for Azure Openai not provided, either via parameters or .env file.")
        
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=api_key
        )

        
        self.memory = [
            {"role": "system", "content": "你是一个可爱的语音助手，协助我完成各种任务。 说话要口语化，不要带有emoji，markdown格式，各种文本符号，要可爱一点，自然一点。"}
        ]
    async def process_frame(self, frame: Frame):
        
        response_id = str(uuid4())
        
        if isinstance(frame, TextFrame):
            user_text = frame.text.strip()
            if not user_text:
                return
            
            print(f"[{self.name}] User said: {user_text}")
            
            self.memory.append({"role": "user", "content": user_text})
            # 修正 1: 使用最新的 openai SDK 调用方式
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self.memory,
                stream=True
            )
            
            is_first = True
            start = time.perf_counter()
            buffered_response = ""
            async for chunk in response:
                # 某些情况下 choices 可能为空，保险起见加上判断
                if not chunk.choices:
                    continue
                    
                # 修正 2: Pydantic对象的属性访问
                content = chunk.choices[0].delta.content or ""
                
                if content:
                    buffered_response += content
                    await self.push(
                        TextStreamFrame(
                            text_chunk=content, 
                            response_id=response_id, 
                            is_first=is_first, 
                            is_end=False
                        )
                    )
                    if is_first:
                        TTFT = (time.perf_counter() - start) * 1000
                        print(f"  [LLM] 首字到达时间: {TTFT:.2f} ms")
                        is_first = False
                                
            if not is_first: # 确保有过正常输出才发送结束包
                await self.push(
                    TextStreamFrame(
                        text_chunk="", 
                        response_id=response_id, 
                        is_first=False, 
                        is_end=True
                    )
                )
                self.memory.append({"role": "assistant", "content": buffered_response})
