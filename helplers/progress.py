import time

from config import Config

# Keeps last-edit timestamps per message so we don't hit Telegram flood limits
_last_update = {}


def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while size > power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}"


def time_formatter(seconds):
    seconds = int(seconds)
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for name, secs in periods:
        if seconds >= secs:
            value, seconds = divmod(seconds, secs)
            result += f"{value}{name} "
    return result.strip() or "0s"


def make_bar(percentage, length=12):
    filled = int(length * percentage / 100)
    return "▣" * filled + "▢" * (length - filled)


async def progress_for_pyrogram(current, total, status, message, start_time):
    """
    Generic progress callback compatible with Pyrogram's download/upload
    progress hook signature (current, total). `status` is a short label
    like "Downloading" or "Uploading".
    """
    now = time.time()
    key = message.id
    last = _last_update.get(key, 0)

    # throttle edits: Telegram rate-limits fast edits
    if (now - last) < Config.PROGRESS_UPDATE_INTERVAL and current != total:
        return
    _last_update[key] = now

    elapsed = now - start_time
    percentage = current * 100 / total if total else 0
    speed = current / elapsed if elapsed else 0
    eta = (total - current) / speed if speed else 0

    text = (
        f"**{status}...**\n\n"
        f"`[{make_bar(percentage)}]` {percentage:.1f}%\n\n"
        f"**Done:** {humanbytes(current)} / {humanbytes(total)}\n"
        f"**Speed:** {humanbytes(speed)}/s\n"
        f"**ETA:** {time_formatter(eta)}"
    )

    try:
        await message.edit_text(text)
    except Exception:
        # message not modified / flood wait — safe to ignore for a progress bar
        pass
