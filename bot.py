import telebot
import os
import asyncio
import tempfile
import subprocess
import hashlib
import re
import json
import requests
from telebot import types
from shazamio import Shazam
import yt_dlp

# ========================================
# BOT TOKEN
BOT_TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"
bot = telebot.TeleBot(BOT_TOKEN)
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
        "📸 Instagram: https://www.instagram.com/bahrombekh_fx?igsh=Y2J0NnFpNm9icTFp"
    )
    bot.send_message(message.chat.id, text)

# TEMP papka yaratish
if not os.path.exists("temp"):
    os.makedirs("temp")

# User session data
user_sessions = {}

# ================= YUKLASH SETTINGLARI =================
# Instagram uchun YANGI SIMPLE format
ydl_opts_instagram = {
    'format': 'best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/instagram_%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 3,
    'ignoreerrors': True,
    'extractor_args': {
        'instagram': {
            'format': 'best',
            'post_data': {}
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    },
}

# TikTok uchun
ydl_opts_tiktok = {
    'format': 'best[height<=720]',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/tiktok_%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 3,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
}

# Audio yuklash uchun (qo'shiq nomi bilan)
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
    
    # Maxsus belgilarni olib tashlash
    for char in r'<>:"/\|?*#%&{}[]':
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
        r'https?://(www\.)?instagram\.com/(p|reel|tv)/',
        r'https?://(www\.)?instagram\.com/reels/',
        r'https?://(www\.)?instagram\.com/tv/',
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

def download_instagram_video_direct(url):
    """Instagram videoni to'g'ridan-to'g'ri yuklash"""
    try:
        # Oddiy usul: yt-dlp bilan
        opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'outtmpl': 'temp/insta_%(id)s.%(ext)s',
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Faylni qidirish
            for file in os.listdir("temp"):
                if file.startswith("insta_") and file.endswith(('.mp4', '.webm', '.mkv')):
                    return os.path.join("temp", file), info.get('title', 'Instagram Video')
        
        return None, "Instagram Video"
        
    except Exception as e:
        print(f"Instagram yuklash xatosi: {e}")
        return None, "Instagram Video"

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
              
            bot.edit_message_text(
                f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n⏳ Tez yuklanmoqda...", 
                message.chat.id, 
                msg.message_id
            )  
              
            # TEZ YUKLASH
            query = f"{artist} {title}"
            try:
                clean_title = clean_filename(title)
                clean_artist = clean_filename(artist)
                
                # YANGI: Video nomi bilan qidirish
                opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': f'temp/{clean_artist}_{clean_title}.%(ext)s',
                    'quiet': True,
                    'socket_timeout': 20,
                    'retries': 2,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # YANGI: video qo'shib qidirish (ko'proq natija uchun)
                    info = ydl.extract_info(f"ytsearch5:{query} official audio", download=True)
                
                # Faylni qidirish
                mp3_files = []
                for file in os.listdir("temp"):
                    if file.endswith('.mp3') and (clean_artist[:10].lower() in file.lower() or clean_title[:10].lower() in file.lower()):
                        mp3_files.append(os.path.join("temp", file))
                
                if mp3_files:
                    # Eng katta faylni tanlash (to'liq bo'lsa)
                    mp3_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
                    best_file = mp3_files[0]
                    
                    file_size = os.path.getsize(best_file)
                    if file_size > 500000:  # 500KB dan katta bo'lsa
                        with open(best_file, 'rb') as f:
                            bot.send_audio(
                                message.chat.id, 
                                f,
                                title=title[:64],
                                performer=artist[:64],
                                caption=f"🎵 {title}\n👤 {artist}"
                            )
                        
                        os.remove(best_file)
                        bot.delete_message(message.chat.id, msg.message_id)
                        
                        # Boshqa fayllarni ham tozalash
                        for mp3_file in mp3_files[1:]:
                            try:
                                os.remove(mp3_file)
                            except:
                                pass
                    else:
                        bot.edit_message_text(
                            f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Fayl juda kichik",
                            message.chat.id,
                            msg.message_id
                        )
                else:
                    bot.edit_message_text(
                        f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Audio yuklanmadi",
                        message.chat.id,
                        msg.message_id
                    )
                    
            except Exception as e:
                bot.edit_message_text(
                    f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}",
                    message.chat.id,
                    msg.message_id
                )
                print(f"Audio yuklash xatosi: {e}")
        else:  
            bot.edit_message_text("❌ Musiqa topilmadi", message.chat.id, msg.message_id)  
              
    except Exception as e:  
        bot.reply_to(message, f"❌ Xatolik yuz berdi")

# ================= INSTAGRAM HANDLER =================
@bot.message_handler(func=lambda m: is_instagram_url(m.text))
def handle_instagram_reel(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 Instagram videoni yuklamoqda...")

        # To'g'ridan-to'g'ri yuklash
        video_path, video_title = download_instagram_video_direct(url)
        
        if video_path and os.path.exists(video_path):
            btn_hash = create_hash(video_path)
            markup = types.InlineKeyboardMarkup()  
            markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"insta_{btn_hash}"))  

            with open(video_path, 'rb') as f:  
                bot.send_video(message.chat.id, f, reply_markup=markup, caption="📱 Instagram video")  

            with open(f"temp/{btn_hash}.txt", "w") as f:  
                f.write(video_path)  

            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(
                "❌ Instagram video yuklanmadi\n\n"
                "Sabablari:\n"
                "1. Video private bo'lishi mumkin\n"
                "2. Instagram blok qo'ygan bo'lishi mumkin\n"
                "3. Boshqa link yuboring yoki\n"
                "4. Videoni audio fayl sifatida yuboring",
                message.chat.id,
                msg.message_id
            )

    except Exception as e:  
        bot.reply_to(message, "❌ Instagram video yuklanmadi")

# ================= TIKTOK HANDLER =================
@bot.message_handler(func=lambda m: is_tiktok_url(m.text))
def handle_tiktok(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 TikTok videoni yuklamoqda...")

        with yt_dlp.YoutubeDL(ydl_opts_tiktok) as ydl:  
            info = ydl.extract_info(url, download=True)
            
            # Faylni qidirish
            video_files = []
            for file in os.listdir("temp"):
                if file.startswith("tiktok_") and file.endswith(('.mp4', '.webm')):
                    video_files.append(os.path.join("temp", file))
            
            if video_files:
                video_path = video_files[0]
                
                btn_hash = create_hash(video_path)
                markup = types.InlineKeyboardMarkup()  
                markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"tiktok_{btn_hash}"))  

                with open(video_path, 'rb') as f:  
                    bot.send_video(message.chat.id, f, reply_markup=markup, caption="📱 TikTok video")  

                with open(f"temp/{btn_hash}.txt", "w") as f:  
                    f.write(video_path)  

                bot.delete_message(message.chat.id, msg.message_id)
            else:
                bot.edit_message_text("❌ TikTok video yuklanmadi", message.chat.id, msg.message_id)

    except Exception as e:  
        bot.reply_to(message, "❌ TikTok video yuklanmadi")

# ================= VIDEO MUSIQANI ANIQLASH =================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("insta_", "tiktok_")))
def handle_media_music(call):
    try:
        prefix, btn_hash = call.data.split("_", 1)
        bot.answer_callback_query(call.id, "🎵 Musiqa izlanmoqda...")

        with open(f"temp/{btn_hash}.txt", "r") as f:  
            video_path = f.read().strip()  

        if not os.path.exists(video_path):
            bot.send_message(call.message.chat.id, "❌ Video fayl topilmadi")
            return

        # FAKAT 15 soniya audio
        short_audio_path = video_path.rsplit('.', 1)[0] + '_audio.mp3'
        
        try:
            subprocess.run([
                'ffmpeg', '-i', video_path, 
                '-t', '15', 
                '-vn', 
                '-acodec', 'mp3', 
                '-ab', '192k',
                '-ar', '44100',
                '-y', short_audio_path
            ], capture_output=True, timeout=30, check=False)
        except Exception as e:
            print(f"FFmpeg xatosi: {e}")

        if not os.path.exists(short_audio_path):
            bot.send_message(call.message.chat.id, "❌ Audio ajratishda xatolik")
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
              
            # YANGI: Kuchliroq qidiruv
            query = f"{artist} {title} official"
            try:
                clean_title = clean_filename(title)
                clean_artist = clean_filename(artist)
                
                # 3 ta natija qidirish
                opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': f'temp/{clean_artist}_{clean_title}_%(id)s.%(ext)s',
                    'quiet': True,
                    'socket_timeout': 20,
                    'retries': 2,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"ytsearch3:{query}", download=True)
                
                # MP3 fayllarni qidirish
                mp3_files = []
                for file in os.listdir("temp"):
                    if file.endswith('.mp3') and (clean_artist[:10].lower() in file.lower() or clean_title[:10].lower() in file.lower() or "audio" in file.lower()):
                        mp3_files.append(os.path.join("temp", file))
                
                if mp3_files:
                    # Eng katta faylni tanlash
                    mp3_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
                    best_file = mp3_files[0]
                    
                    with open(best_file, 'rb') as f:
                        bot.send_audio(
                            call.message.chat.id, 
                            f,
                            title=title[:64],
                            performer=artist[:64],
                            caption=f"✅ Videodan topildi!\n🎵 {title}\n👤 {artist}"
                        )
                    
                    # Barcha fayllarni tozalash
                    for mp3_file in mp3_files:
                        try:
                            os.remove(mp3_file)
                        except:
                            pass
                else:
                    bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}")
                    
            except Exception as e:
                bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}")
                print(f"Audio yuklash xatosi: {e}")
        else:  
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi")  

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Xatolik yuz berdi")
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
        # 10 TA NATIJA
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 20,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)  
            songs = info.get('entries', [])  

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
        
        # Natijalarni ko'rsatish
        show_results_page(user_id, songs, 1, query)
        
        bot.delete_message(user_id, msg.message_id)  

    except Exception as e:  
        bot.edit_message_text(f"❌ Xatolik", message.chat.id, msg.message_id)
        print(f"Qidiruv xatosi: {e}")

def show_results_page(chat_id, songs, page, query):
    """Natijalarni sahifalab ko'rsatish"""
    start_idx = (page - 1) * 10
    end_idx = min(start_idx + 10, len(songs))
    
    text_list = [f"🔍 '{query}' uchun natijalar ({start_idx+1}-{end_idx}):\n"]  
    
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
            
            if idx <= 5:
                first_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
            else:
                second_row.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
    
    if first_row:
        markup.add(*first_row)
    if second_row:
        markup.add(*second_row)
    
    # Navigatsiya tugmalari
    nav_buttons = [
        types.InlineKeyboardButton("⬅️ Orqaga", callback_data="nav_back"),
        types.InlineKeyboardButton("🏠 Bosh", callback_data="nav_home"),
        types.InlineKeyboardButton("Oldinga ➡️", callback_data="nav_next")
    ]
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
        
        # YANGI: To'g'ri nom bilan yuklash
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'temp/{clean_title}_%(id)s.%(ext)s',
            'quiet': True,
            'socket_timeout': 20,
            'retries': 2,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:  
            info = ydl.extract_info(url, download=True)
            actual_title = info.get('title', title)
        
        # Faylni qidirish
        mp3_files = []
        for file in os.listdir("temp"):
            if file.endswith('.mp3') and (clean_title[:15].lower() in file.lower() or h in file):
                mp3_files.append(os.path.join("temp", file))
        
        if mp3_files:
            # Eng katta faylni tanlash
            mp3_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
            best_file = mp3_files[0]
            
            with open(best_file, 'rb') as f:  
                bot.send_audio(call.message.chat.id, f, title=actual_title[:64])
            
            # Barcha fayllarni tozalash
            for mp3_file in mp3_files:
                try:
                    os.remove(mp3_file)
                except:
                    pass
        
        # Hash faylni o'chirish
        if os.path.exists(f"temp/{h}.txt"):
            os.remove(f"temp/{h}.txt")

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Yuklashda xatolik")
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
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if call.data == "nav_back":
        # Orqaga - yangi qidiruv
        msg = bot.send_message(user_id, f"🔍 '{query}' qayta qidirilmoqda...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:  
                info = ydl.extract_info(f"ytsearch10:{query}", download=False)  
                songs = info.get('entries', [])  
            
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
        # Bosh sahifa
        text = "🔍 Qo'shiq nomi yoki ijrochi ismini yuboring:"
        bot.send_message(user_id, text)
    
    elif call.data == "nav_next":
        # Keyingi 10 ta natija
        msg = bot.send_message(user_id, f"🔍 '{query}' - keyingi natijalar...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:  
                info = ydl.extract_info(f"ytsearch20:{query}", download=False)  
                songs = info.get('entries', [])  
            
            if songs and len(songs) > 10:
                user_sessions[user_id]['songs'] = songs
                user_sessions[user_id]['page'] = 2
                
                # 11-20 natijalarni ko'rsatish
                start_idx = 10
                end_idx = min(20, len(songs))
                
                text_list = [f"🔍 '{query}' uchun natijalar (11-{end_idx}):\n"]  
                markup = types.InlineKeyboardMarkup(row_width=5)
                
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
                            markup.add(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
                        else:
                            # Alohida qator
                            pass
                
                # Navigatsiya
                nav_buttons = [
                    types.InlineKeyboardButton("⬅️ Avvalgi", callback_data="nav_prev"),
                    types.InlineKeyboardButton("🏠 Bosh", callback_data="nav_home")
                ]
                markup.add(*nav_buttons)
                
                bot.send_message(user_id, "\n".join(text_list), reply_markup=markup)
            else:
                bot.send_message(user_id, "❌ Ko'proq natija topilmadi")
            
            bot.delete_message(user_id, msg.message_id)
            
        except Exception as e:
            bot.send_message(user_id, "❌ Qidiruvda xatolik")

@bot.callback_query_handler(func=lambda c: c.data == "nav_prev")
def handle_nav_prev(call):
    user_id = call.message.chat.id
    
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "❌ Session topilmadi")
        return
    
    session = user_sessions[user_id]
    query = session['query']
    songs = session.get('songs', [])
    
    try:
        bot.delete_message(user_id, call.message.message_id)
    except:
        pass
    
    if songs:
        user_sessions[user_id]['page'] = 1
        show_results_page(user_id, songs[:10], 1, query)
    else:
        msg = bot.send_message(user_id, f"🔍 '{query}' qayta qidirilmoqda...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:  
                info = ydl.extract_info(f"ytsearch10:{query}", download=False)  
                songs = info.get('entries', [])  
            
            if songs:
                user_sessions[user_id]['songs'] = songs
                show_results_page(user_id, songs, 1, query)
            else:
                bot.send_message(user_id, "❌ Hech qanday natija topilmadi")
            
            bot.delete_message(user_id, msg.message_id)
            
        except Exception as e:
            bot.send_message(user_id, "❌ Qidiruvda xatolik")

# ================= BOT ISHGA TUSHDI =================
print("✅ BOT ISHGA TUSHDI!")
print("🎵 10 ta natija + Navigatsiya tugmalari")
print("⬅️ Orqaga | 🏠 Bosh | Oldinga ➡️")
print("📱 Instagram - oddiy yuklash usuli")
print("🎯 Qo'shiq topish yaxshilandi")
bot.infinity_polling()
