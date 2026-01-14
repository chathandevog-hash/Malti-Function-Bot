import os
import asyncio
import tempfile
import shutil
from flask import Flask

from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ------------------ ENV ------------------
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

async def get_thumb_fileid(user_id: int):
    d = await thumb_col.find_one({"user_id": user_id})
    return d["file_id"] if d else None

async def delete_thumb(user_id: int):
    await thumb_col.delete_one({"user_id": user_id})

# ------------------ Cache ------------------
CACHE = {}

# ------------------ Helper ------------------
def sizeof_fmt(num):
    try:
        num = int(num)
    except Exception:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{num:.2f} PB"

def get_ext(name: str):
    if not name or "." not in name:
        return ""
    return "." + name.split(".")[-1]

async def safe_edit(msg: Message, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup)
    except Exception:
        pass

def error_text(e: Exception):
    return f"❌ ERROR:\n`{e}`"

# ✅ New progress style
def progress_text(step: int):
    if step == 0:
        return "⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪\n0%"
    if step == 40:
        return "🔴🔴🔴⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪\n✅ 40%"
    if step == 50:
        return "🟠🟠🟠🟠🟠🟠⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪\n✅ 50%"
    if step == 75:
        return "🟡🟡🟡🟡🟡🟡🟡🟡🟡🟡⚪⚪⚪⚪⚪⚪\n✅ 75%"
    if step == 100:
        return "🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢\n100%"
    return "Processing..."

# ✅ download thumb file_id -> local jpg
async def get_thumb_path(client: Client, user_id: int):
    file_id = await get_thumb_fileid(user_id)
    if not file_id:
        return None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp.close()
        await client.download_media(file_id, file_name=tmp.name)
        return tmp.name
    except Exception:
        return None

# ✅ main: re-upload file with new filename (title changes at top)
async def download_and_upload(client: Client, chat_id: int, file_id: str, new_name: str, as_video: bool, thumb_path=None):
    tmp_dir = tempfile.mkdtemp()

    try:
        dl_path = await client.download_media(file_id, file_name=tmp_dir)
        if not dl_path:
            raise Exception("Download failed ❌")

        final_path = os.path.join(tmp_dir, new_name)
        try:
            os.rename(dl_path, final_path)
        except Exception:
            # fallback copy
            shutil.copy(dl_path, final_path)

        cap = f"✅ Renamed: `{new_name}`"

        if as_video:
            await client.send_video(
                chat_id=chat_id,
                video=final_path,
                file_name=new_name,
                thumb=thumb_path,
                caption=cap,
                supports_streaming=True
            )
        else:
            await client.send_document(
                chat_id=chat_id,
                document=final_path,
                file_name=new_name,
                thumb=thumb_path,
                caption=cap
            )

    finally:
        # cleanup download temp folder
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except:
            pass

# ------------------ Bot ------------------
bot = Client(
    "MultiFunctionBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
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
    fid = await get_thumb_fileid(uid)
    if fid:
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
        size = getattr(media, "file_size", 0) or 0
        dc_id = getattr(media, "dc_id", "N/A")
        media_type = "document"
    else:
        media = m.video
        file_name = media.file_name or "video.mp4"
        size = getattr(media, "file_size", 0) or 0
        dc_id = getattr(media, "dc_id", "N/A")
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
async def cb(client: Client, cq: CallbackQuery):
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
        thumb_path = await get_thumb_path(client, uid)

        try:
            await safe_edit(cq.message, progress_text(0))
            await asyncio.sleep(0.6)
            await safe_edit(cq.message, progress_text(40))
            await asyncio.sleep(0.6)
            await safe_edit(cq.message, progress_text(50))
            await asyncio.sleep(0.6)
            await safe_edit(cq.message, progress_text(75))
            await asyncio.sleep(0.6)
            await safe_edit(cq.message, progress_text(100))

            # ✅ re-upload with new filename
            if cq.data == "fmt_doc":
                await download_and_upload(
                    client=client,
                    chat_id=cq.message.chat.id,
                    file_id=sess["file_id"],
                    new_name=sess["new_name"],
                    as_video=False,
                    thumb_path=thumb_path
                )
            else:
                await download_and_upload(
                    client=client,
                    chat_id=cq.message.chat.id,
                    file_id=sess["file_id"],
                    new_name=sess["new_name"],
                    as_video=True,
                    thumb_path=thumb_path
                )

            CACHE.pop(uid, None)
            await cq.answer("✅ Completed")

        except Exception as e:
            await cq.message.reply_text(error_text(e))
            await cq.answer("Error", show_alert=True)

        finally:
            if thumb_path and os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                except:
                    pass

# ------------------ Name Input ------------------
@bot.on_message(filters.private & filters.text)
async def newname(_, m: Message):
    uid = m.from_user.id
    name = (m.text or "").strip()

    if name.startswith("/"):
        return
    if uid not in CACHE:
        return

    if not m.reply_to_message:
        await m.reply_text("⚠️ Please reply to the rename message.")
        return

    sess = CACHE[uid]
    ext = get_ext(sess["file_name"])

    # extension not required
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
