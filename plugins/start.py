from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from helpers.database import db

START_TEXT = """Welcome {mention} 👋

Send me any **video, audio, document or zip file** and I'll rename it for you.
I can also edit metadata, strip unwanted audio/subtitle streams, add a custom
thumbnail, and upload the result to Telegram or GoFile.

Use the buttons below to explore what I can do."""

FEATURES_TEXT = """**Manual Rename Bot Features**

⚡ **High Speed Download**
• Fast Transfers: optimized chunked download with a live progress bar.

📥 **Upload & Storage**
• Telegram: custom thumbnail, caption, split size, upload chat.
• GoFile: upload using your own User Token and Folder ID.

🎬 **Media & Metadata**
• Video Tools: extract streams, audio swap, remove streams.
• Metadata: modify video title, description, artist, album, year,
  audio title, and subtitle title.

📦 **Archive Tools**
• Auto-detects .zip files and offers to unzip and rename contents.

🛠 **Extra Tools**
• Renaming: add prefix/suffix, regex or simple word replacement.
"""

HELP_TEXT = """**How to use me**

1. Send a file (video/audio/document/zip).
2. Choose **Rename**, **Metadata**, or (for zips) **Unzip**.
3. If renaming, send the new filename — keep or change the extension.
4. For videos, pick which audio/subtitle streams to keep.
5. I'll download, process and upload the file, with a progress bar
   at every step.

**Commands**
/start - show this menu
/settings - upload destination, thumbnail, caption, prefix/suffix
/thumb - set or view your custom thumbnail
/mediainfo - inspect a file's streams
/my_plan - check your subscription
"""


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await db.get_user(message.from_user.id)  # ensures a DB record exists
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 Update Channel", url="https://t.me/"),
                InlineKeyboardButton("🌐 Network", url="https://t.me/"),
            ],
            [
                InlineKeyboardButton("📚 Help", callback_data="help"),
                InlineKeyboardButton("🤖 Features", callback_data="features"),
            ],
        ]
    )
    await message.reply_text(
        START_TEXT.format(mention=message.from_user.mention),
        reply_markup=buttons,
    )


@Client.on_callback_query(filters.regex("^help$"))
async def help_cb(client, query):
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    )
    await query.message.edit_text(HELP_TEXT, reply_markup=buttons)


@Client.on_callback_query(filters.regex("^features$"))
async def features_cb(client, query):
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    )
    await query.message.edit_text(FEATURES_TEXT, reply_markup=buttons)


@Client.on_callback_query(filters.regex("^home$"))
async def home_cb(client, query):
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 Update Channel", url="https://t.me/Anime_Hub_Tamil"),
                InlineKeyboardButton("🌐 Network", url="https://t.me/Anime_Hub_Tamil"),
            ],
            [
                InlineKeyboardButton("📚 Help", callback_data="help"),
                InlineKeyboardButton("🤖 Features", callback_data="features"),
            ],
        ]
    )
    await query.message.edit_text(
        START_TEXT.format(mention=query.from_user.mention), reply_markup=buttons
    )
