let ws;
let audioContext;
let stream;
let scriptProcessor;
let analyser;
let micAnimationFrame;

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const orb = document.getElementById('orb');
const statusEl = document.getElementById('status');

const JITTER_BUFFER_SECONDS = 0.2; // 200ms Jitter Buffer
let ttsStartTime = 0;
let micContext;

startBtn.onclick = async () => {
    try {
        startBtn.disabled = true;
        
        if (statusEl) statusEl.innerText = 'Connecting...';

        ws = new WebSocket(`ws://${window.location.host}/ws/agent`);
        ws.binaryType = "arraybuffer";

        ws.onopen = async () => {
            console.log("WebSocket connected");
            // Must share AudioContext for downstream TTS playback
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            
            // Re-init TTS
            ttsStartTime = 0;
            
            // Microphone stream
            // AEC / Noise Suppression are native browser flags:
            stream = await navigator.mediaDevices.getUserMedia({ 
                audio: { 
                    echoCancellation: true, 
                    noiseSuppression: true, 
                    autoGainControl: true 
                } 
            });

            // ASR expects 16kHz
            micContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const source = micContext.createMediaStreamSource(stream);
            
            // For animation
            analyser = micContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            updateMicVolume();

            // WebRTC style capture via script processor
            scriptProcessor = micContext.createScriptProcessor(4096, 1, 1);
            source.connect(scriptProcessor);
            scriptProcessor.connect(micContext.destination);

            scriptProcessor.onaudioprocess = (e) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const int16Data = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        int16Data[i] = Math.max(-1, Math.min(1, inputData[i])) * 32767;
                    }
                    ws.send(int16Data.buffer);
                }
                
                // CRUCIAL: Zero out the output buffer to avoid echoing from mic context!
                const outputData = e.outputBuffer.getChannelData(0);
                for (let i = 0; i < outputData.length; i++) {
                    outputData[i] = 0; 
                }
            };

            stopBtn.disabled = false;
            if (statusEl) statusEl.innerText = 'Active (Listening)';
        };

        ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                // Incoming TTS from backend (24000Hz, 16bit PCM)
                const int16Data = new Int16Array(event.data);
                const float32Data = new Float32Array(int16Data.length);
                for (let i = 0; i < int16Data.length; i++) {
                    float32Data[i] = int16Data[i] / 32768.0;
                }

                const audioBuffer = audioContext.createBuffer(1, float32Data.length, 24000);
                audioBuffer.copyToChannel(float32Data, 0);

                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioContext.destination);

                const currentTime = audioContext.currentTime;
                // Buffer to smooth playback
                if (ttsStartTime < currentTime + JITTER_BUFFER_SECONDS) {
                    ttsStartTime = currentTime + JITTER_BUFFER_SECONDS;
                }
                source.start(ttsStartTime);
                ttsStartTime += audioBuffer.duration;
            }
        };

        ws.onclose = () => stopPlayback();
        ws.onerror = (e) => { console.error(e); stopPlayback(); };

    } catch (err) {
        console.error("Error starting stream:", err);
        stopPlayback();
    }
};

stopBtn.onclick = () => {
    stopPlayback();
};

function stopPlayback() {
    if (ws) {
        ws.close();
        ws = null;
    }
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (micContext) {
        micContext.close();
        micContext = null;
    }
    cancelAnimationFrame(micAnimationFrame);
    orb.style.setProperty('--mic-vol', '0');

    startBtn.disabled = false;
    stopBtn.disabled = true;
    if (statusEl) statusEl.innerText = 'Ready to connect';
}

function updateMicVolume() {
    if (!analyser) return;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    // Normalize ratio 0 to 1
    const volRatio = Math.min(avg / 128.0, 1.0);
    
    orb.style.setProperty('--mic-vol', volRatio.toString());
    micAnimationFrame = requestAnimationFrame(updateMicVolume);
}
