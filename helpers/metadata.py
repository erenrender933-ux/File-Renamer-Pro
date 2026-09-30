import os
import json
import asyncio
import motor.motor_asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# ==========================================
# DATABASE SETUP (MONGODB)
# ==========================================

# Ungaloda MongoDB Atlas URI-a inga maathikonga allathu config-il irunthu import pannunga
MONGODB_URI = os.environ.get("MONGODB_URI", "YOUR_MONGODB_URI_HERE")

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.metadata

    async def save_meta(self, user_id, key, value):
        await self.col.update_one(
            {"_id": user_id},
            {"$set": {key: value}},
            upsert=True
        )

    async def get_meta(self, user_id):
        user_data = await self.col.find_one({"_id": user_id})
        return user_data if user_data else {}

db = Database(MONGODB_URI, "FileRenamerPro")

# ==========================================
# FFMPEG & FFPROBE FUNCTIONS
# ==========================================

FFPROBE_CMD = (
    'ffprobe -v quiet -print_format json -show_format -show_streams "{file}"'
)

async def get_media_info(file_path):
    """Run ffprobe and return parsed media information."""
    if not file_path or not os.path.exists(file_path):
        return None

    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        print(
            f"FFPROBE ERROR ({process.returncode}): "
            f"{stderr.decode(errors='replace')}"
        )
        return None

    try:
        return json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        print(f"FFPROBE JSON ERROR: {e}")
        print(stdout.decode(errors="replace")[:2000])
        return None


def list_streams(info):
    """
    Groups streams from ffprobe info into video/audio/subtitle buckets.
    Returns a dict: {"video": [...], "audio": [...], "subtitle": [...]}
    Each entry: {"index": int, "codec": str, "lang": str, "title": str}
    """
    buckets = {"video": [], "audio": [], "subtitle": []}
    if not info:
        return buckets
    for stream in info.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type not in buckets:
            continue
        tags = stream.get("tags", {})
        buckets[codec_type].append(
            {
                "index": stream.get("index"),
                "codec": stream.get("codec_name", "unknown"),
                "lang": tags.get("language", "und"),
                "title": tags.get("title", ""),
            }
        )
    return buckets


async def remap_streams(input_path, output_path, keep_indexes):
    """
    Re-muxes the file keeping only the stream indexes in `keep_indexes`
    (a list of ints). Uses stream copy so it's fast — no re-encoding.
    """
    map_args = " ".join(f"-map 0:{i}" for i in keep_indexes)
    cmd = (
        f'ffmpeg -y -i "{input_path}" {map_args} -c copy '
        f'-map_metadata 0 "{output_path}"'
    )
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_path)


async def set_metadata(
    input_path,
    output_path,
    title=None,
    artist=None,
    album=None,
    year=None,
    audio_title=None,
    subtitle_title=None,
):
    """
    Rewrites container-level and per-stream metadata without re-encoding.
    Any field left as None is skipped.
    """
    meta_args = []
    if title:
        meta_args.append(f'-metadata title="{title}"')
    if artist:
        meta_args.append(f'-metadata artist="{artist}"')
    if album:
        meta_args.append(f'-metadata album="{album}"')
    if year:
        meta_args.append(f'-metadata date="{year}"')
    if audio_title:
        meta_args.append(f'-metadata:s:a:0 title="{audio_title}"')
    if subtitle_title:
        meta_args.append(f'-metadata:s:s:0 title="{subtitle_title}"')

    cmd = (
        f'ffmpeg -y -i "{input_path}" -map 0 -c copy '
        f'{" ".join(meta_args)} "{output_path}"'
    )
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_path)


async def swap_audio(video_path, new_audio_path, output_path):
    """Replaces the audio track of a video with a new audio file."""
    cmd = (
        f'ffmpeg -y -i "{video_path}" -i "{new_audio_path}" '
        f'-map 0:v -map 1:a -c:v copy -shortest "{output_path}"'
    )
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_path)

# ==========================================
# PYROGRAM COMMAND HANDLER (/meta)
# ==========================================

@Client.on_message(filters.command("meta") & filters.private)
async def meta_command(client: Client, message: Message):
    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        user_meta = await db.get_meta(message.from_user.id)
        current_meta = "\n".join([f"**{k.title()}**: `{v}`" for k, v in user_meta.items() if k != "_id"])
        
        text = (
            "**⚙️ Metadata Settings**\n\n"
            "**Usage:** `/meta <key> <value>`\n"
            "**Valid Keys:** `title`, `artist`, `album`, `year`, `audio_title`, `subtitle_title`\n\n"
            "**Current Saved Metadata:**\n"
            f"{current_meta if current_meta else 'No metadata saved yet.'}"
        )
        await message.reply_text(text)
        return

    key = args[1].lower()
    value = args[2]
    
    valid_keys = ["title", "artist", "album", "year", "audio_title", "subtitle_title"]
    
    if key not in valid_keys:
        await message.reply_text(f"❌ Invalid key! Please use one of:\n`{', '.join(valid_keys)}`")
        return

    await db.save_meta(message.from_user.id, key, value)
    await message.reply_text(f"✅ Metadata updated in database!\n**{key.title()}**: `{value}`")
    
