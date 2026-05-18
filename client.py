import asyncio
import websockets
import pyaudio
import threading
import queue
import time

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 480 # 30ms

is_running = True
audio_out_queue = queue.Queue()

def mic_worker(ws, loop, stream_in):
    print("🎤 Start talking...")
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

def speaker_worker(stream_out):
    while is_running:
        try:
            # Pop with a short timeout so we can periodically check `is_running`
            data = audio_out_queue.get(timeout=0.05)
            
            # --- LATENCY CLAMP (Anti-Bufferbloat) ---
            # Relaxed threshold: tolerate up to 10 chunks (~300ms) of jitter buffer.
            # Only drop if it gets really high, avoiding choppy audio caused by micro-bursts.
            stale_dropped = 0
            while audio_out_queue.qsize() > 10:
                try:
                    data = audio_out_queue.get_nowait()
                    stale_dropped += 1
                except queue.Empty:
                    break
                    
            # if stale_dropped > 0:
            #     print(f"⚠️ Dropped {stale_dropped} stale chunks to preserve low latency")
                
            # Write practically to hardware
            stream_out.write(data)
        except queue.Empty:
            continue
        except Exception as e:
            if is_running:
                print(f"Speaker error: {e}")
            break

async def main():
    global is_running
    p = pyaudio.PyAudio()
    
    stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    stream_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

    uri = "ws://127.0.0.1:8000/ws/echo"
    
    try:
        async with websockets.connect(uri) as ws:
            print(f"✅ Connected to {uri}")
            
            loop = asyncio.get_running_loop()
            
            # Use dedicated OS threads instead of async loop tasks for PyAudio blocking boundaries
            t_mic = threading.Thread(target=mic_worker, args=(ws, loop, stream_in), daemon=True)
            t_spk = threading.Thread(target=speaker_worker, args=(stream_out,), daemon=True)
            
            t_mic.start()
            t_spk.start()
            
            # The async loop only handles receiving from networking layer
            while is_running:
                data = await ws.recv()
                if isinstance(data, bytes):
                    audio_out_queue.put(data)
                    
    except websockets.exceptions.ConnectionClosed:
        print("🔊 Connection closed.")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        is_running = False
        # Give threads a tiny moment to see is_running = False
        await asyncio.sleep(0.1)
        try:
            stream_in.stop_stream()
            stream_in.close()
            stream_out.stop_stream()
            stream_out.close()
            p.terminate()
        except:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Client stopped by user.")
