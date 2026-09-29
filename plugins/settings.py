from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from helpers.database import db
from helpers.state import clear_pending, get_pending, set_pending


def settings_menu(user):
    mode = user.get("upload_mode", "telegram")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"📤 Upload: {mode.title()}", callback_data="set_uploadmode"
                )
            ],
            [
                InlineKeyboardButton("✏️ Caption", callback_data="set_caption"),
                InlineKeyboardButton("🖼 Thumbnail", callback_data="set_thumb_info"),
            ],
            [
                InlineKeyboardButton("➕ Prefix", callback_data="set_prefix"),
                InlineKeyboardButton("➕ Suffix", callback_data="set_suffix"),
            ],
            [
                InlineKeyboardButton("🔤 Word Replace", callback_data="set_replace"),
                InlineKeyboardButton("🔣 Regex Replace", callback_data="set_regex"),
            ],
            [InlineKeyboardButton("🔑 GoFile Token", callback_data="set_gofile")],
            [InlineKeyboardButton("❌ Close", callback_data="close_settings")],
        ]
    )


@Client.on_message(filters.command("settings") & filters.private)
async def settings_cmd(client: Client, message: Message):
    user = await db.get_user(message.from_user.id)
    await message.reply_text(
        "**⚙️ Your Settings**\n\nTap a button to change it.",
        reply_markup=settings_menu(user),
    )


@Client.on_callback_query(filters.regex("^set_uploadmode$"))
async def toggle_upload_mode(client: Client, query: CallbackQuery):
    user = await db.get_user(query.from_user.id)
    new_mode = "gofile" if user.get("upload_mode", "telegram") == "telegram" else "telegram"
    await db.set_upload_mode(query.from_user.id, new_mode)
    user["upload_mode"] = new_mode
    await query.message.edit_reply_markup(settings_menu(user))
    await query.answer(f"Upload destination set to {new_mode.title()}")


@Client.on_callback_query(filters.regex("^set_thumb_info$"))
async def thumb_info(client: Client, query: CallbackQuery):
    await query.answer(
        "Use /thumb to view your thumbnail, or send a photo to set one.",
        show_alert=True,
    )


@Client.on_callback_query(filters.regex("^set_caption$"))
async def ask_caption(client: Client, query: CallbackQuery):
    set_pending(query.from_user.id, "caption")
    await query.message.reply_text(
        "Send your new caption template.\n\n"
        "Placeholders: `{filename}`, `{filesize}`, `{duration}`\n"
        "Send /cancel to abort."
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^set_prefix$"))
async def ask_prefix(client: Client, query: CallbackQuery):
    set_pending(query.from_user.id, "prefix")
    await query.message.reply_text("Send the prefix to add before every filename.")
    await query.answer()


@Client.on_callback_query(filters.regex("^set_suffix$"))
async def ask_suffix(client: Client, query: CallbackQuery):
    set_pending(query.from_user.id, "suffix")
    await query.message.reply_text("Send the suffix to add after every filename (before the extension).")
    await query.answer()


@Client.on_callback_query(filters.regex("^set_replace$"))
async def ask_replace(client: Client, query: CallbackQuery):
    set_pending(query.from_user.id, "replace_words")
    await query.message.reply_text(
        "Send word pairs to replace, comma separated:\n`old:new,foo:bar`"
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^set_regex$"))
async def ask_regex(client: Client, query: CallbackQuery):
    set_pending(query.from_user.id, "regex")
    await query.message.reply_text(
        "Send your pattern and replacement separated by `###`:\n"
        "`S(\\d+)E(\\d+)###Season \\1 Episode \\2`"
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^set_gofile$"))
async def ask_gofile(client: Client, query: CallbackQuery):
    set_pending(query.from_user.id, "gofile_token")
    await query.message.reply_text(
        "Send your GoFile API token (from gofile.io account settings).\n"
        "This links uploads to your own GoFile account."
    )
    await query.answer()


@Client.on_callback_query(filters.regex("^close_settings$"))
async def close_settings(client: Client, query: CallbackQuery):
    await query.message.delete()


@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    clear_pending(message.from_user.id)
    await message.reply_text("Cancelled.")


# Catches plain text replies while a setting is "pending" for this user.
# Must be registered with a low group priority relative to the rename
# filename handler in plugins/rename.py (see that file's group=1).
@Client.on_message(filters.text & filters.private, group=2)
async def settings_text_catcher(client: Client, message: Message):
    pending = get_pending(message.from_user.id)
    if not pending:
        return  # let other handlers (e.g. rename filename input) see it

    action = pending["action"]
    value = message.text.strip()
    field_map = {
        "caption": "caption",
        "prefix": "prefix",
        "suffix": "suffix",
        "replace_words": "replace_words",
        "regex": "regex",
        "gofile_token": "gofile_token",
    }
    field = field_map.get(action)
    if field:
        await db.update_field(message.from_user.id, field, value)
        await message.reply_text(f"✅ Saved.")
    clear_pending(message.from_user.id)
