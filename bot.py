import os
import logging
import asyncio
import urllib.parse
import re
import time
from aiohttp import web

# --- 🛠️ LOOP FIX ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- ⚙️ CONFIGURATION ---
try:
    API_ID = int(os.environ.get("API_ID", "0"))
    log_channel_str = os.environ.get("LOG_CHANNEL", "0").strip()
    if log_channel_str and not log_channel_str.startswith("-100"):
        log_channel_str = "-100" + log_channel_str
    LOG_CHANNEL = int(log_channel_str)
except (ValueError, TypeError):
    logging.error("FATAL: API_ID or LOG_CHANNEL is invalid.")
    exit(1)

API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").strip().rstrip('/')
WEB_APP_URL = os.environ.get("WEB_APP_URL", "playbox://play").strip()
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

WELCOME_IMAGE = "https://telegra.ph/file/a1c1d85e7a9b09be8b082.jpg"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists("sessions"):
    os.makedirs("sessions")

# 🚀 DUAL ENGINE SETUP
bot_app = Client("sessions/Bot_Engine", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("sessions/User_Engine", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

routes = web.RouteTableDef()

@routes.get("/")
async def status_check(request):
    return web.Response(text="✅ PlayBox 10000x Mega Server is Live & Crash-Proof!")

# =================================================================
# 🚀 1. SUPER OPTIMIZED STREAMING (RAM Bachaane Wala Code)
# =================================================================
@routes.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        message_id = int(request.match_info['message_id'])
        
        message = await user_app.get_messages(chat_id, message_id)
        if not message or message.empty: return web.Response(status=404, text="Message Not Found")
        
        media = message.video or message.document or message.audio
        if not media: return web.Response(status=404, text="No Media")

        file_size = getattr(media, "file_size", 0)
        file_name = getattr(media, "file_name", "video.mp4") or "video.mp4"
        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"
        if "video" not in mime_type.lower(): mime_type = "video/mp4"

        range_header = request.headers.get('Range', '')
        start = 0
        end = file_size - 1

        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                if match.group(2): end = int(match.group(2))

        if start >= file_size: return web.Response(status=416, text="Requested Range Not Satisfiable")
        length = end - start + 1

        headers = {
            'Content-Type': mime_type,
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': str(length),
            'Content-Disposition': f'inline; filename="{file_name}"',
            'Access-Control-Allow-Origin': '*'
        }
        
        response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
        await response.prepare(request)

        try:
            # 🚀 MEMORY FIX: Aiohttp direct pipe
            async for chunk in user_app.stream_media(message, offset=start, limit=length):
                await response.write(chunk)
        except (asyncio.CancelledError, ConnectionResetError):
            pass # User ne app band kiya, server ko farq nahi padega
        except Exception as e:
            logger.error(f"Stream error: {e}")

        return response
    except Exception as e:
        return web.Response(status=500, text=f"Error: {e}")

# =================================================================
# 🚀 2. DOWNLOAD ROUTE (Bina Crash Wala)
# =================================================================
@routes.get("/download/{chat_id}/{message_id}")
async def download_handler(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        message_id = int(request.match_info['message_id'])
        message = await user_app.get_messages(chat_id, message_id)
        media = message.video or message.document or message.audio
        file_name = getattr(media, "file_name", "PlayBox_Video.mp4") or "PlayBox_Video.mp4"
        file_size = getattr(media, "file_size", 0)

        headers = {
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{file_name}"',
            'Content-Length': str(file_size),
            'Access-Control-Allow-Origin': '*'
        }
        
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)

        try:
            async for chunk in user_app.stream_media(message):
                await response.write(chunk)
        except (asyncio.CancelledError, ConnectionResetError): pass

        return response
    except Exception:
        return web.Response(status=500, text="Download Error")

# =================================================================
# 🚀 3. SMART REDIRECT ROUTE
# =================================================================
@routes.get("/watch/{chat_id}/{message_id}")
async def watch_redirect(request):
    chat_id = request.match_info['chat_id']
    message_id = request.match_info['message_id']
    stream_link = f"{PUBLIC_URL}/stream/{chat_id}/{message_id}"
    
    # 💯 PRO ANDROID INTENT
    android_intent = f"intent://play?url={urllib.parse.quote(stream_link)}#Intent;scheme=myvideoplayer;package=com.playbox.app;end;"
    apk_download_link = "https://your-website.com/PlayBox.apk" 

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PlayBox - Ultra HD</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; text-align: center; background-color: #0A0C10; color: white; padding-top: 50px; }}
            .logo {{ font-size: 36px; font-weight: bold; color: #1976D2; margin-bottom: 5px; }}
            .loader {{ border: 4px solid #1A1D1E; border-top: 4px solid #1976D2; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            .btn {{ background-color: #1976D2; color: white; text-decoration: none; padding: 15px 30px; border-radius: 30px; display: inline-block; margin-top: 25px; font-weight: bold; }}
            .btn-secondary {{ background-color: transparent; border: 2px solid #00E676; color: #00E676; margin-top: 10px; }}
            #fallback {{ display: none; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="logo">▶ PlayBox</div>
        <p style="color:#8A8D93;">Ultra HD Video Player</p>
        <h3 id="status">Redirecting to App...</h3>
        <div class="loader" id="load-icon"></div>
        <a href="{android_intent}" class="btn" id="open-btn">Open in PlayBox App</a>
        
        <div id="fallback">
            <p style="color: #FF1744;">App Not Installed?</p>
            <a href="{apk_download_link}" class="btn btn-secondary">⬇ Download PlayBox APK</a>
        </div>
        <script>
            window.location.href = "{android_intent}";
            setTimeout(function() {{
                document.getElementById('status').style.display = 'none';
                document.getElementById('load-icon').style.display = 'none';
                document.getElementById('fallback').style.display = 'block';
            }}, 2500); 
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

# =================================================================
# 🤖 BOT COMMANDS
# =================================================================

@bot_app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    text = f"👋 **Hello {message.from_user.first_name}! Welcome to PlayBox Pro.**\n\n"
    text += f"🆔 **Your ID:** `{message.from_user.id}`\n"
    text += f"⚙️ **Status:** `Premium Active 👑`\n\n"
    text += f"Send me any Movie or Video file, and I will generate an **Ultra HD Streaming Link** for you. 🚀"

    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Help Menu", callback_data="help")]])
    try:
        await message.reply_photo(photo=WELCOME_IMAGE, caption=text, reply_markup=buttons)
    except Exception:
        await message.reply_text(text, reply_markup=buttons)

@bot_app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    await message.reply_text("**🛠 PlayBox Help Menu:**\n\n1. Send any MKV/MP4 video.\n2. Get an instant secure link.\n3. Watch seamlessly without downloading.")

@bot_app.on_message(filters.command("ping") & filters.private)
async def ping_cmd(client, message):
    start_time = time.time()
    msg = await message.reply_text("Pinging Servers...")
    end_time = time.time()
    await msg.edit_text(f"🏓 **Pong!**\nSpeed: `{round((end_time - start_time) * 1000)}ms`")

@bot_app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def media_handler(client, message):
    if not PUBLIC_URL or not STRING_SESSION or LOG_CHANNEL == 0:
        return await message.reply_text("🔴 ERROR: Backend env variables missing.")

    try:
        processing_msg = await message.reply_text("⏳ `Extracting & Generating Link...`")
        
        media = message.video or message.document or message.audio
        if not media: 
            return await processing_msg.edit_text("❌ No valid media found.")
            
        file_name = getattr(media, "file_name", "PlayBox_Video.mp4") or "PlayBox_Video.mp4"
        try:
            size_mb = round(getattr(media, "file_size", 0) / (1024 * 1024), 2)
        except:
            size_mb = 0

        # Safe forward to LOG CHANNEL
        try:
            copied_msg = await message.copy(chat_id=LOG_CHANNEL)
        except Exception as e:
            return await processing_msg.edit_text(f"❌ Error copying to Log Channel: {e}")

        # LINKS GENERATION
        watch_link = f"{PUBLIC_URL}/watch/{LOG_CHANNEL}/{copied_msg.id}"
        download_link = f"{PUBLIC_URL}/download/{LOG_CHANNEL}/{copied_msg.id}"

        # DISKWALA STYLE TEXT FORMAT
        text = f"**{file_name}**\n"
        text += f"💾 **Size:** `{size_mb} MB`\n\n"
        text += f"🔗 **PlayBox Link:**\n[{watch_link}]({watch_link})\n\n"
        text += f"PlayBox offers Ultra HD Ad-Free video streaming."

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Watch in PlayBox", url=watch_link)],
            [InlineKeyboardButton("📥 Download File", url=download_link)]
        ])

        # 🚀 THE ULTIMATE THUMBNAIL CRASH FIX 🚀
        thumb_path = None
        if getattr(media, "thumbs", None) and len(media.thumbs) > 0:
            try:
                # Agar thumbnail aaram se download hua toh theek
                thumb_path = await bot_app.download_media(media.thumbs[0].file_id)
            except Exception as thumb_error:
                # Agar "0 B" wala error aaya, toh ignore kardo, crash mat ho!
                logger.warning(f"Thumbnail failed (0 B Error ignored): {thumb_error}")
                thumb_path = None

        await processing_msg.delete()
        
        # Agar photo mili toh photo ke sath bhejo
        if thumb_path and os.path.exists(thumb_path):
            await message.reply_photo(photo=thumb_path, caption=text, reply_markup=buttons)
            os.remove(thumb_path) # Memory saaf karo
        else:
            # Agar photo nahi mili toh sirf Text aur Link bhejo, par ruko mat!
            await message.reply_text(text, disable_web_page_preview=False, reply_markup=buttons)

    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text(f"😥 Error generating link: {e}")

# --- RUNNER ---
async def start_services():
    # Max size badha di taaki heavy files accept hon
    app_runner = web.AppRunner(web.Application(client_max_size=1024**3))
    app_runner.app.add_routes(routes)
    await app_runner.setup()
    site = web.TCPSite(app_runner, HOST, PORT)
    await site.start()
    logger.info("✅ Web Server running")
    
    await bot_app.start()
    await user_app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(start_services())
