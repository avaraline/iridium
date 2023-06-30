import aiohttp

ENDPOINT = "http://api.openweathermap.org/data/2.5/weather"
AQI_ENDPOINT = "https://www.airnowapi.org/aq/observation/latLong/current/"


def to_c(f):
    return (f - 32) * 5.0 / 9.0


def get_aqi(data):
    max_aqi = 0
    pollutant = "None"
    condition = "Good"
    for d in data:
        if d["AQI"] < max_aqi:
            continue
        max_aqi = d["AQI"]
        pollutant = d["ParameterName"]
        condition = d["Category"]["Name"]
    return "AQI = {} [{}] - {}".format(max_aqi, pollutant, condition)


async def handle(message, *args, appid=None, airnow=None):
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

            if data["sys"]["country"] not in ["US", "MM", "LR"]:
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

        if airnow:
            params = {
                "format": "application/json",
                "latitude": data["coord"]["lat"],
                "longitude": data["coord"]["lon"],
                "API_KEY": airnow,
            }
            async with session.get(AQI_ENDPOINT, params=params) as resp:
                aqi_data = await resp.json()
                weather += " ({})".format(get_aqi(aqi_data))

        await message.reply(weather)
