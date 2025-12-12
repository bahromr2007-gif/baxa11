import telebot
import os
import asyncio
import tempfile
import subprocess
import hashlib
from telebot import types
from shazamio import Shazam
import yt_dlp

# ========================================
# BOT TOKEN - o'zingizning tokeningizni qo'ying
BOT_TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"
bot = telebot.TeleBot(BOT_TOKEN)

# ========================================
# /start — faqat salomlashadi
@bot.message_handler(commands=['start'])
def start_message(message):
    text = (
        "👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        "Menga quyidagilarni yuborishingiz mumkin:\n"
        "1. 📱 Instagram Reel linki\n"
        "2. 📱 TikTok video linki\n"
        "3. 🎤 Qo'shiq nomi yoki ijrochi ismi\n"
        "4. 🎵 Audio fayl (musiqani aniqlash uchun)\n\n"
        "👤 Telegram: @Rustamov_v1\n"
        "📸 Instagram: https://www.instagram.com/bahrombekh_fx?igsh=Y2J0NnFpNm9icTFp"
    )
    bot.send_message(message.chat.id, text)

# TEMP papka
if not os.path.exists("temp"):
    os.makedirs("temp")

# Download opts
ydl_opts_video = {
    'format': 'best',
    'quiet': True,
    'merge_output_format': 'mp4',
    'outtmpl': 'temp/%(id)s.%(ext)s',
}
ydl_opts_audio = {
    'format': 'bestaudio/best',
    'quiet': True,
    'outtmpl': 'temp/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# ================= Helper Functions
def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def clean_filename(filename):
    """Fayl nomini tozalash"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename[:100]

# ================= Shazam aniqlash
async def recognize_song(audio_bytes):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        shazam = Shazam()
        result = await shazam.recognize(tmp_path)
        os.unlink(tmp_path)

        if result and 'track' in result:
            track = result['track']
            return {
                'found': True, 
                'title': track.get('title', 'Noma\'lum'),
                'artist': track.get('subtitle', 'Noma\'lum'),
                'link': track.get('share', {}).get('href', ''),
                'image': track.get('images', {}).get('coverarthq', '')
            }
    except Exception as e:
        print(f"Shazam xatosi: {e}")
    return {'found': False}

# ================= Audio fayl yuborilganda (Shazam) - TO'G'RIDAN AUDIO YUBORADI
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    try:
        msg = bot.reply_to(message, "🎵 Musiqa aniqlanmoqda...")
        
        if message.audio:
            file_info = bot.get_file(message.audio.file_id)
        elif message.voice:
            file_info = bot.get_file(message.voice.file_id)
        else:
            return
            
        downloaded_file = bot.download_file(file_info.file_path)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song(downloaded_file))
        loop.close()
        
        if result['found']:
            title = result['title']
            artist = result['artist']
            
            # TO'G'RIDAN AUDIO YUKLAB YUBORISH
            bot.edit_message_text(f"✅ Musiqa topildi! Yuklanmoqda...", message.chat.id, msg.message_id)
            
            # YouTube orqali full audio yuklash
            query = f"{artist} {title}"
            try:
                opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': 'temp/%(title)s.%(ext)s',
                    'quiet': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192'
                    }]
                }
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                    if 'entries' in info:
                        song = info['entries'][0]
                        filename = ydl.prepare_filename(song)
                        filename = filename.rsplit(".", 1)[0] + ".mp3"
                        
                        with open(filename, 'rb') as f:
                            bot.send_audio(
                                message.chat.id, 
                                f, 
                                title=title, 
                                performer=artist,
                                caption=f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}"
                            )
                        
                        os.remove(filename)
                        bot.delete_message(message.chat.id, msg.message_id)
                        
            except Exception as download_error:
                bot.edit_message_text(
                    f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Yuklab olishda xatolik: {str(download_error)[:100]}", 
                    message.chat.id, 
                    msg.message_id
                )
        else:
            bot.edit_message_text("❌ Musiqa topilmadi. Iltimos, yana bir bor urinib ko'ring.", message.chat.id, msg.message_id)
            
    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {str(e)[:100]}")

# ================= Instagram handler
@bot.message_handler(func=lambda m: 'instagram.com' in m.text and ('/reel/' in m.text or '/p/' in m.text or '/tv/' in m.text))
def handle_instagram_reel(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 Instagram videoni yuklamoqda...")

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            btn_hash = create_hash(filename)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"insta_{btn_hash}"))

            with open(filename, 'rb') as f:
                bot.send_video(message.chat.id, f, reply_markup=markup)

            with open(f"temp/{btn_hash}.txt", "w") as f:
                f.write(filename)

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {str(e)[:100]}")

# ================= TikTok handler
@bot.message_handler(func=lambda m: 'tiktok.com' in m.text)
def handle_tiktok(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 TikTok videoni yuklamoqda...")

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            btn_hash = create_hash(filename)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"tiktok_{btn_hash}"))

            with open(filename, 'rb') as f:
                bot.send_video(message.chat.id, f, reply_markup=markup)

            with open(f"temp/{btn_hash}.txt", "w") as f:
                f.write(filename)

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik: {str(e)[:100]}")

# ================= Inline tugma handler (Instagram/TikTok) - TO'G'RIDAN AUDIO YUBORADI
@bot.callback_query_handler(func=lambda call: call.data.startswith(("insta_", "tiktok_")))
def handle_media_music(call):
    try:
        prefix, btn_hash = call.data.split("_", 1)
        bot.answer_callback_query(call.id, "🎵 Musiqa izlanmoqda...")

        with open(f"temp/{btn_hash}.txt", "r") as f:
            video_path = f.read().strip()

        # Shazam uchun 15 soniya audio
        short_audio_path = video_path.rsplit('.', 1)[0] + '_short.mp3'
        subprocess.run([
            'ffmpeg', '-i', video_path, '-t', '15', '-vn', '-acodec', 'mp3',
            '-ab', '192k', '-ar', '44100', '-y', short_audio_path
        ], capture_output=True, timeout=60)

        with open(short_audio_path, 'rb') as f:
            short_audio_data = f.read()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song(short_audio_data))
        loop.close()

        if result['found']:
            title = result['title']
            artist = result['artist']
            
            # TO'G'RIDAN AUDIO YUKLAB YUBORISH
            bot.send_message(call.message.chat.id, f"✅ Musiqa topildi! Yuklanmoqda...")
            
            # YouTube orqali full audio yuklash
            query = f"{artist} {title}"
            try:
                opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': 'temp/%(title)s.%(ext)s',
                    'quiet': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192'
                    }]
                }
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                    if 'entries' in info:
                        song = info['entries'][0]
                        filename = ydl.prepare_filename(song)
                        filename = filename.rsplit(".", 1)[0] + ".mp3"
                        
                        with open(filename, 'rb') as f:
                            bot.send_audio(
                                call.message.chat.id, 
                                f, 
                                title=title, 
                                performer=artist,
                                caption=f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}"
                            )
                        
                        os.remove(filename)
                        
            except Exception as download_error:
                bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Yuklab olishda xatolik: {str(download_error)[:100]}")
        else:
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Xatolik: {str(e)[:100]}")

    finally:
        try:
            if 'video_path' in locals() and os.path.exists(video_path):
                os.remove(video_path)
            if 'short_audio_path' in locals() and os.path.exists(short_audio_path):
                os.remove(short_audio_path)
            if 'btn_hash' in locals() and os.path.exists(f"temp/{btn_hash}.txt"):
                os.remove(f"temp/{btn_hash}.txt")
        except:
            pass

# =====================================================
# === 🎵 ARTIST NOMINI YOZIB MUSIQALARINI CHIQARISH ===
# =====================================================

@bot.message_handler(func=lambda m: True)
def search_artist_music(message):
    artist_name = message.text.strip()

    # Instagram/TikTok link bo'lsa - yuqoridagi handler ishlaydi
    if "instagram.com" in artist_name or "tiktok.com" in artist_name:
        return

    msg = bot.reply_to(message, f"🔍 {artist_name} musiqalari izlanmoqda...")

    try:
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'extract_flat': False}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{artist_name}", download=False)
            songs = info['entries']

        # Matn ro'yxati
        text_list = [f"🔍 '{artist_name}' uchun natijalar:\n"]
        for i, s in enumerate(songs, 1):
            title = s.get("title", "Noma'lum")
            duration = s.get("duration", 0)
            m, s2 = divmod(duration, 60)
            text_list.append(f"{i}. {title} ⏱️ {m}:{s2:02d}")

        # Inline tugmalar (gorizontal 1 2 3 4 ...)
        markup = types.InlineKeyboardMarkup(row_width=5)
        buttons = []

        for i, s in enumerate(songs, 1):
            url = s.get("url", s.get("webpage_url", ""))
            if url:
                h = create_hash(url)
                with open(f"temp/{h}.txt", "w") as f:
                    f.write(f"{url}|{s.get('title', 'Unknown')}")
                buttons.append(types.InlineKeyboardButton(str(i), callback_data=f"song_{h}"))

        if buttons:
            markup.add(*buttons)
            bot.send_message(message.chat.id, "\n".join(text_list), reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "❌ Hech qanday natija topilmadi.")

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)[:100]}", message.chat.id, msg.message_id)

# ====================
# == AUDIO DOWNLOAD ==
# ====================

@bot.callback_query_handler(func=lambda c: c.data.startswith("song_"))
def download_audio(call):
    h = call.data.split("_", 1)[1]

    with open(f"temp/{h}.txt") as f:
        data = f.read().strip()
    
    if "|" in data:
        url, title = data.split("|", 1)
    else:
        url = data
        title = "Unknown"

    bot.answer_callback_query(call.id, "🎵 Yuklanmoqda...")

    try:
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp/%(title)s.%(ext)s',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = filename.rsplit(".", 1)[0] + ".mp3"

        with open(filename, 'rb') as f:
            bot.send_audio(call.message.chat.id, f, title=info.get("title", title))

        os.remove(filename)
        os.remove(f"temp/{h}.txt")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Xatolik: {str(e)[:100]}")

# ================= Bot ishga tushishi
print("✅ BOT ISHGA TUSHDI! Instagram + TikTok + YouTube + Musiqa qidirish + Shazam")
print("🎵 Endi 'Musiqa topildi' xabari tagiga tugma qo'shilmaydi, to'g'ridan-to'g'ri audio yuboriladi!")
bot.infinity_polling()
