import aiohttp


async def handle(message, *args, user=None, token=None, repo=None, labels=None):
    if not user or not token:
        return
    auth = aiohttp.BasicAuth(user, token)
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    if len(args) == 2:
        data = {
            "title": args[0],
            "body": args[1],
        }
    else:
        data = {
            "title": " ".join(args),
        }
    if labels:
        data["labels"] = labels
    async with aiohttp.ClientSession(headers=headers, auth=auth) as session:
        async with session.post(url, json=data) as resp:
            issue = await resp.json()
            await message.reply(issue["html_url"])
