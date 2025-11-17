import os
import asyncio
import yt_dlp
from pydub import AudioSegment
from shazamio import Shazam

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters)

# ================= SOZLAMALAR =================
TELEGRAM_TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"
MY_TG = "@Rustamov_v1"
MY_IG = "https://www.instagram.com/bahrombekh_fx?igsh=Y2J0NnFpNm9icTFp"
# ==============================================
yt_cache = "yt-dlp-cache"  # papka nomi
command = [
    "yt-dlp",
    "--cache-dir", yt_cache,
    url]

# Instagram videolarni vaqtincha saqlash
insta_videos = {}  # {chat_id: video_file_path}
# ================= /start KOMANDASI =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
        f"👤 Telegram: {MY_TG}\n"
        f"📸 Instagram: {MY_IG}\n\n"
        "Menga qo‘shiq nomi yozing yoki Instagram link tashlang 🎧"
    )
    await update.message.reply_text(text)

# ================= YOUTUBE QIDIRUV + PAGINATION =================
async def search_youtube_paginated(update: Update, query: str, page: int = 0):
    search_url = f"ytsearch20:{query} official audio"  # 20 natija
    ydl_opts = {"format": "bestaudio/best", "quiet": True}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            entries = info.get("entries", [])
            if not entries:
                await update.message.reply_text("🔍 Natija topilmadi.")
                return

            # Pagination sozlash
            per_page = 5
            start = page * per_page
            end = start + per_page
            current_entries = entries[start:end]
            keyboard = []
            row = []

            for idx, e in enumerate(current_entries, start=start+1):
                title = e.get("title", "No title")[:50]
                url = e.get("webpage_url")

                yt_cache[idx] = url

                btn = InlineKeyboardButton(f"{idx}. {title}", callback_data=f"yt|{idx}")
                row.append(btn)

            keyboard.append(row)

            # Bu joy ESDA QOLSIN: tanlang degan matn yo‘q!
            await update.message.reply_text(
                "\n".join([f"{i}. {current_entries[i-start-1].get('title','')[:50]}" for i in range(start+1, start+1+len(current_entries))]),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

             keyboard = []
             for idx, e in enumerate(current_entries, start=start+1):
                 title = e.get("title", "No title")[:50]
                 url = e.get("webpage_url")
                 yt_cache[idx] = url
                 keyboard.append([InlineKeyboardButton(f"{idx}. {title}", callback_data=f"yt|{idx}")])

            # Next / Back tugmalar
            nav_buttons = []
            if start > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"page|{page-1}|{query}"))
            if end < len(entries):
                nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"page|{page+1}|{query}"))
            if nav_buttons:
                keyboard.append(nav_buttons)

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🎧 Tanlang:", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ YouTube xatosi: {e}")
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("yt|"):
        vid_id = int(data.split("|")[1])
        await download_and_send_youtube(update, vid_id)
    elif data.startswith("page|"):
        _, page, query_text = data.split("|", 2)
        await search_youtube_paginated(update, query_text, int(page))
        await query.message.delete()  # eski xabarni o‘chirish

# ================= YOUTUBE QIDIRUV =================
async def search_youtube(update: Update, query: str):
    """
    Foydalanuvchi yozgan qo‘shiq nomi yoki link bo‘yicha YouTube qidiradi
    va 5 ta natijani InlineKeyboard orqali chiqaradi
    """
    search_url = f"ytsearch5:{query} official audio"
    ydl_opts = {"format": "bestaudio/best", "quiet": True}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            entries = info.get("entries", [])[:5]

            if not entries:
                await update.message.reply_text("🔍 Natija topilmadi.")
                return


            # Inline tugmalar yaratish
            keyboard = []
            for idx, e in enumerate(entries, start=1):
                vid_id = idx
                title = e.get("title", "No title")[:60]
                url = e.get("webpage_url")
                yt_cache[vid_id] = url
                keyboard.append([InlineKeyboardButton(f"{idx}. {title}", callback_data=f"yt|{vid_id}")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🎧 Quyidagi videolardan birini tanlang:", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ YouTube xatosi: {e}")
# ================= YOUTUBE MP3 YUKLASH =================
async def download_and_send_youtube(update: Update, vid_id: int):
    """
    YouTube video URL ni mp3 ga yuklab, Telegramga yuboradi
    """
    url = yt_cache.get(vid_id)
    if not url:
        await update.callback_query.message.reply_text("⚠️ Video topilmadi.")
        return

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "song_temp.%(ext)s",
        "quiet": True,
    }

    # Foydalanuvchiga yuklanmoqda xabarini ko‘rsatish
    await update.callback_query.edit_message_text("⏳ Yuklanmoqda...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = f"song_temp.{info.get('ext', 'mp3')}"

        # Har doim mp3 ga konvert qilamiz
        audio = AudioSegment.from_file(fname)
        audio.export("song_temp.mp3", format="mp3")

        # Telegramga yuborish
        await update.effective_chat.send_audio(
            audio=open("song_temp.mp3", "rb"),
            caption=f"🎶 {info.get('title', '')}"
        )

    except Exception as e:
        await update.effective_chat.send_message(f"⚠️ Yuklab bo‘lmadi: {e}")

    finally:
        # Fayllarni tozalash
        for f in [fname, "song_temp.mp3"]:
            if os.path.exists(f):
                os.remove(f)


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
    """
    Shazam bilan musiqa aniqlash
    Agar topilmasa None qaytaradi
    """
    shazam = Shazam()
    try:
        out = await shazam.recognize_song(audio_path)
        if not out:
            return None

        track = out.get("track")
        if not track:
            return None

        title = track.get("title", "Noma’lum")
        artist = track.get("subtitle", "Noma’lum")
        return f"{title} - {artist}"

    except Exception as e:
        print(f"⚠️ Shazam xatosi: {e}")
        return None


# ================= INSTAGRAM VIDEO HANDLER =================
async def download_instagram(update: Update, link: str):
    chat_id = update.effective_chat.id
    await update.message.reply_text("📥 Instagram videosi yuklanmoqda...")

    ydl_opts = {"format": "best", "outtmpl": "insta_temp.%(ext)s", "quiet": True}

    try:
        # Video yuklash
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            fname = f"insta_temp.{info.get('ext', 'mp4')}"

        # Telegramga video yuborish
        await update.message.reply_video(video=open(fname, "rb"), caption="📸 Video yuklandi")

        # Video → audio mp3
        audio_path = "insta_audio.mp3"
        AudioSegment.from_file(fname).export(audio_path, format="mp3")

        # Shazam bilan musiqa aniqlash
        await update.message.reply_text("🎧 Musiqa aniqlanmoqda...")
        music_full = await recognize_music_safe(audio_path)


        if not music_full:
            await update.message.reply_text("❌ Musiqa aniqlanmadi.")
        else:
            if " - " in music_full:
                track_name, artist_name = music_full.split(" - ", 1)
            else:
                track_name = music_full
                artist_name = "Noma’lum"

            # Vertikal formatda chiqarish
            await update.message.reply_text(f"🎵 Qo'shiq: {track_name}\n👤 Ijrochi: {artist_name}")

            # Shu musiqa nomi bilan YouTube qidirish
            await search_youtube(update, music_full)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Instagram video yuklab bo‘lmadi: {e}")

    finally:
        # Temp fayllarni o‘chirish
        for f in [fname, audio_path]:
            if os.path.exists(f):
                os.remove(f)
# ================= ASOSIY HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Foydalanuvchidan kelgan matnni tekshiradi
    - Instagram link → download_instagram
    - YouTube link → download_and_send_youtube
    - Boshqa matn → YouTube qidiruv
    """
    text = update.message.text.strip()

    if "instagram.com" in text:
        await download_instagram(update, text)
    elif "youtube.com" in text or "youtu.be" in text:
        # YouTube linkni bevosita yuklash
        # Index 0 ni vaqtincha ishlatamiz
        yt_cache[0] = text
        await download_and_send_youtube(update, 0)
    else:
        await update.message.reply_text("🎧 Musiqa qidirilmoqda...")
        await search_youtube(update, text)


# ================= BOTNI ISHGA TUSHURISH =================
def build_app():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # /start
    app.add_handler(CommandHandler("start", start))
    # Matnli xabarlar
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Callback query (Inline tugmalar)
    app.add_handler(CallbackQueryHandler(callback_handler))

    return app


if __name__ == "__main__":
    app = build_app()
    print("🤖 Bot ishga tushdi...")
    asyncio.run(app.run_polling())
