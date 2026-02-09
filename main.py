import os
import asyncio
import time
import threading
import tempfile
import subprocess
from flask import Flask, request, abort
import telebot
import edge_tts
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from pymongo import MongoClient
import logging

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8508232988:AAETkYzPTnevP3hylhX-I_v0UDrK0h1wD9k")
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", "https://somtts.onrender.com")
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "/webhook/")
WEBHOOK_URL = WEBHOOK_URL_BASE.rstrip('/') + WEBHOOK_PATH if WEBHOOK_URL_BASE else ""
DOWNLOADS_DIR = os.environ.get("DOWNLOADS_DIR", "./downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
PIN_SOURCE = os.environ.get("PIN_SOURCE", "-1003516493646")
GROQ_KEYS = os.environ.get("GROQ_KEYS", "")
GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://lakiup3_db_user:V4Nbt6YcqH0qCBix@cluster0.my3ety2.mongodb.net/?appName=Cluster0")
client = MongoClient(MONGO_URI)
db = client.get_database("somtts_bot")
users_col = db.get_collection("users")
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
flask_app = Flask(__name__)
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6964068910"))
BAN_MESSAGE = os.environ.get("BAN_MESSAGE", "🚫Waa luu xanibay sababo la xariira spam la xariir lakiup3@gmail.com")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KeyRotator:
    def __init__(self, keys_str):
        self.keys = [k.strip() for k in keys_str.split(",") if k.strip()] if isinstance(keys_str, str) else list(keys_str or [])
        self.index = 0
        self.lock = threading.Lock()
    def get_key(self):
        with self.lock:
            if not self.keys:
                return None
            key = self.keys[self.index]
            self.index = (self.index + 1) % len(self.keys)
            return key
    def mark_success(self, key):
        with self.lock:
            try:
                i = self.keys.index(key)
                self.index = (i + 1) % len(self.keys)
            except ValueError:
                pass
    def mark_failure(self, key):
        self.mark_success(key)

key_manager = KeyRotator(GROQ_KEYS)

def get_user_data(user_id):
    user = users_col.find_one({"user_id": str(user_id)})
    if not user:
        user = {"user_id": str(user_id), "voice": {"name": "so-SO-MuuseNeural", "label": "Muuse 👨🏻‍🦱"}, "rate": 0, "pitch": 0, "banned": False}
        users_col.insert_one(user)
    return user

def update_user_data(user_id, updates):
    users_col.update_one({"user_id": str(user_id)}, {"$set": updates}, upsert=True)

def is_banned(user_id):
    user = users_col.find_one({"user_id": str(user_id)})
    return bool(user and user.get("banned", False))

def process_text_with_groq(text):
    instruction = """You are a text normalization assistant specialized ONLY in numbers and money.
YOUR ONLY TASK IS:
1. If the text contains numbers or money symbols ($, USD, 0.5, 100, 2024, etc.), convert ONLY those parts into natural Somali words that are easy to read aloud.
   Examples:
   - 100 -> boqol
   - 25 -> labaatan iyo shan
   - $10 -> toban doolar
   - 0.5$ -> nus doolar
   - 2026 -> laba kun labaatan iyo lix
2. DO NOT change anything else:
   - Do NOT translate words
   - Do NOT fix grammar
   - Do NOT correct spelling
   - Do NOT rephrase sentences
   - Do NOT change punctuation
   - Do NOT change formatting
3. If the text does NOT contain any numbers or money:
   → Return the text EXACTLY as it is, without changing even a single character.
4. Your output must contain ONLY the final processed text. Do NOT add explanations.
IMPORTANT:
If there are no numbers or money in the input, the output MUST be a 100% identical copy of the input"""
    if not key_manager.keys:
        return text
    total = len(key_manager.keys) or 1
    for _ in range(total + 1):
        api_key = key_manager.get_key()
        if not api_key:
            return text
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": GROQ_TEXT_MODEL, "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": text}], "temperature": 0.2}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                content = response.json()
                return content['choices'][0]['message']['content'].strip()
        except Exception:
            continue
    return text

def generate_tts_filename(user_id):
    safe_id = str(user_id).replace(" ", "_")
    return os.path.join(DOWNLOADS_DIR, f"Codka_{safe_id}_{int(time.time()*1000)}.mp3")

def create_voice_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(KeyboardButton("Ubax 👩🏻‍🦳"), KeyboardButton("Muuse 👨🏻‍🦱"))
    return keyboard

def rate_keyboard(current):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("➖", callback_data="rate_down"), InlineKeyboardButton(f"Rate: {current}", callback_data="rate_noop"), InlineKeyboardButton("➕", callback_data="rate_up"))
    return kb

def pitch_keyboard(current):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("➖", callback_data="pitch_down"), InlineKeyboardButton(f"Pitch: {current}", callback_data="pitch_noop"), InlineKeyboardButton("➕", callback_data="pitch_up"))
    return kb

def keep_sending_upload_action(chat_id, stop_event, interval=3):
    while not stop_event.is_set():
        try:
            bot.send_chat_action(chat_id, "upload_audio")
        except Exception:
            pass
        time.sleep(interval)

def forward_pinned_to_user(dest_chat_id, pin_source):
    if not pin_source:
        return False
    try:
        me = bot.get_me()
        member = bot.get_chat_member(pin_source, me.id)
        status = getattr(member, "status", "")
        if status not in ("administrator", "creator"):
            return False
        chat_info = bot.get_chat(pin_source)
        pinned = getattr(chat_info, "pinned_message", None)
        if pinned and getattr(pinned, "message_id", None):
            bot.forward_message(dest_chat_id, pin_source, pinned.message_id)
            return True
    except Exception:
        return False
    return False

def split_text_into_chunks(text, min_len=250, max_len=300):
    words = text.split()
    if not words:
        return []
    chunks = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= max_len:
            cur += " " + w
        else:
            chunks.append(cur)
            cur = w
    if cur:
        chunks.append(cur)
    merged = []
    i = 0
    while i < len(chunks):
        if len(chunks[i]) >= min_len or i == len(chunks) - 1:
            merged.append(chunks[i])
            i += 1
        else:
            if i + 1 < len(chunks):
                combined = chunks[i] + " " + chunks[i + 1]
                if len(combined) <= max_len:
                    chunks[i + 1] = combined
                    i += 1
                else:
                    merged.append(chunks[i])
                    i += 1
            else:
                merged.append(chunks[i])
                i += 1
    return merged

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None

def convert_mp3_to_wav(mp3_path, wav_path, sample_rate=24000, channels=1):
    cmd = ["ffmpeg", "-y", "-i", mp3_path, "-ar", str(sample_rate), "-ac", str(channels), wav_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def concat_wavs_ffmpeg(wav_files, out_wav):
    listfile = os.path.join(DOWNLOADS_DIR, f"wav_list_{int(time.time()*1000)}.txt")
    try:
        with open(listfile, "w", encoding="utf-8") as lf:
            for f in wav_files:
                lf.write(f"file '{os.path.abspath(f)}'\n")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_wav]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            os.remove(listfile)
        except Exception:
            pass
        return True
    except Exception:
        try:
            if os.path.exists(listfile):
                os.remove(listfile)
        except Exception:
            pass
        return False

def concat_wavs_pydub(wav_files, out_wav):
    try:
        combined = AudioSegment.empty()
        for f in wav_files:
            seg = AudioSegment.from_file(f, format="wav")
            combined += seg
        combined.export(out_wav, format="wav")
        return True
    except Exception:
        return False

def convert_wav_to_mp3(wav_path, mp3_path, bitrate="128k"):
    cmd = ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-b:a", bitrate, mp3_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

async def tts_save_mp3(text, voice_name, rate, pitch, out_mp3):
    tts = edge_tts.Communicate(text, voice_name, rate=rate, pitch=pitch)
    await tts.save(out_mp3)

async_loop = None
async_loop_thread = None

def start_background_loop():
    global async_loop, async_loop_thread
    if async_loop is not None:
        return
    async_loop = asyncio.new_event_loop()
    def _run():
        asyncio.set_event_loop(async_loop)
        async_loop.run_forever()
    async_loop_thread = threading.Thread(target=_run, daemon=True)
    async_loop_thread.start()

@bot.message_handler(commands=["ban"])
def ban_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "Fadlan qor ID-ga userka. Tusaale: /ban 12345678")
            return
        target_id = args[1]
        users_col.update_one({"user_id": str(target_id)}, {"$set": {"banned": True}}, upsert=True)
        bot.reply_to(message, f"✅ User {target_id} waa la mamnuucay (Banned).")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=["unban"])
def unban_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "Fadlan qor ID-ga userka. Tusaale: /unban 12345678")
            return
        target_id = args[1]
        users_col.update_one({"user_id": str(target_id)}, {"$set": {"banned": False}}, upsert=True)
        bot.reply_to(message, f"✅ User {target_id} xayiraada waa laga qaaday (Unbanned).")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=["start"])
def start(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    get_user_data(message.from_user.id)
    keyboard = create_voice_keyboard()
    bot.send_message(message.chat.id, "Soo dhawow! Waxaan ahay Somali Text to Speech bot waxaa i samee yay zack3d:\n\nii soo dir qoraal si aan ugu badalo cod💗", reply_markup=keyboard, reply_to_message_id=message.message_id)

@bot.message_handler(func=lambda m: m.text in ["Ubax 👩🏻‍🦳", "Muuse 👨🏻‍🦱"])
def set_voice(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    user_id = message.from_user.id
    choice = message.text
    if "Ubax" in choice:
        voice_data = {"name": "so-SO-UbaxNeural", "label": "Ubax 👩🏻‍🦳"}
    else:
        voice_data = {"name": "so-SO-MuuseNeural", "label": "Muuse 👨🏻‍🦱"}
    update_user_data(user_id, {"voice": voice_data})
    bot.send_message(message.chat.id, f"Ok hada Codka waa: {choice}\n\n ii soo dir qoraalka 👍", reply_to_message_id=message.message_id)

@bot.message_handler(commands=['rate'])
def cmd_rate(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    user = get_user_data(message.from_user.id)
    current = user.get("rate", 0)
    bot.send_message(message.chat.id, "(Speed) ok taabo bottom ka ➕ ta:", reply_markup=rate_keyboard(current))

@bot.message_handler(commands=['pitch'])
def cmd_pitch(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    user = get_user_data(message.from_user.id)
    current = user.get("pitch", 0)
    bot.send_message(message.chat.id, "(pitch) ok taabo bottom ka ➕ ta:", reply_markup=pitch_keyboard(current))

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith(("rate_", "pitch_")))
def slider_handler(call):
    if is_banned(call.from_user.id):
        bot.answer_callback_query(call.id, text=BAN_MESSAGE, show_alert=True)
        return
    uid = call.from_user.id
    user = get_user_data(uid)
    if call.data.startswith("rate_"):
        val = user.get("rate", 0)
        if call.data == "rate_up": val += 5
        elif call.data == "rate_down": val -= 5
        val = max(-100, min(100, val))
        update_user_data(uid, {"rate": val})
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=rate_keyboard(val))
        except Exception:
            pass
    elif call.data.startswith("pitch_"):
        val = user.get("pitch", 0)
        if call.data == "pitch_up": val += 5
        elif call.data == "pitch_down": val -= 5
        val = max(-100, min(100, val))
        update_user_data(uid, {"pitch": val})
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=pitch_keyboard(val))
        except Exception:
            pass
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

@bot.message_handler(content_types=['voice', 'audio', 'video', 'document'])
def handle_other_media(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    forward_pinned_to_user(message.chat.id, PIN_SOURCE)
    return

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    user_id = message.from_user.id
    user = get_user_data(user_id)
    admin_info = (f"@{message.from_user.username if message.from_user.username else 'No Username'}\nId: {message.from_user.id}\nFirst: {message.from_user.first_name}\nLang: {message.from_user.language_code}\ntext {message.text}")
    try:
        bot.send_message(ADMIN_ID, admin_info)
    except Exception:
        pass
    raw_text = message.text.replace(".", ",")
    text = process_text_with_groq(raw_text)
    voice_name = user["voice"]["name"]
    final_mp3 = generate_tts_filename(user_id)
    pitch_val = user.get("pitch", 0)
    rate_val = user.get("rate", 0)
    pitch = f"+{pitch_val}Hz" if pitch_val >= 0 else f"{pitch_val}Hz"
    rate = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"
    chunks = split_text_into_chunks(text, 250, 300)
    if not chunks:
        bot.send_message(message.chat.id, "Qoraal la'aan ama qoraalka ma habboona.", reply_to_message_id=message.message_id)
        return
    start_background_loop()
    temp_mp3s = []
    temp_wavs = []
    stop_event = threading.Event()
    action_thread = threading.Thread(target=keep_sending_upload_action, args=(message.chat.id, stop_event))
    action_thread.daemon = True
    action_thread.start()
    try:
        for idx, chunk in enumerate(chunks):
            tmp_mp3 = os.path.join(DOWNLOADS_DIR, f"chunk_{user_id}_{int(time.time()*1000)}_{idx}.mp3")
            temp_mp3s.append(tmp_mp3)
            coro = tts_save_mp3(chunk, voice_name, rate, pitch, tmp_mp3)
            fut = asyncio.run_coroutine_threadsafe(coro, async_loop)
            fut.result(timeout=120)
            tmp_wav = os.path.join(DOWNLOADS_DIR, f"chunk_{user_id}_{int(time.time()*1000)}_{idx}.wav")
            ok = convert_mp3_to_wav(tmp_mp3, tmp_wav)
            if not ok:
                raise Exception("ffmpeg conversion failed")
            temp_wavs.append(tmp_wav)
        success = False
        final_wav = os.path.join(DOWNLOADS_DIR, f"final_{user_id}_{int(time.time()*1000)}.wav")
        if AudioSegment is not None:
            success = concat_wavs_pydub(temp_wavs, final_wav)
        if not success:
            success = concat_wavs_ffmpeg(temp_wavs, final_wav)
        if not success:
            raise Exception("Unable to concatenate wav files")
        ok = convert_wav_to_mp3(final_wav, final_mp3)
        if not ok:
            raise Exception("Final mp3 conversion failed")
        with open(final_mp3, "rb") as audio:
            bot.send_audio(message.chat.id, audio, reply_to_message_id=message.message_id, title=f"Codka_{user_id}_{int(time.time())}", performer="SomTTS Bot")
    except Exception as e:
        bot.send_message(message.chat.id, f"Khalad: {e}", reply_to_message_id=message.message_id)
    finally:
        stop_event.set()
        for f in temp_mp3s + temp_wavs + [final_wav if 'final_wav' in locals() else None, final_mp3]:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

@flask_app.route("/", methods=["GET"])
def index():
    return "Bot-ka wuu socdaa💗", 200

@flask_app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        raw = request.get_data().decode('utf-8')
        bot.process_new_updates([Update.de_json(raw)])
        return '', 200
    abort(403)

if __name__ == "__main__":
    start_background_loop()
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            time.sleep(0.5)
            bot.set_webhook(url=WEBHOOK_URL)
        except Exception:
            pass
        flask_app.run(host="0.0.0.0", port=PORT)
    else:
        print("Webhook URL lama dhisin, waan baxayaa.")
