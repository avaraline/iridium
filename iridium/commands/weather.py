import aiohttp

ENDPOINT = "http://api.openweathermap.org/data/2.5/weather"


async def handle(message, *args, appid=None):
    if not appid:
        return
    params = {
        "units": "imperial",
        "appid": appid,
    }
    if len(args) == 1 and args[0].isdigit():
        params["zip"] = args[0]
    else:
        params["q"] = " ".join(args)
    async with aiohttp.ClientSession() as session:
        async with session.get(ENDPOINT, params=params) as resp:
            data = await resp.json()
            weather = "Currently in {}: {}°F (feels like {}°F) and {}".format(
                data["name"],
                data["main"]["temp"],
                data["main"]["feels_like"],
                data["weather"][0]["description"],
            )
            await message.reply(weather)
