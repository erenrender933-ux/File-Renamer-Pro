from pyrogram import Client, filters
from pyrogram.types import Message

from helpers.database import db


@Client.on_message(filters.command("thumb") & filters.private)
async def thumb_cmd(client: Client, message: Message):
    thumb = await db.get_thumbnail(message.from_user.id)
    if thumb:
        await client.send_photo(
            message.chat.id,
            photo=thumb,
            caption="This is your current thumbnail.\n\n"
            "Send a photo to replace it, or /delthumb to remove it.",
        )
    else:
        await message.reply_text(
            "You don't have a custom thumbnail set.\n\n"
            "Send me a photo and I'll save it as your thumbnail."
        )


@Client.on_message(filters.command("delthumb") & filters.private)
async def del_thumb_cmd(client: Client, message: Message):
    await db.set_thumbnail(message.from_user.id, None)
    await message.reply_text("Thumbnail deleted.")


@Client.on_message(filters.photo & filters.private)
async def save_thumb(client: Client, message: Message):
    await db.set_thumbnail(message.from_user.id, message.photo.file_id)
    await message.reply_text("✅ Thumbnail saved! It will be used for future uploads.")
