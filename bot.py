#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Multi-Platform Downloader Bot
Instagram, TikTok, Snapchat, Likee, Pinterest + Shazam
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
import logging
import json
from pathlib import Path
from typing import Optional, Dict, List

import telebot
from telebot import types
from telebot.apihelper import ApiException
from shazamio import Shazam
import yt_dlp
import requests

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==================== CONFIG ====================
BOT_TOKEN = "8575775719:AAFk71ow9WR7crlONGpnP56qAZjO88Hj4eI"
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024
CLEANUP_INTERVAL = 600

user_sessions: Dict[int, Dict] = {}
bot_instance: Optional[telebot.TeleBot] = None

# ==================== BOT INIT ====================
def init_bot() -> telebot.TeleBot:
    global bot_instance
    try:
        temp_bot = telebot.TeleBot(BOT_TOKEN)
        temp_bot.remove_webhook()
        logger.info("✅ Webhook o'chirildi")
    except Exception as e:
        logger.warning(f"⚠️ Webhook xatosi: {e}")
    
    bot_instance = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=False, skip_pending=True)
    return bot_instance

bot = init_bot()

# ==================== UTILITY ====================
def cleanup_old_files() -> None:
    try:
        current_time = time.time()
        deleted = 0
        for f in TEMP_DIR.iterdir():
            if f.is_file() and (current_time - f.stat().st_mtime) > CLEANUP_INTERVAL:
                f.unlink()
                deleted += 1
        if deleted > 0:
            logger.info(f"🧹 {deleted} ta fayl o'chirildi")
    except Exception as e:
        logger.error(f"Cleanup xatosi: {e}")

def safe_delete(filepath: Optional[str | Path]) -> None:
    try:
        if filepath:
            path = Path(filepath)
            if path.exists() and path.is_file():
                path.unlink()
    except:
        pass

def create_hash(text: str) -> str:
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()[:12]

def clean_filename(text: str) -> str:
    if not text:
        return "audio"
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:50].strip('_') or "audio"

# ==================== URL DETECTION ====================
def is_instagram_url(url: str) -> bool:
    patterns = [r'instagram\.com/(p|reel|reels|tv)/', r'instagram\.com/stories/']
    return any(re.search(p, url.lower()) for p in patterns)

def is_tiktok_url(url: str) -> bool:
    patterns = [r'tiktok\.com/', r'vm\.tiktok\.com/', r'vt\.tiktok\.com/']
    return any(re.search(p, url.lower()) for p in patterns)

def is_snapchat_url(url: str) -> bool:
    return 'snapchat.com' in url.lower() or 't.snapchat.com' in url.lower()

def is_likee_url(url: str) -> bool:
    return 'likee.video' in url.lower() or 'like.video' in url.lower()

def is_pinterest_url(url: str) -> bool:
    return 'pinterest.com' in url.lower() or 'pin.it' in url.lower()

# ==================== SHAZAM ====================
async def recognize_audio_async(audio_bytes: bytes) -> Dict:
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        shazam = Shazam()
        result = await shazam.recognize(temp_path)
        
        if result and 'track' in result:
            track = result['track']
            return {
                'found': True,
                'title': track.get('title', 'Unknown'),
                'artist': track.get('subtitle', 'Unknown'),
            }
    except Exception as e:
        logger.error(f"Shazam xatosi: {e}")
    finally:
        if temp_file:
            safe_delete(temp_path)
    return {'found': False}

def recognize_audio(audio_bytes: bytes) -> Dict:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_audio_async(audio_bytes))
        loop.close()
        return result
    except:
        return {'found': False}

# ==================== YOUTUBE AUDIO ====================
def download_youtube_audio(query: str, filename_hint: str = "") -> Optional[Path]:
    try:
        clean_name = clean_filename(filename_hint or query)
        output_path = TEMP_DIR / f"audio_{clean_name}.mp3"
        
        options = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'outtmpl': str(TEMP_DIR / f"audio_{clean_name}.%(ext)s"),
            'restrictfilenames': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
        
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([f"ytsearch1:{query}"])
        
        if output_path.exists():
            return output_path
        
        mp3_files = sorted(TEMP_DIR.glob('audio_*.mp3'), key=lambda f: f.stat().st_mtime, reverse=True)
        if mp3_files and (time.time() - mp3_files[0].stat().st_mtime) < 120:
            return mp3_files[0]
    except Exception as e:
        logger.error(f"Audio yuklash xatosi: {e}")
    return None

# ==================== EXTRACT AUDIO FROM VIDEO ====================
def extract_audio_from_video(video_path: str | Path, duration: int = 10) -> Optional[Path]:
    try:
        video_path = Path(video_path)
        audio_path = video_path.parent / f"{video_path.stem}_audio.mp3"
        
        command = [
            'ffmpeg', '-i', str(video_path), '-t', str(duration),
            '-vn', '-acodec', 'mp3', '-ar', '44100', '-ab', '128k',
            '-y', str(audio_path)
        ]
        
        subprocess.run(command, capture_output=True, timeout=60, check=False)
        
        if audio_path.exists() and audio_path.stat().st_size > 0:
            return audio_path
    except Exception as e:
        logger.error(f"Audio extraction xatosi: {e}")
    return None

# ==================== START COMMAND ====================
@bot.message_handler(commands=['start', 'help'])
def start_command(message: types.Message) -> None:
    cleanup_old_files()
    
    welcome = (
        "🔥 *Assalomu alaykum!* Botga xush kelibsiz.\n\n"
        "📥 *Yuklab olish:*\n"
        "• Instagram - post, IGTV + audio\n"
        "• TikTok - suv belgisiz + audio\n"
        "• Snapchat - suv belgisiz + audio\n"
        "• Likee - suv belgisiz + audio\n"
        "• Pinterest - video/rasm + audio\n\n"
        "🎵 *Shazam funksiya:*\n"
        "• Qo'shiq nomi yoki ijrochi\n"
        "• Ovozli xabar\n"
        "• Video/Audio fayl\n"
        "• Video xabar\n\n"
        "🚀 Yuklab olish uchun link yuboring!\n"
        "😎 Bot guruhlarda ham ishlaydi!"
    )
    
    try:
        bot.send_message(message.chat.id, welcome, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, welcome.replace('*', ''))

# ==================== INSTAGRAM ====================
@bot.message_handler(func=lambda m: m.text and is_instagram_url(m.text))
def handle_instagram(message: types.Message) -> None:
    status_msg = None
    video_path = None
    
    try:
        url = message.text.strip().split('?')[0]
        status_msg = bot.reply_to(message, "📱 Instagram yuklanmoqda...")
        
        logger.info(f"Instagram URL: {url}")
        
        # Alternative API - Insta Downloader (no login required)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        # Method 1: Try with SaveFrom.net API
        try:
            api_url = f"https://v3.savefrom.net/api/ajaxSearch"
            data = {
                'q': url,
                'lang': 'en'
            }
            response = requests.post(api_url, data=data, headers=headers, timeout=20)
            result = response.json()
            
            if result.get('status') == 'ok' and result.get('data'):
                # Parse download links
                import json
                from html.parser import HTMLParser
                
                class LinkParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.links = []
                    
                    def handle_starttag(self, tag, attrs):
                        if tag == 'a':
                            for attr, value in attrs:
                                if attr == 'href' and value.startswith('http'):
                                    self.links.append(value)
                
                parser = LinkParser()
                parser.feed(result['data'])
                
                if parser.links:
                    download_url = parser.links[0]
                    
                    video_response = requests.get(download_url, stream=True, timeout=60, headers=headers)
                    video_response.raise_for_status()
                    
                    video_hash = create_hash(url)
                    video_path = TEMP_DIR / f"ig_{video_hash}.mp4"
                    
                    with open(video_path, 'wb') as f:
                        for chunk in video_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    if video_path.stat().st_size < 1000:
                        raise Exception("Fayl juda kichik")
                    
                    if video_path.stat().st_size > MAX_FILE_SIZE:
                        bot.edit_message_text("❌ Video juda katta (50 MB)", message.chat.id, status_msg.message_id)
                        return
                    
                    btn_hash = create_hash(str(video_path))
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
                    
                    with open(video_path, 'rb') as vf:
                        bot.send_video(message.chat.id, vf, reply_markup=markup, caption="📱 Instagram", supports_streaming=True, timeout=120)
                    
                    (TEMP_DIR / f"{btn_hash}.path").write_text(str(video_path))
                    bot.delete_message(message.chat.id, status_msg.message_id)
                    logger.info("✅ Instagram yuborildi (SaveFrom)")
                    return
        except Exception as e:
            logger.warning(f"SaveFrom API xatosi: {e}")
        
        # Method 2: Fallback to yt-dlp with cookies
        bot.edit_message_text("📱 Instagram yuklanmoqda (alternate)...", message.chat.id, status_msg.message_id)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
            'outtmpl': str(TEMP_DIR / 'ig_%(id)s.%(ext)s'),
            'socket_timeout': 30,
            'retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'extractor_args': {
                'instagram': {
                    'api_version': 'v1'
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'video')
        
        video_files = list(TEMP_DIR.glob(f"ig_{video_id}*"))
        if not video_files:
            video_files = sorted(TEMP_DIR.glob('ig_*.mp4'), key=lambda f: f.stat().st_mtime, reverse=True)
        
        if not video_files:
            bot.edit_message_text("❌ Video yuklanmadi\n\nInstagram private bo'lishi mumkin", message.chat.id, status_msg.message_id)
            return
        
        video_path = video_files[0]
        
        if video_path.stat().st_size > MAX_FILE_SIZE:
            bot.edit_message_text("❌ Video juda katta (50 MB)", message.chat.id, status_msg.message_id)
            return
        
        btn_hash = create_hash(str(video_path))
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        with open(video_path, 'rb') as vf:
            bot.send_video(message.chat.id, vf, reply_markup=markup, caption="📱 Instagram", supports_streaming=True, timeout=120)
        
        (TEMP_DIR / f"{btn_hash}.path").write_text(str(video_path))
        bot.delete_message(message.chat.id, status_msg.message_id)
        logger.info("✅ Instagram yuborildi (yt-dlp)")
    
    except Exception as e:
        logger.error(f"Instagram xatosi: {e}")
        if status_msg:
            bot.edit_message_text("❌ Instagram yuklanmadi\n\nBoshqa link bilan urinib ko'ring", message.chat.id, status_msg.message_id)
    
    finally:
        if video_path:
            import threading
            def delayed(): time.sleep(60); safe_delete(video_path)
            threading.Thread(target=delayed, daemon=True).start()

# ==================== TIKTOK ====================
@bot.message_handler(func=lambda m: m.text and is_tiktok_url(m.text))
def handle_tiktok(message: types.Message) -> None:
    status_msg = None
    video_path = None
    
    try:
        url = message.text.strip()
        status_msg = bot.reply_to(message, "📱 TikTok yuklanmoqda...")
        
        api_url = "https://www.tikwm.com/api/"
        params = {'url': url, 'hd': 1}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        data = response.json()
        
        if data.get('code') != 0 or not data.get('data'):
            bot.edit_message_text("❌ TikTok yuklanmadi", message.chat.id, status_msg.message_id)
            return
        
        video_data = data['data']
        download_url = video_data.get('hdplay') or video_data.get('play')
        
        if not download_url:
            raise Exception("Video URL topilmadi")
        
        video_response = requests.get(download_url, stream=True, timeout=60, headers=headers)
        video_response.raise_for_status()
        
        video_hash = create_hash(url)
        video_path = TEMP_DIR / f"tt_{video_hash}.mp4"
        
        with open(video_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if video_path.stat().st_size < 1000:
            raise Exception("Fayl juda kichik")
        
        if video_path.stat().st_size > MAX_FILE_SIZE:
            bot.edit_message_text("❌ Video juda katta", message.chat.id, status_msg.message_id)
            return
        
        btn_hash = create_hash(str(video_path))
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        with open(video_path, 'rb') as vf:
            bot.send_video(message.chat.id, vf, reply_markup=markup, caption="📱 TikTok (Suv belgisiz)", supports_streaming=True, timeout=120)
        
        (TEMP_DIR / f"{btn_hash}.path").write_text(str(video_path))
        bot.delete_message(message.chat.id, status_msg.message_id)
        logger.info("✅ TikTok yuborildi")
    
    except Exception as e:
        logger.error(f"TikTok xatosi: {e}")
        if status_msg:
            bot.edit_message_text("❌ TikTok yuklanmadi", message.chat.id, status_msg.message_id)
    
    finally:
        if video_path:
            import threading
            def delayed(): time.sleep(60); safe_delete(video_path)
            threading.Thread(target=delayed, daemon=True).start()

# ==================== SNAPCHAT/LIKEE/PINTEREST ====================
@bot.message_handler(func=lambda m: m.text and (is_snapchat_url(m.text) or is_likee_url(m.text) or is_pinterest_url(m.text)))
def handle_other_platforms(message: types.Message) -> None:
    status_msg = None
    video_path = None
    
    try:
        url = message.text.strip()
        
        if is_snapchat_url(url):
            platform = "Snapchat"
            prefix = "sc"
        elif is_likee_url(url):
            platform = "Likee"
            prefix = "lk"
        else:
            platform = "Pinterest"
            prefix = "pin"
        
        status_msg = bot.reply_to(message, f"📱 {platform} yuklanmoqda...")
        
        ydl_opts = {
            'quiet': True,
            'format': 'best',
            'outtmpl': str(TEMP_DIR / f'{prefix}_%(id)s.%(ext)s'),
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        
        video_files = sorted(TEMP_DIR.glob(f'{prefix}_*'), key=lambda f: f.stat().st_mtime, reverse=True)
        
        if not video_files:
            bot.edit_message_text(f"❌ {platform} yuklanmadi", message.chat.id, status_msg.message_id)
            return
        
        video_path = video_files[0]
        
        if video_path.stat().st_size > MAX_FILE_SIZE:
            bot.edit_message_text("❌ Fayl juda katta", message.chat.id, status_msg.message_id)
            return
        
        btn_hash = create_hash(str(video_path))
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        if video_path.suffix in ['.mp4', '.webm', '.mov']:
            with open(video_path, 'rb') as vf:
                bot.send_video(message.chat.id, vf, reply_markup=markup, caption=f"📱 {platform}", timeout=120)
        else:
            with open(video_path, 'rb') as pf:
                bot.send_photo(message.chat.id, pf, caption=f"📷 {platform}")
        
        (TEMP_DIR / f"{btn_hash}.path").write_text(str(video_path))
        bot.delete_message(message.chat.id, status_msg.message_id)
        logger.info(f"✅ {platform} yuborildi")
    
    except Exception as e:
        logger.error(f"{platform} xatosi: {e}")
        if status_msg:
            bot.edit_message_text(f"❌ {platform} yuklanmadi", message.chat.id, status_msg.message_id)
    
    finally:
        if video_path:
            import threading
            def delayed(): time.sleep(60); safe_delete(video_path)
            threading.Thread(target=delayed, daemon=True).start()

# ==================== AUDIO/VOICE HANDLER ====================
@bot.message_handler(content_types=['audio', 'voice', 'video_note'])
def handle_audio_message(message: types.Message) -> None:
    status_msg = None
    audio_file_path = None
    
    try:
        status_msg = bot.reply_to(message, "🎵 Musiqa aniqlanmoqda...")
        
        if message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id
        else:
            file_id = message.video_note.file_id
        
        file_info = bot.get_file(file_id)
        audio_data = bot.download_file(file_info.file_path)
        
        result = recognize_audio(audio_data)
        
        if not result['found']:
            bot.edit_message_text("❌ Musiqa tanilmadi", message.chat.id, status_msg.message_id)
            return
        
        title = result['title']
        artist = result['artist']
        
        bot.edit_message_text(f"✅ Topildi: {title} - {artist}\n⏳ Yuklanmoqda...", message.chat.id, status_msg.message_id)
        
        query = f"{artist} {title}"
        audio_file_path = download_youtube_audio(query, f"{artist}_{title}")
        
        if audio_file_path and audio_file_path.exists():
            with open(audio_file_path, 'rb') as af:
                bot.send_audio(message.chat.id, af, title=title[:64], performer=artist[:64], caption=f"🎵 {title}\n👤 {artist}")
            bot.delete_message(message.chat.id, status_msg.message_id)
        else:
            bot.edit_message_text(f"✅ Topildi:\n🎵 {title}\n👤 {artist}\n\n❌ Yuklanmadi", message.chat.id, status_msg.message_id)
    
    except Exception as e:
        logger.error(f"Audio handler xatosi: {e}")
        if status_msg:
            bot.edit_message_text("❌ Xatolik", message.chat.id, status_msg.message_id)
    
    finally:
        safe_delete(audio_file_path)

# ==================== VIDEO MUSIC RECOGNITION ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith('music_'))
def handle_video_music(call: types.CallbackQuery) -> None:
    audio_path = None
    audio_file_path = None
    
    try:
        btn_hash = call.data.split('_')[1]
        bot.answer_callback_query(call.id, "🎵 Aniqlanmoqda...")
        
        path_file = TEMP_DIR / f"{btn_hash}.path"
        if not path_file.exists():
            bot.send_message(call.message.chat.id, "❌ Video topilmadi")
            return
        
        video_path = path_file.read_text().strip()
        if not Path(video_path).exists():
            bot.send_message(call.message.chat.id, "❌ Fayl o'chirilgan")
            return
        
        audio_path = extract_audio_from_video(video_path, 10)
        
        if not audio_path or not audio_path.exists():
            bot.send_message(call.message.chat.id, "❌ Audio ajratilmadi")
            return
        
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        result = recognize_audio(audio_data)
        
        if not result['found']:
            bot.send_message(call.message.chat.id, "❌ Musiqa tanilmadi")
            return
        
        title = result['title']
        artist = result['artist']
        
        bot.send_message(call.message.chat.id, f"✅ Topildi: {title} - {artist}\n⏳ Yuklanmoqda...")
        
        query = f"{artist} {title}"
        audio_file_path = download_youtube_audio(query, f"{artist}_{title}")
        
        if audio_file_path and audio_file_path.exists():
            with open(audio_file_path, 'rb') as af:
                bot.send_audio(call.message.chat.id, af, title=title[:64], performer=artist[:64], caption=f"🎵 {title}\n👤 {artist}")
        else:
            bot.send_message(call.message.chat.id, f"✅ Topildi:\n🎵 {title}\n👤 {artist}\n\n❌ Yuklanmadi")
    
    except Exception as e:
        logger.error(f"Video music xatosi: {e}")
        bot.send_message(call.message.chat.id, "❌ Xatolik")
    
    finally:
        safe_delete(audio_path)
        safe_delete(audio_file_path)

# ==================== TEXT SEARCH ====================
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def handle_search(message: types.Message) -> None:
    status_msg = None
    
    try:
        query = message.text.strip()
        status_msg = bot.reply_to(message, f"🔍 '{query}' qidirilmoqda...")
        
        ydl_opts = {'quiet': True, 'extract_flat': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch40:{query}", download=False)
            songs = info.get('entries', [])
        
        if not songs:
            bot.edit_message_text("❌ Topilmadi", message.chat.id, status_msg.message_id)
            return
        
        # Pagination qo'shish
        user_sessions[message.chat.id] = {
            'songs': songs,
            'query': query,
            'page': 0
        }
        
        show_search_page(message.chat.id, songs, query, 0, status_msg.message_id)
    
    except Exception as e:
        logger.error(f"Qidiruv xatosi: {e}")
        if status_msg:
            bot.edit_message_text("❌ Xatolik", message.chat.id, status_msg.message_id)

def show_search_page(chat_id: int, songs: List, query: str, page: int, msg_id: int = None):
    """Qidiruv natijalarini sahifalash bilan ko'rsatish"""
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_songs = songs[start:end]
    
    if not page_songs:
        bot.send_message(chat_id, "❌ Boshqa natija yo'q")
        return
    
    text = [f"🔍 *{query}* - Sahifa {page + 1}\n"]
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = []
    
    for idx, song in enumerate(page_songs, start=1):
        if not song:
            continue
        title = song.get('title', 'Unknown')[:40]
        text.append(f"{idx}. {title}")
        
        url = song.get('url') or song.get('webpage_url')
        if url:
            h = create_hash(url)
            (TEMP_DIR / f"song_{h}.txt").write_text(f"{url}|{title}")
            buttons.append(types.InlineKeyboardButton(str(idx), callback_data=f"dl_{h}"))
    
    if buttons:
        markup.add(*buttons)
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if end < len(songs):
        nav_buttons.append(types.InlineKeyboardButton("➡️ Keyingi", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    try:
        if msg_id:
            bot.edit_message_text("\n".join(text), chat_id, msg_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "\n".join(text), reply_markup=markup, parse_mode='Markdown')
    except:
        if msg_id:
            bot.edit_message_text("\n".join(text).replace('*', ''), chat_id, msg_id, reply_markup=markup)
        else:
            bot.send_message(chat_id, "\n".join(text).replace('*', ''), reply_markup=markup)

# ==================== PAGE NAVIGATION ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith('page_'))
def handle_page_navigation(call: types.CallbackQuery) -> None:
    try:
        page = int(call.data.split('_')[1])
        
        session = user_sessions.get(call.message.chat.id)
        if not session:
            bot.answer_callback_query(call.id, "❌ Sessiya tugagan, qayta qidiring", show_alert=True)
            return
        
        bot.answer_callback_query(call.id)
        show_search_page(call.message.chat.id, session['songs'], session['query'], page, call.message.message_id)
    
    except Exception as e:
        logger.error(f"Page navigation xatosi: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik", show_alert=True)

# ==================== DOWNLOAD SONG ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith('dl_'))
def handle_song_download(call: types.CallbackQuery) -> None:
    audio_file_path = None
    
    try:
        btn_hash = call.data.split('_')[1]
        data_file = TEMP_DIR / f"song_{btn_hash}.txt"
        
        if not data_file.exists():
            bot.answer_callback_query(call.id, "❌ Vaqt o'tgan", show_alert=True)
            return
        
        data = data_file.read_text().strip()
        url, title = data.split('|', 1) if '|' in data else (data, 'Audio')
        
        bot.answer_callback_query(call.id, "⏳ Yuklanmoqda...")
        
        audio_file_path = download_youtube_audio(url, title)
        
        if audio_file_path and audio_file_path.exists():
            with open(audio_file_path, 'rb') as af:
                bot.send_audio(call.message.chat.id, af, title=title[:64])
        else:
            bot.send_message(call.message.chat.id, "❌ Yuklanmadi")
        
        safe_delete(data_file)
    
    except Exception as e:
        logger.error(f"Download xatosi: {e}")
        bot.send_message(call.message.chat.id, "❌ Xatolik")
    
    finally:
        safe_delete(audio_file_path)

# ==================== SHUTDOWN ====================
def shutdown_handler(signum, frame):
    logger.info("\n🛑 Bot to'xtatilmoqda...")
    cleanup_old_files()
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ==================== PERIODIC CLEANUP ====================
def start_periodic_cleanup():
    import threading
    def cleanup_loop():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            cleanup_old_files()
    threading.Thread(target=cleanup_loop, daemon=True).start()

# ==================== MAIN ====================
def main():
    logger.info("=" * 60)
    logger.info("🎵 MULTI-PLATFORM DOWNLOADER BOT")
    logger.info("📱 Instagram, TikTok, Snapchat, Likee, Pinterest")
    logger.info("🎵 Shazam + YouTube Music")
    logger.info("=" * 60)
    
    cleanup_old_files()
    start_periodic_cleanup()
    
    try:
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30, none_stop=True)
    except KeyboardInterrupt:
        shutdown_handler(None, None)
    except Exception as e:
        logger.error(f"❌ Fatal xatolik: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
