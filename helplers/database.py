import motor.motor_asyncio

from config import Config


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users

    def new_user(self, user_id):
        return dict(
            _id=user_id,
            file_id=None,           # custom thumbnail file_id
            caption=None,           # custom caption template
            prefix=None,            # filename prefix
            suffix=None,            # filename suffix
            replace_words=None,     # "old:new,old2:new2" simple word replace
            regex=None,             # regex pattern for renaming
            upload_mode="telegram", # "telegram" or "gofile"
            gofile_token=None,      # user's own GoFile API token
            gofile_folder=None,     # optional GoFile folder id
            format_template=None,   # metadata: video/audio title template
            metadata_enabled=False,
            plan="free",
            plan_expiry=None,
        )

    async def add_user(self, user_id):
        user = self.new_user(user_id)
        await self.users.insert_one(user)

    async def is_user_exist(self, user_id):
        found = await self.users.find_one({"_id": user_id})
        return bool(found)

    async def get_user(self, user_id):
        user = await self.users.find_one({"_id": user_id})
        if not user:
            await self.add_user(user_id)
            user = await self.users.find_one({"_id": user_id})
        return user

    async def update_field(self, user_id, field, value):
        await self.users.update_one(
            {"_id": user_id}, {"$set": {field: value}}, upsert=True
        )

    # --- convenience wrappers -------------------------------------------------
    async def set_thumbnail(self, user_id, file_id):
        await self.update_field(user_id, "file_id", file_id)

    async def get_thumbnail(self, user_id):
        user = await self.get_user(user_id)
        return user.get("file_id")

    async def set_caption(self, user_id, caption):
        await self.update_field(user_id, "caption", caption)

    async def get_caption(self, user_id):
        user = await self.get_user(user_id)
        return user.get("caption")

    async def set_prefix_suffix(self, user_id, prefix=None, suffix=None):
        update = {}
        if prefix is not None:
            update["prefix"] = prefix
        if suffix is not None:
            update["suffix"] = suffix
        if update:
            await self.users.update_one({"_id": user_id}, {"$set": update}, upsert=True)

    async def set_upload_mode(self, user_id, mode):
        await self.update_field(user_id, "upload_mode", mode)

    async def set_gofile_token(self, user_id, token):
        await self.update_field(user_id, "gofile_token", token)

    async def get_all_users(self):
        return self.users.find({})

    async def total_users_count(self):
        return await self.users.count_documents({})


db = Database(Config.DB_URL, Config.DB_NAME)
