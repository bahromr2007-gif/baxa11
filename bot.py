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

# ================= TEZ YUKLASH SETTINGLARI =================
# TEZLIK uchun konvertatsiyasiz yuklash
ydl_opts_fast = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(id)s.%(ext)s',  # ID bilan nomlash
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': 30,
    'retries': 3,
    'fragment_retries': 3,
    'continue_dl': True,
    'noplaylist': True,
    'geo_bypass': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '128',  # Pastroq sifat lekin tezroq
    }],
}

# Video yuklash uchun
ydl_opts_video = {
    'format': 'best[filesize<50M]',  # 50MB dan katta bo'lmasin
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'temp/%(id)s.%(ext)s',
    'socket_timeout': 30,
    'retries': 3,
}

# ================= YORDAMCHI FUNKSIYALAR =================
def create_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

def clean_filename(text):
    """Fayl nomini tozalash"""
    # Maxsus belgilarni olib tashlash
    for char in r'<>:"/\|?*':
        text = text.replace(char, '')
    # Bo'sh joylarni pastki chiziqqa almashtirish
    text = text.replace(' ', '_')
    # Qisqartirish
    if len(text) > 40:
        text = text[:40]
    return text

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
                clean_query = clean_filename(f"{artist}_{title}")
                output_file = f"temp/{clean_query}.mp3"
                
                # Agar fayl allaqachon mavjud bo'lsa, o'chirish
                if os.path.exists(output_file):
                    os.remove(output_file)
                
                # Tez yuklash opsiyalari
                fast_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': output_file.replace('.mp3', '.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': 15,
                    'retries': 2,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                    }],
                }
                
                with yt_dlp.YoutubeDL(fast_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                    
                if os.path.exists(output_file):
                    # Audio sifatini tekshirish
                    file_size = os.path.getsize(output_file)
                    if file_size > 1024:  # 1KB dan katta bo'lsa
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
                        bot.edit_message_text(
                            f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Fayl yuklanmadi (hajmi juda kichik)",
                            message.chat.id,
                            msg.message_id
                        )
                else:
                    # Alternativ usul
                    bot.edit_message_text(
                        f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n🔗 {result.get('link', '')}",
                        message.chat.id,
                        msg.message_id
                    )
                    
            except Exception as e:
                bot.edit_message_text(
                    f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n❌ Yuklashda xatolik",
                    message.chat.id,
                    msg.message_id
                )
                print(f"Yuklash xatosi: {e}")
        else:  
            bot.edit_message_text("❌ Musiqa topilmadi", message.chat.id, msg.message_id)  
              
    except Exception as e:  
        bot.reply_to(message, f"❌ Xatolik yuz berdi")

# ================= INSTAGRAM HANDLER =================
@bot.message_handler(func=lambda m: 'instagram.com' in m.text and ('/reel/' in m.text or '/p/' in m.text or '/tv/' in m.text))
def handle_instagram_reel(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 Instagram videoni yuklamoqda...")

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:  
            info = ydl.extract_info(url, download=True)  
            video_id = info.get('id', 'temp')
            filename = f"temp/{video_id}.mp4"
            
            if os.path.exists(filename):
                btn_hash = create_hash(filename)
                markup = types.InlineKeyboardMarkup()  
                markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"insta_{btn_hash}"))  

                with open(filename, 'rb') as f:  
                    bot.send_video(message.chat.id, f, reply_markup=markup)  

                with open(f"temp/{btn_hash}.txt", "w") as f:  
                    f.write(filename)  

            bot.delete_message(message.chat.id, msg.message_id)  

    except Exception as e:  
        bot.reply_to(message, "❌ Instagram video yuklanmadi")

# ================= TIKTOK HANDLER =================
@bot.message_handler(func=lambda m: 'tiktok.com' in m.text)
def handle_tiktok(message):
    try:
        url = message.text.strip()
        msg = bot.reply_to(message, "📱 TikTok videoni yuklamoqda...")

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:  
            info = ydl.extract_info(url, download=True)  
            video_id = info.get('id', 'temp')
            filename = f"temp/{video_id}.mp4"
            
            if os.path.exists(filename):
                btn_hash = create_hash(filename)
                markup = types.InlineKeyboardMarkup()  
                markup.add(types.InlineKeyboardButton("🎵 Musiqani aniqlash", callback_data=f"tiktok_{btn_hash}"))  

                with open(filename, 'rb') as f:  
                    bot.send_video(message.chat.id, f, reply_markup=markup)  

                with open(f"temp/{btn_hash}.txt", "w") as f:  
                    f.write(filename)  

            bot.delete_message(message.chat.id, msg.message_id)  

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

        # FAQDAS 10 soniya audio (tezroq)
        short_audio_path = video_path.replace('.mp4', '_short.mp3')  
        subprocess.run([  
            'ffmpeg', '-i', video_path, '-t', '10', '-vn', '-acodec', 'mp3', '-y', short_audio_path  
        ], capture_output=True, timeout=30)  

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
                clean_query = clean_filename(f"{artist}_{title}")
                output_file = f"temp/{clean_query}.mp3"
                
                # Tez yuklash
                fast_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': output_file.replace('.mp3', '.%(ext)s'),
                    'quiet': True,
                    'socket_timeout': 15,
                    'retries': 2,
                }
                
                with yt_dlp.YoutubeDL(fast_opts) as ydl:
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
                    
            except Exception as e:
                bot.send_message(call.message.chat.id, f"✅ Musiqa topildi!\n🎵 {title}\n👤 {artist}\n\n🔗 {result.get('link', '')}")
        else:  
            bot.send_message(call.message.chat.id, "❌ Musiqa topilmadi")  

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Xatolik yuz berdi")
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
    if "instagram.com" in query or "tiktok.com" in query:  
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
            songs = info['entries']  

        if not songs:
            bot.edit_message_text("❌ Hech qanday natija topilmadi", message.chat.id, msg.message_id)
            return

        # Matn ro'yxati  
        text_list = [f"🔍 '{query}' uchun natijalar:\n"]  
        markup = types.InlineKeyboardMarkup(row_width=5)  
        buttons = []  

        for i, song in enumerate(songs, 1):  
            title = song.get("title", "Noma'lum")[:50]
            duration = song.get("duration", 0)  
            if duration:  
                m, s = divmod(duration, 60)  
                time_str = f" ({m}:{s:02d})"  
            else:  
                time_str = ""  
            
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
        bot.edit_message_text(f"❌ Xatolik: {str(e)[:100]}", message.chat.id, msg.message_id)

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
        
        opts = {  
            'format': 'bestaudio/best',
            'outtmpl': output_file.replace('.mp3', '.%(ext)s'),  
            'quiet': True,  
            'socket_timeout': 15,
            'retries': 2,
            'postprocessors': [{  
                'key': 'FFmpegExtractAudio',  
                'preferredcodec': 'mp3',  
            }]  
        }  

        with yt_dlp.YoutubeDL(opts) as ydl:  
            ydl.download([url])  

        if os.path.exists(output_file):
            with open(output_file, 'rb') as f:  
                bot.send_audio(call.message.chat.id, f, title=title[:64])  

            os.remove(output_file)  
            os.remove(f"temp/{h}.txt")  
        else:
            # Agar .mp3 fayl topilmasa, boshqa formatda qidirish
            for file in os.listdir("temp"):
                if file.startswith(clean_title[:20]) and file.endswith(('.mp3', '.m4a', '.webm')):
                    full_path = os.path.join("temp", file)
                    with open(full_path, 'rb') as f:  
                        bot.send_audio(call.message.chat.id, f, title=title[:64])  
                    os.remove(full_path)
                    os.remove(f"temp/{h}.txt")
                    break

    except Exception as e:  
        bot.send_message(call.message.chat.id, f"❌ Yuklashda xatolik")

# ================= BOT ISHGA TUSHDI =================
print("✅ BOT ISHGA TUSHDI!")
print("🎵 TEZ YUKLASH VA TO'G'RI NOM BERISH FAOL")
bot.infinity_polling()
