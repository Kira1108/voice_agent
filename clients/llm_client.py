import asyncio
import websockets
import pyaudio
import threading

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 480 # 30ms

is_running = True

def mic_worker(ws, loop, stream_in):
    print("🎤 Start talking... (Server will print STT and LLM responses in its own terminal)")
    while is_running:
        try:
            # Block and read perfectly from hardware
            data = stream_in.read(CHUNK, exception_on_overflow=False)
            if is_running:
                # Dispatch safely to async event loop
                asyncio.run_coroutine_threadsafe(ws.send(data), loop)
        except Exception as e:
            if is_running:
                print(f"Mic error: {e}")
            break

async def main():
    global is_running
    p = pyaudio.PyAudio()
    
    # Only open the input stream (no need for speaker here since LLM is text output on server)
    stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    # Note the updated endpoint: /ws/llm
    uri = "ws://127.0.0.1:8000/ws/llm"
    
    try:
        async with websockets.connect(uri) as ws:
            print(f"✅ Connected to {uri}")
            
            loop = asyncio.get_running_loop()
            
            # Use dedicated OS thread for PyAudio blocking boundaries
            t_mic = threading.Thread(target=mic_worker, args=(ws, loop, stream_in), daemon=True)
            t_mic.start()
            
            # The async loop handles receiving from networking layer (to detect disconnects)
            while is_running:
                try:
                    data = await ws.recv()
                    # Server currently prints in its own console, but if we later 
                    # decide to send JSON/Text transcripts back, we can print them here.
                    if isinstance(data, str):
                        print(f"[{uri}] Server says: {data}")
                except websockets.exceptions.ConnectionClosed:
                    break
                    
    except websockets.exceptions.ConnectionClosed:
        print("🔊 Connection closed by server.")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        if isinstance(e, ConnectionRefusedError):
            print("🔊 Connection refused. Is the server running?")
        else:
            print(f"Error occurred: {e}")
    finally:
        is_running = False
        # Give thread a tiny moment to see is_running = False
        await asyncio.sleep(0.1)
        try:
            stream_in.stop_stream()
            stream_in.close()
            p.terminate()
        except:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Client stopped by user.")