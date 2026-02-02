import asyncio
import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template_string

app = Flask(__name__)

AUDIO_DIR = "static/audio"
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR, exist_ok=True)

history_data = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Codka Soomaaliga - TTS</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: 221 83% 53%;
            --background: 210 40% 98%;
        }
        body { font-family: 'DM Sans', sans-serif; background-color: hsl(var(--background)); }
        .glass-panel { background: white; border: 1px solid #e5e7eb; box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.04); }
        
        input[type=range] {
            -webkit-appearance: none;
            background: transparent;
        }
        input[type=range]::-webkit-slider-runnable-track {
            width: 100%;
            height: 6px;
            background: #e5e7eb;
            border-radius: 10px;
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 18px;
            width: 18px;
            border-radius: 50%;
            background: #2563eb;
            cursor: pointer;
            margin-top: -6px;
            box-shadow: 0 0 10px rgba(37, 99, 235, 0.3);
        }

        .voice-btn-active { 
            border-color: #2563eb; 
            background-color: #eff6ff; 
            color: #2563eb; 
        }

        .wave-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 3px;
            height: 60px;
        }
        .bar {
            width: 4px;
            height: 8px;
            background: #2563eb;
            border-radius: 10px;
            transition: height 0.2s ease;
        }
        .bar.animating {
            animation: wave 1s ease-in-out infinite;
        }
        @keyframes wave {
            0%, 100% { height: 8px; }
            50% { height: 40px; }
        }
    </style>
</head>
<body class="min-h-screen py-10 px-4">
    <div class="max-w-4xl mx-auto space-y-8">
        
        <div class="text-center space-y-2">
            <div class="inline-flex items-center justify-center p-3 bg-blue-50 rounded-2xl mb-2 text-blue-600">
                <i data-lucide="languages" class="w-8 h-8"></i>
            </div>
            <h1 class="text-4xl font-bold text-gray-900">Codka Soomaaliga</h1>
            <p class="text-gray-500 font-medium">Advanced Neural Text-to-Speech Engine</p>
        </div>

        <div class="grid lg:grid-cols-5 gap-8">
            <div class="lg:col-span-3 space-y-6">
                <div class="glass-panel p-6 rounded-3xl space-y-6">
                    
                    <div class="grid grid-cols-2 gap-4">
                        <button id="btnMuuse" onclick="setVoice('so-SO-MuuseNeural')" class="voice-btn-active flex flex-col items-center p-4 rounded-2xl border-2 transition-all">
                            <i data-lucide="user" class="w-6 h-6 mb-2"></i>
                            <span class="font-bold text-sm">Muuse (Male)</span>
                        </button>
                        <button id="btnUbax" onclick="setVoice('so-SO-UbaxNeural')" class="flex flex-col items-center p-4 rounded-2xl border-2 border-gray-100 text-gray-400 transition-all">
                            <i data-lucide="user" class="w-6 h-6 mb-2"></i>
                            <span class="font-bold text-sm">Ubax (Female)</span>
                        </button>
                    </div>

                    <div class="space-y-2">
                        <label class="text-sm font-bold text-gray-700">Enter Somali Text</label>
                        <div class="relative">
                            <textarea id="textInput" oninput="handleInput()" class="w-full min-h-[150px] p-4 rounded-2xl border-2 border-gray-100 focus:border-blue-500 outline-none transition-all text-gray-700" placeholder="Qor halkan qoraalka aad rabto..."></textarea>
                            <div class="absolute bottom-3 right-3 text-[10px] text-gray-400 font-bold uppercase tracking-wider">
                                <span id="charCount">0</span> chars
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-6 p-4 bg-gray-50 rounded-2xl">
                        <div class="space-y-3">
                            <div class="flex justify-between text-xs font-bold text-gray-500">
                                <span>SPEED</span>
                                <span id="rateLabel">0%</span>
                            </div>
                            <input type="range" id="rate" min="-50" max="50" value="0" oninput="updateSliders()">
                        </div>
                        <div class="space-y-3">
                            <div class="flex justify-between text-xs font-bold text-gray-500">
                                <span>PITCH</span>
                                <span id="pitchLabel">0Hz</span>
                            </div>
                            <input type="range" id="pitch" min="-20" max="20" value="0" oninput="updateSliders()">
                        </div>
                    </div>

                    <button id="generateBtn" onclick="generate()" disabled class="w-full h-14 bg-gray-200 text-gray-400 font-bold rounded-2xl transition-all flex items-center justify-center gap-2">
                        <i data-lucide="sparkles" class="w-5 h-5"></i>
                        <span>Generate Speech</span>
                    </button>
                </div>
            </div>

            <div class="lg:col-span-2 space-y-6">
                <div id="playerCard" class="hidden glass-panel p-6 rounded-3xl space-y-6 animate-in fade-in duration-500">
                    <div class="wave-container" id="waveform"></div>
                    
                    <div class="space-y-2">
                        <input type="range" id="audioSeek" value="0" class="w-full">
                        <div class="flex justify-between text-[10px] font-bold text-gray-400">
                            <span id="currentTime">0:00</span>
                            <span id="durationTime">0:00</span>
                        </div>
                    </div>

                    <div class="flex items-center justify-center gap-6">
                        <button onclick="restartAudio()" class="text-gray-300 hover:text-blue-600 transition"><i data-lucide="rotate-ccw"></i></button>
                        <button onclick="togglePlay()" class="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center text-white shadow-xl hover:scale-105 transition active:scale-95">
                            <i data-lucide="play" id="playIcon" class="fill-current"></i>
                        </button>
                        <a id="downloadBtn" href="#" download class="text-gray-300 hover:text-blue-600 transition"><i data-lucide="download"></i></a>
                    </div>
                </div>

                <div class="glass-panel rounded-3xl overflow-hidden flex flex-col h-[350px]">
                    <div class="p-4 border-b bg-gray-50/50 flex items-center gap-2">
                        <i data-lucide="history" class="w-4 h-4 text-blue-600"></i>
                        <h3 class="font-bold text-xs uppercase tracking-widest text-gray-500">History</h3>
                    </div>
                    <div id="historyList" class="flex-1 overflow-y-auto p-4 space-y-4"></div>
                </div>
            </div>
        </div>
    </div>

    <audio id="hiddenAudio"></audio>

    <script>
        let selectedVoice = 'so-SO-MuuseNeural';
        const audio = document.getElementById('hiddenAudio');
        const genBtn = document.getElementById('generateBtn');

        function handleInput() {
            const val = document.getElementById('textInput').value.trim();
            document.getElementById('charCount').innerText = val.length;
            
            if(val.length > 0) {
                genBtn.disabled = false;
                genBtn.className = "w-full h-14 bg-blue-600 text-white font-bold rounded-2xl shadow-lg shadow-blue-200 hover:-translate-y-1 transition-all flex items-center justify-center gap-2";
            } else {
                genBtn.disabled = true;
                genBtn.className = "w-full h-14 bg-gray-200 text-gray-400 font-bold rounded-2xl transition-all flex items-center justify-center gap-2";
            }
        }

        function updateSliders() {
            document.getElementById('rateLabel').innerText = document.getElementById('rate').value + '%';
            document.getElementById('pitchLabel').innerText = document.getElementById('pitch').value + 'Hz';
        }

        function setVoice(v) {
            selectedVoice = v;
            document.getElementById('btnMuuse').className = v === 'so-SO-MuuseNeural' ? 'voice-btn-active flex flex-col items-center p-4 rounded-2xl border-2 transition-all' : 'flex flex-col items-center p-4 rounded-2xl border-2 border-gray-100 text-gray-400 transition-all';
            document.getElementById('btnUbax').className = v === 'so-SO-UbaxNeural' ? 'voice-btn-active flex flex-col items-center p-4 rounded-2xl border-2 transition-all' : 'flex flex-col items-center p-4 rounded-2xl border-2 border-gray-100 text-gray-400 transition-all';
        }

        async function generate() {
            const text = document.getElementById('textInput').value.trim();
            genBtn.disabled = true;
            genBtn.innerText = "Generating...";

            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    text, voice: selectedVoice,
                    rate: document.getElementById('rate').value,
                    pitch: document.getElementById('pitch').value
                })
            });
            const data = await res.json();
            if(data.audioUrl) {
                showPlayer(data.audioUrl);
                loadHistory();
            }
            genBtn.disabled = false;
            genBtn.innerHTML = '<i data-lucide="sparkles" class="w-5 h-5"></i><span>Generate Speech</span>';
            lucide.createIcons();
        }

        function showPlayer(url) {
            document.getElementById('playerCard').classList.remove('hidden');
            audio.src = url;
            document.getElementById('downloadBtn').href = url;
            
            const wave = document.getElementById('waveform');
            wave.innerHTML = Array.from({length: 25}).map(() => '<div class="bar"></div>').join('');
            
            audio.play();
        }

        function togglePlay() {
            if(audio.paused) audio.play(); else audio.pause();
        }

        function restartAudio() {
            audio.currentTime = 0;
            audio.play();
        }

        audio.onplay = () => {
            document.getElementById('playIcon').setAttribute('data-lucide', 'pause');
            document.querySelectorAll('.bar').forEach((b, i) => {
                b.classList.add('animating');
                b.style.animationDelay = `${i * 0.05}s`;
            });
            lucide.createIcons();
        };

        audio.onpause = () => {
            document.getElementById('playIcon').setAttribute('data-lucide', 'play');
            document.querySelectorAll('.bar').forEach(b => b.classList.remove('animating'));
            lucide.createIcons();
        };

        audio.ontimeupdate = () => {
            const prog = (audio.currentTime / audio.duration) * 100;
            document.getElementById('audioSeek').value = prog || 0;
            document.getElementById('currentTime').innerText = formatTime(audio.currentTime);
            document.getElementById('durationTime').innerText = formatTime(audio.duration);
        };

        function formatTime(t) {
            if(isNaN(t)) return "0:00";
            const m = Math.floor(t/60), s = Math.floor(t%60);
            return `${m}:${s < 10 ? '0'+s : s}`;
        }

        async function loadHistory() {
            const res = await fetch('/api/history');
            const data = await res.json();
            document.getElementById('historyList').innerHTML = data.map(i => `
                <div onclick="showPlayer('${i.audioUrl}')" class="group cursor-pointer">
                    <div class="flex justify-between items-center mb-1">
                        <span class="text-[9px] font-black text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full uppercase">${i.voice.includes('Muuse') ? 'Muuse' : 'Ubax'}</span>
                        <span class="text-[10px] text-gray-300 font-bold">${i.time}</span>
                    </div>
                    <p class="text-xs text-gray-600 line-clamp-2 group-hover:text-blue-600 transition-colors">${i.text}</p>
                </div>
            `).join('');
        }

        lucide.createIcons();
        loadHistory();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/static/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    text, voice, rate, pitch = data.get('text'), data.get('voice'), data.get('rate'), data.get('pitch')
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    r = f"+{rate}%" if int(rate) >= 0 else f"{rate}%"
    p = f"+{pitch}Hz" if int(pitch) >= 0 else f"{pitch}Hz"
    
    async def run_tts():
        cmd = f'edge-tts --voice {voice} --text "{text}" --rate={r} --pitch={p} --write-media {filepath}'
        proc = await asyncio.create_subprocess_shell(cmd)
        await proc.communicate()

    asyncio.run(run_tts())
    
    item = {"text": text, "voice": voice, "audioUrl": f"/static/audio/{filename}", "time": datetime.now().strftime("%d/%m/%Y")}
    history_data.insert(0, item)
    return jsonify({"audioUrl": f"/static/audio/{filename}"})

@app.route('/api/history')
def get_history():
    return jsonify(history_data[:10])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
