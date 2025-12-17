import sys
import telebot.apihelper
import telebot
import os
import asyncio
import tempfile
import subprocess
import hashlib
import re
import json
import time
import signal
from telebot import types
from shazamio import Shazam
import yt_dlp
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ========================================
# BOT TOKEN
BOT_TOKEN = "8575775719:AAFk71ow9WR7crlONGpnP56qAZjO88Hj4eI"

# Webhook va oldingi instancelarni o'chirish
try:
    temp_bot = telebot.TeleBot(BOT_TOKEN)
    temp_bot.remove_webhook()
    print("✅ Webhook o'chirildi")
except Exception as e:
    print(f"⚠️ Webhook xatosi: {e}")

# Bot yaratish
bot = telebot.TeleBot(BOT_TOKEN, threaded=False, skip_pending=True)
# ========================================

# TEMP papka yaratish
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# User sessions
user_sessions = {}

# ================= FAYL TOZALASH =================
def cleanup_old_files():
    """15 daqiqadan eski fayllarni o'chirish"""
    try:
        current_time = time.time()
        for file in TEMP_DIR.iterdir():
            if file.is_file():
                if current_time - file.stat().st_mtime > 900:  # 15 daqiqa
                    file.unlink()
    except:
        pass

def safe_remove(filepath):
    """Faylni xavfsiz o'chirish"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass

# ================= YUKLASH SETTINGLARI =================
ydl_opts_base = {
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': 30,
    'retries': 3,
    'extract_flat': False,
    'nocheckcertificate': True,
    'prefer_insecure': True,
    'age_limit': None,
}

ydl_opts_instagram = {
    **ydl_opts_base,
    'format': 'best',
    'outtmpl': str(TEMP_DIR / '%(id)s.%(ext)s'),
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
    },
    'cookiefile': None,
    'nocheckcertificate': True,
    'no_check_certificate': True,
}

ydl_opts_tiktok = {
    **ydl_opts_base,
    'format': 'best[height<=720]',
    'outtmpl': str(TEMP_DIR / '%(id)s.%(ext)s'),
}

ydl_opts_audio = {
    **ydl_opts_base,
    'format': 'bestaudio/best',
    'outtmpl': str(TEMP_DIR / '%(title)s.%(ext)s'),
    'restrictfilenames': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '128',
    }],
}

# ================= YORDAMCHI FUNKSIYALAR =================
def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def clean_filename(text):
    if not text:
        return "musiqa"
    
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = text[:40]
    
    return text if text.strip('_') else "musiqa"

def format_duration(seconds):
    try:
        seconds = int(float(seconds))
        return f" ({seconds//60}:{seconds%60:02d})"
    except:
        return ""

def is_instagram_url(url):
    patterns = [
        r'instagram\.com/(p|reel|tv)/',
        r'instagram\.com/reels/',
    ]
    return any(re.search(p, url.lower()) for p in patterns)

def is_tiktok_url(url):
    patterns = [
        r'tiktok\.com/',
        r'vm\.tiktok\.com/',
        r'vt\.tiktok\.com/',
    ]
    return any(re.search(p, url.lower()) for p in patterns)

# ================= /START =================
@bot.message_handler(commands=['start'])
def start_message(message):
    cleanup_old_files()
    text = (
        "👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        "📱 Instagram/TikTok video linki yuboring\n"
        "🎤 Qo'shiq yoki ijrochi nomini yozing\n"
        "🎵 Audio fayl yuboring (aniqlash uchun)\n\n"
        "👤 Telegram: @Rustamov_v1"
    )
    bot.send_message(message.chat.id, text)

# ================= SHAZAM =================
async def recognize_song(audio_bytes):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        shazam = Shazam()
        result = await shazam.recognize(tmp_path)
        
        if result and 'track' in result:
            track = result['track']
            return {
                'found': True,
                'title': track.get('title', 'Noma\'lum'),
                'artist': track.get('subtitle', 'Noma\'lum'),
            }
    except Exception as e:
        print(f"Shazam xatosi: {e}")
    finally:
        safe_remove(tmp_path)
    
    return {'found': False}

# ================= AUDIO HANDLER =================
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    msg = None
    try:
        msg = bot.reply_to(message, "⏳ Tahlil qilinmoqda...")
        
        file_info = bot.get_file(message.audio.file_id if message.audio else message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song(downloaded_file))
        loop.close()
        
        if result['found']:
            title = result['title']
            artist = result['artist']
            
            bot.edit_message_text("⏳ Yuklanmoqda...", message.chat.id, msg.message_id)
            
            query = f"{artist} {title}"
            clean_title = clean_filename(f"{artist}_{title}")
            output_file = TEMP_DIR / f"{clean_title}.mp3"
            
            opts = ydl_opts_audio.copy()
            opts['outtmpl'] = str(TEMP_DIR / f"{clean_title}.%(ext)s")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"ytsearch1:{query}"])
            
            if output_file.exists():
                with open(output_file, 'rb') as f:
                    bot.send_audio(
                        message.chat.id,
                        f,
                        title=title[:64],
                        performer=artist[:64],
                        caption=f"🎵 {title}\n👤 {artist}"
                    )
                safe_remove(output_file)
                bot.delete_message(message.chat.id, msg.message_id)
            else:
                for file in TEMP_DIR.glob('*.mp3'):
                    if clean_title[:20] in file.name:
                        with open(file, 'rb') as f:
                            bot.send_audio(message.chat.id, f, title=title[:64], performer=artist[:64])
                        safe_remove(file)
                        bot.delete_message(message.chat.id, msg.message_id)
                        break
                else:
                    bot.edit_message_text(f"✅ Topildi: {title}\n👤 {artist}\n\n❌ Yuklanmadi", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ Musiqa tanilmadi", message.chat.id, msg.message_id)
            
    except Exception as e:
        print(f"Audio xatosi: {e}")
        if msg:
            bot.edit_message_text("❌ Xatolik", message.chat.id, msg.message_id)

# ================= INSTAGRAM =================
@bot.message_handler(func=lambda m: is_instagram_url(m.text))
def handle_instagram(message):
    msg = None
    video_path = None
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "⏳ Instagram yuklanmoqda...")
        
        # URL tozalash
        url = url.split('?')[0]  # Query parametrlarni olib tashlash
        
        print(f"Instagram URL: {url}")
        
        # yt-dlp bilan yuklash
        with yt_dlp.YoutubeDL(ydl_opts_instagram) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id', 'instagram')
                print(f"Video ID: {video_id}")
                
                # Yuklanagan faylni topish
                video_files = list(TEMP_DIR.glob(f"*{video_id}*"))
                if not video_files:
                    video_files = list(TEMP_DIR.glob("*.mp4")) + list(TEMP_DIR.glob("*.webm"))
                
                if video_files:
                    # Eng yangi faylni tanlash
                    video_path = max(video_files, key=os.path.getctime)
                    print(f"Video fayl: {video_path}")
                    
                    # Fayl hajmini tekshirish
                    file_size = video_path.stat().st_size
                    print(f"Fayl hajmi: {file_size / (1024*1024):.2f} MB")
                    
                    # Telegram limit: 50 MB
                    if file_size > 50 * 1024 * 1024:
                        bot.edit_message_text(
                            "❌ Video juda katta (>50MB)\n"
                            "Telegram limiti: 50MB",
                            message.chat.id,
                            msg.message_id
                        )
                        safe_remove(video_path)
                        return
                    
                    btn_hash = create_hash(str(video_path))
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"vid_{btn_hash}"))
                    
                    # Video yuborish
                    with open(video_path, 'rb') as f:
                        bot.send_video(
                            message.chat.id, 
                            f, 
                            reply_markup=markup,
                            caption="📱 Instagram",
                            supports_streaming=True,
                            timeout=120
                        )
                    
                    (TEMP_DIR / f"{btn_hash}.txt").write_text(str(video_path))
                    bot.delete_message(message.chat.id, msg.message_id)
                    print("✅ Video yuborildi")
                else:
                    bot.edit_message_text(
                        "❌ Video yuklanmadi\n\n"
                        "Sabablari:\n"
                        "• Video private (shaxsiy)\n"
                        "• Link noto'g'ri\n"
                        "• Instagram blok qilgan",
                        message.chat.id,
                        msg.message_id
                    )
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                print(f"yt-dlp xatosi: {error_msg}")
                
                if "Private" in error_msg or "login" in error_msg.lower():
                    bot.edit_message_text(
                        "❌ Bu video private (shaxsiy)\n"
                        "Faqat ommaviy videolarni yuklay olaman",
                        message.chat.id,
                        msg.message_id
                    )
                elif "unavailable" in error_msg.lower():
                    bot.edit_message_text(
                        "❌ Video mavjud emas yoki o'chirilgan",
                        message.chat.id,
                        msg.message_id
                    )
                else:
                    bot.edit_message_text(
                        "❌ Instagram video yuklanmadi\n\n"
                        "Yana bir bor urinib ko'ring yoki\n"
                        "boshqa link yuboring",
                        message.chat.id,
                        msg.message_id
                    )
        
    except Exception as e:
        print(f"Instagram xatosi: {e}")
        if msg:
            bot.edit_message_text(
                "❌ Video yuklanmadi\n\n"
                "Link to'g'riligini tekshiring:\n"
                "• /reel/ yoki /p/ bo'lishi kerak\n"
                "• Video public bo'lishi kerak",
                message.chat.id,
                msg.message_id
            )
    finally:
        # Video yuborilgandan keyin o'chirish
        if video_path and video_path.exists():
            try:
                # 30 soniya kutish (Telegram yuklashi uchun)
                time.sleep(30)
                safe_remove(video_path)
            except:
                pass

# ================= TIKTOK =================
@bot.message_handler(func=lambda m: is_tiktok_url(m.text))
def handle_tiktok(message):
    msg = None
    video_path = None
    try:
        msg = bot.reply_to(message, "⏳ TikTok yuklanmoqda...")
        
        with yt_dlp.YoutubeDL(ydl_opts_tiktok) as ydl:
            info = ydl.extract_info(message.text.strip(), download=True)
        
        video_files = list(TEMP_DIR.glob('*.mp4')) + list(TEMP_DIR.glob('*.webm'))
        if video_files:
            video_path = max(video_files, key=os.path.getctime)
            
            btn_hash = create_hash(str(video_path))
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"vid_{btn_hash}"))
            
            with open(video_path, 'rb') as f:
                bot.send_video(message.chat.id, f, reply_markup=markup)
            
            (TEMP_DIR / f"{btn_hash}.txt").write_text(str(video_path))
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ Video yuklanmadi", message.chat.id, msg.message_id)
            
    except Exception as e:
        print(f"TikTok xatosi: {e}")
        if msg:
            bot.edit_message_text("❌ Video yuklanmadi", message.chat.id, msg.message_id)
    finally:
        safe_remove(video_path)

# ================= VIDEO MUSIQANI ANIQLASH =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("vid_"))
def handle_video_music(call):
    video_path = None
    audio_path = None
    try:
        btn_hash = call.data.split("_", 1)[1]
        bot.answer_callback_query(call.id, "🎵 Aniqlanmoqda...")
        
        video_path = (TEMP_DIR / f"{btn_hash}.txt").read_text().strip()
        
        if not os.path.exists(video_path):
            bot.send_message(call.message.chat.id, "❌ Video topilmadi")
            return
        
        audio_path = Path(video_path).with_suffix('.mp3')
        
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-t', '10', '-vn',
            '-acodec', 'mp3',
            '-y', str(audio_path)
        ], capture_output=True, timeout=30, check=False)
        
        if not audio_path.exists():
            bot.send_message(call.message.chat.id, "❌ Audio ajratilmadi")
            return
        
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song(audio_data))
        loop.close()
        
        if result['found']:
            title = result['title']
            artist = result['artist']
            
            bot.send_message(call.message.chat.id, "⏳ Yuklanmoqda...")
            
            query = f"{artist} {title}"
            clean_title = clean_filename(f"{artist}_{title}")
            output_file = TEMP_DIR / f"{clean_title}.mp3"
            
            opts = ydl_opts_audio.copy()
            opts['outtmpl'] = str(TEMP_DIR / f"{clean_title}.%(ext)s")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"ytsearch1:{query}"])
            
            if output_file.exists():
                with open(output_file, 'rb') as f:
                    bot.send_audio(call.message.chat.id, f, title=title[:64], performer=artist[:64])
                safe_remove(output_file)
            else:
                bot.send_message(call.message.chat.id, f"✅ {title} - {artist}\n\n❌ Yuklanmadi")
        else:
            bot.send_message(call.message.chat.id, "❌ Musiqa tanilmadi")
            
    except Exception as e:
        print(f"Video music xatosi: {e}")
        bot.send_message(call.message.chat.id, "❌ Xatolik")
    finally:
        safe_remove(video_path)
        safe_remove(audio_path)

# ================= QIDIRUV =================
@bot.message_handler(func=lambda m: True)
def search_music(message):
    query = message.text.strip()
    msg = None
    
    try:
        msg = bot.reply_to(message, f"🔍 Qidirilmoqda...")
        
        opts = {
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 20,
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            songs = info.get('entries', [])
        
        if not songs:
            bot.edit_message_text("❌ Topilmadi", message.chat.id, msg.message_id)
            return
        
        user_sessions[message.chat.id] = {'query': query, 'songs': songs, 'page': 1}
        show_results(message.chat.id, songs[:10], query, 1)
        bot.delete_message(message.chat.id, msg.message_id)
        
    except Exception as e:
        print(f"Qidiruv xatosi: {e}")
        if msg:
            bot.edit_message_text("❌ Xatolik", message.chat.id, msg.message_id)

def show_results(chat_id, songs, query, page):
    text = [f"🔍 '{query}' ({(page-1)*10+1}-{(page-1)*10+len(songs)}):\n"]
    markup = types.InlineKeyboardMarkup(row_width=5)
    
    row1, row2 = [], []
    for i, song in enumerate(songs, start=(page-1)*10+1):
        if not song:
            continue
        
        title = song.get("title", "")[:50]
        duration = format_duration(song.get("duration", 0))
        text.append(f"{i}. {title}{duration}")
        
        url = song.get("url", song.get("webpage_url", ""))
        if url:
            h = create_hash(url)
            (TEMP_DIR / f"{h}.txt").write_text(f"{url}|{title}")
            
            if i <= 5:
                row1.append(types.InlineKeyboardButton(str(i), callback_data=f"song_{h}"))
            else:
                row2.append(types.InlineKeyboardButton(str(i), callback_data=f"song_{h}"))
    
    if row1:
        markup.add(*row1)
    if row2:
        markup.add(*row2)
    
    markup.add(
        types.InlineKeyboardButton("⬅️", callback_data="nav_back"),
        types.InlineKeyboardButton("🏠", callback_data="nav_home"),
        types.InlineKeyboardButton("➡️", callback_data="nav_next")
    )
    
    bot.send_message(chat_id, "\n".join(text), reply_markup=markup)

# ================= AUDIO YUKLASH =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("song_"))
def download_song(call):
    try:
        h = call.data.split("_", 1)[1]
        data = (TEMP_DIR / f"{h}.txt").read_text().strip()
        url, title = data.split("|", 1) if "|" in data else (data, "Musiqa")
        
        bot.answer_callback_query(call.id, "⏳ Yuklanmoqda...")
        
        clean_title = clean_filename(title)
        output_file = TEMP_DIR / f"{clean_title}.mp3"
        
        opts = ydl_opts_audio.copy()
        opts['outtmpl'] = str(TEMP_DIR / f"{clean_title}.%(ext)s")
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        if output_file.exists():
            with open(output_file, 'rb') as f:
                bot.send_audio(call.message.chat.id, f, title=title[:64])
            safe_remove(output_file)
        else:
            for file in TEMP_DIR.glob('*.mp3'):
                if clean_title[:20] in file.name:
                    with open(file, 'rb') as f:
                        bot.send_audio(call.message.chat.id, f, title=title[:64])
                    safe_remove(file)
                    break
        
        safe_remove(TEMP_DIR / f"{h}.txt")
        
    except Exception as e:
        print(f"Yuklash xatosi: {e}")
        bot.send_message(call.message.chat.id, "❌ Yuklanmadi")

# ================= NAVIGATSIYA =================
@bot.callback_query_handler(func=lambda c: c.data in ["nav_back", "nav_home", "nav_next"])
def handle_nav(call):
    user_id = call.message.chat.id
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if user_id not in user_sessions:
        bot.send_message(user_id, "❌ Session topilmadi")
        return
    
    session = user_sessions[user_id]
    query = session['query']
    
    if call.data == "nav_home":
        start_message(call.message)
    elif call.data == "nav_back":
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            songs = info.get('entries', [])
        show_results(user_id, songs, query, 1)
    elif call.data == "nav_next":
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            info = ydl.extract_info(f"ytsearch20:{query}", download=False)
            songs = info.get('entries', [])[10:20]
        if songs:
            show_results(user_id, songs, query, 2)
        else:
            bot.send_message(user_id, "❌ Ko'proq natija yo'q")

# ================= GRACEFUL SHUTDOWN =================
def signal_handler(sig, frame):
    print("\n🛑 Bot to'xtatilmoqda...")
    bot.stop_polling()
    cleanup_old_files()
    print("✅ Bot to'xtatildi")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ================= ISHGA TUSHIRISH =================
if __name__ == "__main__":
    print("✅ BOT ISHGA TUSHDI!")
    print("🚀 Optimallashtirilgan versiya")
    print("⚡ Railway uchun tayyor")
    print("🔄 Webhook o'chirildi, polling boshlandi")
    
    # Eski fayllarni tozalash
    cleanup_old_files()
    
    try:
        bot.infinity_polling(
            skip_pending=True,
            none_stop=True,
            interval=1,
            timeout=30,
            long_polling_timeout=30
        )
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        time.sleep(5)
        print("🔄 Qayta urinilmoqda...")
        bot.infinity_polling(skip_pending=True, none_stop=True)
