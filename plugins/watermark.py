import os
import time
import asyncio
import re
import motor.motor_asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import MessageNotModified
from helpers.progress import progress_for_pyrogram
from config import Config

# ==========================================
# DATABASE SETUP (MONGODB)
# ==========================================
# Ungaloda MongoDB Atlas URI-a inga replace pannunga allathu Config-la irunthu edunga
MONGODB_URI = os.environ.get("MONGODB_URI", "YOUR_MONGODB_URI_HERE")
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
wm_db = db_client["FileRenamerPro"]["watermark_data"]

async def set_wm_data(user_id, key, value):
    await wm_db.update_one({"_id": user_id}, {"$set": {key: value}}, upsert=True)

async def get_wm_data(user_id):
    data = await wm_db.find_one({"_id": user_id})
    return data if data else {}

# ==========================================
# WATERMARK SETTINGS COMMANDS
# ==========================================

@Client.on_message(filters.command("set_wm_txt") & filters.private)
async def set_wm_txt(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ **Usage:** `/set_wm_txt <Your Text>`")
    
    text = message.text.split(maxsplit=1)[1]
    await set_wm_data(message.from_user.id, "text", text)
    await set_wm_data(message.from_user.id, "type", "text") # Set type to text
    await message.reply_text(f"✅ **Watermark Text Saved:** `{text}`")

@Client.on_message(filters.command("set_wt_pos") & filters.private)
async def set_wt_pos(client: Client, message: Message):
    valid_positions = ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
    if len(message.command) < 2 or message.command[1].lower() not in valid_positions:
        return await message.reply_text(f"❌ **Usage:** `/set_wt_pos <position>`\n\n**Valid Positions:**\n`{', '.join(valid_positions)}`")
    
    pos = message.command[1].lower()
    await set_wm_data(message.from_user.id, "position", pos)
    await message.reply_text(f"✅ **Watermark Position Saved:** `{pos}`")

@Client.on_message(filters.command("set_wm_sz") & filters.private)
async def set_wm_sz(client: Client, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("❌ **Usage:** `/set_wm_sz <Number>`\n*(Example: 24 for Text Font Size, 100 for Image Width)*")
    
    size = int(message.command[1])
    await set_wm_data(message.from_user.id, "size", size)
    await message.reply_text(f"✅ **Watermark Size Saved:** `{size}`")

@Client.on_message(filters.command("set_wt_img") & filters.private)
async def set_wt_img(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("❌ **Please reply to an image with** `/set_wt_img`")
    
    status = await message.reply_text("⏳ **Downloading Image...**")
    img_path = os.path.join(Config.DOWNLOAD_DIR, f"wm_{message.from_user.id}.jpg")
    await message.reply_to_message.download(img_path)
    
    await set_wm_data(message.from_user.id, "image", img_path)
    await set_wm_data(message.from_user.id, "type", "image") # Set type to image
    await status.edit_text("✅ **Watermark Image Saved Successfully!**")

# ==========================================
# WATERMARK PROCESSING (/st_wm)
# ==========================================

async def get_video_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await process.communicate()
    try:
        return float(stdout.decode().strip())
    except:
        return 0.0

def make_progress_bar(percentage):
    filled = int(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return bar

@Client.on_message(filters.command("st_wm") & filters.private)
async def start_watermark(client: Client, message: Message):
    target = message.reply_to_message
    if not target or not target.video:
        return await message.reply_text("❌ **Reply to a video file with** `/st_wm` **to add watermark.**")

    user_data = await get_wm_data(message.from_user.id)
    wm_type = user_data.get("type")
    
    if not wm_type:
        return await message.reply_text("❌ **You haven't set any watermark yet!**\nUse `/set_wm_txt` or `/set_wt_img` first.")

    status = await message.reply_text("📥 **Downloading Video...**")
    start_time = time.time()
    
    input_path = os.path.join(Config.DOWNLOAD_DIR, f"in_{message.message_id}.mp4")
    output_path = os.path.join(Config.DOWNLOAD_DIR, f"out_{message.message_id}.mp4")
    
    # 1. Download Video
    downloaded_file = await client.download_media(
        target,
        file_name=input_path,
        progress=progress_for_pyrogram,
        progress_args=("**📥 Downloading Video...**", status, start_time)
    )
    
    if not downloaded_file:
        return await status.edit_text("❌ **Download Failed.**")

    await status.edit_text("⚙️ **Preparing to Watermark...**")
    
    # 2. Setup FFmpeg Command
    wm_pos = user_data.get("position", "bottom_right")
    wm_size = user_data.get("size", 24)
    total_duration = await get_video_duration(input_path)

    cmd = []
    
    if wm_type == "image":
        wm_img = user_data.get("image")
        if not wm_img or not os.path.exists(wm_img):
            return await status.edit_text("❌ **Saved watermark image not found. Please set it again.**")
            
        pos_map = {
            "top_left": "10:10", "top_right": "W-w-10:10",
            "bottom_left": "10:H-h-10", "bottom_right": "W-w-10:H-h-10",
            "center": "(W-w)/2:(H-h)/2"
        }
        overlay = pos_map.get(wm_pos, "W-w-10:H-h-10")
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-i", wm_img,
            "-filter_complex", f"[1:v]scale={wm_size}:-1[wm];[0:v][wm]overlay={overlay}",
            "-c:a", "copy", output_path
        ]
        
    elif wm_type == "text":
        wm_text = user_data.get("text", "Watermark")
        pos_map = {
            "top_left": "x=10:y=10", "top_right": "x=W-tw-10:y=10",
            "bottom_left": "x=10:y=H-th-10", "bottom_right": "x=W-tw-10:y=H-th-10",
            "center": "x=(W-tw)/2:y=(H-th)/2"
        }
        draw_pos = pos_map.get(wm_pos, "x=W-tw-10:y=H-th-10")
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"drawtext=text='{wm_text}':fontcolor=white:fontsize={wm_size}:{draw_pos}",
            "-c:a", "copy", output_path
        ]

    # 3. Process with FFmpeg and Show Progress
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Read stderr to get FFmpeg Progress
    last_update = time.time()
    time_regex = re.compile(r"time=(?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})\.(?P<ms>\d{2})")
    
    while True:
        line = await process.stderr.readline()
        if not line:
            break
            
        line = line.decode("utf-8", errors="replace").strip()
        match = time_regex.search(line)
        
        if match and total_duration > 0:
            current_time = time.time()
            if current_time - last_update > 5:  # Update message every 5 seconds
                hours = int(match.group("hour"))
                minutes = int(match.group("min"))
                seconds = int(match.group("sec"))
                
                elapsed = (hours * 3600) + (minutes * 60) + seconds
                percentage = min(100.0, (elapsed / total_duration) * 100)
                
                bar = make_progress_bar(percentage)
                msg = f"⚙️ **Adding Watermark...**\n\n**Progress:** [{bar}] {percentage:.2f}%\n**Processed:** {elapsed}s / {int(total_duration)}s"
                
                try:
                    await status.edit_text(msg)
                    last_update = current_time
                except MessageNotModified:
                    pass
                except Exception:
                    pass

    await process.wait()

    # 4. Upload Output Video
    if os.path.exists(output_path):
        await status.edit_text("📤 **Uploading Watermarked Video...**")
        start_time = time.time()
        
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            reply_to_message_id=target.id,
            caption=f"✅ Watermarked File\n\n**Type:** {wm_type.title()}",
            progress=progress_for_pyrogram,
            progress_args=("**📤 Uploading Video...**", status, start_time)
        )
        await status.delete()
    else:
        await status.edit_text("❌ **Failed to process watermark.**")

    # 5. Cleanup
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
  
