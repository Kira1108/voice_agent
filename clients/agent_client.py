import asyncio
import websockets
import pyaudio
import threading

# ================= AUDIO SETTINGS =================
FORMAT = pyaudio.paInt16
CHANNELS = 1

# 麦克风输入给服务器（配合腾讯 ASR 的 16000 采样率）
INPUT_RATE = 16000 
INPUT_CHUNK = 480 # 30ms

# 扬声器播放从服务器接收的声音 （配合 MLX TTS 输出的 24000 采样率）
OUTPUT_RATE = 24000
OUTPUT_CHUNK = 1200 # 对写流没那么严格限制，写块即可

is_running = True

def mic_worker(ws, loop, stream_in):
    print("\n🎤 语音助手已就绪，请直接开始说话... (按 Ctrl+C 退出)")
    while is_running:
        try:
            # 阻塞从硬件读取声音
            data = stream_in.read(INPUT_CHUNK, exception_on_overflow=False)
            if is_running:
                # 推送给后端的 asyncio loop 走 WebSockets
                asyncio.run_coroutine_threadsafe(ws.send(data), loop)
        except Exception as e:
            if is_running:
                print(f"Mic error: {e}")
            break


async def main():
    global is_running
    p = pyaudio.PyAudio()
    
    # 开启两个流：一个专属 input, 一个专属 output
    stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=INPUT_RATE, input=True, frames_per_buffer=INPUT_CHUNK)
    stream_out = p.open(format=FORMAT, channels=CHANNELS, rate=OUTPUT_RATE, output=True)

    # 路由为我们刚新增的端点全链路 Agent
    uri = "ws://127.0.0.1:8000/ws/agent"
    
    try:
        # 为了防止后端首次连接时加载巨型模型卡住导致握手超时，我们将超时放宽！
        async with websockets.connect(uri, open_timeout=60, ping_timeout=60) as ws:
            print(f"✅ 连接成功： {uri}")
            
            loop = asyncio.get_running_loop()
            
            # 使用独立线程跑麦克风避免阻塞 WebSocket 获取回复
            t_mic = threading.Thread(target=mic_worker, args=(ws, loop, stream_in), daemon=True)
            t_mic.start()
            
            # 主循环：全速接收后端传回的 TTS 二进制音频并播放
            while is_running:
                try:
                    message = await ws.recv()
                    if isinstance(message, bytes):
                        # 为了极低延迟，把播放丢进线程慢慢排队写入声卡
                        await asyncio.to_thread(stream_out.write, message)
                    elif isinstance(message, str):
                        print(f"[{uri}] Server message: {message}")
                except websockets.exceptions.ConnectionClosed:
                    break
                    
    except websockets.exceptions.ConnectionClosed:
        print("🔊 服务器断开了连接。")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        if isinstance(e, ConnectionRefusedError):
            print("🔊 连接被拒绝，Uvicorn 服务器启动了吗？")
        else:
            print(f"Error occurred: {e}")
    finally:
        is_running = False
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
        print("\n⏹️ 客户端已关闭。")