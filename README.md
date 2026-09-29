# File Rename Bot (Pyrogram)

A Telegram bot to rename video/audio/document files, edit metadata, strip
unwanted audio/subtitle streams, unzip archives, and upload the result to
Telegram or GoFile — with live progress bars throughout.

## Features
- ✏️ Rename with custom filename, prefix/suffix, word replace, regex replace
- 🖼 Custom thumbnail (`/thumb`) and caption template (`/settings`)
- 🎬 Stream editor: pick which video/audio/subtitle streams to keep
- 🏷 Metadata editor: title, artist, album, year, audio title, subtitle title
- 📦 Auto-detects `.zip` uploads and offers to unzip + upload every file inside
- 📤 Upload destination toggle: Telegram (default) or your own GoFile account
- ⚡ Progress bar with speed/ETA on every download and upload
- 🗄 Per-user settings stored in MongoDB (survives restarts)

## Repo structure
