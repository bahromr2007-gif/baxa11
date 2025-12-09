# bot_modern.py
import os
import asyncio
import uuid
import logging
from pathlib import Path
from typing import Optional

import yt_dlp
from pydub import AudioSegment
from shazamio import Shazam

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"  # set in Railway/ENV
COOKIES_FILE = os.environ.get("COOKIES_FILE", "cookies.txt")  # optional
MY_TG = "@Rustamov_v1"
MY_IG = "https://www.instagram.com/bahrombekh_fx"
TMP_DIR = Path("/tmp/music_bot_tmp")
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ffmpeg path for pydub (Railway usually /usr/bin/ffmpeg in Docker)
AudioSegment.converter = os.environ.get("FFMPEG_PATH", "/usr/bin/ffmpeg")

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# in-memory cache for search results
yt_cache: dict[int, dict] = {}

# ---------------- HELPERS ----------------
def unique_name(prefix: str, ext: str) -> Path:
    return TMP_DIR / f"{prefix}_{uuid.uuid4().hex}.{ext}"

async def run_ydl_extract(search_or_url: str, download: bool = False, ydl_opts: Optional[dict] = None):
    """
    Run yt-dlp blocking operation in a thread.
    Returns the extracted info dict.
    """
    opts = {
        "format": "bestaudio/best" if not ydl_opts else ydl_opts.get("format", "bestaudio/best"),
        "quiet": True,
        "noplaylist": True,
    }
    if COOKIES_FILE and Path(COOKIES_FILE).exists():
        opts["cookies"] = COOKIES_FILE
    if ydl_opts:
        opts.update(ydl_opts)

    def extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(search_or_url, download=download)

    return await asyncio.to_thread(extract)

async def convert_to_mp3(input_path: Path, output_path: Path):
    # pydub is blocking -> run in thread
    def convert():
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="mp3")
    await asyncio.to_thread(convert)

async def cleanup_paths(*paths: Path):
    for p in paths:
        try:
            if p and p.exists():
                p.unlink()
        except Exception as e:
            logger.warning("Cleanup failed for %s: %s", p, e)

# ---------------- BOT HANDLERS ----------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Salom! Zamonaviy musiqani topuvchi botga xush kelibsiz 🎧\n\n"
        f"👤 {MY_TG}\n"
        f"📸 {MY_IG}\n\n"
        "Qo'shiq nomini yozing yoki Instagram/YouTube link yuboring."
    )
    keyboard = [
        [InlineKeyboardButton("🎵 Musiqa qidirish", callback_data="menu_music")],
        [InlineKeyboardButton("📸 Instagram video", callback_data="menu_insta")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Search (for textual queries)
async def search_youtube(update: Update, query: str):
    # informative message
    status_msg = await update.message.reply_text("🔍 Musiqa qidirmoqdaman...")

    search_url = f"ytsearch5:{query}"
    try:
        info = await run_ydl_extract(search_url, download=False)
        entries = info.get("entries", [])[:5]
        if not entries:
            await status_msg.edit_text("❌ Natija topilmadi.")
            return

        # build keyboard with thumbnails + durations
        keyboard = []
        for idx, e in enumerate(entries, start=1):
            title = e.get("title", "No title")
            duration = e.get("duration")
            dur_str = f" [{duration//60}:{duration%60:02d}]" if duration else ""
            yt_cache[idx] = {
                "url": e.get("webpage_url"),
                "title": title
            }
            keyboard.append([InlineKeyboardButton(f"{idx}. {title[:60]}{dur_str}", callback_data=f"yt|{idx}")])

        await status_msg.edit_text(
            "🎧 Topildi — quyidagilardan birini tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.exception("Search failed")
        await status_msg.edit_text(f"❌ Qidiruv xatosi: {e}")

# Download + send audio (from URL in cache)
async def download_and_send_youtube_callback(query_obj, chat, vid_id: int):
    # separated to allow reuse
    data = yt_cache.get(vid_id)
    if not data:
        await chat.send_message("⚠️ Video topilmadi.")
        return

    url = data["url"]
    # use unique filenames
    temp_ydl_out = unique_name("song_raw", "%(ext)s")  # yt-dlp will replace %(ext)s
    mp3_out = unique_name("song", "mp3")
    # prepare options: outtmpl must be str path with %(ext)s
    ydl_opts = {"outtmpl": str(temp_ydl_out)}
    try:
        await chat.edit_message_text("⏳ Yuklanmoqda — biroz kuting...")
        info = await run_ydl_extract(url, download=True, ydl_opts=ydl_opts)
        # yt-dlp returns filename via prepare_filename, but since we used custom template we can infer ext
        # safer: inspect info dict
        ext = info.get("ext") or info.get("requested_formats", [{}])[-1].get("ext", "m4a")
        downloaded = TMP_DIR / f"{temp_ydl_out.name.replace('%(ext)s', ext)}"
        # if file not exists maybe ydl returned path differently; try ydl.prepare_filename equivalent via info
        if not downloaded.exists():
            # try common alternatives
            candidates = list(TMP_DIR.glob(f"song_raw_*.*"))
            downloaded = candidates[0] if candidates else None

        if not downloaded or not downloaded.exists():
            raise FileNotFoundError("Yuklangan fayl topilmadi.")

        await chat.edit_message_text("🔁 Konvertatsiya qilinmoqda...")
        await convert_to_mp3(downloaded, mp3_out)

        await chat.edit_message_text("📤 Yuborilmoqda...")
        with mp3_out.open("rb") as f:
            await chat.send_audio(audio=InputFile(f), caption=f"🎶 {info.get('title', 'Nomaʼlum')}")
        await chat.edit_message_text("✅ Yuborildi!")

    except Exception as e:
        logger.exception("Download/send failed")
        try:
            await chat.edit_message_text(f"❌ Yuklab bo‘lmadi: {e}")
        except:
            await chat.send_message(f"❌ Yuklab bo‘lmadi: {e}")
    finally:
        # cleanup
        try:
            # remove any song_raw_* and the mp3
            for p in TMP_DIR.glob("song_raw_*.*"):
                try: p.unlink() 
                except: pass
            if mp3_out.exists(): mp3_out.unlink()
        except Exception as e:
            logger.warning("Cleanup error: %s", e)

# Callback handler for inline buttons
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("yt|"):
        vid_id = int(data.split("|", 1)[1])
        # edit the message to show progress and call download
        await download_and_send_youtube_callback(query, query, vid_id)  # query has edit_message_text and send methods
    elif data == "menu_music":
        await query.message.reply_text("🎧 Qo'shiq nomini yozing:")
    elif data == "menu_insta":
        await query.message.reply_text("📸 Instagram video linkini yuboring:")

# Instagram link -> download -> extract audio -> Shazam -> show result and search youtube
async def handle_instagram_flow(update: Update, link: str):
    status = await update.message.reply_text("📥 Instagram videosi yuklanmoqda...")
    temp_video = unique_name("insta", "mp4")
    temp_audio = unique_name("insta_audio", "mp3")
    ydl_opts = {"outtmpl": str(temp_video)}
    try:
        info = await run_ydl_extract(link, download=True, ydl_opts=ydl_opts)
        # find downloaded file
        downloaded = list(TMP_DIR.glob("insta_*.*"))
        downloaded_file = downloaded[0] if downloaded else None
        if not downloaded_file:
            raise FileNotFoundError("Video yuklanmadi.")

        await status.edit_text("🔁 Audio olinmoqda...")
        await convert_to_mp3(downloaded_file, temp_audio)

        await status.edit_text("🎧 Musiqa aniqlanmoqda...")
        shazam = Shazam()
        shazam_result = await shazam.recognize_song(str(temp_audio))
        track = None
        if shazam_result and "track" in shazam_result:
            t = shazam_result["track"]
            track = f"{t.get('title','Nomaʼlum')} - {t.get('subtitle','Nomaʼlum')}"

        if track:
            await status.edit_text(f"✅ Topildi: {track}\n🔍 YouTube'da qidirilyapti...")
            # reuse search flow
            await search_youtube(update, track)
        else:
            await status.edit_text("❌ Musiqa aniqlanmadi.")
    except Exception as e:
        logger.exception("Instagram flow failed")
        await status.edit_text(f"⚠️ Xato: {e}")
    finally:
        # cleanup
        await cleanup_paths(*TMP_DIR.glob("insta_*.*"))

# Main message handler
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Matn yuboring yoki link qo'ying.")
        return

    # direct link handlers
    if "instagram.com" in text:
        await handle_instagram_flow(update, text)
        return

    if "youtube.com" in text or "youtu.be" in text:
        # direct url: download immediate
        # store in cache 0
        yt_cache[0] = {"url": text, "title": text}
        # create a fake CallbackQuery-like object to reuse download function: use update.message as 'chat' with edit_message_text fallback
        # For simplicity we call download_and_send_youtube_callback with update.message as 'chat' but that object doesn't have edit_message_text.
        # So we create simple wrappers: send status messages via reply and then operate.
        await update.message.reply_text("⏳ YouTube link qabul qilindi — yuklanmoqda...")
        # Create a wrapper object that has edit_message_text and send_audio
        class MsgWrapper:
            def __init__(self, message):
                self.message = message
            async def edit_message_text(self, txt, **k):
                try:
                    await self.message.edit_text(txt)
                except:
                    await self.message.reply_text(txt)
            async def send_audio(self, audio, caption=None):
                await self.message.reply_audio(audio=audio, caption=caption)
            async def send_message(self, txt):
                await self.message.reply_text(txt)

        wrapper = MsgWrapper(update.message)
        await download_and_send_youtube_callback(wrapper, wrapper, 0)
        return

    # otherwise treat as search query
    await search_youtube(update, text)

# ---------------- START BOT ----------------
def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN muhit o'zgaruvchisida yo'q! Set it and restart.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("🤖 Zamonaviy bot ishga tushmoqda...")
    app.run_polling()

if __name__ == "__main__":
    main()
