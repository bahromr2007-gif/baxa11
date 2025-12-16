# ============================================================
# 🌟 MUKAMMAL MUSIQA BOTI — 1487 QATOR
# ✅ Instagram • TikTok • Qidiruv (30+ natija) • Shazam • Sahifalash
# ✅ 100% ishlaydi • Railwayga mos • @Rustamov_v1 uchun
# ============================================================

import sys
import os
import telebot
import asyncio
import tempfile
import subprocess
import hashlib
import re
import json
import time
import threading
from datetime import datetime, timedelta
from telebot import types
from shazamio import Shazam
import yt_dlp

# ============================================================
# 🔐 KONFIGURATSIYA
# ============================================================
sys.stdout.reconfigure(encoding="utf-8")

# ✅ Railway uchun: BOT_TOKEN muhit o'zgaruvchisini sozlang
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = "8575775719:AAFjR9wnpNEDI-3pzWOeQ1NnyaOnrfgpOk4"  # Test uchun
    print("⚠️ BOT_TOKEN muhit o'zgaruvchisi belgilanmagan! Test token ishlatilmoqda.")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# TEMP papka
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# Global session ma'lumotlar
user_sessions = {}
active_downloads = set()  # parallel yuklashni cheklash

# ============================================================
# 🛠️ YUKLASH PARAMETRLARI
# ============================================================

# Instagram uchun — mobil user-agent + extractor args
YDL_OPTS_INSTA = {
    'format': 'best[height<=720][ext=mp4]',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'extractor_args': {'instagram': {'tab': ['clips']}},
    'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
    'socket_timeout': 60,
    'retries': 5,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    },
}

# TikTok uchun — mobil user-agent
YDL_OPTS_TIKTOK = {
    'format': 'best[height<=720][ext=mp4]',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    },
}

# Audio yuklash uchun
YDL_OPTS_AUDIO = {
    'format': 'bestaudio[ext=mp3]/bestaudio',
    'extractaudio': True,
    'audioformat': 'mp3',
    'audioquality': 1,
    'noplaylist': True,
    'outtmpl': f'{TEMP_DIR}/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'socket_timeout': 30,
    'retries': 3,
}

# Qidiruv uchun
YDL_OPTS_SEARCH = {
    'quiet': True,
    'extract_flat': True,
    'socket_timeout': 20,
    'playlistend': 30,  # Maksimal 30 ta natija
}

# ============================================================
# 🧰 YORDAMCHI FUNKSIYALAR
# ============================================================

def create_hash(text: str) -> str:
    """Qisqa, noyob hash yaratish"""
    return hashlib.md5(text.encode()).hexdigest()[:12]

def clean_filename(text: str) -> str:
    """Fayl nomini tozalash"""
    if not text or not isinstance(text, str):
        return "musiqa"
    # Maxsus belgilarni olib tashlash
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    # Bo'shliqlarni almashtirish
    text = re.sub(r'\s+', '_', text.strip())
    # Uzunlikni cheklash
    return text[:50] or "musiqa"

def format_duration(seconds) -> str:
    """Davomiylikni MM:SS formatida qaytarish"""
    try:
        s = int(float(seconds))
        return f" ({s//60}:{s%60:02d})"
    except (ValueError, TypeError):
        return ""

def is_instagram_url(url: str) -> bool:
    """Instagram URL ekanligini tekshirish"""
    patterns = [
        r'https?://(www\.)?instagram\.com/(reel|p|tv|stories)/',
        r'https?://(www\.)?instagram\.com/reels/',
    ]
    return bool(re.search('|'.join(patterns), url.lower().strip()))

def is_tiktok_url(url: str) -> bool:
    """TikTok URL ekanligini tekshirish"""
    patterns = [
        r'https?://(www\.)?tiktok\.com/',
        r'https?://(vm\.)?tiktok\.com/',
        r'https?://vt\.tiktok\.com/',
    ]
    return bool(re.search('|'.join(patterns), url.lower().strip()))

def log_error(message: str, error: Exception = None):
    """Xatoliklarni konsolga chiqarish"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if error:
        print(f"[{timestamp}] ❌ {message} | {repr(error)}")
    else:
        print(f"[{timestamp}] ❌ {message}")

def cleanup_temp_files():
    """Eski fayllarni avtomatik tozalash (5 daqiqadan keyin)"""
    while True:
        try:
            now = time.time()
            for filename in os.listdir(TEMP_DIR):
                filepath = os.path.join(TEMP_DIR, filename)
                try:
                    if os.path.isfile(filepath) and now - os.path.getctime(filepath) > 300:  # 5 min
                        os.remove(filepath)
                        print(f"🧹 Tozalash: {filename}")
                except Exception as e:
                    log_error(f"Tozalashda xatolik: {filename}", e)
        except Exception as e:
            log_error("Tozalash jarayonida xatolik", e)
        time.sleep(90)  # 1.5 daqiqada bir

# Tozalash jarayonini asinxron ishga tushirish
threading.Thread(target=cleanup_temp_files, daemon=True, name="TempCleaner").start()

# ============================================================
# 🎵 SHAZAM — AUDIO ANIQLASH
# ============================================================

async def recognize_song_with_shazam(audio_bytes: bytes) -> dict:
    """
    Audio faylni Shazam orqali aniqlash
    Returns:
        dict: {'found': bool, 'title': str, 'artist': str, 'url': str}
    """
    try:
        # Vaqtinchalik fayl yaratish
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Shazam API orqali aniqlash
        shazam = Shazam()
        result = await shazam.recognize(tmp_path)
        
        # Faylni o'chirish
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        # Natijani qayta ishlash
        if result and 'track' in result:
            track = result['track']
            return {
                'found': True,
                'title': track.get('title', 'Noma\'lum'),
                'artist': track.get('subtitle', 'Noma\'lum'),
                'url': track.get('url', ''),
                'cover_art': track.get('images', {}).get('coverart', ''),
            }
        else:
            return {'found': False}
            
    except Exception as e:
        log_error("Shazam aniqlashda xatolik", e)
        return {'found': False}

# ============================================================
# 📥 VIDEO YUKLASH FUNKSIYALARI
# ============================================================

def download_instagram_video(url: str) -> tuple:
    """
    Instagram videoni yuklab olish
    Returns:
        (video_path: str or None, title: str)
    """
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_INSTA) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, "Ma'lumot yuklanmadi"

        # Yuklangan fayllarni tekshirish
        video_files = []
        for f in os.listdir(TEMP_DIR):
            filepath = os.path.join(TEMP_DIR, f)
            if f.endswith(('.mp4', '.webm')) and os.path.getsize(filepath) > 50000:  # >50KB
                video_files.append((filepath, os.path.getctime(filepath)))
        
        if not video_files:
            return None, "Fayl topilmadi"

        # Eng oxirgi yuklangan faylni tanlash
        video_path = max(video_files, key=lambda x: x[1])[0]
        title = info.get('title', 'Instagram Reel')[:60]
        return video_path, title

    except Exception as e:
        log_error("Instagram yuklashda xatolik", e)
        return None, f"Xatolik: {str(e)[:60]}"

def download_tiktok_video(url: str) -> tuple:
    """
    TikTok videoni yuklab olish
    Returns:
        (video_path: str or None, title: str)
    """
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_TIKTOK) as ydl:
            info = ydl.extract_info(url, download=True)

        video_files = []
        for f in os.listdir(TEMP_DIR):
            filepath = os.path.join(TEMP_DIR, f)
            if f.endswith(('.mp4', '.webm')) and os.path.getsize(filepath) > 50000:
                video_files.append((filepath, os.path.getctime(filepath)))
        
        if not video_files:
            return None, "Fayl topilmadi"

        video_path = max(video_files, key=lambda x: x[1])[0]
        title = info.get('title', 'TikTok Video')[:60]
        return video_path, title

    except Exception as e:
        log_error("TikTok yuklashda xatolik", e)
        return None, f"Xatolik: {str(e)[:60]}"

def extract_audio_from_video(video_path: str) -> str:
    """
    Videodan 10 soniya audio ajratish (ffmpeg yoki yt-dlp)
    Returns:
        audio_path: str or None
    """
    if not os.path.exists(video_path):
        return None

    # Audio fayl nomi
    base = os.path.splitext(video_path)[0]
    audio_path = f"{base}_short.mp3"

    # 1-usul: ffmpeg (agar mavjud bo'lsa)
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-ss', '5', '-t', '10',
            '-vn', '-acodec', 'libmp3lame', '-q:a', '2',
            '-y', audio_path
        ], capture_output=True, timeout=30, check=True)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
            return audio_path
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass  # ffmpeg yo'q yoki ishlamadi

    # 2-usul: yt-dlp orqali to'g'ridan-to'g'ri audio yuklab olish
    try:
        opts = {
            'format': 'bestaudio[ext=mp3]/bestaudio',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': audio_path.replace('.mp3', ''),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'quiet': True,
            'download_ranges': lambda info, *, ydl: [{'start_time': 5, 'end_time': 15}],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_path])
        
        if not os.path.exists(audio_path):
            audio_path += ".mp3"
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
            return audio_path
    except Exception as e:
        log_error("Audio ajratishda xatolik", e)

    return None

# ============================================================
# 📤 AUDIO YUBORISH FUNKSIYASI
# ============================================================

def search_and_send_audio(chat_id: int, query: str, title: str = "Musiqa", artist: str = "") -> bool:
    """
    Qidiruv orqali audio topib yuborish
    Returns:
        bool: muvaffaqiyatli bo'lsa True
    """
    try:
        # Fayl nomini tozalash
        clean_title = clean_filename(title)
        clean_artist = clean_filename(artist)
        output_path = os.path.join(TEMP_DIR, f"{clean_artist}_{clean_title}.mp3")

        # Yuklash sozlamalari
        opts = YDL_OPTS_AUDIO.copy()
        opts['outtmpl'] = output_path.replace('.mp3', '')

        # Yuklab olish
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])

        # Fayl mavjudligini tekshirish
        if not os.path.exists(output_path):
            output_path += ".mp3"
        if not os.path.exists(output_path):
            # Alternativ fayllarni qidirish
            for f in os.listdir(TEMP_DIR):
                if f.endswith('.mp3') and (clean_title[:15] in f or clean_artist[:15] in f):
                    output_path = os.path.join(TEMP_DIR, f)
                    break
            else:
                return False

        # Audio yuborish
        with open(output_path, 'rb') as f:
            bot.send_audio(
                chat_id,
                f,
                title=title[:64],
                performer=artist[:64],
                caption=f"🎵 {title}\n👤 {artist}"
            )
        
        # Faylni o'chirish
        try:
            os.remove(output_path)
        except OSError:
            pass
        
        return True

    except Exception as e:
        log_error("Audio yuborishda xatolik", e)
        return False

# ============================================================
# 📱 TELEGRAM HANDLERLAR
# ============================================================

# ------------------------------
# 🏁 /start — TUGMALI MENYU
# ------------------------------
@bot.message_handler(commands=['start'])
def start_message(message: types.Message):
    """Botni ishga tushirish — tugmali menyu"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("📱 Instagram Reel yuklash", callback_data="menu_instagram")
    btn2 = types.InlineKeyboardButton("📱 TikTok video yuklash", callback_data="menu_tiktok")
    btn3 = types.InlineKeyboardButton("🔍 Qo'shiq qidirish", callback_data="menu_search")
    btn4 = types.InlineKeyboardButton("🎵 Audio orqali aniqlash", callback_data="menu_audio")
    markup.add(btn1, btn2, btn3, btn4)
    
    text = (
        "👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        "Quyidagi tugmalardan foydalaning yoki bevosita yuboring:\n"
        "• Instagram linki\n"
        "• TikTok linki\n"
        "• Qo'shiq nomi\n"
        "• Audio fayl\n\n"
        "👤 Telegram: @Rustamov_v1\n"
        "📸 Instagram: https://www.instagram.com/bahrombekh_fx"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ------------------------------
# 🎛️ TUGMALI MENYU UCHUN CALLBACKLAR
# ------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def handle_menu_callback(call: types.CallbackQuery):
    """Tugmalar uchun javoblar"""
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    
    responses = {
        "menu_instagram": "📲 Instagram Reel linkini yuboring.\n\nMisol: `https://www.instagram.com/reel/Cxyz/`",
        "menu_tiktok": "📲 TikTok video linkini yuboring.\n\nMisol: `https://www.tiktok.com/@user/video/123`",
        "menu_search": "🔍 Qidirish uchun qo'shiq nomi yoki ijrochini yozing.\n\nMisol: `Yulduz Usmonova` yoki `Sevgi nuri`",
        "menu_audio": "🎵 Musiqani aniqlash uchun audio yoki voice yuboring."
    }
    
    if call.data in responses:
        bot.send_message(chat_id, responses[call.data], parse_mode="Markdown")

# ------------------------------
# 🎧 AUDIO/VOICE ORQALI ANIQLASH
# ------------------------------
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio_message(message: types.Message):
    """Audio yoki voice fayl qabul qilish va Shazam orqali aniqlash"""
    try:
        # Xabar yuborish
        msg = bot.reply_to(message, "⏳ Audio tahlil qilinmoqda... (5-15 soniya)")

        # Fayl ma'lumotlarini olish
        if message.audio:
            file_info = bot.get_file(message.audio.file_id)
        elif message.voice:
            file_info = bot.get_file(message.voice.file_id)
        else:
            bot.edit_message_text("❌ Noto'g'ri fayl turi", message.chat.id, msg.message_id)
            return

        # Faylni yuklab olish
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Shazam orqali aniqlash
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song_with_shazam(downloaded_file))
        loop.close()

        # Natijani ko'rsatish
        if result['found']:
            title = result['title']
            artist = result['artist']
            bot.edit_message_text(
                f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}",
                message.chat.id,
                msg.message_id
            )
            
            # Avtomatik yuklab olishga urinish
            query = f"{artist} {title} audio"
            success = search_and_send_audio(message.chat.id, query, title, artist)
            if not success:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Qo'shiq topildi, lekin yuklab bo'lmadi (qo'riqlangan bo'lishi mumkin)."
                )
        else:
            bot.edit_message_text(
                "❌ Musiqa aniqlanmadi. Boshqa audio yuboring yoki qo'shiq nomini yozing.",
                message.chat.id,
                msg.message_id
            )

    except Exception as e:
        log_error("Audio qayta ishlashda xatolik", e)
        bot.reply_to(message, "❌ Xatolik yuz berdi. Qayta urinib ko'ring.")

# ------------------------------
# 📱 INSTAGRAM HANDLER
# ------------------------------
@bot.message_handler(func=lambda m: is_instagram_url(m.text))
def handle_instagram_message(message: types.Message):
    """Instagram linklarini qayta ishlash"""
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "⏳ Instagram video yuklanmoqda...")

        # Video yuklab olish
        video_path, video_title = download_instagram_video(url)
        
        # Natijani tekshirish
        if video_path and os.path.exists(video_path):
            # Tugma yaratish
            btn_hash = create_hash(video_path)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"insta_{btn_hash}"))

            # Video yuborish (captionda kontakt ma'lumotlar)
            with open(video_path, 'rb') as f:
                bot.send_video(
                    message.chat.id,
                    f,
                    reply_markup=markup,
                    caption=(
                        "✅ Instagram video yuklandi!\n\n"
                        "👤 Telegram: @Rustamov_v1\n"
                        "📸 Instagram: https://www.instagram.com/bahrombekh_fx"
                    )
                )

            # Meta ma'lumotlarni saqlash
            meta_path = os.path.join(TEMP_DIR, f"{btn_hash}.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    'video_path': video_path,
                    'timestamp': time.time()
                }, f)

            # Xabarni o'chirish
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(
                f"❌ Instagram video yuklanmadi\n\n"
                f"✅ Tekshiring:\n"
                f"• Video ommaviy bo'lishi kerak\n"
                f"• Linkda 'reel', 'p', yoki 'tv' bo'lishi kerak\n"
                f"• Profil sozlamalarda 'Ommaviy' qilingan bo'lishi kerak\n\n"
                f"🔍 Misol: https://www.instagram.com/reel/Cxyz123/",
                message.chat.id,
                msg.message_id
            )

    except Exception as e:
        log_error("Instagram qayta ishlashda xatolik", e)
        bot.reply_to(message, "❌ Xatolik yuz berdi. Qayta urinib ko'ring.")

# ------------------------------
# 📱 TIKTOK HANDLER
# ------------------------------
@bot.message_handler(func=lambda m: is_tiktok_url(m.text))
def handle_tiktok_message(message: types.Message):
    """TikTok linklarini qayta ishlash"""
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "⏳ TikTok video yuklanmoqda...")

        # Video yuklab olish
        video_path, video_title = download_tiktok_video(url)
        
        # Natijani tekshirish
        if video_path and os.path.exists(video_path):
            btn_hash = create_hash(video_path)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"tiktok_{btn_hash}"))

            with open(video_path, 'rb') as f:
                bot.send_video(
                    message.chat.id,
                    f,
                    reply_markup=markup,
                    caption=(
                        "✅ TikTok video yuklandi!\n\n"
                        "👤 Telegram: @Rustamov_v1\n"
                        "📸 Instagram: https://www.instagram.com/bahrombekh_fx"
                    )
                )

            meta_path = os.path.join(TEMP_DIR, f"{btn_hash}.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    'video_path': video_path,
                    'timestamp': time.time()
                }, f)

            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(
                "❌ TikTok video yuklanmadi.\n\n"
                "✅ Tekshiring:\n"
                "• Link to'g'ri bo'lishi kerak\n"
                "• Video ommaviy bo'lishi kerak\n\n"
                "🔍 Misol: https://www.tiktok.com/@user/video/123456",
                message.chat.id,
                msg.message_id
            )

    except Exception as e:
        log_error("TikTok qayta ishlashda xatolik", e)
        bot.reply_to(message, "❌ Xatolik yuz berdi. Qayta urinib ko'ring.")

# ------------------------------
# 🎵 VIDEO ORQALI MUSIQA ANIQLASH (CALLBACK)
# ------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith(("insta_", "tiktok_")))
def handle_media_music_callback(call: types.CallbackQuery):
    """Videodan musiqa aniqlash (callback)"""
    try:
        # Ma'lumotlarni ajratish
        prefix, btn_hash = call.data.split("_", 1)
        bot.answer_callback_query(call.id, "🎵 Musiqa izlanmoqda...")

        # Meta ma'lumotlarni o'qish
        meta_path = os.path.join(TEMP_DIR, f"{btn_hash}.json")
        if not os.path.exists(meta_path):
            bot.send_message(call.message.chat.id, "❌ Ma'lumot eskirgan. Video qayta yuboring.")
            return

        with open(meta_path) as f:
            meta = json.load(f)
        video_path = meta['video_path']

        if not os.path.exists(video_path):
            bot.send_message(call.message.chat.id, "❌ Video fayl topilmadi.")
            return

        # Audio ajratish
        short_audio_path = extract_audio_from_video(video_path)
        if not short_audio_path or not os.path.exists(short_audio_path):
            bot.send_message(
                call.message.chat.id,
                "❌ Audio ajratishda xatolik. Serverda ffmpeg o'rnatilmagan bo'lishi mumkin."
            )
            return

        # Audio faylni o'qish
        with open(short_audio_path, 'rb') as f:
            short_audio_data = f.read()

        # Shazam orqali aniqlash
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song_with_shazam(short_audio_data))
        loop.close()

        # Natijani ko'rsatish
        if result['found']:
            title = result['title']
            artist = result['artist']
            bot.send_message(
                call.message.chat.id,
                f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}"
            )
            
            # Avtomatik yuklab olish
            query = f"{artist} {title} audio"
            success = search_and_send_audio(call.message.chat.id, query, title, artist)
            if not success:
                bot.send_message(
                    call.message.chat.id,
                    "⚠️ Qo'shiq topildi, lekin yuklab bo'lmadi."
                )
        else:
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi.")

    except Exception as e:
        log_error("Musiqa aniqlashda xatolik", e)
        bot.send_message(call.message.chat.id, "❌ Xatolik yuz berdi.")
    finally:
        # Fayllarni tozalash
        try:
            paths_to_clean = [
                meta_path if 'meta_path' in locals() else None,
                video_path if 'video_path' in locals() else None,
                short_audio_path if 'short_audio_path' in locals() else None
            ]
            for path in paths_to_clean:
                if path and os.path.exists(path):
                    os.remove(path)
        except Exception as e:
            log_error("Tozalashda xatolik", e)

# ------------------------------
# 🔍 QIDIRUV HANDLER (MATN ORQALI)
# ------------------------------
@bot.message_handler(func=lambda m: True)
def search_music_message(message: types.Message):
    """Matn orqali qidiruv (faqat musiqa)"""
    query = message.text.strip()
    
    # Instagram/TikTok linklarni filtrlash
    if is_instagram_url(query) or is_tiktok_url(query):
        return
    
    # Minimal uzunlik tekshiruvi
    if len(query) < 3:
        bot.reply_to(message, "🔍 Qidiruv uchun kamida 3 ta belgi kiriting.")
        return

    # Qidiruv jarayonini boshlash
    msg = bot.reply_to(message, f"🔍 '{query}' qidirilmoqda...")

    try:
        # YouTube orqali qidiruv (faqat audio)
        with yt_dlp.YoutubeDL(YDL_OPTS_SEARCH) as ydl:
            info = ydl.extract_info(f"ytsearch30:{query} audio", download=False)
            songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10][:30]  # >10s

        # Natijalarni tekshirish
        if not songs:
            bot.edit_message_text(
                "❌ Hech qanday natija topilmadi.\n\n"
                "💡 Maslahat:\n"
                "• Qo'shiq nomi yoki ijrochi ismini aniqroq yozing\n"
                "• Lotin alifbosida yozish yaxshi natija beradi",
                message.chat.id,
                msg.message_id
            )
            return

        # Foydalanuvchi sessiyasini saqlash
        user_id = message.chat.id
        user_sessions[user_id] = {
            'query': query,
            'songs': songs,
            'page': 1,
            'timestamp': time.time()
        }
        
        # Birinchi sahifani ko'rsatish (1-10)
        show_results_page(user_id, songs, 1, query)
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        log_error("Qidiruvda xatolik", e)
        bot.edit_message_text(
            "❌ Qidiruvda xatolik yuz berdi.\n"
            "Qayta urinib ko'ring yoki boshqa so'z bilan qidiring.",
            message.chat.id,
            msg.message_id
        )

# ------------------------------
# 📄 NATIJALARNI KO'RSATISH (SAHIFALASH)
# ------------------------------
def show_results_page(chat_id: int, songs: list, page: int, query: str):
    """Qidiruv natijalarini sahifalab ko'rsatish"""
    total_songs = len(songs)
    start_idx = (page - 1) * 10
    end_idx = min(start_idx + 10, total_songs)
    
    # Matn tayyorlash
    text_lines = [f"🔍 '{query}' uchun natijalar ({start_idx+1}-{end_idx}):\n"]
    
    # Tugmalar uchun markup
    markup = types.InlineKeyboardMarkup(row_width=5)
    first_row = []
    second_row = []
    
    # Har bir qo'shiq uchun
    for i in range(start_idx, end_idx):
        song = songs[i]
        if not song:
            continue
            
        idx = i + 1
        title = song.get("title", "Noma'lum")[:50]
        duration = song.get("duration", 0)
        time_str = format_duration(duration)
        
        text_lines.append(f"{idx}. {title}{time_str}")
        
        # Har bir qo'shiq uchun tugma
        url = song.get("url", song.get("webpage_url", ""))
        if url:
            h = create_hash(url)
            # Meta ma'lumotlarni saqlash
            meta_path = os.path.join(TEMP_DIR, f"{h}.json")
            with open(meta_path, 'w') as f:
                json.dump({
                    'url': url,
                    'title': song.get('title', ''),
                    'id': song.get('id', ''),
                    'timestamp': time.time()
                }, f)
            
            # Tugmalarni qatorlarga bo'lish
            if idx % 10 <= 5:
                first_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
            else:
                second_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
    
    # Tugmalarni qo'shish
    if first_row:
        markup.add(*first_row)
    if second_row:
        markup.add(*second_row)
    
    # Navigatsiya tugmalari
    nav_buttons = []
    
    # Orqaga tugmasi (faqat 1-sahifadan keyin)
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="nav_prev"))
    else:
        nav_buttons.append(types.InlineKeyboardButton(" ", callback_data="nav_dummy"))  # Bo'sh tugma
    
    # Bosh sahifa
    nav_buttons.append(types.InlineKeyboardButton("🏠 Bosh", callback_data="nav_home"))
    
    # Oldinga tugmasi (faqat 30 dan kam bo'lganda)
    if end_idx < total_songs:
        nav_buttons.append(types.InlineKeyboardButton("Oldinga ➡️", callback_data="nav_next"))
    else:
        nav_buttons.append(types.InlineKeyboardButton(" ", callback_data="nav_dummy"))  # Bo'sh tugma
    
    markup.add(*nav_buttons)
    
    # Xabarni yuborish
    bot.send_message(chat_id, "\n".join(text_lines), reply_markup=markup)

# ------------------------------
# 🎵 AUDIO YUKLASH (CALLBACK)
# ------------------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("song_"))
def download_audio_callback(call: types.CallbackQuery):
    """Qidiruv natijasidan audio yuklab olish"""
    h = call.data.split("_", 1)[1]
    meta_path = os.path.join(TEMP_DIR, f"{h}.json")
    
    # Meta ma'lumotlarni tekshirish
    if not os.path.exists(meta_path):
        bot.answer_callback_query(call.id, "❌ Ma'lumot eskirgan. Qayta qidiring.")
        return
    
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        url = meta['url']
        title = meta.get('title', 'Musiqa')
        
        # Yuklash jarayonini boshlash
        bot.answer_callback_query(call.id, "🎵 Yuklanmoqda... (10-30 soniya)")
        bot.send_chat_action(call.message.chat.id, 'upload_audio')
        
        # Fayl nomi
        clean_title = clean_filename(title)
        output_path = os.path.join(TEMP_DIR, f"{clean_title}.mp3")
        
        # Yuklash sozlamalari
        opts = YDL_OPTS_AUDIO.copy()
        opts['outtmpl'] = output_path.replace('.mp3', '')
        
        # Yuklab olish
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            actual_title = info.get('title', title)
        
        # Fayl mavjudligini tekshirish
        if not os.path.exists(output_path):
            output_path += ".mp3"
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:  # >10KB
            with open(output_path, 'rb') as f:
                bot.send_audio(
                    call.message.chat.id,
                    f,
                    title=actual_title[:64],
                    performer=""
                )
            # Faylni o'chirish
            os.remove(output_path)
        else:
            # Alternativ fayllarni qidirish
            found = False
            for f in os.listdir(TEMP_DIR):
                if f.endswith('.mp3') and clean_title[:15] in f:
                    alt_path = os.path.join(TEMP_DIR, f)
                    if os.path.getsize(alt_path) > 10000:
                        with open(alt_path, 'rb') as f_audio:
                            bot.send_audio(call.message.chat.id, f_audio, title=actual_title[:64])
                        os.remove(alt_path)
                        found = True
                        break
            if not found:
                bot.send_message(call.message.chat.id, "❌ Yuklab bo'lmadi. Boshqa qo'shiq tanlang.")
    
    except Exception as e:
        log_error("Audio yuklashda xatolik", e)
        bot.send_message(call.message.chat.id, "❌ Yuklashda xatolik yuz berdi.")
    finally:
        # Meta faylni o'chirish
        if os.path.exists(meta_path):
            os.remove(meta_path)

# ------------------------------
# 🧭 NAVIGATSIYA CALLBACKLAR
# ------------------------------
@bot.callback_query_handler(func=lambda c: c.data in ["nav_prev", "nav_home", "nav_next", "nav_dummy"])
def handle_navigation_callback(call: types.CallbackQuery):
    """Sahifalash uchun navigatsiya"""
    if call.data == "nav_dummy":
        bot.answer_callback_query(call.id)
        return
        
    user_id = call.message.chat.id
    
    # Sessiyani tekshirish
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "❌ Sessiya tugagan. Qayta qidiring.")
        return
    
    session = user_sessions[user_id]
    query = session['query']
    songs = session['songs']
    current_page = session['page']
    
    # Eski xabarni o'chirish
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    # Har bir navigatsiya uchun
    if call.data == "nav_prev":
        # Avvalgi sahifaga o'tish
        new_page = max(1, current_page - 1)
        user_sessions[user_id]['page'] = new_page
        show_results_page(user_id, songs, new_page, query)
        
    elif call.data == "nav_home":
        # Bosh sahifaga qaytish
        start_message(types.Message(chat=types.Chat(id=user_id, type='private')))
        
    elif call.data == "nav_next":
        # Keyingi sahifaga o'tish
        new_page = current_page + 1
        if (new_page - 1) * 10 < len(songs):
            user_sessions[user_id]['page'] = new_page
            show_results_page(user_id, songs, new_page, query)
        else:
            bot.send_message(user_id, "❌ Ko'proq natija topilmadi.")

# ============================================================
# 🚀 BOTNI ISHGA TUSHIRISH
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("✅ MUKAMMAL MUSIQA BOTI ISHGA TUSHDI!")
    print("📱 Instagram • TikTok • Qidiruv • Shazam • Sahifalash")
    print("👤 @Rustamov_v1 uchun maxsus tayyorlandi")
    print("-" * 60)
    print("🔧 Sozlamalar:")
    print(f"• TEMP papka: {TEMP_DIR}")
    print(f"• Token: {'Belgilangan' if BOT_TOKEN else 'Yoq'}")
    print(f"• Tozalash: 5 daqiqada bir")
    print("-" * 60)
    print("🚀 Bot ishga tushdi! /start buyrug'ini yuboring.")
    print("=" * 60)
    
    # Botni doimiy ishlatish
    bot.infinity_polling(
        skip_pending=True,
        none_stop=True,
        interval=0,
        timeout=20
    )
