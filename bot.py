import os
import logging
import asyncio
import urllib.parse
import re
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
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0")) # Naya
except (ValueError, TypeError):
    logging.error("FATAL: API_ID or LOG_CHANNEL is not valid.")
    exit(1)

API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION") # Naya
PUBLIC_URL = os.environ.get("PUBLIC_URL")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists("sessions"):
    os.makedirs("sessions")

# =================================================================
# 🚀 2 ENGINES SETUP (DiskWala Trick)
# bot_app: Message bhejega.
# user_app: 2GB ki file stream karega.
# =================================================================
bot_app = Client("sessions/Bot_Engine", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("sessions/User_Engine", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

routes = web.RouteTableDef()

@routes.get("/")
async def status_check(request):
    return web.Response(text="✅ Bot & Server Online! (2GB Streaming Enabled)")

# =================================================================
# 1. ADVANCED STREAMING ROUTE (Yahan User Account kaam karega)
# =================================================================
@routes.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        message_id = int(request.match_info['message_id'])
        
        # User account video uthayega taaki 50MB limit na lage
        message = await user_app.get_messages(chat_id, message_id)
        media = message.video or message.document or message.audio
        
        if not media:
            return web.Response(status=404, text="No Media Found")

        file_size = getattr(media, "file_size", 0)
        file_name = getattr(media, "file_name", "video.mp4") or "video.mp4"
        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"

        # Chrome/App ko force karo ki ye Video hi hai
        if "video" not in mime_type:
            mime_type = "video/mp4"

        # --- VIDEO KO TUKDO MEIN BHEJNE KA LOGIC (Range Request) ---
        range_header = request.headers.get('Range', '')
        start = 0
        end = file_size - 1

        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))

        if start >= file_size:
            return web.Response(status=416, text="Requested Range Not Satisfiable")

        length = end - start + 1

        # Professional Stream Response (Ye crash nahi hone dega)
        response = web.StreamResponse(
            status=206 if range_header else 200,
            headers={
                'Content-Type': mime_type,
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Content-Length': str(length),
                'Content-Disposition': f'inline; filename="{file_name}"',
                'Access-Control-Allow-Origin': '*'
            }
        )
        await response.prepare(request)

        try:
            bytes_sent = 0
            async for chunk in user_app.stream_media(message, offset=start):
                if bytes_sent + len(chunk) > length:
                    chunk = chunk[:length - bytes_sent]
                
                await response.write(chunk)
                bytes_sent += len(chunk)
                
                if bytes_sent >= length:
                    break
        except asyncio.CancelledError:
            pass # App band kiya
        except Exception as e:
            logger.error(f"Stream interrupted: {e}")

        return response
    except Exception as e:
        logger.error(f"Handler Error: {e}")
        return web.Response(status=500, text="Server Error")

# =================================================================
# 2. REDIRECT ROUTE (TeraBox wala Magic Page - Same to same)
# =================================================================
@routes.get("/watch/{chat_id}/{message_id}")
async def watch_redirect(request):
    chat_id = request.match_info['chat_id']
    message_id = request.match_info['message_id']
    stream_link = f"{PUBLIC_URL}/stream/{chat_id}/{message_id}"
    app_deep_link = f"{WEB_APP_URL}?url={urllib.parse.quote(stream_link)}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Opening App...</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding-top: 50px; background-color: #121212; color: white; }}
            .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            a {{ color: #3498db; text-decoration: none; padding: 10px 20px; border: 1px solid #3498db; border-radius: 5px; display: inline-block; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h2>Opening in DiskPlayer App...</h2>
        <div class="loader"></div>
        <p>If the app does not open automatically, click below:</p>
        <a href="{app_deep_link}">Open App Manually</a>
        <script>window.location.href = "{app_deep_link}";</script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

# --- BOT COMMANDS ---
@bot_app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(f"👋 **Bot Started!**\n\nServer Link: `{PUBLIC_URL}`\nWaiting for files...")

@bot_app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def media_handler(client, message):
    if not PUBLIC_URL or not WEB_APP_URL or not STRING_SESSION or LOG_CHANNEL == 0:
        return await message.reply_text("🔴 ERROR: Settings missing in Render.")

    try:
        media = message.video or message.document or message.audio
        if not media: return
        file_name = getattr(media, "file_name", "video") or "video"

        # ⚠️ Yahan Bot file ko Log Channel mein copy karega
        copied_msg = await message.copy(chat_id=LOG_CHANNEL)
        
        # Link ab Log Channel se banega
        watch_link = f"{PUBLIC_URL}/watch/{LOG_CHANNEL}/{copied_msg.id}"

        # Aapka TeraBox jaisa Copy karne wala Message
        text = f"**{file_name}**\n\n"
        text += f"**Watch Video / Download:**\n"
        text += f"`{watch_link}`\n\n"
        text += f"👆 *Click the link above to watch in DiskPlayer app or copy it to share!*"

        await message.reply_text(
            text, disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Watch in App", url=watch_link)]])
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text(f"😥 Error: {e}")

# --- RUNNER ---
async def start_services():
    app_runner = web.AppRunner(web.Application(client_max_size=1024**3))
    app_runner.app.add_routes(routes)
    await app_runner.setup()
    site = web.TCPSite(app_runner, HOST, PORT)
    await site.start()
    logger.info(f"✅ Web Server running")

    # Dono start honge
    await bot_app.start()
    await user_app.start()
    logger.info("✅ Telegram Bot & User Engine Started")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(start_services())
