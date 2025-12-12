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

# ================= YUKLASH SETTINGLARI =================
# Instagram uchun YANGI va SIMPLE settinglar
ydl_opts_instagram = {
    'format': 'best',  # Eng yaxshi formatni tanlash
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/%(id)s.%(ext)s',
    'socket_timeout': 60,
    'retries': 10,
    'fragment_retries': 10,
    'ignoreerrors': True,
    'no_check_certificate': True,
    'geo_bypass': True,
    'geo_bypass_country': 'US',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    },
}

# Instagram uchun ALTERNATIVE format
ydl_opts_instagram_alt = {
    'format': 'best[height<=720]/best[height<=480]/worst',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/instagram_%(id)s.%(ext)s',
    'socket_timeout': 60,
    'retries': 5,
    'ignoreerrors': True,
    'extractor_args': {
        'instagram': {
            'format': 'best',
            'post_data': {}
        }
    },
}

# TikTok uchun
ydl_opts_tiktok = {
    'format': 'best[height<=720]',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/%(id)s.%(ext)s',
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
    for char in r'<>:"/\|?*':
        text = text.replace(char, '')
    
    # Bo'sh joylarni pastki chiziqqa almashtirish
    text = text.replace(' ', '_')
    
    # Qisqartirish
    if len(text) > 40:
        text = text[:40]
    
    # Agar bo'sh qolsa
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
        r'https?://(www\.)?instagram\.com/stories/',
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
        r'https?://m\.tiktok\.com/',
    ]
    
    url = url.lower().strip()
    for pattern in patterns:
        if re.search(pattern, url):
            return True
    return False

def extract_instagram_video_simple(url):
    """Instagram videoni oddiy usulda yuklash"""
    try:
        # Birinchi urinish: asosiy format
        with yt_dlp.YoutubeDL(ydl_opts_instagram) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'instagram_video')
            title = info.get('title', 'Instagram Video')
            
            # Faylni qidirish
            for file in os.listdir("temp"):
                if file.startswith(video_id) or video_id in file:
                    return os.path.join("temp", file), title
            
            # Agar topilmasa
            for file in os.listdir("temp"):
                if file.endswith(('.mp4', '.webm', '.mkv')):
                    file_path = os.path.join("temp", file)
                    # Eng yangi fayl
                    if os.path.getctime(file_path) > os.path.getctime("temp") + 5:
                        return file_path, title
                        
        return None, title
        
    except yt_dlp.utils.DownloadError:
        # Ikkinchi urinish: alternativ format
        try:
            with yt_dlp.YoutubeDL(ydl_opts_instagram_alt) as ydl:
                info = ydl.extract_info(url, download=True)
                
                for file in os.listdir("temp"):
                    if file.startswith('instagram_') and file.endswith(('.mp4', '.webm')):
                        return os.path.join("temp", file), info.get('title', 'Instagram Video')
                        
                return None, info.get('title', 'Instagram Video')
                
        except Exception as e:
            print(f"Instagram alternativ xatosi: {e}")
            return None, "Instagram Video"
            
    except Exception as e:
        print(f"Instagram umumiy xatosi: {e}")
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
            query = f"{artist} {title} audio"
            try:
                # To'g'ri nom bilan yuklash
                clean_title = clean_filename(title)
                clean_artist = clean_filename(artist)
                output_file = f"temp/{clean_artist} - {clean_title}.mp3"
                
                opts = ydl_opts_audio_named.copy()
                opts['outtmpl'] = f"temp/{clean_artist} - {clean_title}.%(ext)s"
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                
                # Faylni qidirish
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
                    # Boshqa nom bilan qidirish
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
                            f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}",
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
        bot.reply_to(message, f"❌ Xatolik yuz berdi")

# ================= INSTAGRAM HANDLER =================
@bot.message_handler(func=lambda m: is_instagram_url(m.text))
def handle_instagram_reel(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 Instagram videoni yuklamoqda...")

        # Videoni yuklash
        video_path, video_title = extract_instagram_video_simple(url)
        
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
                "❌ Instagram video yuklanmadi\n"
                "Iltimos:\n"
                "1. Video ommaviy bo'lishi kerak (private emas)\n"
                "2. To'g'ri Instagram linki bo'lishi kerak\n"
                "3. Boshqa video yuboring",
                message.chat.id,
                msg.message_id
            )

    except Exception as e:  
        bot.reply_to(message, f"❌ Instagram video yuklanmadi\nXato: {str(e)[:100]}")

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
                if file.endswith(('.mp4', '.webm')):
                    video_files.append(os.path.join("temp", file))
            
            if video_files:
                video_path = max(video_files, key=os.path.getctime)
                
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
        bot.reply_to(message, f"❌ TikTok video yuklanmadi: {str(e)[:100]}")

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

        # FAQAT 10 soniya audio (tezroq)
        short_audio_path = video_path.rsplit('.', 1)[0] + '_short.mp3'
        
        try:
            subprocess.run([
                'ffmpeg', '-i', video_path, 
                '-t', '10', 
                '-vn', 
                '-acodec', 'mp3', 
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
              
            # TEZ YUKLASH
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
                            caption=f"✅ Videodan topildi!\n🎵 {title}\n👤 {artist}"
                        )
                    
                    os.remove(output_file)
                else:
                    # Boshqa nom bilan qidirish
                    for file in os.listdir("temp"):
                        if file.endswith('.mp3') and (clean_title[:20] in file or clean_artist[:20] in file):
                            with open(os.path.join("temp", file), 'rb') as f:
                                bot.send_audio(
                                    call.message.chat.id, 
                                    f,
                                    title=title[:64],
                                    performer=artist[:64],
                                    caption=f"✅ Videodan topildi!\n🎵 {title}\n👤 {artist}"
                                )
                            os.remove(os.path.join("temp", file))
                            break
                    else:
                        bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}")
                    
            except Exception as e:
                bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}")
                print(f"Audio yuklash xatosi: {e}")
        else:  
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi")  

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Xatolik yuz berdi: {str(e)[:100]}")
    finally:  
        # Fayllarni tozalash
        try:  
            if 'video_path' in locals() and os.path.exists(video_path):  
                os.remove(video_path)  
            if 'short_audio_path' in locals() and os.path.exists(short_audio_path):  
                os.remove(short_audio_path)  
            if 'btn_hash' in locals() and os.path.exists(f"temp/{btn_hash}.txt"):  
                os.remove(f"temp/{btn_hash}.txt")  
        except:  
            pass

# ================= QIDIRUV HANDLER =================
@bot.message_handler(func=lambda m: True)
def search_music(message):
    query = message.text.strip()
    
    # Instagram/TikTok link bo'lsa - yuqoridagi handler ishlaydi  
    if is_instagram_url(query) or is_tiktok_url(query):  
        return  
    
    msg = bot.reply_to(message, f"🔍 '{query}' qidirilmoqda...")  
    
    try:  
        # 5 ta natija
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 15,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)  
            songs = info.get('entries', [])  

        if not songs:
            bot.edit_message_text("❌ Hech qanday natija topilmadi", message.chat.id, msg.message_id)
            return

        # Matn ro'yxati  
        text_list = [f"🔍 '{query}' uchun natijalar:\n"]  
        markup = types.InlineKeyboardMarkup(row_width=5)  
        buttons = []  

        for i, song in enumerate(songs, 1):  
            if not song:
                continue
                
            title = song.get("title", "Noma'lum")[:50]
            duration = song.get("duration", 0)  
            
            # Vaqtni formatlash
            time_str = format_duration(duration)
            
            text_list.append(f"{i}. {title}{time_str}")  
            
            # Inline tugma
            url = song.get("url", song.get("webpage_url", ""))
            if url:
                h = create_hash(url)
                with open(f"temp/{h}.txt", "w") as f:  
                    f.write(f"{url}|{title}")  
                buttons.append(types.InlineKeyboardButton(str(i), callback_data=f"song_{h}"))  

        if buttons:  
            markup.add(*buttons)  
            bot.send_message(message.chat.id, "\n".join(text_list), reply_markup=markup)  
        
        bot.delete_message(message.chat.id, msg.message_id)  

    except Exception as e:  
        bot.edit_message_text(f"❌ Xatolik", message.chat.id, msg.message_id)
        print(f"Qidiruv xatosi: {e}")

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
        # TEZ YUKLASH
        clean_title = clean_filename(title)
        output_file = f"temp/{clean_title}.mp3"
        
        opts = ydl_opts_audio_named.copy()
        opts['outtmpl'] = f"temp/{clean_title}.%(ext)s"
        
        with yt_dlp.YoutubeDL(opts) as ydl:  
            info = ydl.extract_info(url, download=True)
            actual_title = info.get('title', title)
        
        # Faylni qidirish
        if os.path.exists(output_file):
            with open(output_file, 'rb') as f:  
                bot.send_audio(call.message.chat.id, f, title=actual_title[:64])  

            os.remove(output_file)  
        else:
            # Boshqa nom bilan qidirish
            for file in os.listdir("temp"):
                if file.endswith('.mp3') and clean_title[:20] in file:
                    with open(os.path.join("temp", file), 'rb') as f:  
                        bot.send_audio(call.message.chat.id, f, title=actual_title[:64])
                    os.remove(os.path.join("temp", file))
                    break
        
        # Hash faylni o'chirish
        if os.path.exists(f"temp/{h}.txt"):
            os.remove(f"temp/{h}.txt")

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Yuklashda xatolik")
        print(f"Yuklash xatosi: {e}")

# ================= BOT ISHGA TUSHDI =================
print("✅ BOT ISHGA TUSHDI!")
print("📱 Instagram va TikTok qo'llab-quvvatlanadi")
print("🎵 To'g'ri nom bilan audio yuklash faol")
bot.infinity_polling()
