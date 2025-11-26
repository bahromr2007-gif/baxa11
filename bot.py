import os
import asyncio
import yt_dlp
from pydub import AudioSegment
from shazamio import Shazam

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes, filters
)

# ================= SOZLAMALAR =================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Railwayda Environment Variable sifatida o'rnat
MY_TG = "@Rustamov_v1"
MY_IG = "https://www.instagram.com/bahrombekh_fx?igsh=Y2J0NnFpNm9icTFp"
COOKIES_FILE = "cookies.txt"  # Shu faylni bot papkasiga qo'yish kerak
# ==============================================

yt_cache = {}
yt_cache_folder = "yt-dlp-cache"

# FFmpeg yo'lni aniqlash (Railway uchun)
AudioSegment.converter = "/usr/bin/ffmpeg"

# ================= /start KOMANDASI =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        f"👤 Telegram: {MY_TG}\n"
        f"📸 Instagram: {MY_IG}\n\n"
        "Menga qo'shiq nomi yozing yoki Instagram link tashlang 🎧"
    )
    await update.message.reply_text(text)

# ================= YOUTUBE QIDIRUV =================
async def search_youtube(update: Update, query: str):
    search_url = f"ytsearch5:{query}"
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "cookies": COOKIES_FILE,  # Railway uchun cookies
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            entries = info.get("entries", [])[:5]

            if not entries:
                await update.message.reply_text("🔍 Natija topilmadi.")
                return

            keyboard = []
            for idx, e in enumerate(entries, start=1):
                title = e.get("title", "No title")[:60]
                url = e.get("webpage_url")
                yt_cache[idx] = url
                keyboard.append([InlineKeyboardButton(f"{idx}. {title}", callback_data=f"yt|{idx}")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🎧 Quyidagi videolardan birini tanlang:", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ YouTube xatosi: {e}")

# ================= YOUTUBE MP3 YUKLASH =================
async def download_and_send_youtube(update: Update, vid_id: int):
    url = yt_cache.get(vid_id)
    if not url:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text("⚠️ Video topilmadi.")
        return

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "song_temp.%(ext)s",
        "quiet": True,
        "cookies": COOKIES_FILE,  # Shu qatorda cookies ishlatiladi
    }

    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("⏳ Yuklanmoqda...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            original_filename = ydl.prepare_filename(info)

        # MP3 ga konvert qilish
        output_filename = "song_temp.mp3"
        audio = AudioSegment.from_file(original_filename)
        audio.export(output_filename, format="mp3")

        # Telegramga yuborish
        caption = f"🎶 {info.get('title', 'Nomaʼlum')}"
        await update.effective_chat.send_audio(
            audio=open(output_filename, "rb"),
            caption=caption
        )

    except Exception as e:
        error_msg = f"⚠️ Yuklab bo'lmadi: {str(e)}"
        await update.effective_chat.send_message(error_msg)

    finally:
        # Fayllarni tozalash
        for filename in [original_filename, output_filename]:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except:
                    pass

# ================= CALLBACK HANDLER =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("yt|"):
        vid_id = int(data.split("|")[1])
        await download_and_send_youtube(update, vid_id)

# ================= MUSIQA ANIQLASH =================
async def recognize_music_safe(audio_path: str):
    try:
        shazam = Shazam()
        out = await shazam.recognize_song(audio_path)
        
        if not out or 'track' not in out:
            return None
            
        track = out['track']
        title = track.get("title", "Nomaʼlum")
        artist = track.get("subtitle", "Nomaʼlum")
        
        return f"{title} - {artist}"
    except Exception as e:
        print(f"Shazam xatosi: {e}")
        return None

# ================= INSTAGRAM VIDEO HANDLER =================
async def download_instagram(update: Update, link: str):
    await update.message.reply_text("📥 Instagram videosi yuklanmoqda...")

    ydl_opts = {
        "format": "best",
        "outtmpl": "insta_temp.%(ext)s",
        "quiet": True,
        "cookies": COOKIES_FILE,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_filename = ydl.prepare_filename(info)

        # Videoni yuborish
        await update.message.reply_video(
            video=open(video_filename, "rb"), 
            caption="📸 Video yuklandi"
        )

        # Audio konvert qilish
        audio_filename = "insta_audio.mp3"
        audio = AudioSegment.from_file(video_filename)
        audio.export(audio_filename, format="mp3")

        # Musiqani aniqlash
        await update.message.reply_text("🎧 Musiqa aniqlanmoqda...")
        music_info = await recognize_music_safe(audio_filename)

        if music_info:
            if " - " in music_info:
                track_name, artist_name = music_info.split(" - ", 1)
            else:
                track_name = music_info
                artist_name = "Nomaʼlum"

            await update.message.reply_text(
                f"🎵 Qo'shiq: {track_name}\n👤 Ijrochi: {artist_name}"
            )
            await search_youtube(update, music_info)
        else:
            await update.message.reply_text("❌ Musiqa aniqlanmadi.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Xato: {str(e)}")

    finally:
        # Fayllarni tozalash
        for filename in [video_filename, audio_filename]:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except:
                    pass

# ================= ASOSIY HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "instagram.com" in text:
        await download_instagram(update, text)
    elif "youtube.com" in text or "youtu.be" in text:
        yt_cache[0] = text
        await download_and_send_youtube(update, 0)
    else:
        await update.message.reply_text("🎧 Musiqa qidirilmoqda...")
        await search_youtube(update, text)

# ================= BOTNI ISHGA TUSHURISH =================
def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN topilmadi!")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
