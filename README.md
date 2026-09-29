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
Filerenamebot/
├── bot.py                 # entrypoint
├── config.py               # env-driven settings
├── requirements.txt
├── nixpacks.toml            # Railway build (installs Python + ffmpeg)
├── railway.toml
├── Procfile
├── Dockerfile               # optional, if you deploy outside Railway
├── .env.example
├── helpers/
│   ├── database.py         # MongoDB (motor) wrapper
│   ├── progress.py          # progress bar / humanbytes / ETA
│   ├── metadata.py          # ffprobe/ffmpeg: streams + metadata
│   ├── utils.py              # rename rules, zip handling
│   ├── gofile.py             # GoFile.io upload
│   └── state.py              # tiny in-memory "waiting for text" tracker
└── plugins/
├── start.py               # /start, help & features menu
├── settings.py            # /settings menu
├── thumbnail.py           # /thumb, /delthumb
├── mediainfo.py           # /mediainfo
├── myplan.py              # /my_plan
└── rename.py              # the core file → rename/edit/unzip → upload flow
## 1. Get your credentials
1. **API_ID / API_HASH** — https://my.telegram.org → API Development Tools.
2. **BOT_TOKEN** — talk to [@BotFather](https://t.me/BotFather) → `/newbot`.
3. **DB_URL** — create a free cluster at https://www.mongodb.com/atlas,
   add a database user, then copy the connection string (Drivers → Python).
4. **OWNER_ID** — message [@userinfobot](https://t.me/userinfobot) to get your numeric ID.

## 2. Run locally (optional, for testing)
```bash
git clone <your-repo-url>
cd Filerenamebot
pip install -r requirements.txt
cp .env.example .env      # fill in the values
export $(cat .env | xargs)
python bot.py
ffmpeg must be installed and on PATH locally (sudo apt install ffmpeg on
Debian/Ubuntu, brew install ffmpeg on macOS).
3. Deploy on Railway
Push this folder to a GitHub repo.
On https://railway.app → New Project → Deploy from GitHub repo.
Open the service → Variables tab → paste every key from .env.example
with your real values.
Railway reads nixpacks.toml, which installs Python and ffmpeg, then
runs python bot.py. No extra buildpack config needed.
Once deployed, check the Deployments → Logs tab for
Bot started as @yourbotname.
4. Bot Commands
Command
Description
/start
Welcome message + Help/Features buttons
/settings
Upload destination, caption, prefix, suffix, word replace, regex replace, GoFile token
/thumb
View your saved thumbnail (send a photo to set one)
/delthumb
Delete your saved thumbnail
/mediainfo
Reply to a file to inspect its video/audio/subtitle streams
/my_plan
Check your subscription status
/cancel
Cancel whatever the bot is currently waiting for from
4. Bot Commands
Command
Description
/start
Welcome message + Help/Features buttons
/settings
Upload destination, caption, prefix, suffix, word replace, regex replace, GoFile token
/thumb
View your saved thumbnail (send a photo to set one)
/delthumb
Delete your saved thumbnail
/mediainfo
Reply to a file to inspect its video/audio/subtitle streams
/my_plan
Check your subscription status
/cancel
Cancel whatever the bot is currently waiting for from you
5. Using the bot
Send any video/audio/document/zip file.
Pick Rename, Streams/Metadata, or (for zips) Unzip & Upload.
Notes on the stream editor
Stream removal and metadata edits use ffmpeg -c copy (stream copy), so
they're fast — no re-encoding, no quality loss. Audio-swap re-encodes only
if needed to match durations (see helpers/metadata.py:swap_audio).
Extending further
helpers/state.py is an in-memory dict — fine for one worker process.
If you scale to multiple instances, back it with Redis instead.
plugins/rename.py keeps per-file job data in the JOBS dict; long-lived
jobs across bot restarts aren't preserved (as with most Telegram bots).
## BotFather commands list

Paste this into **@BotFather → /setcommands** for your bot:
start - Show welcome menu
settings - Upload destination, caption, prefix/suffix, replace rules
thumb - View or set your custom thumbnail
delthumb - Delete your custom thumbnail
mediainfo - Reply to a file to see its streams
my_plan - Check your subscription status
cancel - Cancel the current pending action
