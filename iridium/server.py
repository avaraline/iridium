import asyncio

from .bridge import BridgeClient, UserProxy
from .irc import IRCSession


class BridgeChannel:
    def __init__(self, name):
        self.name = name
        self.irc_name = "#" + self.name
        self.topic = ""
        # Mapping of discord username to UserProxy.
        self.members = {}
        # List of active IRCSession objects in this channel.
        self.sessions = []
        self.webhook = None
        self.default = False
        self.log = False

    @property
    def num_users(self):
        return len(self.sessions) + len(self.members)

    async def configure(self, bridge, **options):
        channel = bridge.named_channel(self.name)
        webhook_name = options.get("webhook", "IRC")
        self.topic = channel.topic
        self.default = options.get("default", self.default)
        self.log = options.get("log", self.log)
        self.webhook = None
        for hook in await channel.webhooks():
            if hook.name == webhook_name:
                self.webhook = hook
                break
        if self.webhook is None:
            self.webhook = await channel.create_webhook(name=webhook_name)
        self.members = {m.name: UserProxy(m) for m in channel.members}

    async def sync(self, bridge):
        channel = bridge.named_channel(self.name)
        new_topic = channel.topic or ""
        if new_topic != self.topic:
            self.topic = new_topic
            for session in self.sessions:
                session.write("TOPIC", self.irc_name, self.topic)
        new_members = {m.name: UserProxy(m) for m in channel.members}
        for user in set(new_members).difference(self.members):
            self.join(new_members[user])
        for user in set(self.members).difference(new_members):
            self.part(self.members[user], "Leaving")
        self.members = new_members

    def join(self, user):
        if isinstance(user, IRCSession) and user not in self.sessions:
            self.sessions.append(user)
        for session in self.sessions:
            session.join(user, self)

    def part(self, user, reason):
        for session in self.sessions:
            session.part(user, self, reason)
        if isinstance(user, IRCSession) and user in self.sessions:
            self.sessions.remove(user)

    def quit(self, user, reason):
        for session in self.sessions:
            session.quit(user, reason)
        if isinstance(user, IRCSession) and user in self.sessions:
            self.sessions.remove(user)

    def message(self, content, sender=None):
        if isinstance(sender, IRCSession):
            asyncio.create_task(self.webhook.send(content, username=sender.nickname))
        else:
            for session in self.sessions:
                session.message(content, sender=sender, channel=self)

    def users(self):
        yield from self.members.values()
        yield from self.sessions

    def clear(self):
        for session in self.sessions:
            session.part(session, self, "RIP")
        self.sessions = []


class Server:
    def __init__(self, config):
        self.config = config
        self.loop = None
        self.server = None
        self.bridge = None
        self.sessions = []
        self.name = self.config.get("irc", {}).get("name", "Iridium")
        self.password = self.config.get("irc", {}).get("password", "")
        self.host = self.config.get("irc", {}).get("bind", "0.0.0.0")
        self.port = self.config.get("irc", {}).get("port", 6667)
        self.automap = self.config.get("irc", {}).get("automap", True)
        self.channels = {}

    @property
    def default_channel(self):
        default = None
        for channel in self.channels.values():
            if default is None:
                default = channel
            if channel.default:
                return channel
        return default

    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.server = await self.loop.create_server(
            lambda: IRCSession(self),
            host=self.host,
            port=self.port,
            start_serving=False,
        )
        self.bridge = BridgeClient(self, loop=self.loop)
        await self.bridge.start(self.config["discord"]["token"])

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()
        await self.bridge.logout()

    async def reconfigure(self):
        print("Configuring channels...")
        new_channels = {}
        for channel in self.bridge.guild.text_channels:
            options = self.config.get("channels", {}).get(channel.name, {})
            if options or self.automap:
                old_channel = self.channels.get(channel.name)
                new_channel = BridgeChannel(channel.name)
                await new_channel.configure(self.bridge, **options)
                if old_channel:
                    new_channel.sessions.extend(old_channel.sessions)
                    print("  ~", channel.name)
                else:
                    print("  +", channel.name)
                await new_channel.sync(self.bridge)
                new_channels[channel.name] = new_channel
        # If any of the channels have gone away, clear them out on IRC as well.
        for name, channel in self.channels.items():
            if name not in new_channels:
                print("  -", name)
                channel.clear()
        self.channels = new_channels

    async def bridge_ready(self):
        await self.reconfigure()
        if not self.server.is_serving():
            await self.server.start_serving()
            print(f"Listening on {self.host}:{self.port}")

    async def sync_channels(self):
        for channel in self.channels.values():
            await channel.sync(self.bridge)

    async def connected(self, session):
        self.sessions.append(session)

    async def disconnected(self, session):
        for channel in self.channels.values():
            channel.quit(session, session.quit_reason)
        self.sessions.remove(session)

    def valid_nick(self, nick):
        for session in self.sessions:
            if session.nickname == nick:
                return False
        for member in self.bridge.guild.members:
            if UserProxy(member).nickname == nick:
                return False
        return True

    def user(self, nick):
        for session in self.sessions:
            if session.nickname == nick:
                return session
        return None
