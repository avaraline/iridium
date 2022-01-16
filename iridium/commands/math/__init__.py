from .parser import evaluate

async def handle(message, *args):
	try:
		result = str(evaluate("".join(args)))
		await message.reply(result)
	except ZeroDivisionError:
		await message.reply("division by zero")
	except Exception as ex:
		await message.reply(str(ex))