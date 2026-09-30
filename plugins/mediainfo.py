import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import Config
from helpers.metadata import get_media_info, list_streams
from helpers.progress import progress_for_pyrogram

# Useroda file matrum stream selections-a save panna oru dictionary
USER_DATA = {}

@Client.on_message(filters.command("mediainfo") & filters.private)
async def mediainfo_cmd(client: Client, message: Message):
    target = message.reply_to_message

    if not target or not (target.video or target.audio or target.document):
        await message.reply_text("Reply to a video, audio, or document with /mediainfo to inspect its streams.")
        return

    status = await message.reply_text("**⚡Downloading...**")
    start = time.time()
    
    try:
        file_path = await client.download_media(
            target,
            file_name=os.path.join(Config.DOWNLOAD_DIR, f"probe_{message.id}"),
            progress=progress_for_pyrogram,
            progress_args=("Downloading", status, start),
        )

        if not file_path or not os.path.exists(file_path):
            await status.edit_text("❌ **Download failed.**")
            return

        await status.edit_text("**🔍 Probing streams...**")
        info = await get_media_info(file_path)

        if not info:
            await status.edit_text("❌ **Unable to read media streams.**\n\nFFprobe could not analyze this file.")
            return

        buckets = list_streams(info)
        
        # Save data to memory for callback handling
        USER_DATA[message.from_user.id] = {
            "file_path": file_path,
            "message_id": message.id,
            "buckets": buckets,
            "to_remove": set(), # Store stream absolute indexes to remove
            "target_msg": target
        }

        # Main Menu UI
        reply_markup = get_main_menu_keyboard()
        await status.edit_text(
            "**Remove Stream**\n\nChoose which stream type to configure:",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"MEDIAINFO ERROR: {type(e).__name__}: {e}")
        try:
            await status.edit_text(f"❌ **Media info failed.**\n\n`{type(e).__name__}: {e}`")
        except Exception:
            pass

def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data="stream_menu_audio"),
            InlineKeyboardButton("📝 Subtitle", callback_data="stream_menu_subtitle")
        ],
        [InlineKeyboardButton("✅ Process File", callback_data="process_streams")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_process")]
    ])

def get_stream_keyboard(user_id, stream_type):
    data = USER_DATA.get(user_id)
    if not data: return None
    
    streams = data["buckets"].get(stream_type, [])
    buttons = []
    
    for idx, s in enumerate(streams):
        stream_index = s['index']
        lang = s.get('lang', 'Unknown').upper()
        # ❌ mark add pandrom if stream is selected for removal
        prefix = "❌ " if stream_index in data["to_remove"] else ""
        btn_text = f"{prefix}Track {idx + 1} - {lang}"
        
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"toggle_{stream_index}_{stream_type}")])
    
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)

@Client.on_callback_query(filters.regex(r"^stream_menu_(audio|subtitle)$"))
async def show_stream_type(client: Client, query: CallbackQuery):
    stream_type = query.matches[0].group(1)
    user_id = query.from_user.id
    
    if user_id not in USER_DATA:
        await query.answer("Session expired. Send /mediainfo again.", show_alert=True)
        return
        
    markup = get_stream_keyboard(user_id, stream_type)
    await query.message.edit_text(
        f"**Remove {stream_type.title()}**\n\nSelect the streams you wish to modify. Changes are saved automatically.",
        reply_markup=markup
    )

@Client.on_callback_query(filters.regex(r"^toggle_(\d+)_(audio|subtitle)$"))
async def toggle_stream(client: Client, query: CallbackQuery):
    stream_index = int(query.matches[0].group(1))
    stream_type = query.matches[0].group(2)
    user_id = query.from_user.id
    
    if user_id not in USER_DATA:
        await query.answer("Session expired.", show_alert=True)
        return

    # Toggle selection
    if stream_index in USER_DATA[user_id]["to_remove"]:
        USER_DATA[user_id]["to_remove"].remove(stream_index)
    else:
        USER_DATA[user_id]["to_remove"].add(stream_index)
        
    markup = get_stream_keyboard(user_id, stream_type)
    await query.message.edit_reply_markup(reply_markup=markup)

@Client.on_callback_query(filters.regex(r"^back_to_main$"))
async def back_to_main(client: Client, query: CallbackQuery):
    markup = get_main_menu_keyboard()
    await query.message.edit_text(
        "**Remove Stream**\n\nChoose which stream type to configure:",
        reply_markup=markup
    )

@Client.on_callback_query(filters.regex(r"^cancel_process$"))
async def cancel_process(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id in USER_DATA:
        file_path = USER_DATA[user_id]["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)
        del USER_DATA[user_id]
    await query.message.edit_text("❌ Process Cancelled.")

@Client.on_callback_query(filters.regex(r"^process_streams$"))
async def process_streams(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if user_id not in USER_DATA:
        await query.answer("Session expired.", show_alert=True)
        return

    data = USER_DATA[user_id]
    to_remove = data["to_remove"]
    input_file = data["file_path"]
    target_msg = data["target_msg"]
    
    if not to_remove:
        await query.answer("No streams selected to remove!", show_alert=True)
        return

    await query.message.edit_text("⚙️ **Processing Video...**\nRemoving selected streams.")
    
    output_file = os.path.join(Config.DOWNLOAD_DIR, f"output_{user_id}_{int(time.time())}.mkv")
    
    # Building FFmpeg command
    cmd = ["ffmpeg", "-i", input_file, "-map", "0"]
    for stream_idx in to_remove:
        cmd.extend(["-map", f"-0:{stream_idx}"])
    cmd.extend(["-c", "copy", output_file])
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        if os.path.exists(output_file):
            await query.message.edit_text("📤 **Uploading processed file...**")
            await client.send_document(
                chat_id=query.message.chat.id,
                document=output_file,
                reply_to_message_id=target_msg.id,
                caption="Here is your modified file."
            )
            await query.message.delete()
        else:
            await query.message.edit_text("❌ Processing failed.")
            
    except Exception as e:
        await query.message.edit_text(f"❌ Error during processing: `{e}`")
    finally:
        # Cleanup files
        if os.path.exists(input_file): os.remove(input_file)
        if os.path.exists(output_file): os.remove(output_file)
        del USER_DATA[user_id]
        
