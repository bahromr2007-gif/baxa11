import os
import re
import asyncio
import tempfile
import subprocess
import hashlib
import telebot
from telebot import types
from shazamio import Shazam
import yt_dlp

# ========================================
BOT_TOKEN = "8575775719:AAFjR9wnpNEDI-3pzWOeQ1NnyaOnrfgpOk4"
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
# ========================================

# TEMP papka yaratish
if not os.path.exists("temp"):
    os.makedirs("temp")

# User session
user_sessions = {}

# =================== YT-DLP OPTIONS ===================
ydl_opts_audio = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(title)s.%(ext)s',
    'quiet': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

ydl_opts_video = {
    'format': 'best',
    'quiet': True,
    'outtmpl': 'temp/%(id)s.%(ext)s',
    'retries': 3,
    'fragment_retries': 3,
}

# =================== HELPER FUNKSIYALAR ===================
def clean_filename(text):
    if not text:
        return "musiqa"
    for c in r'<>:"/\|?*':
        text = text.replace(c, '')
    text = text.replace(' ', '_')
    return text[:50] if text else "musiqa"

def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def is_instagram_url(url):
    return re.search(r'https?://(www\.)?instagram\.com/(p|reel|tv)/', url.lower())

def is_tiktok_url(url):
    return re.search(r'https?://(www\.)?tiktok\.com/|https?://vm\.tiktok\.com/', url.lower())

async def recognize_song(audio_bytes):
    """Shazam orqali musiqani aniqlash"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir="temp") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        shazam = Shazam()
        result = await shazam.recognize(tmp_path)
        os.unlink(tmp_path)
        if result.get('track'):
            track = result['track']
            return {
                'found': True,
                'title': track.get('title', 'Noma\'lum'),
                'artist': track.get('subtitle', 'Noma\'lum'),
                'link': track.get('share', {}).get('href', ''),
            }
    except Exception as e:
        print(f"Shazam xatosi: {e}")
    return {'found': False}

def extract_audio_from_video(video_path, duration=10):
    """Videodan qisqa audio ajratish"""
    output = video_path.rsplit('.', 1)[0] + "_short.mp3"
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-t', str(duration),
            '-vn', '-acodec', 'mp3', '-ar', '16000', '-ac', '1', '-y', output
        ], capture_output=True, check=False, timeout=30)
    except:
        pass
    return output if os.path.exists(output) else None

# =================== START HANDLER ===================
@bot.message_handler(commands=['start'])
def start_message(message):
    text = (
        "👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        "1️⃣ Instagram / TikTok link yuboring\n"
        "2️⃣ Qo'shiq nomi yoki ijrochi\n"
        "3️⃣ Audio / Voice yuboring"
    )
    bot.send_message(message.chat.id, text)

# =================== AUDIO / VOICE HANDLER ===================
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    msg = bot.reply_to(message, "🎤 Audio tahlil qilinmoqda...")
    try:
        file_info = bot.get_file(message.audio.file_id if message.audio else message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # Temp faylga yozamiz va optimal MP3 formatga konvert qilamiz
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg", dir="temp") as tmp:
            tmp.write(downloaded)
            tmp_path = tmp.name
        
        mp3_path = tmp_path.rsplit('.',1)[0]+"_conv.mp3"
        subprocess.run(['ffmpeg','-i',tmp_path,'-ar','16000','-ac','1','-y',mp3_path],
                       capture_output=True, check=False, timeout=20)
        with open(mp3_path,'rb') as f:
            audio_bytes = f.read()
        
        os.unlink(tmp_path)
        os.unlink(mp3_path)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song(audio_bytes))
        loop.close()
        
        if result['found']:
            title = result['title']
            artist = result['artist']
            bot.edit_message_text(f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}", message.chat.id, msg.message_id)
            
            # YouTube qidiruv fallback
            search_query = f"{artist} - {title} official audio"
            output_file = f"temp/{clean_filename(artist)}-{clean_filename(title)}.mp3"
            opts = ydl_opts_audio.copy()
            opts['outtmpl'] = output_file
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"ytsearch1:{search_query}"])
            
            if os.path.exists(output_file):
                with open(output_file,'rb') as f:
                    bot.send_audio(message.chat.id,f,title=title,performer=artist)
                os.remove(output_file)
            
        else:
            bot.edit_message_text("❌ Musiqa topilmadi", message.chat.id, msg.message_id)
    except Exception as e:
        print(f"Audio xatosi: {e}")
        bot.edit_message_text("❌ Xatolik yuz berdi", message.chat.id, msg.message_id)

# =================== INSTAGRAM / TIKTOK ===================
@bot.message_handler(func=lambda m: is_instagram_url(m.text) or is_tiktok_url(m.text))
def handle_video(message):
    msg = bot.reply_to(message,"⏳ Video yuklanmoqda...")
    url = message.text.strip()
    try:
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(url, download=True)
        
        video_files = [os.path.join("temp",f) for f in os.listdir("temp") if f.endswith(('.mp4','.webm'))]
        if not video_files:
            bot.edit_message_text("❌ Video topilmadi", message.chat.id, msg.message_id)
            return
        
        video_path = max(video_files,key=os.path.getctime)
        audio_path = extract_audio_from_video(video_path)
        
        if audio_path:
            with open(audio_path,'rb') as f:
                audio_bytes = f.read()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(recognize_song(audio_bytes))
            loop.close()
            
            if result['found']:
                title = result['title']
                artist = result['artist']
                bot.edit_message_text(f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}", message.chat.id, msg.message_id)
                
                search_query = f"{artist} - {title} official audio"
                output_file = f"temp/{clean_filename(artist)}-{clean_filename(title)}.mp3"
                opts = ydl_opts_audio.copy()
                opts['outtmpl'] = output_file
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([f"ytsearch1:{search_query}"])
                
                if os.path.exists(output_file):
                    with open(output_file,'rb') as f:
                        bot.send_audio(message.chat.id,f,title=title,performer=artist)
                    os.remove(output_file)
            else:
                bot.edit_message_text("❌ Musiqa topilmadi", message.chat.id, msg.message_id)
        
        os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        
    except Exception as e:
        print(f"Video xatosi: {e}")
        bot.edit_message_text("❌ Xatolik yuz berdi", message.chat.id, msg.message_id)

# =================== TEXT SEARCH ===================
@bot.message_handler(func=lambda m: True)
def search_text(message):
    query = message.text.strip()
    msg = bot.reply_to(message,f"🔍 '{query}' qidirilmoqda...")
    try:
        output_file = f"temp/{clean_filename(query)}.mp3"
        opts = ydl_opts_audio.copy()
        opts['outtmpl'] = output_file
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])
        if os.path.exists(output_file):
            with open(output_file,'rb') as f:
                bot.send_audio(message.chat.id,f,title=query)
            os.remove(output_file)
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        print(f"Text search xatosi: {e}")
        bot.edit_message_text("❌ Xatolik yuz berdi", message.chat.id, msg.message_id)

# =================== BOT ISHGA TUSHURISH ===================
print("✅ BOT ISHGA TUSHDI!")
bot.infinity_polling(skip_pending=True, none_stop=True, interval=0)
