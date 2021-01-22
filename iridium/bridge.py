import discord


class UserProxy:
    def __init__(self, member):
        self.member = member

    def __str__(self):
        return f"{self.nickname}!{self.username}@{self.hostname}"

    def join(self, user, channel):
        pass

    def part(self, user, channel):
        pass

    def message(self, content, sender=None):
        pass

    @property
    def nickname(self):
        return self.member.display_name

    @property
    def username(self):
        return self.member.name

    @property
    def hostname(self):
        return "discord"

    @property
    def realname(self):
        return self.member.display_name


class BridgeClient(discord.Client):
    def __init__(self, server, **options):
        self.irc = server
        self.guild = None
        # Make sure we add the members intent, so we can access member information.
        intents = discord.Intents.default()
        intents.members = True
        options["intents"] = intents
        super().__init__(**options)

    async def on_ready(self):
        for guild in self.guilds:
            if guild.id == self.irc.config["discord"]["guild_id"]:
                self.guild = guild
        if self.guild:
            await self.irc.bridge_ready()
        else:
            print("Unknown guild {}".format(self.irc.config["discord"]["guild_id"]))

    async def on_message(self, message):
        if message.author == self.user:
            return

        if not message.guild or message.guild != self.guild:
            return

        if message.channel.type == discord.ChannelType.text:
            channel = self.irc.channels.get(message.channel.name)
            if channel:
                if channel.webhook and channel.webhook.id == message.webhook_id:
                    return
                user = UserProxy(message.author)
                channel.message(message.content, sender=user)
