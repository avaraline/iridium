import aiohttp

ENDPOINT = "http://api.openweathermap.org/data/2.5/weather"

def to_c(f):
    return (f - 32) * 5.0 / 9.0

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
            
            unit = "F"
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]


            metric = not data["sys"]["country"] in ["US", "MM", "LR"]

            if metric:
                unit = "C"
                temp = to_c(temp)
                feels_like = to_c(feels_like)

            weather = "Currently in {}: {:.2f}°{} (feels like {:.2f}°{}) and {}".format(
                data["name"],
                temp,
                unit,
                feels_like,
                unit,
                data["weather"][0]["description"],
            )
            await message.reply(weather)
