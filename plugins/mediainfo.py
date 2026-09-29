import os
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from helpers.metadata import get_media_info, list_streams
from helpers.progress import progress_for_pyrogram


@Client.on_message(filters.command("mediainfo") & filters.private)
async def mediainfo_cmd(client: Client, message: Message):
    target = message.reply_to_message

    if not target or not (
        target.video
        or target.audio
        or target.document
    ):
        await message.reply_text(
            "Reply to a video, audio, or document with /mediainfo to inspect its streams."
        )
        return

    status = await message.reply_text(
        "**Downloading for inspection...**"
    )

    start = time.time()
    file_path = None

    try:
        file_path = await client.download_media(
            target,
            file_name=os.path.join(
                Config.DOWNLOAD_DIR,
                f"probe_{message.id}"
            ),
            progress=progress_for_pyrogram,
            progress_args=("Downloading", status, start),
        )

        if not file_path or not os.path.exists(file_path):
            await status.edit_text(
                "❌ **Download failed.**"
            )
            return

        await status.edit_text(
            "**🔍 Probing streams...**"
        )

        # Run FFprobe
        info = await get_media_info(file_path)

        # FFprobe failed
        if not info:
            await status.edit_text(
                "❌ **Unable to read media streams.**\n\n"
                "FFprobe could not analyze this file."
            )
            return

        # Group streams
        buckets = list_streams(info)

        lines = [
            "**📊 Media Info**",
            ""
        ]

        for kind, streams in buckets.items():

            if not streams:
                continue

            lines.append(
                f"**{kind.title()} streams:**"
            )

            for s in streams:

                title = (
                    f" — {s['title']}"
                    if s["title"]
                    else ""
                )

                lines.append(
                    f"  `[{s['index']}]` "
                    f"{s['codec']} "
                    f"({s['lang']})"
                    f"{title}"
                )

            lines.append("")

        # FFprobe succeeded but no streams were detected
        if not any(buckets.values()):
            lines.append(
                "⚠️ **No readable streams found.**"
            )

        await status.edit_text(
            "\n".join(lines)
        )

    except Exception as e:

        print(
            f"MEDIAINFO ERROR: "
            f"{type(e).__name__}: {e}"
        )

        try:
            await status.edit_text(
                "❌ **Media info failed.**\n\n"
                f"`{type(e).__name__}: {e}`"
            )
        except Exception:
            pass

    finally:

        # Remove temporary downloaded file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
