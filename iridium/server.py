import asyncio

from .bridge import BridgeClient, UserProxy
from .irc import IRCSession


class BridgeChannel:
    def __init__(self, discord_channel):
        self.discord = discord_channel
        self.irc_name = "#" + self.discord.name
        self.sessions = []
        self.webhook = None
        self.default = False
        self.log = False

    async def configure(self, bridge, **options):
        webhook_name = options.get("webhook", "IRC")
        self.default = options.get("default", self.default)
        self.log = options.get("log", self.log)
        for hook in await self.discord.webhooks():
            if hook.name == webhook_name:
                self.webhook = hook
                break
        if self.webhook is None:
            self.webhook = await self.discord.create_webhook(name=webhook_name)

    @property
    def topic(self):
        return self.discord.topic

    def join(self, user):
        self.sessions.append(user)
        for session in self.sessions:
            session.join(user, self)

    def part(self, user):
        if user not in self.sessions:
            return
        for session in self.sessions:
            session.part(user, self)
        self.sessions.remove(user)

    def message(self, content, sender=None):
        for session in self.sessions:
            session.message(content, sender=sender, channel=self)
        if isinstance(sender, IRCSession):
            asyncio.create_task(self.webhook.send(content, username=sender.nickname))

    def users(self):
        for member in self.discord.members:
            yield UserProxy(member)
        yield from self.sessions


class Server:
    def __init__(self, config):
        self.config = config
        self.loop = None
        self.server = None
        self.bridge = None
        self.sessions = []
        self.name = self.config.get("irc", {}).get("name", "Iridium")
        self.password = self.config.get("irc", {}).get("password", "")
        self.channels = {}

    @property
    def default_channel(self):
        first = None
        for channel in self.channels.values():
            if first is None:
                first = channel
            if channel.default:
                return channel
        return first

    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.server = await self.loop.create_server(
            lambda: IRCSession(self),
            self.config.get("irc", {}).get("bind", "0.0.0.0"),
            self.config.get("irc", {}).get("port", 6667),
        )
        self.bridge = BridgeClient(self, loop=self.loop)
        await self.bridge.start(self.config["discord"]["token"])

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()
        await self.bridge.logout()

    async def bridge_ready(self):
        print("Discord bridge ready, configuring channels...")
        for channel in self.bridge.guild.text_channels:
            options = self.config.get("channels", {}).get(channel.name)
            if options:
                print("  +", channel.name)
                irc_channel = BridgeChannel(channel)
                await irc_channel.configure(self.bridge)
                self.channels[channel.name] = irc_channel

    async def connected(self, session):
        print("New connection - {}".format(session))
        self.sessions.append(session)

    async def disconnected(self, session):
        print("Disconnected - {}".format(session))
        for channel in self.channels.values():
            channel.part(session)
        self.sessions.remove(session)

    def valid_nick(self, nick):
        for session in self.sessions:
            if session.nickname == nick:
                return False
        for member in self.bridge.guild.members:
            if member.display_name == nick:
                return False
        return True

    def user(self, nick):
        for session in self.sessions:
            if session.nickname == nick:
                return session
        return None

    def channel(self, name):
        return self.channels.get(name)
