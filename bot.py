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
from telebot import types
from shazamio import Shazam
import yt_dlp
sys.stdout.reconfigure(encoding="utf-8")
telebot.apihelper.delete_webhook = True
# ========================================
# BOT TOKEN
BOT_TOKEN = "8575775719:AAFjR9wnpNEDI-3pzWOeQ1NnyaOnrfgpOk4"
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
# ========================================

# /start komandasi
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
        "📸 Instagram: https://www.instagram.com/bahrombekh_fx?igsh=Y2J0NnFpNm9icTFp "
    )
    bot.send_message(message.chat.id, text)

# TEMP papka yaratish
if not os.path.exists("temp"):
    os.makedirs("temp")

# User session data
user_sessions = {}

# ================= YUKLASH SETTINGLARI =================
ydl_opts_instagram = {
    'format': 'best[height<=720][ext=mp4]',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'extractor_args': {'instagram': {'tab': ['clips']}},
    'outtmpl': 'temp/%(id)s.%(ext)s',
    'socket_timeout': 60,
    'retries': 5,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    },
}

ydl_opts_tiktok = {
    'format': 'best[height<=720][ext=mp4]',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'outtmpl': 'temp/%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    },
}

ydl_opts_audio_named = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(title)s.%(ext)s',
    'quiet': True,
    'socket_timeout': 30,
    'retries': 3,
    'restrictfilenames': True,
    'windowsfilenames': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# ================= YORDAMCHI FUNKSIYALAR =================
def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def clean_filename(text):
    """Fayl nomini tozalash"""
    if not text:
        return "musiqa"
    
    for char in r'<>:"/\|?*':
        text = text.replace(char, '')
    
    text = text.replace(' ', '_')
    
    if len(text) > 40:
        text = text[:40]
    
    if not text.strip('_'):
        text = "musiqa"
    
    return text

def format_duration(seconds):
    """Vaqtni MM:SS formatida qaytarish"""
    if not seconds:
        return ""
    
    try:
        seconds = int(float(seconds))
        minutes = seconds // 60
        seconds = seconds % 60
        return f" ({minutes}:{seconds:02d})"
    except:
        return ""

def is_instagram_url(url):
    """Instagram linkini tekshirish"""
    patterns = [
        r'https?://(www\.)?instagram\.com/(p|reel|tv|stories)/',
        r'https?://(www\.)?instagram\.com/reels/',
    ]
    
    url = url.lower().strip()
    for pattern in patterns:
        if re.search(pattern, url):
            return True
    return False

def is_tiktok_url(url):
    """TikTok linkini tekshirish"""
    patterns = [
        r'https?://(www\.)?tiktok\.com/',
        r'https?://(vm\.)?tiktok\.com/',
        r'https?://vt\.tiktok\.com/',
    ]
    
    url = url.lower().strip()
    for pattern in patterns:
        if re.search(pattern, url):
            return True
    return False

# 🔧 YANGILANGAN: ISHLAYDIGAN INSTAGRAM YUKLOVCHI
def extract_instagram_video_simple(url):
    """Instagram videoni ishonchli usulda yuklash (cookies siz)"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts_instagram) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, "Ma'lumot topilmadi"
            
            video_id = info.get('id', 'instagram_video')
            title = info.get('title', 'Instagram Video')[:60]
            
            # To'g'ri faylni topish
            for file in os.listdir("temp"):
                if file.startswith(video_id[:15]) and file.endswith(('.mp4', '.webm')):
                    return os.path.join("temp", file), title
            
            # Oxirgi yuklangan faylni qaytarish (agar ID mos kelmasa)
            video_files = [f for f in os.listdir("temp") if f.endswith(('.mp4', '.webm'))]
            if video_files:
                latest_file = max(video_files, key=lambda f: os.path.getctime(os.path.join("temp", f)))
                return os.path.join("temp", latest_file), title
                
        return None, title
        
    except Exception as e:
        print(f"Instagram xatosi: {e}")
        return None, f"Xatolik: {str(e)[:50]}"

# ================= SHAZAM ANIQLASH =================
async def recognize_song(audio_bytes):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir='temp') as tmp:
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
            }  
    except Exception as e:  
        print(f"Shazam xatosi: {e}")  
    return {'found': False}

# ================= AUDIO FAYL YUBORILGANDA =================
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    try:
        msg = bot.reply_to(message, "⏳")

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
              
            bot.edit_message_text(
                f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}", 
                message.chat.id, 
                msg.message_id
            )  
              
            query = f"{artist} {title} audio"
            try:
                clean_title = clean_filename(title)
                clean_artist = clean_filename(artist)
                output_file = f"temp/{clean_artist} - {clean_title}.mp3"
                
                opts = ydl_opts_audio_named.copy()
                opts['outtmpl'] = f"temp/{clean_artist} - {clean_title}.%(ext)s"
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                
                if os.path.exists(output_file):
                    with open(output_file, 'rb') as f:
                        bot.send_audio(
                            message.chat.id, 
                            f,
                            title=title[:64],
                            performer=artist[:64],
                            caption=f"🎵 {title}\n👤 {artist}"
                        )
                    
                    os.remove(output_file)
                    bot.delete_message(message.chat.id, msg.message_id)
                else:
                    for file in os.listdir("temp"):
                        if file.endswith('.mp3') and (clean_title[:20] in file or clean_artist[:20] in file):
                            with open(os.path.join("temp", file), 'rb') as f:
                                bot.send_audio(
                                    message.chat.id, 
                                    f,
                                    title=title[:64],
                                    performer=artist[:64],
                                    caption=f"🎵 {title}\n👤 {artist}"
                                )
                            os.remove(os.path.join("temp", file))
                            bot.delete_message(message.chat.id, msg.message_id)
                            break
                    else:
                        bot.edit_message_text(
                            f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n⚠️ Yuklab bo'lmadi (qo'shiq qo'riqlangan)",
                            message.chat.id,
                            msg.message_id
                        )
                    
            except Exception as e:
                bot.edit_message_text(
                    f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Yuklashda xatolik",
                    message.chat.id,
                    msg.message_id
                )
                print(f"Audio yuklash xatosi: {e}")
        else:  
            bot.edit_message_text("❌ Musiqa topilmadi", message.chat.id, msg.message_id)  
              
    except Exception as e:  
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")

# ================= INSTAGRAM HANDLER =================
@bot.message_handler(func=lambda m: is_instagram_url(m.text))
def handle_instagram_reel(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "⏳")

        video_path, video_title = extract_instagram_video_simple(url)
        
        if video_path and os.path.exists(video_path):
            btn_hash = create_hash(video_path)
            markup = types.InlineKeyboardMarkup()  
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"insta_{btn_hash}"))  

            with open(video_path, 'rb') as f:  
                bot.send_video(message.chat.id, f, reply_markup=markup, caption="✅ Video yuklandi!")  

            with open(f"temp/{btn_hash}.txt", "w") as f:  
                f.write(video_path)  

            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(
                f"❌ Instagram video yuklanmadi\n\n"
                f"👉 Sabab: {video_title}\n\n"
                "✅ Video ommaviy bo'lishi kerak.\n"
                "✅ Linkda 'reel', 'p', yoki 'tv' bo'lishi kerak.",
                message.chat.id,
                msg.message_id
            )

    except Exception as e:  
        bot.reply_to(message, f"❌ Xatolik: {e}")

# ================= TIKTOK HANDLER =================
@bot.message_handler(func=lambda m: is_tiktok_url(m.text))
def handle_tiktok(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "⏳")

        with yt_dlp.YoutubeDL(ydl_opts_tiktok) as ydl:  
            info = ydl.extract_info(url, download=True)
            
            video_files = []
            for file in os.listdir("temp"):
                if file.endswith(('.mp4', '.webm')):
                    video_files.append(os.path.join("temp", file))
            
            if video_files:
                video_path = max(video_files, key=os.path.getctime)
                
                btn_hash = create_hash(video_path)
                markup = types.InlineKeyboardMarkup()  
                markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"tiktok_{btn_hash}"))  

                with open(video_path, 'rb') as f:  
                    bot.send_video(message.chat.id, f, reply_markup=markup, caption="✅ TikTok video yuklandi!")  

                with open(f"temp/{btn_hash}.txt", "w") as f:  
                    f.write(video_path)  

                bot.delete_message(message.chat.id, msg.message_id)
            else:
                bot.edit_message_text("❌ TikTok video yuklanmadi. Iltimos, to'g'ri link yuboring.", message.chat.id, msg.message_id)

    except Exception as e:  
        bot.reply_to(message, f"❌ TikTok xatosi: {e}")

# ================= VIDEO MUSIQANI ANIQLASH =================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("insta_", "tiktok_")))
def handle_media_music(call):
    try:
        prefix, btn_hash = call.data.split("_", 1)
        bot.answer_callback_query(call.id, "🎵 Musiqa izlanmoqda...")

        with open(f"temp/{btn_hash}.txt", "r") as f:  
            video_path = f.read().strip()  

        if not os.path.exists(video_path):
            bot.send_message(call.message.chat.id, "❌ Video fayl topilmadi (vaqt tugadi)")
            return

        short_audio_path = video_path.rsplit('.', 1)[0] + '_short.mp3'
        
        try:
            # Faqat audio ajratish (ffmpeg bo'lmagan holatda ham ishlaydi)
            opts = {
                'format': 'bestaudio[ext=mp3]/bestaudio',
                'extractaudio': True,
                'audioformat': 'mp3',
                'outtmpl': short_audio_path.replace('.mp3', ''),
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
        except:
            # Agar ishlamasa — oddiy audio yuklab olish
            try:
                opts = {
                    'format': 'bestaudio[ext=mp3]/bestaudio',
                    'extractaudio': True,
                    'audioformat': 'mp3',
                    'outtmpl': short_audio_path.replace('.mp3', ''),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([video_path])
            except Exception as e:
                print(f"Audio yuklashda xatolik: {e}")
                bot.send_message(call.message.chat.id, "❌ Audio ajratishda xatolik")
                return

        if not os.path.exists(short_audio_path):
            short_audio_path += ".mp3"
        if not os.path.exists(short_audio_path):
            bot.send_message(call.message.chat.id, "❌ Audio fayl yaratilmadi")
            return

        with open(short_audio_path, 'rb') as f:  
            short_audio_data = f.read()  

        loop = asyncio.new_event_loop()  
        asyncio.set_event_loop(loop)  
        result = loop.run_until_complete(recognize_song(short_audio_data))  
        loop.close()  

        if result['found']:  
            title = result['title']  
            artist = result['artist']  
              
            bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}")  
              
            query = f"{artist} {title} audio"
            try:
                clean_title = clean_filename(title)
                clean_artist = clean_filename(artist)
                output_file = f"temp/{clean_artist} - {clean_title}.mp3"
                
                opts = ydl_opts_audio_named.copy()
                opts['outtmpl'] = f"temp/{clean_artist} - {clean_title}.%(ext)s"
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([f"ytsearch1:{query}"])
                
                if os.path.exists(output_file):
                    with open(output_file, 'rb') as f:
                        bot.send_audio(
                            call.message.chat.id, 
                            f,
                            title=title[:64],
                            performer=artist[:64],
                            caption=f"🎵 {title}\n👤 {artist}"
                        )
                    
                    os.remove(output_file)
                else:
                    for file in os.listdir("temp"):
                        if file.endswith('.mp3') and (clean_title[:20] in file or clean_artist[:20] in file):
                            with open(os.path.join("temp", file), 'rb') as f:
                                bot.send_audio(
                                    call.message.chat.id, 
                                    f,
                                    title=title[:64],
                                    performer=artist[:64],
                                    caption=f"🎵 {title}\n👤 {artist}"
                                )
                            os.remove(os.path.join("temp", file))
                            break
                    else:
                        bot.send_message(call.message.chat.id, f"⚠️ Yuklab bo'lmadi (qo'riqlangan qo'shiq)")
                    
            except Exception as e:
                bot.send_message(call.message.chat.id, f"❌ Yuklashda xatolik")
        else:  
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi")  

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Xatolik: {e}")
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

# ================= QIDIRUV HANDLER - 10 ta natija =================
@bot.message_handler(func=lambda m: True)
def search_music(message):
    query = message.text.strip()
    
    if is_instagram_url(query) or is_tiktok_url(query):  
        return  
    
    msg = bot.reply_to(message, f"🔍 '{query}' qidirilmoqda...")  
    
    try:  
        # 🔧 YANGILANISH: " audio" qo'shildi → faqat musiqa chiqadi
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 20,
            'playlistend': 10,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  
            info = ydl.extract_info(f"ytsearch10:{query} audio", download=False)  # 🔑 " audio" qo'shildi
            songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10][:10]  # faqat >10s

        if not songs:
            bot.edit_message_text("❌ Hech qanday natija topilmadi", message.chat.id, msg.message_id)
            return

        # User session saqlash
        user_id = message.chat.id
        user_sessions[user_id] = {
            'query': query,
            'songs': songs,
            'page': 1
        }
        
        # 1-10 qo'shiqlarni ko'rsatish
        show_results_page(message.chat.id, songs, 1, query)
        
        bot.delete_message(message.chat.id, msg.message_id)  

    except Exception as e:  
        bot.edit_message_text(f"❌ Xatolik: {e}", message.chat.id, msg.message_id)
        print("Qidiruv xatosi:", repr(e))
        
def show_results_page(chat_id, songs, page, query):
    """Natijalarni sahifalab ko'rsatish"""
    total_songs = len(songs)
    start_idx = (page - 1) * 10
    end_idx = min(start_idx + 10, total_songs)
    
    # Matn ro'yxati  
    text_list = [f"🔍 '{query}' uchun natijalar ({start_idx+1}-{end_idx}):\n"]  
    
    # Inline tugmalar uchun
    markup = types.InlineKeyboardMarkup(row_width=5)
    
    # Birinchi qator: 1-5 raqamlar
    first_row = []
    # Ikkinchi qator: 6-10 raqamlar
    second_row = []
    
    for i in range(start_idx, end_idx):
        song = songs[i]
        if not song:
            continue
            
        idx = i + 1
        title = song.get("title", "Noma'lum")[:50]
        duration = song.get("duration", 0)  
        time_str = format_duration(duration)
        
        text_list.append(f"{idx}. {title}{time_str}")  
        
        # Inline tugma
        url = song.get("url", song.get("webpage_url", ""))
        if url:
            h = create_hash(url)
            with open(f"temp/{h}.txt", "w") as f:  
                f.write(f"{url}|{title}")  
            
            if idx <= 5:
                first_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
            else:
                second_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
    
    # Tugmalarni qo'shish
    if first_row:
        markup.add(*first_row)
    if second_row:
        markup.add(*second_row)
    
    # NAVIGATSIYA tugmalari
    nav_buttons = []
    
    # FAKAT bir sahifa bo'lsa ham, ORQAGA va OLDINGA tugmalarini qo'shamiz
    nav_buttons.append(types.InlineKeyboardButton("⬅️", callback_data="nav_back"))
    nav_buttons.append(types.InlineKeyboardButton("❌", callback_data="nav_home"))
    nav_buttons.append(types.InlineKeyboardButton("➡️", callback_data="nav_next"))
    
    markup.add(*nav_buttons)
    
    bot.send_message(chat_id, "\n".join(text_list), reply_markup=markup)

# ================= AUDIO YUKLASH =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("song_"))
def download_audio(call):
    h = call.data.split("_", 1)[1]
    
    with open(f"temp/{h}.txt") as f:  
        data = f.read().strip()  
    
    if "|" in data:  
        url, title = data.split("|", 1)  
    else:  
        url = data  
        title = "Musiqa"  
    
    bot.answer_callback_query(call.id, "🎵 Tez yuklanmoqda...")  
    
    try:  
        clean_title = clean_filename(title)
        output_file = f"temp/{clean_title}.mp3"
        
        opts = ydl_opts_audio_named.copy()
        opts['outtmpl'] = f"temp/{clean_title}.%(ext)s"
        
        with yt_dlp.YoutubeDL(opts) as ydl:  
            info = ydl.extract_info(url, download=True)
            actual_title = info.get('title', title)
        
        if os.path.exists(output_file):
            with open(output_file, 'rb') as f:  
                bot.send_audio(call.message.chat.id, f, title=actual_title[:64])  

            os.remove(output_file)  
        else:
            for file in os.listdir("temp"):
                if file.endswith('.mp3') and clean_title[:20] in file:
                    with open(os.path.join("temp", file), 'rb') as f:  
                        bot.send_audio(call.message.chat.id, f, title=actual_title[:64])
                    os.remove(os.path.join("temp", file))
                    break
        
        if os.path.exists(f"temp/{h}.txt"):
            os.remove(f"temp/{h}.txt")

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Yuklashda xatolik: {e}")
        print(f"Yuklash xatosi: {e}")

# ================= NAVIGATSIYA HANDLER =================
@bot.callback_query_handler(func=lambda c: c.data in ["nav_back", "nav_home", "nav_next"])
def handle_navigation(call):
    user_id = call.message.chat.id
    
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "❌ Session topilmadi")
        return
    
    session = user_sessions[user_id]
    query = session['query']
    songs = session['songs']
    current_page = session['page']
    
    # Oldingi xabarni o'chirish
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if call.data == "nav_back":
        # Orqaga qaytish - yangi qidiruv
        msg = bot.send_message(user_id, f"🔍 '{query}' qayta qidirilmoqda...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'playlistend': 10}) as ydl:  
                info = ydl.extract_info(f"ytsearch10:{query} audio", download=False)  # 🔑 " audio"
                songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10][:10]
            
            if songs:
                user_sessions[user_id]['songs'] = songs
                user_sessions[user_id]['page'] = 1
                show_results_page(user_id, songs, 1, query)
            else:
                bot.send_message(user_id, "❌ Hech qanday natija topilmadi")
            
            bot.delete_message(user_id, msg.message_id)
            
        except Exception as e:
            bot.send_message(user_id, "❌ Qidiruvda xatolik")
    
    elif call.data == "nav_home":
        # Bosh sahifa - /start
        text = (
            "👋 Salom! Men musiqa topuvchi botman 🎵\n\n"
            "Menga quyidagilarni yuborishingiz mumkin:\n"
            "1. 📱 Instagram Reel linki\n"
            "2. 📱 TikTok video linki\n"
            "3. 🎤 Qo'shiq nomi yoki ijrochi ismi\n"
            "4. 🎵 Audio fayl (musiqani aniqlash uchun)\n\n"
            "Yana qo'shiq nomi yoki ijrochi ismini yuboring!"
        )
        bot.send_message(user_id, text)
    
    elif call.data == "nav_next":
        # Oldinga - yangi 10 ta natija
        # Agar hozirgi sahifa 1 bo'lsa, keyingi sahifa (11-20)
        if current_page == 1:
            # Yangi qidiruv: 11-20 natijalar
            msg = bot.send_message(user_id, f"🔍 '{query}' - keyingi natijalar qidirilmoqda...")
            
            try:
                # Keyingi 10 ta natija uchun
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'playlistend': 20}) as ydl:  
                    info = ydl.extract_info(f"ytsearch20:{query} audio", download=False)  # 🔑 " audio"
                    songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10]
                
                if songs and len(songs) > 10:
                    # Faqat 11-20 natijalar
                    user_sessions[user_id]['songs'] = songs
                    user_sessions[user_id]['page'] = 2
                    
                    # 11-20 natijalarni ko'rsatish
                    show_results_page_next(user_id, songs, 11, 20, query)
                else:
                    bot.send_message(user_id, "❌ Ko'proq natija topilmadi")
                
                bot.delete_message(user_id, msg.message_id)
                
            except Exception as e:
                bot.send_message(user_id, "❌ Qidiruvda xatolik")

def show_results_page_next(chat_id, songs, start_num, end_num, query):
    """Keyingi natijalarni ko'rsatish (11-20)"""
    start_idx = start_num - 1
    end_idx = min(end_num, len(songs))
    
    text_list = [f"🔍 '{query}' uchun natijalar ({start_num}-{end_num}):\n"]  
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    first_row = []
    second_row = []
    
    for i in range(start_idx, end_idx):
        song = songs[i]
        if not song:
            continue
            
        idx = i + 1
        title = song.get("title", "Noma'lum")[:50]
        duration = song.get("duration", 0)  
        time_str = format_duration(duration)
        
        text_list.append(f"{idx}. {title}{time_str}")  
        
        url = song.get("url", song.get("webpage_url", ""))
        if url:
            h = create_hash(url)
            with open(f"temp/{h}.txt", "w") as f:  
                f.write(f"{url}|{title}")  
            
            if idx <= 15:
                first_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
            else:
                second_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
    
    if first_row:
        markup.add(*first_row)
    if second_row:
        markup.add(*second_row)
    
    # Navigatsiya tugmalari
    nav_buttons = []
    nav_buttons.append(types.InlineKeyboardButton("⬅️", callback_data="nav_prev_page"))
    nav_buttons.append(types.InlineKeyboardButton("❌", callback_data="nav_home"))
    nav_buttons.append(types.InlineKeyboardButton("➡️", callback_data="nav_more"))
    
    markup.add(*nav_buttons)
    
    bot.send_message(chat_id, "\n".join(text_list), reply_markup=markup)

# ================= QO'SHIMCHA NAVIGATSIYA =================
@bot.callback_query_handler(func=lambda c: c.data in ["nav_prev_page", "nav_more"])
def handle_more_navigation(call):
    user_id = call.message.chat.id
    
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "❌ Session topilmadi")
        return
    
    session = user_sessions[user_id]
    query = session['query']
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if call.data == "nav_prev_page":
        # Avvalgi sahifaga qaytish (1-10)
        msg = bot.send_message(user_id, f"🔍 '{query}' qayta qidirilmoqda...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'playlistend': 10}) as ydl:  
                info = ydl.extract_info(f"ytsearch10:{query} audio", download=False)  # 🔑 " audio"
                songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10][:10]
            
            if songs:
                user_sessions[user_id]['songs'] = songs
                user_sessions[user_id]['page'] = 1
                show_results_page(user_id, songs, 1, query)
            else:
                bot.send_message(user_id, "❌ Hech qanday natija topilmadi")
            
            bot.delete_message(user_id, msg.message_id)
            
        except Exception as e:
            bot.send_message(user_id, "❌ Qidiruvda xatolik")
    
    elif call.data == "nav_more":
        # Yana keyingi natijalar (21-30)
        msg = bot.send_message(user_id, f"🔍 '{query}' - yana natijalar qidirilmoqda...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'playlistend': 30}) as ydl:  
                info = ydl.extract_info(f"ytsearch30:{query} audio", download=False)  # 🔑 " audio"
                songs = [e for e in info.get('entries', []) if e.get('duration', 0) > 10]
            
            if songs and len(songs) > 20:
                user_sessions[user_id]['songs'] = songs
                user_sessions[user_id]['page'] = 3
                
                # 21-30 natijalarni ko'rsatish
                text_list = [f"🔍 '{query}' uchun natijalar (21-30):\n"]  
                markup = types.InlineKeyboardMarkup(row_width=5)
                
                for i in range(20, min(30, len(songs))):
                    song = songs[i]
                    if not song:
                        continue
                        
                    idx = i + 1
                    title = song.get("title", "Noma'lum")[:50]
                    duration = song.get("duration", 0)  
                    time_str = format_duration(duration)
                    
                    text_list.append(f"{idx}. {title}{time_str}")  
                    
                    url = song.get("url", song.get("webpage_url", ""))
                    if url:
                        h = create_hash(url)
                        with open(f"temp/{h}.txt", "w") as f:  
                            f.write(f"{url}|{title}")  
                        
                        if idx <= 25:
                            markup.add(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
                        else:
                            # 26-30 alohida qator
                            pass
                
                # Navigatsiya
                nav_buttons = [
                    types.InlineKeyboardButton("⬅️ Avvalgi", callback_data="nav_prev_to_11_20"),
                    types.InlineKeyboardButton("🏠 Bosh", callback_data="nav_home")
                ]
                markup.add(*nav_buttons)
                
                bot.send_message(user_id, "\n".join(text_list), reply_markup=markup)
            else:
                bot.send_message(user_id, "❌ Ko'proq natija topilmadi")
            
            bot.delete_message(user_id, msg.message_id)
            
        except Exception as e:
            bot.send_message(user_id, "❌ Qidiruvda xatolik")

@bot.callback_query_handler(func=lambda c: c.data == "nav_prev_to_11_20")
def handle_prev_to_11_20(call):
    user_id = call.message.chat.id
    
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "❌ Session topilmadi")
        return
    
    session = user_sessions[user_id]
    query = session['query']
    songs = session['songs']
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if songs and len(songs) > 10:
        user_sessions[user_id]['page'] = 2
        show_results_page_next(user_id, songs, 11, 20, query)
    else:
        bot.send_message(user_id, "❌ Natijalar topilmadi")

# ================= BOT ISHGA TUSHDI =================
print("✅ BOT ISHGA TUSHDI!")
print("🎵 Instagram & TikTok endi ishlaydi!")
print("🔍 Qidiruvda faqat musiqa chiqadi!")
bot.infinity_polling(
    skip_pending=True,
    none_stop=True,
    interval=0
)
