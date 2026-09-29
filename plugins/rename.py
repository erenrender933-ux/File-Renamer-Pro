import os
import time

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from helpers.database import db
from helpers.gofile import upload_to_gofile
from helpers.metadata import get_media_info, list_streams, remap_streams, set_metadata
from helpers.progress import humanbytes, progress_for_pyrogram
from helpers.state import clear_pending, get_pending, set_pending
from helpers.utils import (
    apply_prefix_suffix,
    apply_regex,
    apply_word_replace,
    safe_filename,
    unzip_file,
)

# Per-(user_id, message_id) scratch space: which streams the user picked to
# keep, path of the downloaded source file, etc. Cleared once a job finishes.
JOBS = {}


def job_key(user_id, message_id):
    return f"{user_id}:{message_id}"


def original_filename(message: Message):
    media = message.video or message.audio or message.document
    return getattr(media, "file_name", None) or "unnamed_file"


def file_action_menu(message_id, is_zip):
    rows = [
        [
            InlineKeyboardButton("✏️ Rename", callback_data=f"act:{message_id}:rename"),
            InlineKeyboardButton("🎬 Streams/Metadata", callback_data=f"act:{message_id}:edit"),
        ]
    ]
    if is_zip:
        rows.append(
            [InlineKeyboardButton("📦 Unzip & Upload", callback_data=f"act:{message_id}:unzip")]
        )
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"act:{message_id}:cancel")])
    return InlineKeyboardMarkup(rows)


@Client.on_message(
    (filters.video | filters.audio | filters.document) & filters.private
)
async def incoming_file(client: Client, message: Message):
    fname = original_filename(message)
    is_zip = fname.lower().endswith(".zip")
    JOBS[job_key(message.from_user.id, message.id)] = {"source_message_id": message.id}
    await message.reply_text(
        f"**File:** `{fname}`\n**Size:** {humanbytes(message.document.file_size if message.document else (message.video.file_size if message.video else message.audio.file_size))}\n\n"
        "What would you like to do?",
        reply_markup=file_action_menu(message.id, is_zip),
        quote=True,
    )


# --------------------------------------------------------------------------- #
# Action: Rename only (fast path, no ffmpeg re-mux needed)
# --------------------------------------------------------------------------- #
@Client.on_callback_query(filters.regex(r"^act:(\d+):rename$"))
async def act_rename(client: Client, query: CallbackQuery):
    message_id = int(query.matches[0].group(1))
    set_pending(query.from_user.id, "new_filename", message_id=message_id)
    await query.message.edit_text(
        "Send the new file name (with extension). Send /cancel to abort."
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^act:(\d+):cancel$"))
async def act_cancel(client: Client, query: CallbackQuery):
    message_id = int(query.matches[0].group(1))
    JOBS.pop(job_key(query.from_user.id, message_id), None)
    clear_pending(query.from_user.id)
    await query.message.edit_text("Cancelled.")


# Single consolidated text catcher for this plugin's pending actions.
# IMPORTANT: Pyrogram only invokes the *first* matching handler within a
# given group, so all "waiting for a text reply" cases handled by this
# plugin must live in one function — hence the if/elif dispatch below,
# rather than several separate @on_message(..., group=1) handlers.
# group=1 runs before the generic settings text catcher (group=2).
@Client.on_message(filters.text & filters.private, group=1)
async def rename_plugin_text_catcher(client: Client, message: Message):
    pending = get_pending(message.from_user.id)
    if not pending:
        return  # not our turn — let group=2 (settings) handle it

    action = pending.get("action")

    if action == "new_filename":
        await _handle_new_filename(client, message, pending)
    elif action == "metadata_fields":
        await _handle_metadata_fields(client, message, pending)
    elif action == "new_filename_after_edit":
        await _handle_filename_after_edit(client, message, pending)
    # any other action (e.g. a /settings field) isn't ours — leave it
    # for group=2 by not clearing it and simply returning.


async def _handle_new_filename(client, message, pending):
    message_id = pending["message_id"]
    clear_pending(message.from_user.id)
    original_msg = await client.get_messages(message.chat.id, message_id)
    new_name = safe_filename(message.text.strip())

    user = await db.get_user(message.from_user.id)
    new_name = apply_prefix_suffix(new_name, user.get("prefix"), user.get("suffix"))
    new_name = apply_word_replace(new_name, user.get("replace_words"))
    new_name = apply_regex(new_name, user.get("regex"))

    await process_and_upload(client, message, original_msg, new_name, keep_indexes=None)


# --------------------------------------------------------------------------- #
# Action: Streams / Metadata editor
# --------------------------------------------------------------------------- #
@Client.on_callback_query(filters.regex(r"^act:(\d+):edit$"))
async def act_edit(client: Client, query: CallbackQuery):
    message_id = int(query.matches[0].group(1))
    original_msg = await client.get_messages(query.message.chat.id, message_id)

    status = query.message
    await status.edit_text("**Downloading for stream inspection...**")
    start = time.time()
    src_path = await client.download_media(
        original_msg,
        file_name=os.path.join(Config.DOWNLOAD_DIR, f"src_{message_id}"),
        progress=progress_for_pyrogram,
        progress_args=("Downloading", status, start),
    )

    info = await get_media_info(src_path)
    buckets = list_streams(info)
    all_indexes = [s["index"] for group in buckets.values() for s in group]

    key = job_key(query.from_user.id, message_id)
    JOBS[key] = {
        "source_message_id": message_id,
        "src_path": src_path,
        "buckets": buckets,
        "keep": set(all_indexes),  # everything kept by default
    }

    await status.edit_text(
        "**Select streams to KEEP** (tap to toggle), then press Done.",
        reply_markup=stream_menu(key),
    )


def stream_menu(key):
    job = JOBS[key]
    rows = []
    for kind, streams in job["buckets"].items():
        for s in streams:
            mark = "✅" if s["index"] in job["keep"] else "❌"
            label = f"{mark} {kind[:1].upper()}{s['index']}: {s['codec']} ({s['lang']})"
            rows.append(
                [InlineKeyboardButton(label, callback_data=f"tog:{key}:{s['index']}")]
            )
    rows.append(
        [
            InlineKeyboardButton("🏷 Edit Metadata", callback_data=f"meta:{key}"),
            InlineKeyboardButton("✅ Done", callback_data=f"done:{key}"),
        ]
    )
    return InlineKeyboardMarkup(rows)


@Client.on_callback_query(filters.regex(r"^tog:([\w:]+):(\d+)$"))
async def toggle_stream(client: Client, query: CallbackQuery):
    key, idx = query.matches[0].group(1), int(query.matches[0].group(2))
    job = JOBS.get(key)
    if not job:
        await query.answer("Session expired, please resend the file.", show_alert=True)
        return
    if idx in job["keep"]:
        job["keep"].discard(idx)
    else:
        job["keep"].add(idx)
    await query.message.edit_reply_markup(stream_menu(key))
    await query.answer()


@Client.on_callback_query(filters.regex(r"^meta:([\w:]+)$"))
async def ask_metadata_fields(client: Client, query: CallbackQuery):
    key = query.matches[0].group(1)
    set_pending(
        query.from_user.id,
        "metadata_fields",
        job_key=key,
    )
    await query.message.reply_text(
        "Send metadata as `field=value` pairs, one per line. Supported fields:\n"
        "`title`, `artist`, `album`, `year`, `audio_title`, `subtitle_title`\n\n"
        "Example:\n`title=My Movie`\n`artist=Studio X`\n`year=2026`\n\n"
        "Send /cancel to skip metadata editing."
    )
    await query.answer()


async def _handle_metadata_fields(client, message, pending):
    key = pending["job_key"]
    clear_pending(message.from_user.id)
    job = JOBS.get(key)
    if not job:
        await message.reply_text("Session expired, please resend the file.")
        return

    fields = {}
    for line in message.text.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip().lower()] = v.strip()
    job["metadata"] = fields
    await message.reply_text(
        "✅ Metadata noted. Tap **Done** on the stream menu to continue.",
        reply_markup=stream_menu(key),
    )


@Client.on_callback_query(filters.regex(r"^done:([\w:]+)$"))
async def finish_stream_selection(client: Client, query: CallbackQuery):
    key = query.matches[0].group(1)
    job = JOBS.get(key)
    if not job:
        await query.answer("Session expired, please resend the file.", show_alert=True)
        return

    set_pending(query.from_user.id, "new_filename_after_edit", job_key=key)
    await query.message.edit_text(
        "Send the new file name (with extension), or /keep to keep the original name."
    )
    await query.answer()


async def _handle_filename_after_edit(client, message, pending):
    key = pending["job_key"]
    clear_pending(message.from_user.id)
    job = JOBS.get(key)
    if not job:
        await message.reply_text("Session expired, please resend the file.")
        return

    message_id = job["source_message_id"]
    original_msg = await client.get_messages(message.chat.id, message_id)

    if message.text.strip() == "/keep":
        new_name = original_filename(original_msg)
    else:
        new_name = safe_filename(message.text.strip())

    user = await db.get_user(message.from_user.id)
    new_name = apply_prefix_suffix(new_name, user.get("prefix"), user.get("suffix"))
    new_name = apply_word_replace(new_name, user.get("replace_words"))
    new_name = apply_regex(new_name, user.get("regex"))

    status = await message.reply_text("**Processing streams/metadata...**")
    src_path = job["src_path"]
    keep = sorted(job["keep"])
    remapped_path = os.path.join(Config.DOWNLOAD_DIR, f"remap_{message_id}_{new_name}")

    ok = await remap_streams(src_path, remapped_path, keep)
    work_path = remapped_path if ok else src_path

    meta = job.get("metadata", {})
    if meta:
        meta_out = os.path.join(Config.DOWNLOAD_DIR, f"meta_{message_id}_{new_name}")
        ok2 = await set_metadata(
            work_path,
            meta_out,
            title=meta.get("title"),
            artist=meta.get("artist"),
            album=meta.get("album"),
            year=meta.get("year"),
            audio_title=meta.get("audio_title"),
            subtitle_title=meta.get("subtitle_title"),
        )
        if ok2:
            if work_path != src_path:
                try:
                    os.remove(work_path)
                except OSError:
                    pass
            work_path = meta_out

    await upload_result(client, message, status, work_path, new_name)

    for p in {src_path, remapped_path, work_path}:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    JOBS.pop(key, None)


# --------------------------------------------------------------------------- #
# Action: Unzip
# --------------------------------------------------------------------------- #
@Client.on_callback_query(filters.regex(r"^act:(\d+):unzip$"))
async def act_unzip(client: Client, query: CallbackQuery):
    message_id = int(query.matches[0].group(1))
    original_msg = await client.get_messages(query.message.chat.id, message_id)

    status = query.message
    await status.edit_text("**Downloading zip file...**")
    start = time.time()
    zip_path = await client.download_media(
        original_msg,
        file_name=os.path.join(Config.DOWNLOAD_DIR, f"zip_{message_id}.zip"),
        progress=progress_for_pyrogram,
        progress_args=("Downloading", status, start),
    )

    await status.edit_text("**Extracting...**")
    extract_dir = os.path.join(Config.DOWNLOAD_DIR, f"extracted_{message_id}")
    files = unzip_file(zip_path, extract_dir)
    files = [f for f in files if os.path.isfile(f)]

    if not files:
        await status.edit_text("The zip file appears to be empty.")
        return

    user = await db.get_user(query.from_user.id)
    await status.edit_text(f"**Found {len(files)} file(s). Uploading...**")

    for i, path in enumerate(files, 1):
        name = apply_prefix_suffix(
            os.path.basename(path), user.get("prefix"), user.get("suffix")
        )
        await status.edit_text(f"**Uploading {i}/{len(files)}:** `{name}`")
        await upload_result(client, query.message, status, path, name, silent_final=True)

    await status.edit_text(f"✅ Done — uploaded {len(files)} file(s).")

    try:
        os.remove(zip_path)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Shared processing helpers
# --------------------------------------------------------------------------- #
async def process_and_upload(client, message, original_msg, new_name, keep_indexes):
    status = await message.reply_text("**Downloading...**")
    start = time.time()
    src_path = await client.download_media(
        original_msg,
        file_name=os.path.join(Config.DOWNLOAD_DIR, f"src_{original_msg.id}"),
        progress=progress_for_pyrogram,
        progress_args=("Downloading", status, start),
    )
    await upload_result(client, message, status, src_path, new_name)
    try:
        os.remove(src_path)
    except OSError:
        pass
    JOBS.pop(job_key(message.from_user.id, original_msg.id), None)


async def upload_result(client, message, status, file_path, new_name, silent_final=False):
    """Renames the local file to `new_name` then uploads it either to
    Telegram (with thumbnail/caption) or GoFile, per the user's settings."""
    final_path = os.path.join(os.path.dirname(file_path), safe_filename(new_name))
    if file_path != final_path:
        os.replace(file_path, final_path)

    user = await db.get_user(message.from_user.id)
    filesize = humanbytes(os.path.getsize(final_path))

    if user.get("upload_mode") == "gofile":
        await status.edit_text("**Uploading to GoFile...**")
        link = await upload_to_gofile(final_path, token=user.get("gofile_token"))
        if link:
            if not silent_final:
                await status.edit_text(f"✅ **Uploaded!**\n\n**{new_name}**\n{link}")
        else:
            await status.edit_text("❌ GoFile upload failed. Check your token in /settings.")
        try:
            os.remove(final_path)
        except OSError:
            pass
        return

    caption_template = user.get("caption") or Config.DEFAULT_CAPTION
    caption = caption_template.format(filename=new_name, filesize=filesize, duration="")
    thumb = user.get("file_id")

    start = time.time()
    ext = os.path.splitext(new_name)[1].lower()
    send_kwargs = dict(
        chat_id=message.chat.id,
        caption=caption,
        thumb=thumb,
        progress=progress_for_pyrogram,
        progress_args=("Uploading", status, start),
    )

    if not silent_final:
        await status.edit_text("**Uploading to Telegram...**")

    try:
        if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
            await client.send_video(video=final_path, **send_kwargs)
        elif ext in (".mp3", ".m4a", ".flac", ".wav", ".ogg"):
            await client.send_audio(audio=final_path, **send_kwargs)
        else:
            await client.send_document(document=final_path, **send_kwargs)
        if not silent_final:
            await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Upload failed: {e}")
    finally:
        try:
            os.remove(final_path)
        except OSError:
            pass
