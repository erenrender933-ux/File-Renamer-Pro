import os


class Config(object):
    # Core Telegram API credentials — get these from https://my.telegram.org
    API_ID = int(os.environ.get("API_ID", "15055049"))
    API_HASH = os.environ.get("API_HASH", "abe3f66fcd80c91e53009ba52c7b3a83")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8779608833:AAGLQekF5jV8h0_z4dApcEQb0imUlVohY4g")

    # MongoDB Atlas connection string
    DB_URL = os.environ.get("DB_URL", "mongodb+srv://azeezbashaimran_db_user:F0NZSClydlcL2TBI@cluster0.sjw3p5j.mongodb.net/?appName=Cluster0")
    DB_NAME = os.environ.get("DB_NAME", "azeezbashaimran_db_user")

    # Telegram numeric user ID of the bot owner (get from @userinfobot)
    OWNER_ID = int(os.environ.get("OWNER_ID", "7653921320"))

    # Comma separated list of admin user ids, e.g. "123,456"
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split(",") if x.strip()]

    # Force-subscribe channel (optional). Leave blank ("") to disable.
    FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "-1002649539214")

    # Log channel where the bot posts activity (optional, leave blank to disable)
    LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "-1003931247038")

    # Default caption template. {filename}, {filesize}, {duration} are supported.
    DEFAULT_CAPTION = os.environ.get(
        "DEFAULT_CAPTION", "**{filename}**\n\n💾 Size: {filesize}"
    )

    # Max concurrent downloads/uploads per user
    MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "1"))

    # Download chunk / progress update throttle (seconds)
    PROGRESS_UPDATE_INTERVAL = 6

    # Working directory for temp downloads
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads")

    # GoFile.io — user tokens are stored per-user in DB, this is just the base API
    GOFILE_API = "https://api.gofile.io"

    START_PIC = os.environ.get(
        "START_PIC", "https://ibb.co/hJHGFfxs"
    )
