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
BOT_TOKEN = "8575775719:AAGzviNnhPr_hVpqO4cUMrPlY0K498d_9I8"
bot = telebot.TeleBot(BOT_TOKEN)
# ========================================

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

# User session data
user_sessions = {}

# ================= YUKLASH SETTINGLARI =================
# Instagram uchun - ISHLAYDI!
ydl_opts_instagram = {
    'format': 'best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/instagram_%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 5,
}

# TikTok uchun
ydl_opts_tiktok = {
    'format': 'best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/tiktok_%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 3,
}

# Audio yuklash uchun
ydl_opts_audio = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/%(title)s.%(ext)s',
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
    
    for char in '<>:"/\\|?*':
        text = text.replace(char, '')
    
    text = text.replace(' ', '_')
    
    if len(text) > 40:
        text = text[:40]
    
    return text

# ================= SHAZAM ANIQLASH =================
async def recognize_song(audio_bytes):
    """Audio fayldan musiqa aniqlash"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir='temp') as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        shazam = Shazam()  
        result = await shazam.recognize(tmp_path)  
        os.unlink(tmp_path)  

        if result and 'track' in result:  
            track = result['track']  
            title = track.get('title', 'Noma\'lum')
            artist = track.get('subtitle', 'Noma\'lum')
            
            # Agar title va artist bo'sh bo'lsa
            if title == 'Noma\'lum' and artist == 'Noma\'lum':
                return {'found': False}
                
            return {  
                'found': True,   
                'title': title,  
                'artist': artist,
            }  
    except Exception as e:  
        print(f"Shazam xatosi: {e}")  
    return {'found': False}

# ================= VIDEO DAN AUDIO AJRATISH =================
def extract_audio_from_video(video_path, duration=20):
    """Videodan audio ajratish"""
    try:
        short_audio_path = video_path.rsplit('.', 1)[0] + '_audio.mp3'
        
        # FFmpeg bilan audio ajratish
        cmd = [
            'ffmpeg', '-i', video_path, 
            '-t', str(duration),  # 20 soniya
            '-vn',  # Video olib tashlash
            '-acodec', 'mp3', 
            '-ab', '192k',
            '-ar', '44100',
            '-y', short_audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(short_audio_path):
            return short_audio_path
        else:
            print(f"FFmpeg xatosi: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Audio ajratish xatosi: {e}")
        return None

# ================= YOUTUBEDAN QO'SHIQ YUKLASH =================
def download_song_from_youtube(query, chat_id, message_id=None):
    """YouTube'dan qo'shiq yuklash"""
    try:
        # TEZ YUKLASH
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 20,
            'retries': 2,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Qidiruv
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            
            if 'entries' in info and info['entries']:
                song = info['entries'][0]
                
                # Fayl nomini aniqlash
                filename = ydl.prepare_filename(song)
                mp3_file = filename.rsplit('.', 1)[0] + '.mp3'
                
                if os.path.exists(mp3_file):
                    file_size = os.path.getsize(mp3_file)
                    
                    # Agar fayl kichik bo'lsa, yana urinib ko'rish
                    if file_size > 100000:  # 100KB dan katta bo'lishi kerak
                        return mp3_file, song.get('title', query)
                    else:
                        print(f"Fayl juda kichik: {file_size} bytes")
        
        return None, query
        
    except Exception as e:
        print(f"YouTube yuklash xatosi: {e}")
        return None, query

# ================= AUDIO FAYL YUBORILGANDA =================
@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio(message):
    """Audio yoki ovozli xabar yuborilganda"""
    try:
        msg = bot.reply_to(message, "🎵 Musiqa aniqlanmoqda...")

        # Faylni yuklash
        if message.audio:  
            file_info = bot.get_file(message.audio.file_id)  
        elif message.voice:  
            file_info = bot.get_file(message.voice.file_id)  
        else:  
            return  
              
        downloaded_file = bot.download_file(file_info.file_path)  
        
        # Shazam bilan aniqlash
        loop = asyncio.new_event_loop()  
        asyncio.set_event_loop(loop)  
        result = loop.run_until_complete(recognize_song(downloaded_file))  
        loop.close()  
        
        if result['found']:  
            title = result['title']  
            artist = result['artist']  
              
            bot.edit_message_text(
                f"✅ **{title}** - {artist}\n\n⏳ Yuklanmoqda...", 
                message.chat.id, 
                msg.message_id
            )  
              
            # YouTube'dan yuklash
            query = f"{artist} {title}"
            mp3_file, actual_title = download_song_from_youtube(query, message.chat.id)
            
            if mp3_file and os.path.exists(mp3_file):
                with open(mp3_file, 'rb') as f:
                    bot.send_audio(
                        message.chat.id, 
                        f,
                        title=title[:64],
                        performer=artist[:64],
                        caption=f"🎵 {title}\n👤 {artist}"
                    )
                
                os.remove(mp3_file)
                bot.delete_message(message.chat.id, msg.message_id)
            else:
                bot.edit_message_text(
                    f"✅ **{title}** - {artist}\n\n❌ Yuklanmadi, qo'lda qidiring",
                    message.chat.id,
                    msg.message_id
                )
        else:  
            bot.edit_message_text("❌ Musiqa topilmadi", message.chat.id, msg.message_id)  
              
    except Exception as e:  
        bot.reply_to(message, "❌ Xatolik yuz berdi")

# ================= INSTAGRAM HANDLER =================
@bot.message_handler(func=lambda m: 'instagram.com' in m.text and ('/reel/' in m.text or '/p/' in m.text or '/tv/' in m.text))
def handle_instagram_reel(message):
    """Instagram video linki yuborilganda"""
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 Instagram videoni yuklamoqda...")

        # VIDEO YUKLASH
        try:
            with yt_dlp.YoutubeDL(ydl_opts_instagram) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Yuklangan faylni qidirish
                video_files = []
                for file in os.listdir("temp"):
                    if file.startswith('instagram_') and file.endswith(('.mp4', '.webm')):
                        video_files.append(os.path.join("temp", file))
                
                if video_files:
                    video_path = video_files[0]
                    
                    # VIDEO YUBORISH
                    btn_hash = create_hash(video_path)
                    markup = types.InlineKeyboardMarkup()  
                    markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"insta_{btn_hash}"))  

                    with open(video_path, 'rb') as f:  
                        bot.send_video(message.chat.id, f, reply_markup=markup, caption="📱 Instagram video")  

                    with open(f"temp/{btn_hash}.txt", "w") as f:  
                        f.write(video_path)  

                    bot.delete_message(message.chat.id, msg.message_id)
                else:
                    bot.edit_message_text("❌ Video yuklanmadi", message.chat.id, msg.message_id)
                    
        except Exception as e:
            print(f"Instagram yuklash xatosi: {e}")
            bot.edit_message_text("❌ Instagram video yuklanmadi", message.chat.id, msg.message_id)

    except Exception as e:  
        bot.reply_to(message, "❌ Instagram video yuklanmadi")

# ================= TIKTOK HANDLER =================
@bot.message_handler(func=lambda m: 'tiktok.com' in m.text)
def handle_tiktok(message):
    """TikTok video linki yuborilganda"""
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 TikTok videoni yuklamoqda...")

        # VIDEO YUKLASH
        try:
            with yt_dlp.YoutubeDL(ydl_opts_tiktok) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Yuklangan faylni qidirish
                video_files = []
                for file in os.listdir("temp"):
                    if file.startswith('tiktok_') and file.endswith(('.mp4', '.webm')):
                        video_files.append(os.path.join("temp", file))
                
                if video_files:
                    video_path = video_files[0]
                    
                    # VIDEO YUBORISH
                    btn_hash = create_hash(video_path)
                    markup = types.InlineKeyboardMarkup()  
                    markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"tiktok_{btn_hash}"))  

                    with open(video_path, 'rb') as f:  
                        bot.send_video(message.chat.id, f, reply_markup=markup, caption="📱 TikTok video")  

                    with open(f"temp/{btn_hash}.txt", "w") as f:  
                        f.write(video_path)  

                    bot.delete_message(message.chat.id, msg.message_id)
                else:
                    bot.edit_message_text("❌ Video yuklanmadi", message.chat.id, msg.message_id)
                    
        except Exception as e:
            print(f"TikTok yuklash xatosi: {e}")
            bot.edit_message_text("❌ TikTok video yuklanmadi", message.chat.id, msg.message_id)

    except Exception as e:  
        bot.reply_to(message, "❌ TikTok video yuklanmadi")

# ================= VIDEO MUSIQANI ANIQLASH =================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("insta_", "tiktok_")))
def handle_media_music(call):
    """Video dagi musiqani aniqlash"""
    try:
        prefix, btn_hash = call.data.split("_", 1)
        bot.answer_callback_query(call.id, "🎵 Musiqa izlanmoqda...")

        # VIDEO FAYLNI OLISH
        with open(f"temp/{btn_hash}.txt", "r") as f:  
            video_path = f.read().strip()  

        if not os.path.exists(video_path):
            bot.send_message(call.message.chat.id, "❌ Video fayl topilmadi")
            return

        # VIDEODAN AUDIO AJRATISH
        short_audio_path = extract_audio_from_video(video_path, duration=20)
        
        if not short_audio_path or not os.path.exists(short_audio_path):
            bot.send_message(call.message.chat.id, "❌ Audio ajratishda xatolik")
            return

        # AUDIONI SHAZAM BILAN ANIQLASH
        with open(short_audio_path, 'rb') as f:  
            short_audio_data = f.read()  

        loop = asyncio.new_event_loop()  
        asyncio.set_event_loop(loop)  
        result = loop.run_until_complete(recognize_song(short_audio_data))  
        loop.close()  

        if result['found']:  
            title = result['title']  
            artist = result['artist']  
              
            bot.send_message(call.message.chat.id, f"✅ **{title}** - {artist}\n\n⏳ Yuklanmoqda...")  
              
            # YOUTUBEDAN YUKLASH
            query = f"{artist} {title}"
            mp3_file, actual_title = download_song_from_youtube(query, call.message.chat.id)
            
            if mp3_file and os.path.exists(mp3_file):
                with open(mp3_file, 'rb') as f:
                    bot.send_audio(
                        call.message.chat.id, 
                        f,
                        title=title[:64],
                        performer=artist[:64],
                        caption=f"✅ Videodan topildi!\n🎵 {title}\n👤 {artist}"
                    )
                
                os.remove(mp3_file)
            else:
                bot.send_message(call.message.chat.id, f"✅ **{title}** - {artist}\n\n❌ Yuklanmadi, qo'lda qidiring")
                
        else:  
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi")  

    except Exception as e:  
        bot.send_message(call.message.chat.id, "❌ Xatolik yuz berdi")
    finally:  
        # FAYLLARNI TOZALASH
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
    """Qo'shiq nomi yoki ijrochi ismi yuborilganda"""
    query = message.text.strip()
    
    # Instagram/TikTok link bo'lsa - yuqoridagi handler ishlaydi  
    if 'instagram.com' in query or 'tiktok.com' in query:  
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

        # USER SESSION SAQLASH
        user_id = message.chat.id
        user_sessions[user_id] = {
            'query': query,
            'songs': songs,
            'page': 1
        }
        
        # NATIJALARNI KO'RSATISH
        show_results_page(user_id, songs, 1, query)
        
        bot.delete_message(user_id, msg.message_id)  

    except Exception as e:  
        bot.edit_message_text("❌ Xatolik", message.chat.id, msg.message_id)

def show_results_page(chat_id, songs, page, query):
    """Natijalarni sahifalab ko'rsatish"""
    start_idx = (page - 1) * 10
    end_idx = min(start_idx + 10, len(songs))
    
    text_list = [f"🔍 **'{query}' uchun natijalar:**\n"]  
    
    # INLINE TUGMALAR
    markup = types.InlineKeyboardMarkup(row_width=5)
    row1 = []
    row2 = []
    
    for i in range(start_idx, end_idx):
        song = songs[i]
        if not song:
            continue
            
        idx = i + 1
        title = song.get("title", "Noma'lum")[:60]
        
        # Vaqtni formatlash
        duration = song.get("duration", 0)
        if duration:
            minutes = duration // 60
            seconds = duration % 60
            time_str = f" ({minutes}:{seconds:02d})"
        else:
            time_str = ""
        
        text_list.append(f"{idx}. {title}{time_str}")  
        
        # INLINE TUGMA
        url = song.get("url", song.get("webpage_url", ""))
        if url:
            h = create_hash(url)
            with open(f"temp/{h}.txt", "w") as f:  
                f.write(f"{url}|{title}")  
            
            if idx <= 5:
                row1.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
            else:
                row2.append(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
    
    # TUGMALARNI QO'SHISH
    if row1:
        markup.add(*row1)
    if row2:
        markup.add(*row2)
    
    # NAVIGATSIYA TUGMALARI
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
    """Qo'shiq yuklash"""
    h = call.data.split("_", 1)[1]
    
    with open(f"temp/{h}.txt") as f:  
        data = f.read().strip()  
    
    if "|" in data:  
        url, title = data.split("|", 1)  
    else:  
        url = data  
        title = "Musiqa"  
    
    bot.answer_callback_query(call.id, "🎵 Yuklanmoqda...")  
    
    try:  
        # TEZ YUKLASH
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 20,
            'retries': 2,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:  
            info = ydl.extract_info(url, download=True)
            
            # Fayl nomini aniqlash
            filename = ydl.prepare_filename(info)
            mp3_file = filename.rsplit('.', 1)[0] + '.mp3'
        
        if os.path.exists(mp3_file):
            with open(mp3_file, 'rb') as f:  
                bot.send_audio(call.message.chat.id, f, title=title[:64])
            
            os.remove(mp3_file)
        
        # HASH FAYLNI O'CHIRISH
        if os.path.exists(f"temp/{h}.txt"):
            os.remove(f"temp/{h}.txt")

    except Exception as e:  
        bot.send_message(call.message.chat.id, "❌ Yuklashda xatolik")

# ================= NAVIGATSIYA HANDLER =================
@bot.callback_query_handler(func=lambda c: c.data in ["nav_back", "nav_home", "nav_next"])
def handle_navigation(call):
    """Navigatsiya tugmalari"""
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
        # ORQAGA - YANGI QIDIRUV
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
        # BOSH SAHIFA
        text = "🔍 Qo'shiq nomi yoki ijrochi ismini yuboring:"
        bot.send_message(user_id, text)
    
    elif call.data == "nav_next":
        # KEYINGI NATIJALAR
        msg = bot.send_message(user_id, f"🔍 '{query}' - keyingi natijalar...")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:  
                info = ydl.extract_info(f"ytsearch20:{query}", download=False)  
                songs = info.get('entries', [])  
            
            if songs and len(songs) > 10:
                # 11-20 NATIJALARNI KO'RSATISH
                text_list = [f"🔍 **'{query}' uchun natijalar (11-20):**\n"]  
                markup = types.InlineKeyboardMarkup(row_width=5)
                
                for i in range(10, min(20, len(songs))):
                    song = songs[i]
                    if not song:
                        continue
                        
                    idx = i + 1
                    title = song.get("title", "Noma'lum")[:60]
                    
                    text_list.append(f"{idx}. {title}")  
                    
                    url = song.get("url", song.get("webpage_url", ""))
                    if url:
                        h = create_hash(url)
                        with open(f"temp/{h}.txt", "w") as f:  
                            f.write(f"{url}|{title}")  
                        
                        markup.add(types.InlineKeyboardButton(str(idx), callback_data=f"song_{h}"))
                
                # NAVIGATSIYA
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
    """Avvalgi sahifaga qaytish"""
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
print("🎵 Instagram/TikTok video → Musiqa topish ISHLAYDI!")
print("🔍 Qo'shiq qidirish + 10 ta natija")
print("⬅️ Orqaga | 🏠 Bosh | Oldinga ➡️")
bot.infinity_polling()
