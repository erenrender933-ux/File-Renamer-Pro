import os
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.metadata import get_media_info, list_streams
from helpers.progress import progress_for_pyrogram


@Client.on_message(filters.command("mediainfo") & filters.private)
async def mediainfo_cmd(client: Client, message: Message):
    target = message.reply_to_message
    if not target or not (target.video or target.audio or target.document):
        await message.reply_text(
            "Reply to a video, audio, or document with /mediainfo to inspect its streams."
        )
        return

    status = await message.reply_text("**Downloading for inspection...**")
    start = time.time()
    file_path = await client.download_media(
        target,
        file_name=os.path.join(Config.DOWNLOAD_DIR, f"probe_{message.id}"),
        progress=progress_for_pyrogram,
        progress_args=("Downloading", status, start),
    )

    await status.edit_text("**Probing streams...**")
    info = await get_media_info(file_path)
    buckets = list_streams(info)

    lines = ["**📊 Media Info**\n"]
    for kind, streams in buckets.items():
        if not streams:
            continue
        lines.append(f"**{kind.title()} streams:**")
        for s in streams:
            title = f" — {s['title']}" if s["title"] else ""
            lines.append(f"  `[{s['index']}]` {s['codec']} ({s['lang']}){title}")
    if not any(buckets.values()):
        lines.append("No readable streams found.")

    await status.edit_text("\n".join(lines))

    try:
        os.remove(file_path)
    except OSError:
        pass
