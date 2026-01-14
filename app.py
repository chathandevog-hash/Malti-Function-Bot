import os
import math
import asyncio
from flask import Flask

from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# -----------------------------
# ENV
# -----------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ✅ OPTION B: Your Render key is MONGO_URI
MONGO_URI = os.getenv("MONGO_URI", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("❌ Missing API_ID / API_HASH / BOT_TOKEN env vars")

if not MONGO_URI:
    raise SystemExit("❌ Missing MONGO_URI env var")

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
# Mongo Setup
# -----------------------------
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["multifunctional_bot"]
thumb_col = db["thumbnails"]   # {user_id:int, file_id:str}

# -----------------------------
# Cache (rename session)
# -----------------------------
RENAME_CACHE = {}
# user_id -> {
#   "msg_id": int,
#   "chat_id": int,
#   "file_id": str,
#   "file_name": str,
#   "file_size": int,
#   "dc_id": int,
#   "is_video": bool,
#   "new_name": str
# }

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
2) Send file/video
3) Click Rename
4) Reply new name
"""

# -----------------------------
# Helpers
# -----------------------------
def sizeof_fmt(num, suffix="B"):
    if num is None:
        return "Unknown"
    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(num) < 1024.0:
            return f"{num:3.2f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.2f} Y{suffix}"

def get_extension(file_name: str):
    if not file_name:
        return ""
    if "." not in file_name:
        return ""
    return "." + file_name.split(".")[-1]

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

async def safe_edit(msg: Message, text: str):
    try:
        if (msg.text or "") != text:
            await msg.edit_text(text)
    except Exception:
        pass

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
# Bot
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
async def start_cmd(_, message: Message):
    await message.reply_text(START_TEXT, disable_web_page_preview=True)

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(_, message: Message):
    await message.reply_text(HELP_TEXT, disable_web_page_preview=True)

@bot.on_message(filters.command("deletetub") & filters.private)
async def delete_thumb_cmd(_, message: Message):
    user_id = message.from_user.id
    old = await get_thumb(user_id)
    if old:
        await delete_thumb(user_id)
        await message.reply_text("✅ Thumbnail Deleted")
    else:
        await message.reply_text("ℹ️ No thumbnail found.")

# -----------------------------
# Auto thumbnail save
# -----------------------------
@bot.on_message(filters.private & filters.photo)
async def save_thumb(_, message: Message):
    user_id = message.from_user.id
    await set_thumb(user_id, message.photo.file_id)
    await message.reply_text("✅ Thumbnail Saved Successfully!")

# -----------------------------
# File/video receive -> show style card with buttons
# -----------------------------
@bot.on_message(filters.private & (filters.document | filters.video))
async def file_in(_, message: Message):
    user_id = message.from_user.id

    if message.document:
        media = message.document
        is_video = False
        file_name = media.file_name or "file"
        file_size = media.file_size
        dc_id = media.dc_id
    else:
        media = message.video
        is_video = True
        file_name = media.file_name or "video.mp4"
        file_size = media.file_size
        dc_id = media.dc_id

    text = (
        "**𝙒𝙃𝘼𝙏 𝘿𝙊 𝙔𝙊𝙐 𝙒𝘼𝙉𝙏 𝙈𝙀 𝙏𝙊 𝘿𝙊 𝙒𝙄𝙏𝙃 𝙏𝙃𝙄𝙎 𝙁𝙄𝙇𝙀 ?**\n\n"
        f"**𝙁𝙄𝙇𝙀 𝙉𝘼𝙈𝙀 :-** `{file_name}`\n"
        f"**𝙁𝙄𝙇𝙀 𝙎𝙄𝙕𝙀 :-** `{sizeof_fmt(file_size)}`\n"
        f"**𝘿𝘾 𝙄𝘿 :-** `{dc_id}`"
    )

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Rename", callback_data="act_rename"),
                InlineKeyboardButton("✖ Cancel", callback_data="act_cancel"),
            ]
        ]
    )

    sent = await message.reply_text(text, reply_markup=buttons)

    RENAME_CACHE[user_id] = {
        "msg_id": sent.id,
        "chat_id": sent.chat.id,
        "file_id": media.file_id,
        "file_name": file_name,
        "file_size": file_size,
        "dc_id": dc_id,
        "is_video": is_video,
    }

# -----------------------------
# Rename button
# -----------------------------
@bot.on_callback_query(filters.regex("^act_"))
async def actions(_, cq: CallbackQuery):
    user_id = cq.from_user.id

    if cq.data == "act_cancel":
        RENAME_CACHE.pop(user_id, None)
        await cq.message.edit_text("✅ Cancelled.")
        await cq.answer()
        return

    if cq.data == "act_rename":
        if user_id not in RENAME_CACHE:
            await cq.answer("Send a file first!", show_alert=True)
            return

        text = (
            "**Please Enter The New Filename...**\n\n"
            "**Note:- Extension Not Required**"
        )
        await cq.message.edit_text(text)
        await cq.answer("✅ Send new name (reply)")

# -----------------------------
# Rename name input (must be reply)
# -----------------------------
@bot.on_message(filters.private & filters.text)
async def name_input(_, message: Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if text.startswith("/"):
        return

    if user_id not in RENAME_CACHE:
        return

    # must be reply to bot rename prompt
    session = RENAME_CACHE[user_id]
    if not message.reply_to_message:
        await message.reply_text("⚠️ Please reply to the rename message.")
        return

    # new name
    old_name = session["file_name"]
    ext = get_extension(old_name)

    # Extension not required -> auto add
    new_name = text
    if ext and not new_name.endswith(ext):
        new_name += ext

    session["new_name"] = new_name

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("📄 Document", callback_data="fmt_doc"),
            InlineKeyboardButton("🎥 Video", callback_data="fmt_vid"),
        ]]
    )

    await message.reply_text(
        f"✅ **Name Set:** `{new_name}`\n\n**Select Format:**",
        reply_markup=buttons
    )

# -----------------------------
# Format callback
# -----------------------------
@bot.on_callback_query(filters.regex("^fmt_"))
async def format_send(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id

    if user_id not in RENAME_CACHE or "new_name" not in RENAME_CACHE[user_id]:
        await cq.answer("Send file + set name first!", show_alert=True)
        return

    session = RENAME_CACHE[user_id]
    file_id = session["file_id"]
    new_name = session["new_name"]

    thumb = await get_thumb(user_id)

    # Progress safely
    await safe_edit(cq.message, progress_text(0))
    await asyncio.sleep(0.6)
    await safe_edit(cq.message, progress_text(40))
    await asyncio.sleep(0.6)
    await safe_edit(cq.message, progress_text(65))
    await asyncio.sleep(0.6)
    await safe_edit(cq.message, progress_text(100))

    caption = f"✅ Renamed: `{new_name}`"

    try:
        if cq.data == "fmt_doc":
            await client.send_document(
                chat_id=cq.message.chat.id,
                document=file_id,
                file_name=new_name,
                thumb=thumb,
                caption=caption
            )
        else:
            await client.send_video(
                chat_id=cq.message.chat.id,
                video=file_id,
                file_name=new_name,
                thumb=thumb,
                caption=caption,
                supports_streaming=True
            )
        await cq.answer("✅ Done!")
    except Exception as e:
        await cq.answer("❌ Failed!", show_alert=True)
        await cq.message.reply_text(f"❌ Error:\n`{e}`")

    RENAME_CACHE.pop(user_id, None)

# -----------------------------
# Start web + bot
# -----------------------------
if __name__ == "__main__":
    from threading import Thread

    def run_web():
        port = int(os.getenv("PORT", "8080"))
        web.run(host="0.0.0.0", port=port)

    Thread(target=run_web).start()
    bot.run()
