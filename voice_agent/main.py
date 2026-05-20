from contextlib import asynccontextmanager
from fastapi import FastAPI
from voice_agent.api.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Preloading AI Models during Server Startup...")
    print("⏳ Note: Apple Silicon MLX relies on Metal JIT. First compile takes ~30 seconds...")
    # Import inside to avoid circular dependencies if any
    from voice_agent.plugins.mlx.tts import MlxTTSComponent
    # Spin up an instance just to trigger the global cache and warmup
    dummy_tts = MlxTTSComponent()
    await dummy_tts.start_engine()
    print("✅ System Ready! Accepting connections. (Now you can run the client)")
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(websocket_router)

