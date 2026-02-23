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
except (ValueError, TypeError):
    logging.error("FATAL: API_ID is not a valid integer.")
    exit(1)

API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
WEB_APP_URL = os.environ.get("WEB_APP_URL")
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- BOT SETUP ---
if not os.path.exists("sessions"):
    os.makedirs("sessions")

app = Client(
    "sessions/DiskWala_Render",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- WEB SERVER ---
routes = web.RouteTableDef()

@routes.get("/")
async def status_check(request):
    return web.Response(text="✅ Bot & Server Online!")

# =================================================================
# 1. ADVANCED DIRECT STREAMING ROUTE (ExoPlayer ke liye best)
# =================================================================
@routes.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        message_id = int(request.match_info['message_id'])
        
        message = await app.get_messages(chat_id, message_id)
        media = message.video or message.document or message.audio
        
        if not media:
            return web.Response(status=404, text="Media Not Found")

        file_size = getattr(media, "file_size", 0)
        file_name = getattr(media, "file_name", "video.mp4") or "video.mp4"
        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"

        # Range Logic
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

        # NAYA TAAQATWAR STREAM RESPONSE (Yeh atakne nahi dega)
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
            # Direct socket stream
            async for chunk in app.stream_media(message, offset=start, limit=length):
                await response.write(chunk)
        except asyncio.CancelledError:
            pass # User ne app band kar diya
        except Exception as e:
            logger.error(f"Stream error: {e}")

        return response
    except Exception as e:
        logger.error(f"Handler Error: {e}")
        return web.Response(status=500, text="Server Error")

# =================================================================
# 2. REDIRECT ROUTE (TeraBox Style Webpage)
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
        <title>DiskWala Player</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background-color: #121415; color: white; padding-top: 50px; margin: 0; }}
            .container {{ padding: 20px; }}
            .logo {{ font-size: 30px; font-weight: bold; color: #0B8A68; margin-bottom: 20px; }}
            .loader {{ border: 4px solid #1A1D1E; border-top: 4px solid #0B8A68; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 30px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            .btn {{ background-color: #0B8A68; color: white; text-decoration: none; padding: 12px 24px; border-radius: 25px; display: inline-block; margin-top: 20px; font-weight: bold; }}
            p {{ color: #A0A0A0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">DiskWala</div>
            <h2>Redirecting to App...</h2>
            <div class="loader"></div>
            <p>If the app doesn't open automatically,<br>please click the button below.</p>
            <a href="{app_deep_link}" class="btn">Open in DiskWala App</a>
        </div>
        <script>setTimeout(function() {{ window.location.href = "{app_deep_link}"; }}, 500);</script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

# --- BOT COMMANDS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(f"👋 **Bot Started!**\n\nServer Link: `{PUBLIC_URL}`\nWaiting for files...")

@app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def media_handler(client, message):
    if not PUBLIC_URL or not WEB_APP_URL:
        return await message.reply_text("🔴 ERROR: PUBLIC_URL or WEB_APP_URL is missing in Render Settings.")

    try:
        chat_id = message.chat.id
        msg_id = message.id
        media = message.video or message.document or message.audio
        if not media: return
        file_name = getattr(media, "file_name", "video") or "video"
        
        watch_link = f"{PUBLIC_URL}/watch/{chat_id}/{msg_id}"
        text = f"**{file_name}**\n\n**Watch Video / Download:**\n`{watch_link}`\n\n👆 *Click the link above to watch in DiskPlayer app or copy it to share!*"

        await message.reply_text(
            text, disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Watch in App", url=watch_link)]])
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text("😥 Error generating link.")

# --- RUNNER ---
async def start_services():
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        logger.error("FATAL: Essential variables missing. Exiting.")
        return
    app_runner = web.AppRunner(web.Application(client_max_size=1024**3))
    app_runner.app.add_routes(routes)
    await app_runner.setup()
    site = web.TCPSite(app_runner, HOST, PORT)
    await site.start()
    logger.info(f"✅ Web Server running on Port {PORT}")
    await app.start()
    logger.info("✅ Telegram Bot Started")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(start_services())
