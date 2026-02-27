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

# 1. STREAMING ROUTE (Aapka original working code)
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
# =================================================================
# 2. REDIRECT ROUTE (SMART TERABOX/MX PLAYER STYLE)
# =================================================================
@routes.get("/watch/{chat_id}/{message_id}")
async def watch_redirect(request):
    chat_id = request.match_info['chat_id']
    message_id = request.match_info['message_id']
    stream_link = f"{PUBLIC_URL}/stream/{chat_id}/{message_id}"
    app_deep_link = f"{WEB_APP_URL}?url={urllib.parse.quote(stream_link)}"
    
    # 🚀 YAHAN APNA DIRECT APK DOWNLOAD LINK DAALEIN 🚀
    # (Jab app Play Store par aa jayega, tab isko Play Store ke link se badal dena)
    apk_download_link = "https://drive.google.com/file/d/1L0LmQ4PmQAtQs1YLibJ-IcpA-hvwN9_Q/view?usp=drivesdk" 

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PlayBox - Ultra HD Player</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background-color: #0A0C10; color: white; padding-top: 50px; margin: 0; }}
            .container {{ padding: 20px; }}
            .logo {{ font-size: 32px; font-weight: bold; color: #FF6F00; margin-bottom: 5px; }}
            .sub-logo {{ font-size: 14px; color: #00E676; margin-bottom: 30px; }}
            .loader {{ border: 4px solid #1A1D1E; border-top: 4px solid #FF6F00; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            .btn {{ background-color: #FF6F00; color: white; text-decoration: none; padding: 15px 30px; border-radius: 30px; display: inline-block; margin-top: 25px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 6px rgba(255,111,0,0.3); }}
            .btn-secondary {{ background-color: #1A1D1E; border: 1px solid #FF6F00; color: #FF6F00; margin-top: 15px; }}
            p {{ color: #A0A0A0; font-size: 14px; line-height: 1.5; margin-top: 20px; }}
            #fallback-msg {{ display: none; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">PlayBox</div>
            <div class="sub-logo">Ultra HD Video Player</div>
            
            <h2 id="status-text">Opening App...</h2>
            <div class="loader" id="loader"></div>
            
            <p>If the app doesn't open automatically,<br>please click the button below.</p>
            <a href="{app_deep_link}" class="btn">▶ Open in PlayBox App</a>

            <!-- 🚀 SMART FALLBACK LOGIC (Jo dikhega jab app nahi hoga) -->
            <div id="fallback-msg">
                <p style="color: #FF1744; font-weight: bold;">App Not Found!</p>
                <p>Looks like you don't have PlayBox installed.<br>Download it now to watch this video in Ultra HD.</p>
                <a href="{apk_download_link}" class="btn btn-secondary">⬇ Download PlayBox App</a>
            </div>
        </div>

        <script>
            // Ye script jaadu karegi!
            // 1. Pehle App kholne ki koshish karegi
            window.location.href = "{app_deep_link}";

            // 2. Agar 2.5 second ke baad bhi page khula hai (matlab app nahi khula),
            // Toh samajh jao app install nahi hai.
            setTimeout(function() {{
                document.getElementById('status-text').style.display = 'none';
                document.getElementById('loader').style.display = 'none';
                document.getElementById('fallback-msg').style.display = 'block';
                
                // Optional: Seedha download shuru karwana ho toh ye line uncomment kar dein:
                // window.location.href = "{apk_download_link}"; 
            }}, 2500); 
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

# --- BOT COMMANDS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        f"👋 **Bot Started!**\n\nServer Link: `{PUBLIC_URL}`\nWaiting for files..."
    )

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

        # ========================================================
        # YAHAN BADLAV HAI: TeraBox jaisa Copy karne wala Message
        # ========================================================
        text = f"**{file_name}**\n\n"
        text += f"**Watch Video / Download:**\n"
        text += f"`{watch_link}`\n\n" # Ye link copy karne ke liye hai
        text += f"👆 *Click the link above to watch in PlayBox app or copy it to share!*"

        await message.reply_text(
            text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Watch in App", url=watch_link)]
            ])
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
    logger.info(f"✅ Web Server running on Port {PORT}")

    await app.start()
    logger.info("✅ Telegram Bot Started")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(start_services())
