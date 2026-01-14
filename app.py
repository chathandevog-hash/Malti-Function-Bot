import os
import time
from flask import Flask

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("❌ Missing API_ID / API_HASH / BOT_TOKEN env vars")

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
# Bot Database (in-memory)
# -----------------------------
THUMB_DB = {}        # user_id -> file_id
RENAME_DB = {}       # user_id -> {"file_id":..., "file_name":..., "is_video": bool}

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
async def delete_thumb(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in THUMB_DB:
        THUMB_DB.pop(user_id, None)
        await message.reply_text("✅ Thumbnail Deleted")
    else:
        await message.reply_text("ℹ️ No thumbnail found.")

# -----------------------------
# Auto save thumbnail
# -----------------------------
@bot.on_message(filters.private & filters.photo)
async def save_thumb(client: Client, message: Message):
    user_id = message.from_user.id
    file_id = message.photo.file_id
    THUMB_DB[user_id] = file_id
    await message.reply_text("✅ Thumbnail Saved Successfully!")

# -----------------------------
# Receive file/video for rename
# -----------------------------
@bot.on_message(filters.private & (filters.document | filters.video))
async def receive_media(client: Client, message: Message):
    user_id = message.from_user.id

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "file"
        is_video = False
    else:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
        is_video = True

    RENAME_DB[user_id] = {
        "file_id": file_id,
        "file_name": file_name,
        "is_video": is_video
    }

    await message.reply_text(
        f"✏️ New name send ചെയ്യൂ:\n\nCurrent: `{file_name}`",
        quote=True
    )

# -----------------------------
# Rename text receiver
# -----------------------------
@bot.on_message(filters.private & filters.text)
async def rename_text(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text.startswith("/"):
        return  # commands ignore

    if user_id not in RENAME_DB:
        return

    data = RENAME_DB[user_id]
    old_name = data["file_name"]

    # keep original extension
    ext = ""
    if "." in old_name:
        ext = "." + old_name.split(".")[-1]

    new_name = text
    if not new_name.endswith(ext):
        new_name += ext

    RENAME_DB[user_id]["new_name"] = new_name

    # show format buttons
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📄 Document", callback_data="fmt_doc"),
                InlineKeyboardButton("🎥 Video", callback_data="fmt_vid"),
            ]
        ]
    )

    await message.reply_text(
        f"✅ Name Set: `{new_name}`\n\nFormat select ചെയ്യൂ:",
        reply_markup=buttons
    )

# -----------------------------
# Callback for format selection
# -----------------------------
@bot.on_callback_query()
async def cb_handler(client, callback_query):
    user_id = callback_query.from_user.id

    if user_id not in RENAME_DB or "new_name" not in RENAME_DB[user_id]:
        await callback_query.answer("Send a file first!", show_alert=True)
        return

    data = RENAME_DB[user_id]
    file_id = data["file_id"]
    new_name = data["new_name"]
    thumb = THUMB_DB.get(user_id)

    await callback_query.message.edit_text(progress_text(0))
    time.sleep(0.6)
    await callback_query.message.edit_text(progress_text(40))
    time.sleep(0.6)
    await callback_query.message.edit_text(progress_text(65))
    time.sleep(0.6)
    await callback_query.message.edit_text(progress_text(100))

    cap = f"✅ Renamed File: `{new_name}`"

    if callback_query.data == "fmt_doc":
        await client.send_document(
            chat_id=callback_query.message.chat.id,
            document=file_id,
            file_name=new_name,
            thumb=thumb,
            caption=cap
        )
    else:
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=file_id,
            file_name=new_name,
            thumb=thumb,
            caption=cap
        )

    # clear
    RENAME_DB.pop(user_id, None)
    await callback_query.answer("✅ Done!")

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
