import os
import asyncio
import yt_dlp
from pydub import AudioSegment
from shazamio import Shazam

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"
COOKIES = "cookies.txt"

# FFmpeg path for Railway / Ubuntu
AudioSegment.converter = "/usr/bin/ffmpeg"

yt_cache = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎵 *Song Finder Bot*\n"
        "Menga qoʻshiq nomi yoki Instagram videosi linkini tashlang.\n\n"
        "⚡ *Tezkor • Aniqlik yuqori • SongFastBot Style*\n"
    )

    keyboard = [
        [InlineKeyboardButton("🎧 Qo‘shiq qidirish", callback_data="menu_music")],
        [InlineKeyboardButton("📸 Instagram video", callback_data="menu_insta")]
    ]

    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ================= YOUTUBE SEARCH =================
async def yt_search(update, query):
    await update.message.reply_text("🔍 *Qidirilmoqda...*", parse_mode="Markdown")

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "cookies": COOKIES
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)

        entries = info["entries"][:5]

        keyboard = []
        yt_cache.clear()
        for idx, e in enumerate(entries, start=1):
            yt_cache[idx] = e["webpage_url"]
            keyboard.append([
                InlineKeyboardButton(
                    f"{idx}. {e['title'][:45]}", callback_data=f"yt|{idx}"
                )
            ])

        await update.message.reply_text(
            f"🎶 *Natijalar topildi:*", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")


# ================= DOWNLOAD MP3 =================
async def yt_download(update, vid_id):
    url = yt_cache.get(vid_id)
    if not url:
        return await update.callback_query.message.reply_text("⚠️ Video topilmadi")

    await update.callback_query.edit_message_text("⏳ *Yuklanmoqda...*", parse_mode="Markdown")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "temp.%(ext)s",
        "quiet": True,
        "cookies": COOKIES
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)

        audio_file = "song.mp3"
        AudioSegment.from_file(video_file).export(audio_file, format="mp3")

        await update.effective_chat.send_audio(
            audio=open(audio_file, "rb"),
            caption=f"🎵 {info['title']}"
        )

    except Exception as e:
        await update.effective_chat.send_message(f"❌ Yuklab bo'lmadi: {e}")

    finally:
        for f in ["temp.webm", "temp.m4a", "song.mp3", video_file]:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass


# ================= INSTAGRAM DOWNLOAD =================
async def insta_dl(update, link):
    await update.message.reply_text("📥 *Instagramdan yuklanmoqda...*", parse_mode="Markdown")

    ydl_opts = {
        "format": "best",
        "outtmpl": "insta.%(ext)s",
        "quiet": True,
        "cookies": COOKIES
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video = ydl.prepare_filename(info)

        await update.message.reply_video(video=open(video, "rb"))

        # Extract audio
        audio_file = "insta.mp3"
        AudioSegment.from_file(video).export(audio_file, format="mp3")

        await update.message.reply_text("🎧 Musiqa aniqlanmoqda...")

        # Shazam
        shazam = Shazam()
        out = await shazam.recognize_song(audio_file)

        if "track" not in out:
            return await update.message.reply_text("❌ Musiqa topilmadi")

        track = out["track"]
        name = track["title"]
        artist = track["subtitle"]
        full = f"{name} - {artist}"

        await update.message.reply_text(
            f"🎵 *{full}*\n\nQuyida variantlar:",
            parse_mode="Markdown"
        )

        await yt_search(update, full)

    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

    finally:
        for f in ["insta.mp4", "insta.webm", "insta.mp3", video]:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass


# ================= MESSAGE HANDLER =================
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "instagram.com" in text:
        return await insta_dl(update, text)
    elif "youtu" in text:
        yt_cache[1] = text
        return await yt_download(update, 1)
    else:
        return await yt_search(update, text)


# ================= CALLBACK =================
async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    if data.startswith("yt|"):
        return await yt_download(update, int(data.split("|")[1]))


# ================= RUN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handler))
    app.add_handler(CallbackQueryHandler(cb))

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
