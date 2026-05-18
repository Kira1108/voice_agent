from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from voice_agent.transport.websocket import WebSocketTransport
from voice_agent.components.base import PipelineComponent
from voice_agent.pipeline.base import Pipeline
from voice_agent.frame import AudioFrame

router = APIRouter()

class EchoComponent(PipelineComponent):
    def __init__(self):
        super().__init__(name="EchoComponent")

    async def process_frame(self, frame):
        # Transparently pass audio frames forward
        if isinstance(frame, AudioFrame):
            await self.push(frame)

@router.websocket("/ws/echo")
async def websocket_echo_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    transport = WebSocketTransport(websocket)
    
    # Get transport input and output components
    input_comp = transport.input
    output_comp = transport.output
    
    # Create the transparent echo component
    echo_comp = EchoComponent()
    
    # Chain components: input -> echo -> output
    input_comp.to(echo_comp).to(output_comp)
    
    # Initialize the pipeline with all components
    pipeline = Pipeline(components=[input_comp, echo_comp, output_comp])
    
    try:
        # Start the pipeline (it will run until SESSION_ENDED is triggered by disconnect)
        await pipeline.run()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Pipeline encountered an error: {e}")
    finally:
        # Give pipeline stop a chance if it hasn't successfully cleaned up
        try:
            await pipeline.stop()
        except Exception:
            pass



