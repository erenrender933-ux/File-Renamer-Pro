import aiohttp

from config import Config


async def get_best_server():
    """GoFile requires uploading to a specific 'best' server."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{Config.GOFILE_API}/getServer") as resp:
            data = await resp.json()
            return data["data"]["server"]


async def upload_to_gofile(file_path, token=None, folder_id=None, progress_callback=None):
    """
    Uploads a file to GoFile. If `token` is provided, the file is linked
    to that user's GoFile account (so it appears in their dashboard);
    otherwise it's uploaded anonymously.
    Returns the public download page URL, or None on failure.
    """
    server = await get_best_server()
    url = f"https://{server}.gofile.io/uploadFile"

    data = aiohttp.FormData()
    data.add_field(
        "file",
        open(file_path, "rb"),
        filename=file_path.split("/")[-1],
    )
    if token:
        data.add_field("token", token)
    if folder_id:
        data.add_field("folderId", folder_id)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            result = await resp.json()
            if result.get("status") == "ok":
                return result["data"].get("downloadPage")
            return None
