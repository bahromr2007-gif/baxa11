import sys
import os
import re
import asyncio
import tempfile
import subprocess
import hashlib
import telebot
from telebot import types
from shazamio import Shazam
import yt_dlp

sys.stdout.reconfigure(encoding='utf-8')
telebot.apihelper.delete_webhook = True

BOT_TOKEN = "8575775719:AAFjR9wnpNEDI-3pzWOeQ1NnyaOnrfgpOk4"
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# TEMP papka
if not os.path.exists("temp"):
    os.makedirs("temp")

# User session
user_sessions = {}

# ==================== Helper Functions ====================
def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def clean_filename(text):
    if not text: return "musiqa"
    for char in r'<>:"/\|?*': text = text.replace(char,'')
    text = text.replace(' ','_')
    return text[:40] if text.strip('_') else "musiqa"

def format_duration(seconds):
    if not seconds: return ""
    try:
        seconds = int(float(seconds))
        m, s = divmod(seconds, 60)
        return f" ({m}:{s:02d})"
    except: return ""

def is_instagram_url(url):
    patterns = [r'instagram\.com/(p|reel|tv)/', r'instagram\.com/reels/', r'instagram\.com/tv/']
    return any(re.search(p, url.lower()) for p in patterns)

def is_tiktok_url(url):
    patterns = [r'tiktok\.com/', r'vm\.tiktok\.com/', r'vt\.tiktok\.com/']
    return any(re.search(p, url.lower()) for p in patterns)

# ==================== Shazam Async ====================
async def recognize_song(audio_bytes):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir='temp') as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        shazam = Shazam()
        result = await shazam.recognize(tmp_path)
        try: os.unlink(tmp_path)
        except: pass
        if result and 'track' in result:
            t = result['track']
            return {'found': True,
                    'title': t.get('title','Noma\'lum qo\'shiq'),
                    'artist': t.get('subtitle','Noma\'lum ijrochi'),
                    'link': t.get('share',{}).get('href','')}
    except Exception as e: print("Shazam xato:", e)
    return {'found': False}

# ==================== Audio / Voice Handler ====================
@bot.message_handler(content_types=['audio','voice'])
def handle_audio(message):
    msg = bot.reply_to(message, "🎤 Audio tahlil qilinmoqda...")
    try:
        file_info = bot.get_file(message.audio.file_id if message.audio else message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)

        # Convert voice to mp3
        if message.voice:
            tmp_ogg = tempfile.NamedTemporaryFile(delete=False, suffix='.ogg', dir='temp').name
            with open(tmp_ogg,'wb') as f: f.write(downloaded)
            mp3_path = tmp_ogg.rsplit('.',1)[0]+'_shazam.mp3'
            subprocess.run(['ffmpeg','-i',tmp_ogg,'-ar','16000','-ac','1','-ab','128k','-y',mp3_path],
                           capture_output=True,timeout=30)
            with open(mp3_path,'rb') as f: audio_bytes=f.read()
            os.unlink(tmp_ogg); os.unlink(mp3_path)
        else: audio_bytes = downloaded

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(recognize_song(audio_bytes))
        loop.close()

        if result['found']:
            title = result['title']; artist=result['artist']; link=result.get('link','')
            bot.edit_message_text(f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n⏳ Yuklanmoqda...", 
                                  message.chat.id, msg.message_id)
            # YouTube download
            query = f"{artist} - {title} official audio"
            clean_title = clean_filename(title); clean_artist=clean_filename(artist)
            out_file=f"temp/{clean_artist}-{clean_title}.mp3"
            ydl_opts={'format':'bestaudio/best','outtmpl':out_file,'quiet':True,'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([f"ytsearch1:{query}"])
            if os.path.exists(out_file):
                with open(out_file,'rb') as f: bot.send_audio(message.chat.id,f,title=title,performer=artist)
                os.remove(out_file)
            else: bot.send_message(message.chat.id,f"✅ {title}\n👤 {artist}\n🔗 [Tinglash]({link})",parse_mode='Markdown',disable_web_page_preview=True)
        else:
            bot.edit_message_text("❌ Musiqa topilmadi. Toza va aniq audio yuboring.",message.chat.id,msg.message_id)
    except Exception as e: print("Audio handler xato:", e)

# ==================== Instagram / TikTok Download ====================
ydl_opts_video = {'format':'best','outtmpl':'temp/%(id)s.%(ext)s','quiet':True,'no_warnings':True}

def extract_video(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(url, download=True)
            vid_id = info.get('id','video')
            for f in os.listdir('temp'):
                if vid_id in f: return os.path.join('temp',f)
    except Exception as e: print("Video extract xato:", e)
    return None

@bot.message_handler(func=lambda m: is_instagram_url(m.text) or is_tiktok_url(m.text))
def handle_video(message):
    url=message.text.strip()
    msg=bot.reply_to(message,"⏳ Video yuklanmoqda...")
    video_path=extract_video(url)
    if video_path:
        btn_hash=create_hash(video_path)
        markup=types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash",callback_data=f"video_{btn_hash}"))
        with open(video_path,'rb') as f: bot.send_video(message.chat.id,f,reply_markup=markup)
        with open(f"temp/{btn_hash}.txt",'w') as f: f.write(video_path)
    bot.delete_message(message.chat.id,msg.message_id)

# ==================== Callback - Video Music ====================
@bot.callback_query_handler(func=lambda c:c.data.startswith("video_"))
def handle_video_music(call):
    btn_hash=call.data.split("_")[1]
    bot.answer_callback_query(call.id,"🎵 Musiqa aniqlanmoqda...")
    try:
        with open(f"temp/{btn_hash}.txt") as f: video_path=f.read().strip()
        short_path=video_path.rsplit('.',1)[0]+'_short.mp3'
        subprocess.run(['ffmpeg','-i',video_path,'-t','15','-vn','-acodec','mp3','-y',short_path],
                       capture_output=True,timeout=30)
        with open(short_path,'rb') as f: audio_bytes=f.read()
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        result=loop.run_until_complete(recognize_song(audio_bytes))
        loop.close()
        if result['found']:
            title=result['title']; artist=result['artist']; link=result.get('link','')
            bot.send_message(call.message.chat.id,f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n⏳ Yuklanmoqda...")
            query=f"{artist} - {title} official audio"
            clean_title=clean_filename(title); clean_artist=clean_filename(artist)
            out_file=f"temp/{clean_artist}-{clean_title}.mp3"
            ydl_opts={'format':'bestaudio/best','outtmpl':out_file,'quiet':True,'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([f"ytsearch1:{query}"])
            if os.path.exists(out_file):
                with open(out_file,'rb') as f: bot.send_audio(call.message.chat.id,f,title=title,performer=artist)
                os.remove(out_file)
            else: bot.send_message(call.message.chat.id,f"✅ {title}\n👤 {artist}\n🔗 [Tinglash]({link})",parse_mode='Markdown',disable_web_page_preview=True)
        else: bot.send_message(call.message.chat.id,"❌ Musiqa topilmadi.")
    except Exception as e: print("Video music callback xato:", e)
    finally:
        try: os.remove(video_path); os.remove(short_path); os.remove(f"temp/{btn_hash}.txt")
        except: pass

# ==================== /start ====================
@bot.message_handler(commands=['start'])
def start_msg(message):
    text=("👋 Salom! Men musiqa topuvchi botman 🎵\n"
          "📱 Instagram/TikTok link\n🎤 Qo'shiq nomi yoki audio yuboring\n"
          "👤 Telegram: @Rustamov_v1")
    bot.send_message(message.chat.id,text)

print("✅ BOT ISHGA TUSHDI!")
bot.infinity_polling(skip_pending=True, none_stop=True, interval=0)
