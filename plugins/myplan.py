from pyrogram import Client, filters
from pyrogram.types import Message

from helpers.database import db


@Client.on_message(filters.command("my_plan") & filters.private)
async def my_plan_cmd(client: Client, message: Message):
    user = await db.get_user(message.from_user.id)
    plan = user.get("plan", "free")
    expiry = user.get("plan_expiry")

    text = f"**📄 Your Plan:** `{plan.title()}`\n"
    if plan != "free" and expiry:
        text += f"**Expires:** `{expiry}`\n"
    else:
        text += (
            "\nFree plan limits: 1 file at a time, standard speed.\n"
            "Contact the bot owner to upgrade."
        )
    await message.reply_text(text)
