import asyncio
import os
import pytest
from dotenv import load_dotenv
from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import Frame, TextFrame, TextStreamFrame
from voice_agent.plugins.azure.llm import SimpleAzureLLM

# 这是一个模拟的下游组件，用于接收 LLM 吐出来的字
class DummyOutputComponent(PipelineComponent):
    def __init__(self):
        super().__init__("DummyOutput")
        self.received_chunks = []
        self.is_finished = asyncio.Event()

    async def process_frame(self, frame: Frame):
        if isinstance(frame, TextStreamFrame):
            if frame.text_chunk:
                self.received_chunks.append(frame.text_chunk)
            
            if frame.is_end:
                self.is_finished.set()

@pytest.mark.asyncio
async def test_azure_llm_response():
    # 测试前加载环境变量
    load_dotenv()
    
    # 简单的环境变量检查，如果没有配置可以直接跳过，防止报错
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        pytest.skip("未在环境中找到 AZURE_OPENAI_API_KEY，跳过真正的网络请求测试。")
    
    llm = SimpleAzureLLM(model="gpt-4o")
    output = DummyOutputComponent()
    
    llm.to(output)
    
    # 启动后台任务
    llm_task = asyncio.create_task(llm.run())
    out_task = asyncio.create_task(output.run())
    
    # 发送测试消息
    await llm.input_queue.put(TextFrame(text="你好，测试。"))
    
    # 加入超时机制（防止网络卡住导致测试死锁，设置15秒超时）
    try:
        await asyncio.wait_for(output.is_finished.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        pytest.fail("等待 Azure LLM 回复超时。")
    finally:
        # 清理工作
        llm._stop_event.set()
        output._stop_event.set()
        llm_task.cancel()
        out_task.cancel()
    
    # 断言：检测是否成功接收到了 LLM 分块返回的文字
    assert len(output.received_chunks) > 0, "没有从 LLM 收到任何回复！"
    
    # 把收到的语句打印出来（加上 -s 参数运行 pytest 可以看到）
    full_response = "".join(output.received_chunks)
    print(f"\n[Test Result] LLM 回复完整内容: {full_response}")