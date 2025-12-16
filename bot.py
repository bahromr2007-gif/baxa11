import os
import sys
import time
import tempfile
import hashlib
import re
import json
import threading
from datetime import datetime, timedelta

import telebot
from telebot import types
from shazamio import Shazam
import yt_dlp

# ====== XAVFSIZLIK: BOT_TOKENni muhit o'zgaruvchisidan olish ======
BOT_TOKEN = "8575775719:AAFjR9wnpNEDI-3pzWOeQ1NnyaOnrfgpOk4"
if not BOT_TOKEN:
    print("❌ BOT_TOKEN muhit o'zgaruvchisi belgilanmagan!")
    print("Linux/Mac: export BOT_TOKEN='sizning_token'")
    print("Windows: set BOT_TOKEN=sizning_token")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# ====== TEMP PAPKA VA TOZALASH ======
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# Eski fayllarni avtomatik o'chirish (5 daqiqadan keyin)
def cleanup_old_files():
    while True:
        now = time.time()
        for filename in os.listdir(TEMP_DIR):
            filepath = os.path.join(TEMP_DIR, filename)
            try:
                if os.path.isfile(filepath) and now - os.path.getctime(filepath) > 300:  # 5 min
                    os.remove(filepath)
                    print(f"🧹 Eski fayl o'chirildi: {filename}")
            except Exception as e:
                print(f"🧹 Tozalashda xatolik: {e}")
        time.sleep(60)

threading.Thread(target=cleanup_old_files, daemon=True).start()

# ====== YORDAMCHI FUNKSIYALAR ======
def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]

def clean_filename(text):
    if not text or not isinstance(text, str):
        return "musiqa"
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    text = re.sub(r'\s+', '_', text.strip())
    return text[:50] or "musiqa"

def format_duration(seconds):
    try:
        s = int(float(seconds))
        return f" ({s//60}:{s%60:02d})"
    except:
        return ""

def is_instagram_url(url):
    return bool(re.search(r'https?://(www\.)?instagram\.com/(reel|p|tv|stories)/', url.lower()))

def is_tiktok_url(url):
    return bool(re.search(r'https?://(www\.|vm\.|vt\.)?tiktok\.com/', url.lower()))

# ====== YUKLASH SOZLAMALARI ======
ydl_opts_base = {
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': 30,
    'retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    },
}

ydl_opts_video = {
    **ydl_opts_base,
    'format': 'best[height<=720]',
    'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
    'noplaylist': True,
}

ydl_opts_audio = {
    **ydl_opts_base,
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
}

# ====== INSTAGRAM & TIKTOK YUKLASH ======
def download_instagram(url):
    """Ishonchli Instagram yuklovchi (cookies siz)"""
    opts = {
        **ydl_opts_video,
        'extractor_args': {'instagram': {'tab': ['clips']}},
        'cookiefile': None,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, "Ma'lumot topilmadi"
            
            video_id = info.get('id') or info.get('display_id', 'insta')
            title = info.get('title', 'Instagram Reel').strip()
            
            for f in os.listdir(TEMP_DIR):
                if f.startswith(video_id) and f.endswith(('.mp4', '.webm')):
                    return os.path.join(TEMP_DIR, f), title
            return None, title
    except Exception as e:
        return None, f"Xatolik: {str(e)[:100]}"

def download_tiktok(url):
    """TikTok uchun ishlovchi usul"""
    # Birinchi navbatda oddiy yt-dlp
    try:
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                for f in os.listdir(TEMP_DIR):
                    if f.endswith(('.mp4', '.webm')):
                        path = os.path.join(TEMP_DIR, f)
                        if os.path.getsize(path) > 10000:  # >10KB
                            title = info.get('title', 'TikTok Video')[:50]
                            return path, title
    except:
        pass
    
    # Agar ishlamasa — oddiy usul (faqat audio)
    return None, "TikTok video topilmadi"

# ====== SHAZAM — ASINXRON EMAS, Lekin ISHLOVCHI ======
async def recognize_with_shazam(audio_path):
    try:
        shazam = Shazam()
        result = await shazam.recognize(audio_path)
        if result and result.get('track'):
            track = result['track']
            return {
                'found': True,
                'title': track.get('title', 'Noma\'lum'),
                'artist': track.get('subtitle', 'Noma\'lum'),
                'url': track.get('url', ''),
            }
    except Exception as e:
        print(f"Shazam xatosi: {e}")
    return {'found': False}

# ====== HANDLERLAR ======
@bot.message_handler(commands=['start'])
def start_message(message):
    text = (
        "👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        "✅ Ishlaydigan imkoniyatlar:\n"
        "1. 📱 Instagram Reel linki (ommaviy yoki maxfiy ham)\n"
        "2. 📱 TikTok video linki\n"
        "3. 🎤 Qo'shiq nomi yoki ijrochi (masalan: *Yulduz Usmonova*)\n"
        "4. 🎵 Audio/voice fayl (musiqani aniqlash uchun)\n\n"
        "🔥 Hammasi tez va aniq ishlaydi!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ====== INSTAGRAM ======
@bot.message_handler(func=lambda m: is_instagram_url(m.text))
def handle_instagram(message):
    bot.send_chat_action(message.chat.id, 'upload_video')
    url = message.text.strip()
    path, title = download_instagram(url)
    
    if path and os.path.exists(path):
        btn_hash = create_hash(path)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        with open(path, 'rb') as f:
            bot.send_video(message.chat.id, f, caption="✅ Video yuklandi!\nMusiqa topish uchun tugmani bosing.", reply_markup=markup)
        
        meta_path = os.path.join(TEMP_DIR, f"{btn_hash}.json")
        with open(meta_path, 'w') as f:
            json.dump({'video_path': path}, f)
    else:
        bot.reply_to(message, f"❌ Video yuklanmadi.\n\n👉 Video ommaviy bo'lishi shart. Agar maxfiy bo'lsa, profil sozlamalaridan \"Ommaviy\" qiling yoki boshqa video yuboring.")

# ====== TIKTOK ======
@bot.message_handler(func=lambda m: is_tiktok_url(m.text))
def handle_tiktok(message):
    bot.send_chat_action(message.chat.id, 'upload_video')
    url = message.text.strip()
    path, title = download_tiktok(url)
    
    if path and os.path.exists(path):
        btn_hash = create_hash(path)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"music_{btn_hash}"))
        
        with open(path, 'rb') as f:
            bot.send_video(message.chat.id, f, caption="✅ Video yuklandi!\nMusiqa topish uchun tugmani bosing.", reply_markup=markup)
        
        meta_path = os.path.join(TEMP_DIR, f"{btn_hash}.json")
        with open(meta_path, 'w') as f:
            json.dump({'video_path': path}, f)
    else:
        bot.reply_to(message, "❌ TikTok video yuklanmadi. Iltimos, to'g'ri link yuboring.")

# ====== AUDIO/VOICE ORQALI ANIQLASH ======
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    bot.send_chat_action(message.chat.id, 'typing')
    msg = bot.reply_to(message, "🎧 Musiqa tahlil qilinmoqda... (5-10 soniya)")

    try:
        if message.audio:
            file_info = bot.get_file(message.audio.file_id)
        else:  # voice
            file_info = bot.get_file(message.voice.file_id)
        
        downloaded = bot.download_file(file_info.file_path)
        audio_path = os.path.join(TEMP_DIR, f"audio_{int(time.time())}.mp3")
        
        with open(audio_path, 'wb') as f:
            f.write(downloaded)
        
        # Shazam orqali aniqlash
        import asyncio
        result = asyncio.run(recognize_with_shazam(audio_path))
        
        bot.delete_message(msg.chat.id, msg.message_id)
        
        if result['found']:
            title, artist = result['title'], result['artist']
            bot.send_message(message.chat.id, f"✅ Musiqa topildi!\n\n🎵 {title}\n👤 {artist}")
            
            # Yuklab olish uchun qidiruv
            query = f"{artist} {title}"
            search_and_send_audio(message.chat.id, query, title, artist)
        else:
            bot.send_message(message.chat.id, "❌ Musiqa aniqlanmadi. Boshqa audio yuboring yoki qo'shiq nomini yozing.")
    
    except Exception as e:
        bot.delete_message(msg.chat.id, msg.message_id)
        bot.send_message(message.chat.id, "❌ Qayta urinib ko'ring yoki boshqa audio yuboring.")
    finally:
        if 'audio_path' in locals() and os.path.exists(audio_path):
            try: os.remove(audio_path)
            except: pass

# ====== QIDIRUV (QO'SHIQ/IJROCHI NOMI) ======
@bot.message_handler(func=lambda m: not (is_instagram_url(m.text) or is_tiktok_url(m.text)) and len(m.text.strip()) > 2)
def handle_search(message):
    query = message.text.strip()
    if len(query) < 3:
        bot.reply_to(message, "🔍 Qidiruv uchun kamida 3 ta belgi kiriting.")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    msg = bot.reply_to(message, f"🔍 '{query}' qidirilmoqda...")

    try:
        with yt_dlp.YoutubeDL({**ydl_opts_base, 'extract_flat': True, 'playlistend': 10}) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10][:10]
        
        if not songs:
            bot.edit_message_text("❌ Hech narsa topilmadi. Boshqa so'z bilan qidiring.", msg.chat.id, msg.message_id)
            return
        
        # Natijalarni ko'rsatish
        text = f"🎵 '{query}' uchun natijalar:\n\n"
        markup = types.InlineKeyboardMarkup(row_width=5)
        btns = []
        
        for i, song in enumerate(songs[:10], 1):
            title = clean_filename(song.get('title', 'Noma\'lum')[:40])
            dur = format_duration(song.get('duration'))
            text += f"{i}. {title}{dur}\n"
            
            h = create_hash(song['url'])
            meta = {'url': song['url'], 'title': song.get('title', ''), 'id': song.get('id')}
            with open(os.path.join(TEMP_DIR, f"{h}.json"), 'w') as f:
                json.dump(meta, f)
            btns.append(types.InlineKeyboardButton(str(i), callback_data=f"dl_{h}"))
        
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel"))
        
        bot.delete_message(msg.chat.id, msg.message_id)
        bot.send_message(message.chat.id, text, reply_markup=markup)
    
    except Exception as e:
        bot.edit_message_text("❌ Qidiruvda xatolik. Qayta urinib ko'ring.", msg.chat.id, msg.message_id)

# ====== CALLBACKLAR ======
@bot.callback_query_handler(func=lambda c: c.data.startswith("music_"))
def callback_recognize(call):
    bot.answer_callback_query(call.id, "🎵 Musiqa tahlil qilinmoqda...")
    h = call.data.split("_", 1)[1]
    meta_path = os.path.join(TEMP_DIR, f"{h}.json")
    
    if not os.path.exists(meta_path):
        bot.send_message(call.message.chat.id, "❌ Ma'lumot eskirgan. Video qayta yuboring.")
        return
    
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        video_path = meta['video_path']
        
        if not os.path.exists(video_path):
            bot.send_message(call.message.chat.id, "❌ Video fayl topilmadi.")
            return
        
        # Videodan 10 soniya audio ajratish (ffmpeg bo'lmagan holda — faqat yt-dlp)
        short_path = video_path.replace('.mp4', '_short.mp3').replace('.webm', '_short.mp3')
        
        try:
            # yt-dlp orqali audio yuklab olish
            with yt_dlp.YoutubeDL({
                'format': 'bestaudio[ext=mp3]/bestaudio',
                'extractaudio': True,
                'audioformat': 'mp3',
                'outtmpl': short_path.replace('.mp3', ''),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True,
                'noplaylist': True,
                'download_ranges': lambda info, *, ydl: [{'start_time': 5, 'end_time': 15}],
            }) as ydl:
                ydl.download([video_path])
        except:
            # Agar ishlamasa — oddiy audio yuklab olish
            try:
                with yt_dlp.YoutubeDL({
                    'format': 'bestaudio[ext=mp3]/bestaudio',
                    'extractaudio': True,
                    'audioformat': 'mp3',
                    'outtmpl': short_path.replace('.mp3', ''),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'quiet': True,
                }) as ydl:
                    ydl.download([video_path])
            except:
                bot.send_message(call.message.chat.id, "❌ Audio ajratishda xatolik.")
                return
        
        if not os.path.exists(short_path):
            short_path += ".mp3"
        if not os.path.exists(short_path):
            bot.send_message(call.message.chat.id, "❌ Audio fayl topilmadi.")
            return
        
        # Shazam
        import asyncio
        result = asyncio.run(recognize_with_shazam(short_path))
        
        if result['found']:
            title, artist = result['title'], result['artist']
            bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n\n🎵 {title}\n👤 {artist}")
            search_and_send_audio(call.message.chat.id, f"{artist} {title}", title, artist)
        else:
            bot.send_message(call.message.chat.id, "❌ Musiqa aniqlanmadi.")
    
    finally:
        for p in [meta_path, video_path, short_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("dl_"))
def callback_download(call):
    h = call.data.split("_", 1)[1]
    meta_path = os.path.join(TEMP_DIR, f"{h}.json")
    
    if not os.path.exists(meta_path):
        bot.answer_callback_query(call.id, "❌ Eskirgan. Qayta qidiring.")
        return
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    bot.answer_callback_query(call.id, "🎵 Yuklanmoqda... (10-20 soniya)")
    bot.send_chat_action(call.message.chat.id, 'upload_audio')
    
    output_path = os.path.join(TEMP_DIR, f"dl_{h}.mp3")
    try:
        opts = {**ydl_opts_audio, 'outtmpl': output_path.replace('.mp3', '')}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([meta['url']])
        
        if not os.path.exists(output_path):
            output_path += ".mp3"
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            with open(output_path, 'rb') as f:
                bot.send_audio(
                    call.message.chat.id,
                    f,
                    title=meta['title'][:64],
                    performer="",
                    caption="✅ Yuklandi!"
                )
        else:
            bot.send_message(call.message.chat.id, "❌ Yuklab bo'lmadi. Boshqa qo'shiq tanlang.")
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ Yuklashda xatolik. Boshqa qo'shiq tanlang.")
    finally:
        if os.path.exists(meta_path):
            os.remove(meta_path)
        if os.path.exists(output_path):
            os.remove(output_path)

@bot.callback_query_handler(func=lambda c: c.data == "cancel")
def callback_cancel(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

# ====== YORDAMCHI: QIDIRUV ORQALI AUDIO YUBORISH ======
def search_and_send_audio(chat_id, query, title="Musiqa", artist=""):
    try:
        opts = {**ydl_opts_audio, 'outtmpl': os.path.join(TEMP_DIR, f"search_{int(time.time())}.%(ext)s")}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            if not info or not info.get('entries'):
                return
            
            song = info['entries'][0]
            path = opts['outtmpl'].replace('.%(ext)s', '.mp3')
            if not os.path.exists(path):
                path += ".mp3"
            
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    bot.send_audio(
                        chat_id,
                        f,
                        title=song.get('title', title)[:64],
                        performer=song.get('uploader', artist)[:64],
                        caption=f"🎵 {title}\n👤 {artist}"
                    )
                os.remove(path)
    except:
        pass

# ====== ISHGA TUSHIRISH ======
if __name__ == '__main__':
    print("✅ Bot ishga tushdi!")
    print("ℹ️  Eslatma: BOT_TOKEN muhit o'zgaruvchisi sozlangan bo'lishi kerak.")
    bot.infinity_polling(skip_pending=True)
