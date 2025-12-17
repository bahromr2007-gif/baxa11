#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Music Bot - Optimized & Fast
Instagram, TikTok, Shazam, YouTube Music Search
"""

import sys
import os
import asyncio
import tempfile
import subprocess
import hashlib
import re
import time
import signal
from pathlib import Path

import telebot
from telebot import types
from shazamio import Shazam
import yt_dlp

# UTF-8
sys.stdout.reconfigure(encoding="utf-8")

# ==================== CONFIG ====================
BOT_TOKEN = "8575775719:AAFk71ow9WR7crlONGpnP56qAZjO88Hj4eI"
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# Webhook o'chirish
try:
    temp_bot = telebot.TeleBot(BOT_TOKEN)
    temp_bot.remove_webhook()
    del temp_bot
except:
    pass

# Bot yaratish
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=False)

# User sessions
user_sessions = {}

# ==================== YT-DLP OPTS ====================
BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': 30,
    'retries': 2,
    'nocheckcertificate': True,
    'geo_bypass': True,
}

INSTAGRAM_OPTS = {
    **BASE_OPTS,
    'format': 'best',
    'outtmpl': str(TEMP_DIR / 'insta_%(id)s.%(ext)s'),
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    },
}

TIKTOK_OPTS = {
    **BASE_OPTS,
    'format': 'best',
    'outtmpl': str(TEMP_DIR / 'tiktok_%(id)s.%(ext)s'),
}

AUDIO_OPTS = {
    **BASE_OPTS,
    'format': 'bestaudio/best',
    'outtmpl': str(TEMP_DIR / '%(title)s.%(ext)s'),
    'restrictfilenames': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '128',
    }],
}

# ==================== UTILS ====================
def cleanup():
    """Eski fayllarni o'chirish (10 daqiqadan eski)"""
    try:
        now = time.time()
        for f in TEMP_DIR.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > 600:
                f.unlink()
    except:
        pass

def safe_delete(path):
    """Faylni xavfsiz o'chirish"""
    try:
        if path and Path(path).exists():
            Path(path).unlink()
    except:
        pass

def create_hash(text):
    """MD5 hash"""
    return hashlib.md5(str(text).encode()).hexdigest()[:10]

def clean_name(text):
    """Fayl nomini tozalash"""
    text = re.sub(r'[<>:"/\\|?*]', '', str(text))
    text = re.sub(r'\s+', '_', text)[:40]
    return text.strip('_') or 'audio'

def format_time(seconds):
    """Vaqtni formatlash"""
    try:
        s = int(float(seconds))
        return f" ({s//60}:{s%60:02d})"
    except:
        return ""

def is_instagram(url):
    """Instagram URL tekshirish"""
    return bool(re.search(r'instagram\.com/(p|reel|reels|tv)/', url.lower()))

def is_tiktok(url):
    """TikTok URL tekshirish"""
    return bool(re.search(r'(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/', url.lower()))

# ==================== SHAZAM ====================
async def shazam_recognize(audio_bytes):
    """Shazam bilan musiqa aniqlash"""
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR)
        tmp.write(audio_bytes)
        tmp.close()
        
        shazam = Shazam()
        result = await shazam.recognize(tmp.name)
        
        if result and 'track' in result:
            return {
                'found': True,
                'title': result['track'].get('title', 'Unknown'),
                'artist': result['track'].get('subtitle', 'Unknown'),
            }
    except:
        pass
    finally:
        if tmp:
            safe_delete(tmp.name)
    
    return {'found': False}

def recognize_audio(audio_bytes):
    """Sync wrapper for Shazam"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(shazam_recognize(audio_bytes))
    loop.close()
    return result

# ==================== DOWNLOAD ====================
def download_audio(query, title_hint=""):
    """YouTube'dan audio yuklash"""
    try:
        clean = clean_name(title_hint or query)
        output = TEMP_DIR / f"{clean}.mp3"
        
        opts = AUDIO_OPTS.copy()
        opts['outtmpl'] = str(TEMP_DIR / f"{clean}.%(ext)s")
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])
        
        if output.exists():
            return output
        
        # Fallback: eng yangi mp3 ni topish
        mp3s = sorted(TEMP_DIR.glob('*.mp3'), key=os.path.getmtime, reverse=True)
        if mp3s and (time.time() - mp3s[0].stat().st_mtime) < 60:
            return mp3s[0]
            
    except:
        pass
    return None

def extract_audio_from_video(video_path, duration=10):
    """Videodan audio ajratish"""
    try:
        audio_path = Path(video_path).with_suffix('.mp3')
        
        subprocess.run([
            'ffmpeg', '-i', str(video_path),
            '-t', str(duration),
            '-vn', '-acodec', 'mp3',
            '-y', str(audio_path)
        ], capture_output=True, timeout=30, check=False)
        
        return audio_path if audio_path.exists() else None
    except:
        return None

# ==================== HANDLERS ====================

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    cleanup()
    bot.reply_to(msg,
        "👋 Salom! Musiqa topuvchi botman 🎵\n\n"
        "📱 Instagram/TikTok linki yuboring\n"
        "🎤 Qo'shiq yoki ijrochi nomini yozing\n"
        "🎵 Audio fayl yuboring (aniqlash uchun)\n\n"
        "Tez ishlash uchun optimallashtirilgan! ⚡"
    )

# ==================== AUDIO/VOICE ====================
@bot.message_handler(content_types=['audio', 'voice'])
def audio_handler(msg):
    status_msg = None
    try:
        status_msg = bot.reply_to(msg, "🎵 Aniqlanmoqda...")
        
        file_info = bot.get_file(msg.audio.file_id if msg.audio else msg.voice.file_id)
        audio_data = bot.download_file(file_info.file_path)
        
        result = recognize_audio(audio_data)
        
        if not result['found']:
            bot.edit_message_text("❌ Musiqa tanilmadi", msg.chat.id, status_msg.message_id)
            return
        
        title = result['title']
        artist = result['artist']
        bot.edit_message_text("⏳ Yuklanmoqda...", msg.chat.id, status_msg.message_id)
        
        audio_file = download_audio(f"{artist} {title}", f"{artist}_{title}")
        
        if audio_file:
            with open(audio_file, 'rb') as f:
                bot.send_audio(msg.chat.id, f, 
                    title=title[:64], 
                    performer=artist[:64],
                    caption=f"🎵 {title}\n👤 {artist}"
                )
            safe_delete(audio_file)
            bot.delete_message(msg.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text(
                f"✅ Topildi:\n🎵 {title}\n👤 {artist}\n\n❌ Yuklashda xatolik",
                msg.chat.id, status_msg.message_id
            )
            
    except Exception as e:
        if status_msg:
            bot.edit_message_text("❌ Xatolik yuz berdi", msg.chat.id, status_msg.message_id)

# ==================== INSTAGRAM ====================
@bot.message_handler(func=lambda m: m.text and is_instagram(m.text))
def instagram_handler(msg):
    status_msg = None
    video_path = None
    
    try:
        status_msg = bot.reply_to(msg, "📱 Instagram yuklanmoqda...")
        url = msg.text.strip().split('?')[0]
        
        with yt_dlp.YoutubeDL(INSTAGRAM_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'video')
        
        # Video topish
        videos = list(TEMP_DIR.glob(f"insta_{video_id}*"))
        if not videos:
            videos = sorted(TEMP_DIR.glob('insta_*.mp4'), key=os.path.getmtime, reverse=True)
        
        if not videos:
            bot.edit_message_text("❌ Video yuklanmadi. Link to'g'rimi?", msg.chat.id, status_msg.message_id)
            return
        
        video_path = videos[0]
        
        # Hajmni tekshirish
        size_mb = video_path.stat().st_size / (1024 * 1024)
        if size_mb > 50:
            bot.edit_message_text(
                f"❌ Video juda katta ({size_mb:.1f}MB)\nTelegram limit: 50MB",
                msg.chat.id, status_msg.message_id
            )
            return
        
        # Yuborish
        btn_hash = create_hash(video_path)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        with open(video_path, 'rb') as f:
            bot.send_video(msg.chat.id, f, reply_markup=markup, supports_streaming=True)
        
        # Session saqlash
        (TEMP_DIR / f"{btn_hash}.path").write_text(str(video_path))
        
        bot.delete_message(msg.chat.id, status_msg.message_id)
        
    except Exception as e:
        if status_msg:
            bot.edit_message_text(
                "❌ Video yuklanmadi\n\n"
                "Sabablar:\n• Link noto'g'ri\n• Video private\n• Instagram blok qilgan",
                msg.chat.id, status_msg.message_id
            )
    finally:
        if video_path:
            asyncio.get_event_loop().call_later(30, lambda: safe_delete(video_path))

# ==================== TIKTOK ====================
@bot.message_handler(func=lambda m: m.text and is_tiktok(m.text))
def tiktok_handler(msg):
    status_msg = None
    video_path = None
    
    try:
        status_msg = bot.reply_to(msg, "📱 TikTok yuklanmoqda...")
        url = msg.text.strip()
        
        with yt_dlp.YoutubeDL(TIKTOK_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
        
        videos = sorted(TEMP_DIR.glob('tiktok_*.mp4'), key=os.path.getmtime, reverse=True)
        if not videos:
            videos = sorted(TEMP_DIR.glob('tiktok_*.webm'), key=os.path.getmtime, reverse=True)
        
        if not videos:
            bot.edit_message_text("❌ TikTok video yuklanmadi", msg.chat.id, status_msg.message_id)
            return
        
        video_path = videos[0]
        
        btn_hash = create_hash(video_path)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        with open(video_path, 'rb') as f:
            bot.send_video(msg.chat.id, f, reply_markup=markup, supports_streaming=True)
        
        (TEMP_DIR / f"{btn_hash}.path").write_text(str(video_path))
        bot.delete_message(msg.chat.id, status_msg.message_id)
        
    except Exception as e:
        if status_msg:
            bot.edit_message_text("❌ TikTok yuklanmadi", msg.chat.id, status_msg.message_id)
    finally:
        if video_path:
            asyncio.get_event_loop().call_later(30, lambda: safe_delete(video_path))

# ==================== VIDEO -> MUSIC ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith('music_'))
def music_from_video(call):
    audio_path = None
    video_path = None
    
    try:
        btn_hash = call.data.split('_')[1]
        bot.answer_callback_query(call.id, "🎵 Musiqa aniqlanmoqda...")
        
        path_file = TEMP_DIR / f"{btn_hash}.path"
        if not path_file.exists():
            bot.send_message(call.message.chat.id, "❌ Video topilmadi (eskirgan)")
            return
        
        video_path = path_file.read_text().strip()
        if not Path(video_path).exists():
            bot.send_message(call.message.chat.id, "❌ Video fayl o'chirilgan")
            return
        
        # Audio ajratish
        audio_path = extract_audio_from_video(video_path, 10)
        if not audio_path:
            bot.send_message(call.message.chat.id, "❌ Audio ajratilmadi")
            return
        
        # Shazam
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        result = recognize_audio(audio_data)
        
        if not result['found']:
            bot.send_message(call.message.chat.id, "❌ Musiqa tanilmadi")
            return
        
        title = result['title']
        artist = result['artist']
        
        bot.send_message(call.message.chat.id, "⏳ Yuklanmoqda...")
        
        # Download
        audio_file = download_audio(f"{artist} {title}", f"{artist}_{title}")
        
        if audio_file:
            with open(audio_file, 'rb') as f:
                bot.send_audio(call.message.chat.id, f,
                    title=title[:64],
                    performer=artist[:64],
                    caption=f"🎵 {title}\n👤 {artist}"
                )
            safe_delete(audio_file)
        else:
            bot.send_message(call.message.chat.id, 
                f"✅ Topildi:\n🎵 {title}\n👤 {artist}\n\n❌ Yuklashda xatolik"
            )
        
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ Xatolik yuz berdi")
    finally:
        safe_delete(audio_path)
        safe_delete(video_path)

# ==================== SEARCH ====================
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def search_handler(msg):
    status_msg = None
    
    try:
        query = msg.text.strip()
        status_msg = bot.reply_to(msg, "🔍 Qidirilmoqda...")
        
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            songs = info.get('entries', [])
        
        if not songs:
            bot.edit_message_text("❌ Hech narsa topilmadi", msg.chat.id, status_msg.message_id)
            return
        
        # Session saqlash
        user_sessions[msg.chat.id] = {
            'query': query,
            'songs': songs,
        }
        
        # Natijalarni ko'rsatish
        show_results(msg.chat.id, songs[:10], query)
        bot.delete_message(msg.chat.id, status_msg.message_id)
        
    except Exception as e:
        if status_msg:
            bot.edit_message_text("❌ Qidiruvda xatolik", msg.chat.id, status_msg.message_id)

def show_results(chat_id, songs, query):
    """Qidiruv natijalarini ko'rsatish"""
    text = [f"🔍 '{query}' natijalar:\n"]
    markup = types.InlineKeyboardMarkup(row_width=5)
    
    row1 = []
    row2 = []
    
    for i, song in enumerate(songs, 1):
        if not song:
            continue
        
        title = song.get('title', 'Unknown')[:50]
        duration = format_time(song.get('duration', 0))
        text.append(f"{i}. {title}{duration}")
        
        url = song.get('url') or song.get('webpage_url')
        if url:
            h = create_hash(url)
            (TEMP_DIR / f"song_{h}.txt").write_text(f"{url}|{title}")
            
            btn = types.InlineKeyboardButton(str(i), callback_data=f"dl_{h}")
            if i <= 5:
                row1.append(btn)
            else:
                row2.append(btn)
    
    if row1:
        markup.add(*row1)
    if row2:
        markup.add(*row2)
    
    # Nav
    markup.add(
        types.InlineKeyboardButton("🔄 Yangi qidiruv", callback_data="nav_new"),
        types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="nav_home")
    )
    
    bot.send_message(chat_id, "\n".join(text), reply_markup=markup)

# ==================== DOWNLOAD SONG ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith('dl_'))
def download_song(call):
    try:
        h = call.data.split('_')[1]
        
        data_file = TEMP_DIR / f"song_{h}.txt"
        if not data_file.exists():
            bot.answer_callback_query(call.id, "❌ Vaqt o'tgan", show_alert=True)
            return
        
        data = data_file.read_text().strip()
        url, title = data.split('|', 1) if '|' in data else (data, 'Audio')
        
        bot.answer_callback_query(call.id, "⏳ Yuklanmoqda...")
        
        audio_file = download_audio(url, title)
        
        if audio_file:
            with open(audio_file, 'rb') as f:
                bot.send_audio(call.message.chat.id, f, title=title[:64])
            safe_delete(audio_file)
        else:
            bot.send_message(call.message.chat.id, "❌ Yuklashda xatolik")
        
        safe_delete(data_file)
        
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ Xatolik")

# ==================== NAVIGATION ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith('nav_'))
def nav_handler(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    if call.data == 'nav_home':
        start_cmd(call.message)
    elif call.data == 'nav_new':
        bot.send_message(call.message.chat.id, "🔍 Yangi qidiruv uchun qo'shiq nomini yozing:")

# ==================== SHUTDOWN ====================
def shutdown_handler(sig, frame):
    print("\n🛑 Bot to'xtatilmoqda...")
    cleanup()
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ==================== MAIN ====================
if __name__ == '__main__':
    print("=" * 50)
    print("🎵 TELEGRAM MUSIC BOT")
    print("=" * 50)
    print("✅ Bot ishga tushdi!")
    print("⚡ Tez va xavfsiz")
    print("📱 Instagram, TikTok, Shazam, YouTube")
    print("=" * 50)
    
    cleanup()
    
    try:
        bot.infinity_polling(
            skip_pending=True,
            timeout=30,
            long_polling_timeout=30
        )
    except KeyboardInterrupt:
        print("\n🛑 To'xtatildi")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        time.sleep(3)
        print("🔄 Qayta ishga tushirilmoqda...")
        bot.infinity_polling(skip_pending=True)
