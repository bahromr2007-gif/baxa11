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
    ContextTypes,
    filters
)

# ================= SOZLAMALAR =================
TELEGRAM_TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"  # ⚠️ Ochiq tashlamang!
MY_TG = "@Rustamov_v1"
MY_IG = "https://www.instagram.com/bahrombekh_fx?igsh=Y2J0NnFpNm9icTFp"
COOKIES_FILE = "cookies.txt"

# Railway uchun ffmpeg yo'li
AudioSegment.converter = "/usr/bin/ffmpeg"

yt_cache = {}

# ================= /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        f"👤 Telegram: {MY_TG}\n"
        f"📸 Instagram: {MY_IG}\n\n"
        "Menga qo'shiq nomi yozing yoki Instagram link tashlang 🎧"
    )
    keyboard = [
        [InlineKeyboardButton("🎵 Musiqa qidirish", callback_data="menu_music")],
        [InlineKeyboardButton("📸 Instagram video", callback_data="menu_insta")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= YOUTUBE QIDIRUV =================
async def search_youtube(update: Update, query: str):
    await update.message.reply_text("🔍 Musiqa qidirmoqdaman...")

    search_url = f"ytsearch5:{query}"
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "cookies": COOKIES_FILE
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            entries = info.get("entries", [])[:5]

        if not entries:
            await update.message.reply_text("❌ Hech narsa topilmadi.")
            return

        keyboard = []
        for idx, e in enumerate(entries, start=1):
            title = e.get("title", "No title")[:60]
            url = e.get("webpage_url")
            yt_cache[idx] = url
            keyboard.append([InlineKeyboardButton(f"{idx}. {title}", callback_data=f"yt|{idx}")])

        await update.message.reply_text(
            "🎧 Quyidagi musiqalardan birini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# ================= YOUTUBE MP3 YUKLASH =================
async def download_and_send_youtube(update: Update, vid_id: int):
    url = yt_cache.get(vid_id)
    if not url:
        await update.callback_query.message.reply_text("⚠️ Video topilmadi.")
        return

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "song.%(ext)s",
        "quiet": True,
        "cookies": COOKIES_FILE
    }

    try:
        await update.callback_query.edit_message_text("⏳ Yuklanmoqda...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        mp3_file = "song.mp3"
        AudioSegment.from_file(filename).export(mp3_file, format="mp3")

        await update.effective_chat.send_audio(
            audio=open(mp3_file, "rb"),
            caption=f"🎶 {info.get('title', 'Nomaʼlum')}"
        )

    except Exception as e:
        await update.effective_chat.send_message(f"⚠️ Xato: {e}")

    finally:
        for file in [filename, mp3_file]:
            try:
                if os.path.exists(file): os.remove(file)
            except: pass

# ================= CALLBACK =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    await update.callback_query.answer()

    if data.startswith("yt|"):
        await download_and_send_youtube(update, int(data.split("|")[1]))
    elif data == "menu_music":
        await update.callback_query.message.reply_text("🎧 Qo'shiq nomini yozing:")
    elif data == "menu_insta":
        await update.callback_query.message.reply_text("📸 Instagram video linkini yuboring:")

# ================= MUSIQA ANIQLASH =================
async def recognize_music_safe(audio_path: str):
    try:
        out = await Shazam().recognize_song(audio_path)
        if "track" not in out:
            return None

        track = out["track"]
        title = track.get("title", "Nomaʼlum")
        artist = track.get("subtitle", "Nomaʼlum")
        return f"{title} - {artist}"

    except:
        return None

# ================= INSTAGRAM VIDEO =================
async def download_instagram(update: Update, link: str):
    await update.message.reply_text("📥 Instagram videosi yuklanmoqda...")

    ydl_opts = {
        "format": "best",
        "outtmpl": "insta.%(ext)s",
        "quiet": True,
        "cookies": COOKIES_FILE
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video = ydl.prepare_filename(info)

        await update.message.reply_video(open(video, "rb"), caption="📸 Video yuklandi")

        # musiqa ajratish
        audio = "insta.mp3"
        AudioSegment.from_file(video).export(audio, format="mp3")

        await update.message.reply_text("🎧 Musiqa aniqlanmoqda...")
        found = await recognize_music_safe(audio)

        if found:
            await update.message.reply_text(f"🎵 Topildi: {found}")
            await search_youtube(update, found)
        else:
            await update.message.reply_text("❌ Musiqa aniqlanmadi.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Xato: {e}")

    finally:
        for f in [video, audio]:
            try:
                if os.path.exists(f): os.remove(f)
            except: pass

# ================= XABARLAR HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "instagram.com" in text:
        await download_instagram(update, text)
    elif "youtube.com" in text or "youtu.be" in text:
        yt_cache[0] = text
        await download_and_send_youtube(update, 0)
    else:
        await search_youtube(update, text)

# ================= BOT ISHGA TUSHURISH =================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
