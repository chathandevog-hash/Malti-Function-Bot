import os
import asyncio
import traceback
from flask import Flask

from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("❌ Missing API_ID / API_HASH / BOT_TOKEN env vars")
if not MONGO_URI:
    raise SystemExit("❌ Missing MONGO_URI env var")

# ------------------ Web (UptimeRobot) ------------------
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Bot alive"

@web.route("/health")
def health():
    return {"ok": True}, 200

# ------------------ Mongo ------------------
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["multifunctional_bot"]
thumb_col = db["thumbnails"]

async def set_thumb(user_id: int, file_id: str):
    await thumb_col.update_one({"user_id": user_id}, {"$set": {"file_id": file_id}}, upsert=True)

async def get_thumb(user_id: int):
    d = await thumb_col.find_one({"user_id": user_id})
    return d["file_id"] if d else None

async def delete_thumb(user_id: int):
    await thumb_col.delete_one({"user_id": user_id})

# ------------------ Cache ------------------
CACHE = {}  # user_id -> file session

# ------------------ Helper ------------------
def sizeof_fmt(num):
    try:
        num = int(num)
    except:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{num:.2f} PB"

def get_ext(name: str):
    if not name:
        return ""
    if "." not in name:
        return ""
    return "." + name.split(".")[-1]

async def safe_edit(msg: Message, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup)
    except Exception:
        # ignore MESSAGE_NOT_MODIFIED etc
        pass

def error_text(e: Exception):
    return f"❌ ERROR:\n`{e}`"

# ------------------ Bot ------------------
bot = Client(
    "MultiFunctionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

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
• /start
• /help
• /deletetub

📌 Usage:
Send photo => thumbnail set
Send file/video => click Rename
"""

# ------------------ Commands ------------------
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(_, m: Message):
    await m.reply_text(START_TEXT)

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(_, m: Message):
    await m.reply_text(HELP_TEXT)

@bot.on_message(filters.command("deletetub") & filters.private)
async def delete_tub_cmd(_, m: Message):
    uid = m.from_user.id
    thumb = await get_thumb(uid)
    if thumb:
        await delete_thumb(uid)
        await m.reply_text("✅ Thumbnail Deleted")
    else:
        await m.reply_text("ℹ️ No thumbnail found")

# ------------------ Thumbnail Save ------------------
@bot.on_message(filters.private & filters.photo)
async def save_thumb_cmd(_, m: Message):
    uid = m.from_user.id
    await set_thumb(uid, m.photo.file_id)
    await m.reply_text("✅ Thumbnail Saved Successfully!")

# ------------------ Receive Media ------------------
@bot.on_message(filters.private & (filters.document | filters.video))
async def receive_media(_, m: Message):
    uid = m.from_user.id

    if m.document:
        media = m.document
        file_name = media.file_name or "file"
        size = media.file_size
        dc_id = media.dc_id
        media_type = "document"
    else:
        media = m.video
        file_name = media.file_name or "video.mp4"
        size = media.file_size
        dc_id = media.dc_id
        media_type = "video"

    text = (
        "**𝙒𝙃𝘼𝙏 𝘿𝙊 𝙔𝙊𝙐 𝙒𝘼𝙉𝙏 𝙈𝙀 𝙏𝙊 𝘿𝙊 𝙒𝙄𝙏𝙃 𝙏𝙃𝙄𝙎 𝙁𝙄𝙇𝙀 ?**\n\n"
        f"**𝙁𝙄𝙇𝙀 𝙉𝘼𝙈𝙀 :-** `{file_name}`\n"
        f"**𝙁𝙄𝙇𝙀 𝙎𝙄𝙕𝙀 :-** `{sizeof_fmt(size)}`\n"
        f"**𝘿𝘾 𝙄𝘿 :-** `{dc_id}`"
    )

    kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✏️ Rename", callback_data="rename"),
            InlineKeyboardButton("✖ Cancel", callback_data="cancel"),
        ]]
    )

    msg = await m.reply_text(text, reply_markup=kb)

    CACHE[uid] = {
        "chat_id": msg.chat.id,
        "prompt_id": msg.id,
        "file_id": media.file_id,
        "file_name": file_name,
        "media_type": media_type
    }

# ------------------ Button Handler ------------------
@bot.on_callback_query()
async def cb(_, cq: CallbackQuery):
    uid = cq.from_user.id

    if cq.data == "cancel":
        CACHE.pop(uid, None)
        await safe_edit(cq.message, "✅ Cancelled.")
        await cq.answer()
        return

    if cq.data == "rename":
        if uid not in CACHE:
            await cq.answer("Send a file first!", show_alert=True)
            return

        await safe_edit(
            cq.message,
            "**Please Enter The New Filename...**\n\n**Note:- Extension Not Required**"
        )
        await cq.answer("Now send new name")
        return

    if cq.data in ["fmt_doc", "fmt_vid"]:
        if uid not in CACHE or "new_name" not in CACHE[uid]:
            await cq.answer("Set name first!", show_alert=True)
            return

        sess = CACHE[uid]
        thumb = await get_thumb(uid)

        try:
            await safe_edit(cq.message, "⚙️ Processing...\n\n0%")
            await asyncio.sleep(0.4)
            await safe_edit(cq.message, "⚙️ Processing...\n\n40%")
            await asyncio.sleep(0.4)
            await safe_edit(cq.message, "⚙️ Processing...\n\n65%")
            await asyncio.sleep(0.4)
            await safe_edit(cq.message, "✅ Done!\n\n100%")

            cap = f"✅ Renamed: `{sess['new_name']}`"

            if cq.data == "fmt_doc":
                await bot.send_document(
                    chat_id=cq.message.chat.id,
                    document=sess["file_id"],
                    file_name=sess["new_name"],
                    thumb=thumb,
                    caption=cap
                )
            else:
                await bot.send_video(
                    chat_id=cq.message.chat.id,
                    video=sess["file_id"],
                    file_name=sess["new_name"],
                    thumb=thumb,
                    caption=cap,
                    supports_streaming=True
                )

            CACHE.pop(uid, None)
            await cq.answer("✅ Completed")
        except Exception as e:
            await cq.message.reply_text(error_text(e))
            await cq.answer("Error", show_alert=True)

# ------------------ Name Input ------------------
@bot.on_message(filters.private & filters.text)
async def newname(_, m: Message):
    uid = m.from_user.id
    name = (m.text or "").strip()

    if name.startswith("/"):
        return
    if uid not in CACHE:
        return

    # must be reply
    if not m.reply_to_message:
        await m.reply_text("⚠️ Please reply to the rename message.")
        return

    sess = CACHE[uid]
    ext = get_ext(sess["file_name"])

    if ext and not name.endswith(ext):
        name += ext

    sess["new_name"] = name

    kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("📄 Document", callback_data="fmt_doc"),
            InlineKeyboardButton("🎥 Video", callback_data="fmt_vid"),
        ]]
    )
    await m.reply_text(f"✅ Name Set: `{name}`\n\nSelect Format:", reply_markup=kb)

# ------------------ Run ------------------
if __name__ == "__main__":
    from threading import Thread

    def run_web():
        port = int(os.getenv("PORT", "8080"))
        web.run(host="0.0.0.0", port=port)

    Thread(target=run_web).start()
    bot.run()
