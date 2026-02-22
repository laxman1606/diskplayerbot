import os
import logging
import asyncio
import urllib.parse
from aiohttp import web

# --- 🛠️ LOOP FIX ---
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- ⚙️ CONFIGURATION (SAFE VERSION) ---
try:
    API_ID = int(os.environ.get("API_ID", "0"))
except (ValueError, TypeError):
    logging.error("FATAL: API_ID is not a valid integer. Please check your environment variables.")
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

        async def file_generator():
            try:
                async for chunk in app.stream_media(message):
                    yield chunk
            except Exception as e:
                logger.error(f"Stream interrupted: {e}")

        return web.Response(
            body=file_generator(),
            headers={
                'Content-Type': mime_type,
                'Content-Disposition': f'inline; filename="{file_name}"',
                'Content-Length': str(file_size),
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        logger.error(f"Handler Error: {e}")
        return web.Response(status=500, text="Server Error")

# --- BOT COMMANDS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        f"👋 **Bot Started!**\n\nServer Link: `{PUBLIC_URL}`\nWaiting for files..."
    )

@app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def media_handler(client, message):
    # =================================================================
    # === FINAL, SUPER-SMART CHECK ===
    # =================================================================
    error_message = ""
    # Check 1: Kya PUBLIC_URL set hai aur sahi format mein hai?
    if not PUBLIC_URL or not PUBLIC_URL.startswith("http"):
        error_message += f"🔴 **PUBLIC_URL Galat Hai!**\n\n"
        error_message += f"**Aapki Value:** `{PUBLIC_URL}`\n"
        error_message += f"**Sahi Value Aisi Honi Chahiye:** `https://diskplayerbot.onrender.com`\n\n"

    # Check 2: Kya WEB_APP_URL set hai aur sahi format mein hai?
    if not WEB_APP_URL or "://" not in WEB_APP_URL:
        error_message += f"🔴 **WEB_APP_URL Galat Hai!**\n\n"
        error_message += f"**Aapki Value:** `{WEB_APP_URL}`\n"
        error_message += f"**Sahi Value Aisi Honi Chahiye:** `myvideoplayer://play`"

    # Agar koi bhi error mila, toh user ko batao aur ruk jao
    if error_message:
        return await message.reply_text(
            "**CONFIGURATION ERROR!**\n\n"
            "Admin, please fix these issues in your Render Environment Variables:\n\n"
            f"----------------------------------------\n{error_message}"
        )
    # =================================================================

    try:
        chat_id = message.chat.id
        msg_id = message.id
        media = message.video or message.document or message.audio
        
        if not media: return

        file_name = getattr(media, "file_name", "file") or "file"
        
        stream_link = f"{PUBLIC_URL}/stream/{chat_id}/{msg_id}"
        app_deep_link = f"{WEB_APP_URL}?url={urllib.parse.quote(stream_link)}"

        await message.reply_text(
            f"✅ **Link Generated!**\n\n"
            f"📂 `{file_name}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Watch in App", url=app_deep_link)]
            ])
        )
    except Exception as e:
        logger.error(f"Error in media_handler: {e}")
        await message.reply_text("😥 Oops! Something unexpected went wrong. Please check logs.")

# --- RUNNER ---
async def start_services():
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        logger.error("FATAL: Essential environment variables (API_ID, API_HASH, BOT_TOKEN) are missing. Exiting.")
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
    try:
        loop.run_until_complete(start_services())
    except Exception as e:
        logger.error(f"FATAL CRASH on startup: {e}")
