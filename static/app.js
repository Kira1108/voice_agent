let ws;
let audioContext;
let mediaStream;
let processor;
let analyser;
let animationFrameId;

let playbackContext;
let nextPlayTime = 0;

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');

// Helper to determine websocket URL
const wsProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
const wsUrl = wsProtocol + window.location.host + "/ws/agent";

startBtn.onclick = async () => {
    startBtn.disabled = true;
    statusDiv.innerText = "Connecting...";

    try {
        ws = new WebSocket(wsUrl);
        ws.binaryType = "arraybuffer";

        ws.onopen = async () => {
            statusDiv.innerText = "Connected. Starting Audio...";
            stopBtn.disabled = false;
            await startAudio();
        };

        ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                playAudioChunk(event.data);
            }
        };

        ws.onclose = () => {
            console.log("WebSocket connection closed.");
            stopAudio();
        };
        
        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
            statusDiv.innerText = "WebSocket Error";
            stopAudio();
        };
    } catch (e) {
        console.error(e);
        statusDiv.innerText = "Error connecting";
        startBtn.disabled = false;
    }
};

stopBtn.onclick = () => {
    if (ws) ws.close();
    stopAudio();
};

async function startAudio() {
    try {
        // Enforce Acoustic Echo Cancellation and request 16kHz
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1,
                sampleRate: 16000 
            }
        });

        // Setup microphone capture context
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(mediaStream);
        
        // 挂载一个分析器，用于前端60fps监听麦克风音量并更新UI 波纹！
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        renderVolume();
        
        // Use ScriptProcessor for easy PCM extraction
        processor = audioContext.createScriptProcessor(4096, 1, 1);

        // 标准抓取麦克风且不产生物理扬声器回溯的安全方式
        source.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = (e) => {
            // 1. 获取麦克风输入的原生声音
            const inputData = e.inputBuffer.getChannelData(0);
            
            // 2. [关键] 将输出频道的所有帧填0（静音），这样才能避免你自己听到你自己说话的回声！
            const outputData = e.outputBuffer.getChannelData(0);
            for (let i = 0; i < outputData.length; i++) {
                outputData[i] = 0;
            }

            if (ws && ws.readyState === WebSocket.OPEN) {
                // Convert Float32 [-1.0, 1.0] to Int16 [-32768, 32767]
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    let s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Send raw bytes to python backend
                ws.send(pcm16.buffer);
            }
        };

        // Setup playback context matching our TTS audio (24kHz is what Qwen3-TTS uses)
        playbackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        nextPlayTime = playbackContext.currentTime;

        statusDiv.innerText = "Active. Speak now!";
        statusDiv.style.color = "#4caf50";
    } catch (err) {
        console.error("Audio error:", err);
        statusDiv.innerText = "Microphone error. Allow permissions.";
        statusDiv.style.color = "#f44336";
        stopAudio();
    }
}

// 采用 60FPS (requestAnimationFrame) 的频率分析声波，动态改变 CSS 音量阈值 --mic-vol
function renderVolume() {
    if (!analyser) return;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for(let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    // 归一化为 0 到 1 之间 (以 80 作为高音基准)
    const vol = Math.min(avg / 80, 1.0);
    
    // 把结果传递给全局 CSS 变量
    document.documentElement.style.setProperty('--mic-vol', vol);
    animationFrameId = requestAnimationFrame(renderVolume);
}

function playAudioChunk(arrayBuffer) {
    if (!playbackContext) return;

    // Convert incoming Int16 to Float32 for Web Audio API
    const int16Array = new Int16Array(arrayBuffer);
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
    }

    const audioBuffer = playbackContext.createBuffer(1, float32Array.length, 24000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = playbackContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackContext.destination);

    // 追加哪怕是一丁点的缓冲时间（Jitter Buffer），对抗网络和 GPU 的抖动
    // 防止后一个包晚到导致 currentTime 追上 nextPlayTime 造成的断档卡顿
    const JITTER_BUFFER_SECONDS = 0.2; // 200毫秒的延迟池

    // 如果播放器处于闲置状态（或者网络彻底断档了）
    if (nextPlayTime < playbackContext.currentTime) {
        nextPlayTime = playbackContext.currentTime + JITTER_BUFFER_SECONDS;
    }
    source.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;
}

function stopAudio() {
    if (processor) processor.disconnect();
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
    if (audioContext) audioContext.close();
    if (playbackContext) playbackContext.close();
    if (analyser) analyser.disconnect();
    if (animationFrameId) cancelAnimationFrame(animationFrameId);

    ws = null;
    processor = null;
    mediaStream = null;
    audioContext = null;
    playbackContext = null;
    analyser = null;
    // 恢复球的静止
    document.documentElement.style.setProperty('--mic-vol', 0);

    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusDiv.innerText = "Disconnected";
    statusDiv.style.color = "#d4d4d4";
}