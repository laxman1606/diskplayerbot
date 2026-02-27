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
from pyrogram.errors import ChatAdminRequired, ChannelInvalid

# --- ⚙️ CONFIGURATION ---
try:
    API_ID = int(os.environ.get("API_ID", "0"))
    # Ensure LOG_CHANNEL is treated as an integer and starts with -100 if it's a channel
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists("sessions"):
    os.makedirs("sessions")

# DUAL ENGINE
bot_app = Client("sessions/Bot_Engine", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("sessions/User_Engine", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

routes = web.RouteTableDef()

# --- WEB SERVER ROUTES ---
@routes.get("/")
async def status_check(request):
    return web.Response(text="✅ PlayBox 1000x Server is Live!")

@routes.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        message_id = int(request.match_info['message_id'])
        
        message = await user_app.get_messages(chat_id, message_id)
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

        async def file_generator():
            try:
                async for chunk in user_app.stream_media(message, offset=start, limit=length): yield chunk
            except asyncio.CancelledError: pass
            except Exception as e: logger.error(f"Stream error: {e}")

        headers = {
            'Content-Type': mime_type,
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': str(length),
            'Content-Disposition': f'inline; filename="{file_name}"',
            'Access-Control-Allow-Origin': '*'
        }
        return web.Response(body=file_generator(), headers=headers, status=206 if range_header else 200)
    except Exception as e:
        return web.Response(status=500, text=f"Error: {e}")

@routes.get("/watch/{chat_id}/{message_id}")
async def watch_redirect(request):
    chat_id = request.match_info['chat_id']
    message_id = request.match_info['message_id']
    stream_link = f"{PUBLIC_URL}/stream/{chat_id}/{message_id}"
    app_deep_link = f"{WEB_APP_URL}?url={urllib.parse.quote(stream_link)}"
    
    apk_download_link = "https://your-website.com/PlayBox.apk" # Isko baad me update kar dena

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PlayBox - Ultra HD</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background-color: #0A0C10; color: white; padding-top: 50px; margin: 0; }}
            .container {{ padding: 20px; }}
            .logo {{ font-size: 36px; font-weight: bold; color: #1976D2; margin-bottom: 5px; }}
            .loader {{ border: 4px solid #1A1D1E; border-top: 4px solid #1976D2; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            .btn {{ background-color: #1976D2; color: white; text-decoration: none; padding: 15px 30px; border-radius: 30px; display: inline-block; margin-top: 25px; font-weight: bold; font-size: 16px; }}
            .btn-secondary {{ background-color: transparent; border: 2px solid #00E676; color: #00E676; }}
            #fallback {{ display: none; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">▶ PlayBox</div>
            <p style="color:#8A8D93;">Ultra HD Video Player</p>
            <h3 id="status">Redirecting to App...</h3>
            <div class="loader" id="load-icon"></div>
            <a href="{app_deep_link}" class="btn" id="open-btn">Open in PlayBox</a>
            
            <div id="fallback">
                <p style="color: #FF1744;">App Not Installed?</p>
                <a href="{apk_download_link}" class="btn btn-secondary">⬇ Download PlayBox APK</a>
            </div>
        </div>
        <script>
            window.location.href = "{app_deep_link}";
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
# 🚀 ADVANCED BOT COMMANDS 
# =================================================================

@bot_app.on_message(filters.command("start"))
async def start(client, message):
    text = f"👋 **Welcome to PlayBox Pro!**\n\nSend me any Video or Document, and I will generate an **Ultra HD High-Speed Streaming Link** for you.\n\nUse /help to see all features."
    await message.reply_text(text)

@bot_app.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = "**🛠 PlayBox Help Menu:**\n\n1. Send any MKV, MP4 video.\n2. Get an instant secure link.\n3. Watch seamlessly without downloading.\n\n`Dev: 1000x Advance Setup`"
    await message.reply_text(text)

@bot_app.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    start_time = time.time()
    msg = await message.reply_text("Pinging...")
    end_time = time.time()
    await msg.edit_text(f"🏓 **Pong!**\nServer Speed: `{round((end_time - start_time) * 1000)}ms`\nStatus: `Ultra Fast 🚀`")

@bot_app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def media_handler(client, message):
    # Safe check variables
    if not PUBLIC_URL or not WEB_APP_URL or not STRING_SESSION or LOG_CHANNEL == 0:
        return await message.reply_text("🔴 ERROR: Backend not configured. (Check ENV Variables)")

    try:
        processing_msg = await message.reply_text("⏳ `Encrypting and Uploading to PlayBox Servers...`")
        
        media = message.video or message.document or message.audio
        if not media: 
            await processing_msg.edit_text("❌ No valid media found.")
            return
            
        # Fallback for file_name
        try:
            file_name = getattr(media, "file_name", "PlayBox_Video.mp4")
            if not file_name: file_name = "PlayBox_Video.mp4"
        except Exception:
            file_name = "PlayBox_Video.mp4"
        
        # Calculate Size
        try:
            size_mb = getattr(media, "file_size", 0) / (1024 * 1024)
        except:
            size_mb = 0

        # 🚀 FIX: TRY TO COPY TO LOG CHANNEL SAFELY
        try:
            copied_msg = await message.copy(chat_id=LOG_CHANNEL)
        except ChatAdminRequired:
            await processing_msg.edit_text("❌ ERROR: Bot is not an Admin in the LOG_CHANNEL.")
            return
        except ChannelInvalid:
            await processing_msg.edit_text("❌ ERROR: The LOG_CHANNEL ID is invalid or Bot is not a member.")
            return
        except Exception as e:
            await processing_msg.edit_text(f"❌ ERROR copying to channel: {e}")
            return

        watch_link = f"{PUBLIC_URL}/watch/{LOG_CHANNEL}/{copied_msg.id}"

        # 🚀 THE TERABOX STYLE BLUE LINK FORMAT 🚀
        text = f"[{watch_link}]({watch_link})\n\n"
        text += f"**playbox.app**\n"
        text += f"**{file_name}** - Shared via PlayBox\n\n"
        text += f"PlayBox offers Ultra HD Ad-Free video streaming. Download the app for secure storage and file sharing anytime, anywhere."

        await processing_msg.delete()
        await message.reply_text(
            text, 
            disable_web_page_preview=False, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Watch Online", url=watch_link)]])
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text(f"😥 Error generating link: {e}")

# --- RUNNER ---
async def start_services():
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
