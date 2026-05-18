from fastapi import FastAPI
from voice_agent.api.websocket import router as websocket_router


app = FastAPI()
app.include_router(websocket_router)

