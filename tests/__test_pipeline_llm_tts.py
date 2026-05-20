
import asyncio
import os
import pyaudio
from dotenv import load_dotenv

from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import Frame, TextFrame, AudioFrame
from voice_agent.plugins.azure.llm import SimpleAzureLLM
from voice_agent.plugins.mlx.tts import MlxTTSComponent

# 定义一个用于在本地直接播放 AudioFrame 的输出组件
class LocalSpeakerComponent(PipelineComponent):
    def __init__(self):
        super().__init__("LocalSpeaker")
        self.p = pyaudio.PyAudio()
        # 根据我们计算出的 MLX TTS 的采样率，设置为 24000 Hz, 单声道, 16位PCM
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            output=True
        )
        self.is_finished = asyncio.Event()
        self._silence_timer = None

    async def process_frame(self, frame: Frame):
        if isinstance(frame, AudioFrame):
            # 将音频数据写入流进行播放。
            # 为了防止阻塞 async loop，我们将其扔到线程池执行
            await asyncio.to_thread(self.stream.write, frame.audio_data)
            
            # 使用一个简单的延时计时器来判断播放是否完全结束 (如果超过 2 秒还没收到新的音频，认为一句话说完了)
            if self._silence_timer:
                self._silence_timer.cancel()
            self._silence_timer = asyncio.create_task(self._mark_finished_after_delay())

    async def _mark_finished_after_delay(self):
        try:
            await asyncio.sleep(2.0)
            self.is_finished.set()
        except asyncio.CancelledError:
            pass

    async def run(self):
        try:
            await super().run()
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()

async def main():
    load_dotenv()
    
    print("正在初始化 LLM 与 TTS 引擎... (这可能需要几秒钟)")
    # 初始化三个节点
    llm = SimpleAzureLLM(model="gpt-4o")
    tts = MlxTTSComponent(voice="serena") # 你也可以试试其它音色比如 "jessica"
    speaker = LocalSpeakerComponent()
    
    # 将他们像乐高一样串联起来： LLM -> TTS -> Speaker
    llm.to(tts).to(speaker)
    
    # 启动所有节点后台任务
    tasks = [
        asyncio.create_task(llm.run()),
        asyncio.create_task(tts.run()),
        asyncio.create_task(speaker.run())
    ]
    
    print("\n✅ 所有引擎就绪！")
    
    # 触发一个模拟测试！
    test_text = "你好啊！我是你亲手开发的语音助手，我现在已经可以完美地调用 MLX 大模型生成非常自然的语音了。快来听听看我的声音怎么样吧？"
    print(f"👉 开始输入: {test_text}")
    print("⏳ 等待大模型生成与音频合成...\n")
    
    await llm.input_queue.put(TextFrame(text=test_text))
    
    # 等待播放组件发出完成信号
    await speaker.is_finished.wait()
    print("\n🔊 本次播放测试结束！")
    
    # 关闭节点与清理任务
    for comp in [llm, tts, speaker]:
        comp._stop_event.set()
        
    for t in tasks:
        t.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n手动中断测试。")