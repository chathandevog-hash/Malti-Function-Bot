import os
import asyncio
from flask import Flask

from motor.motor_asyncio import AsyncIOMotorClient

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

MONGO_URL = os.getenv("MONGO_URL", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("❌ Missing API_ID / API_HASH / BOT_TOKEN env vars")

if not MONGO_URL:
    raise SystemExit("❌ Missing MONGO_URL env var")

# -----------------------------
# Flask Web Server (UptimeRobot)
# -----------------------------
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Bot is alive (Multifunctional Bot)"

@web.route("/health")
def health():
    return {"status": "ok"}, 200

# -----------------------------
# MongoDB Setup
# -----------------------------
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["multifunctional_bot"]
thumb_col = db["thumbnails"]      # {user_id:int, file_id:str}
rename_col = db["rename_queue"]   # {user_id:int, file_id:str, file_name:str}

# -----------------------------
# In-memory rename pending (safe)
# -----------------------------
RENAME_CACHE = {}  # user_id -> dict

# -----------------------------
# Texts
# -----------------------------
START_TEXT = """╔══════════════════════╗
   🤖 Welcome Guys💖
╚══════════════════════╝

✨ I’m your Multifunctional Bot ⚡

✅ Features:
📝 Rename Files
🔗 URL Uploader
🎬 Convert
🗜️ Compress

🚀 Send me a file / link & I’ll do the rest 😎

📌 Use /help for commands
"""

HELP_TEXT = """✅ Commands:
• /start - Start bot
• /help - Help menu
• /deletetub - Delete thumbnail

📌 How to use:
1) Send a photo to set thumbnail
2) Send file/video -> bot asks new name
3) Select format (Document/Video)
"""

# -----------------------------
# Progress Bar
# -----------------------------
def progress_text(step: int):
    if step == 0:
        return "⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪\n0%"
    if step == 40:
        return "🔴🔴🔴⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪\n✅ 40%"
    if step == 65:
        return "🟠🟠🟠🟠🟠🟠⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪\n✅ 65%"
    if step == 100:
        return "🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢\n✅ 100%"
    return "Processing..."

# -----------------------------
# Helpers (Mongo)
# -----------------------------
async def set_thumb(user_id: int, file_id: str):
    await thumb_col.update_one(
        {"user_id": user_id},
        {"$set": {"file_id": file_id}},
        upsert=True
    )

async def get_thumb(user_id: int):
    data = await thumb_col.find_one({"user_id": user_id})
    return data["file_id"] if data else None

async def delete_thumb(user_id: int):
    await thumb_col.delete_one({"user_id": user_id})

# -----------------------------
# Bot client
# -----------------------------
bot = Client(
    "MultiFunctionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# -----------------------------
# Commands
# -----------------------------
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await message.reply_text(START_TEXT, disable_web_page_preview=True)

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    await message.reply_text(HELP_TEXT, disable_web_page_preview=True)

@bot.on_message(filters.command("deletetub") & filters.private)
async def delete_thumb_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    old = await get_thumb(user_id)
    if old:
        await delete_thumb(user_id)
        await message.reply_text("✅ Thumbnail Deleted")
    else:
        await message.reply_text("ℹ️ No thumbnail found.")

# -----------------------------
# Save thumbnail
# -----------------------------
@bot.on_message(filters.private & filters.photo)
async def save_thumb_handler(client: Client, message: Message):
    user_id = message.from_user.id
    await set_thumb(user_id, message.photo.file_id)
    await message.reply_text("✅ Thumbnail Saved Successfully!")

# -----------------------------
# Receive file/video for rename
# -----------------------------
@bot.on_message(filters.private & (filters.document | filters.video))
async def receive_media(client: Client, message: Message):
    user_id = message.from_user.id

    if message.document:
        media = message.document
        file_name = media.file_name or "file"
    else:
        media = message.video
        file_name = media.file_name or "video.mp4"

    RENAME_CACHE[user_id] = {
        "file_id": media.file_id,
        "file_name": file_name
    }

    await message.reply_text(
        f"✏️ New name send ചെയ്യൂ:\n\nCurrent: `{file_name}`",
        quote=True
    )

# -----------------------------
# Rename text
# -----------------------------
@bot.on_message(filters.private & filters.text)
async def rename_text(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text.startswith("/"):
        return

    if user_id not in RENAME_CACHE:
        return

    old_name = RENAME_CACHE[user_id]["file_name"]

    ext = ""
    if "." in old_name:
        ext = "." + old_name.split(".")[-1]

    new_name = text
    if ext and not new_name.endswith(ext):
        new_name += ext

    RENAME_CACHE[user_id]["new_name"] = new_name

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("📄 Document", callback_data="fmt_doc"),
            InlineKeyboardButton("🎥 Video", callback_data="fmt_vid"),
        ]]
    )

    await message.reply_text(
        f"✅ Name Set: `{new_name}`\n\nFormat select ചെയ്യൂ:",
        reply_markup=buttons
    )

# -----------------------------
# Callback
# -----------------------------
@bot.on_callback_query()
async def cb_handler(client, callback_query):
    user_id = callback_query.from_user.id

    if user_id not in RENAME_CACHE or "new_name" not in RENAME_CACHE[user_id]:
        await callback_query.answer("Send a file first!", show_alert=True)
        return

    data = RENAME_CACHE[user_id]
    file_id = data["file_id"]
    new_name = data["new_name"]

    thumb = await get_thumb(user_id)

    await callback_query.message.edit_text(progress_text(0))
    await asyncio.sleep(0.6)
    await callback_query.message.edit_text(progress_text(40))
    await asyncio.sleep(0.6)
    await callback_query.message.edit_text(progress_text(65))
    await asyncio.sleep(0.6)
    await callback_query.message.edit_text(progress_text(100))

    caption = f"✅ Renamed File: `{new_name}`"

    try:
        if callback_query.data == "fmt_doc":
            await client.send_document(
                chat_id=callback_query.message.chat.id,
                document=file_id,
                file_name=new_name,
                thumb=thumb,
                caption=caption
            )
        else:
            await client.send_video(
                chat_id=callback_query.message.chat.id,
                video=file_id,
                file_name=new_name,
                thumb=thumb,
                caption=caption,
                supports_streaming=True
            )

        await callback_query.answer("✅ Done!")
    except Exception as e:
        await callback_query.answer("❌ Failed!", show_alert=True)
        await callback_query.message.reply_text(f"❌ Error:\n`{e}`")

    RENAME_CACHE.pop(user_id, None)

# -----------------------------
# Run Flask + Bot
# -----------------------------
if __name__ == "__main__":
    from threading import Thread

    def run_web():
        port = int(os.getenv("PORT", "8080"))
        web.run(host="0.0.0.0", port=port)

    Thread(target=run_web).start()
    bot.run()
