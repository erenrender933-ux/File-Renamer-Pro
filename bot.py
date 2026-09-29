import logging
import os

from pyrogram import Client

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

LOGGER = logging.getLogger(__name__)

os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)


class RenameBot(Client):
    def __init__(self):
        super().__init__(
            name="filerenamebot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="plugins"),
            workers=50,
            sleep_threshold=15,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username = me.username
        LOGGER.info(f"Bot started as @{me.username}")
        if Config.LOG_CHANNEL:
            try:
                await self.send_message(
                    Config.LOG_CHANNEL, f"✅ **{me.first_name}** restarted successfully."
                )
            except Exception as e:
                LOGGER.warning(f"Could not send startup message to LOG_CHANNEL: {e}")

    async def stop(self, *args):
        await super().stop()
        LOGGER.info("Bot stopped.")


if __name__ == "__main__":
    RenameBot().run()
