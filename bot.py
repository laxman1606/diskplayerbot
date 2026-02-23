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
# 1. BYTE-PERFECT STREAMING ROUTE (Sabse Zaroori Hissa)
# =================================================================
@routes.get("/stream/{chat_id}/{message_id}")
async def stream_handler(request):
    try:
        chat_id = int(request.match_info['chat_id'])
        message_id = int(request.match_info['message_id'])
        
        try:
            message = await app.get_messages(chat_id, message_id)
        except Exception:
            return web.Response(status=404, text="File Not Found")

        media = message.video or message.document or message.audio
        if not media:
            return web.Response(status=400, text="No Media Found")

        file_name = getattr(media, "file_name", "video.mp4") or "video.mp4"
        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"
        file_size = getattr(media, "file_size", 0)

        # --- MATH FIX: Kitna Bhejna Hai? ---
        req_start = 0
        req_end = file_size - 1

        range_header = request.headers.get('Range')
        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                req_start = int(match.group(1))
                if match.group(2):
                    req_end = int(match.group(2))

        # Agar exo player ne limit ke bahar manga toh error 416 do
        if req_start > req_end or req_start >= file_size:
            return web.Response(status=416, text="Requested Range Not Satisfiable")

        length = req_end - req_start + 1

        # --- BYTE COUNTER GENERATOR ---
        async def file_generator():
            bytes_sent = 0
            try:
                # App.stream_media se data lena shuru karo
                async for chunk in app.stream_media(message, offset=req_start, limit=length):
                    chunk_len = len(chunk)
                    
                    # Agar agla chunk bhejkar length limit cross ho rahi hai, toh use kaat do (slice)
                    if bytes_sent + chunk_len > length:
                        remaining_bytes = length - bytes_sent
                        yield chunk[:remaining_bytes]
                        break # Limit poori, loop band
                    
                    yield chunk
                    bytes_sent += chunk_len
                    
            except asyncio.CancelledError:
                pass # Agar user ne video skip/band kiya, toh chupchap stop karo
            except Exception as e:
                logger.error(f"Stream error: {e}")

        # --- HEADERS --- (ExoPlayer ko yahi dekh kar pata chalta hai ki video sahi aayega)
        headers = {
            'Content-Type': mime_type,
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {req_start}-{req_end}/{file_size}',
            'Content-Length': str(length),
            'Content-Disposition': f'inline; filename="{file_name}"',
            'Access-Control-Allow-Origin': '*'
        }

        status_code = 206 if range_header else 200

        return web.Response(
            body=file_generator(),
            headers=headers,
            status=status_code
        )
    except Exception as e:
        logger.error(f"Handler Error: {e}")
        return web.Response(status=500, text="Server Error")

# =================================================================
# 2. REDIRECT ROUTE (Middleman Page)
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
        <a href="{app_deep_link}">Open App Manually</a>
        <script>window.location.href = "{app_deep_link}";</script>
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

        await message.reply_text(
            f"✅ **Ready to Watch!**\n\n📂 `{file_name}`\n\nClick below to play in app!",
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
