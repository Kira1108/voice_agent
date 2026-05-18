# Voice Agent Framework

## 核心设计思想 (Core Design)

该框架采用**“数据流（Data Plane）与控制流（Control Plane）”解耦**的全异步图结构（Graph）架构设计。其核心由四大要素紧密协作：

1. **Components（组件）**：框架内的基础工作单元（如 STT、LLM、TTS 节点）。每个组件都在独立的异步任务中运行，拥有自己的输入队列并独立消化数据，完全消除了因为某个节点的耗时（如网络请求）而阻塞整条链路的可能。
2. **Frame Flow（数据流）**：实体数据（如音频 `AudioFrame`，文本 `TextFrame`）在图网络中以有向的方式顺流而下。上游组件处理完毕后，直接 `push` 到所有通过 `.to()` 建立连接的下游组件队列中，实现数据和处理结果的自然传递。
3. **Events（控制流）**：高优先级的全局信号。受制于网络和硬件 IO，数据流（Frames）在管道中漫流可能会堆积并导致延迟；但是对于“语音打断（Interruption）”等需要立即响应的场景，系统需要一条脱离队列的高速公路，这就是 Events。
4. **AgentSession（会话与中枢）**：作为整个图的生命周期与事件总线（Event Bus）管理核心。它将所有零散的组件绑定到一起。当某组件（如 VAD）触发 `用户开始说话 (打断)` 事件时，Session 会立即将其广播给所有组件；下游的组件（如正在排队等候合成的 TTS 组件）接收到事件后，便可立即执行 `flush_queue()` 丢弃遗留的脏数据并停止当前生成，从而实现低延迟、高灵活的流式对话。

---

An asynchronous, event-driven, pipeline-based framework for building streaming voice agents. This framework allows you to construct audio and text processing pipelines using a source-processor-sink topology, fully managed by an event-driven session lifecycle.

## Core Concepts

*   **Frames**: The data packets flowing through the pipeline (e.g., `AudioFrame`, `TextFrame`).
*   **PipelineComponent**: A node in the graph that consumes frames, processes them, and pushes them downstream. 
*   **BaseSourceComponent**: A special entry-point node that generates frames from external asynchronous IO (like WebSockets or WebRTC).
*   **Events**: Global control signals broadcasted across all components (e.g., `SESSION_ENDED`, `CANCEL_PIPELINE`).
*   **Pipeline**: The core orchestrator that binds components to a session and concurrently runs their internal tasks.

---

## Tutorial: Building a Voice Pipeline

Here is a step-by-step guide on how to build and run a basic pipeline.

### 1. Create a Source Component
Source components ingest data from the outside world. Inherit from `BaseSourceComponent` and implement the `generate_frames` async generator.

```python
import asyncio
from voice_agent.components.base import BaseSourceComponent
from voice_agent.frame.base import TextFrame

class WebSocketSource(BaseSourceComponent):
    def __init__(self, name: str):
        super().__init__(name)

    async def generate_frames(self):
        # Simulate receiving 3 network packets
        for i in range(3):
            await asyncio.sleep(0.5) 
            yield TextFrame(text=f"User input {i}")
```

### 2. Create Processing and Sink Components
Normal components consume data from upstream. Inherit from `PipelineComponent` and implement `process_frame`. 
*   **Processors** modify data and call `await self.push(new_frame)`.
*   **Sinks** simply do not call `push` and instead terminate the data path (like playing back audio or saving to a database).

```python
from voice_agent.components.base import PipelineComponent
from voice_agent.frame.base import TextFrame

class LLMProcessor(PipelineComponent):
    async def process_frame(self, frame: TextFrame):
        print(f"[{self.name}] Thinking about: {frame.text}")
        # Simulate LLM response time
        await asyncio.sleep(1.0)
        
        # Push to the next component
        response_frame = TextFrame(text=f"LLM Reply to '{frame.text}'")
        await self.push(response_frame)

class TextConsoleSink(PipelineComponent):
    async def process_frame(self, frame: TextFrame):
        # Sink components just consume, they don't push further
        print(f"[{self.name}] Output: {frame.text}")
```

### 3. Wire the Pipeline and Run
Use the elegant `.to()` method to chain components together. The `Pipeline` orchestrator handles booting them up concurrently.

```python
import asyncio
from voice_agent.pipeline.base import Pipeline

async def main():
    # 1. Instantiate components
    source = WebSocketSource("NetworkSource")
    llm = LLMProcessor("AwesomeLLM")
    console = TextConsoleSink("ConsoleOut")
    
    # 2. Wire the topology (fluent interface)
    source.to(llm).to(console)
    
    # 3. Register to Pipeline
    pipeline = Pipeline(components=[source, llm, console])
    
    # 4. Run the pipeline in the background
    pipeline_task = asyncio.create_task(pipeline.run())
    
    # 5. Let it run for a while, then gracefully stop
    await asyncio.sleep(4.0)
    await pipeline.stop()
    await pipeline_task

if __name__ == "__main__":
    asyncio.run(main())
```

## Lifecycle & Event Bus

Every component registered to the pipeline gets injected with an `AgentSession`. You can broadcast events across the entire graph natively.

**Emitting an Event:**
```python
from voice_agent.events.base import VoiceAgentEvent, EventType

# Inside any component's process_frame or generator:
await self.emit(VoiceAgentEvent(type=EventType.USER_STARTED_SPEAKING))
```

**Handling an Event:**
Override `handle_event` in your component to react to signals.
```python
async def handle_event(self, event: VoiceAgentEvent):
    if event.type == EventType.USER_STARTED_SPEAKING:
        # e.g., flush current text-to-speech queues to interrupt agent
        self.flush_queue() 

    # Always call super to ensure graceful session stops aren't blocked!
    await super().handle_event(event) 
```