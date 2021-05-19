import importlib
import shlex

import discord


def filesize(size, decimal_places=1):
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            break
        size /= 1024.0
    if unit == "bytes":
        decimal_places = 0
    return f"{size:.{decimal_places}f} {unit}"


class UserProxy:
    def __init__(self, member):
        self.nickname = member.display_name.replace(" ", "_")
        self.username = member.name.replace(" ", "_")
        self.hostname = "discord.gg"
        self.realname = member.display_name

    def __str__(self):
        return f"{self.nickname}!{self.username}@{self.hostname}"

    def join(self, user, channel):
        pass

    def part(self, user, channel, reason):
        pass

    def quit(self, user, reason):
        pass

    def message(self, content, sender=None):
        pass


class BridgeClient(discord.Client):
    def __init__(self, server, **options):
        self.irc = server
        self.guild = None
        self.commands = self.irc.config.get("commands", {})
        # Make sure we add the members intent, so we can access member information.
        intents = discord.Intents.default()
        intents.members = True
        options["intents"] = intents
        super().__init__(**options)

    def named_channel(self, name):
        for channel in self.guild.text_channels:
            if channel.name == name:
                return channel

    async def on_ready(self):
        for guild in self.guilds:
            if guild.id == self.irc.config["discord"]["guild_id"]:
                self.guild = guild
        if self.guild:
            await self.irc.bridge_ready()
        else:
            print("Unknown guild {}".format(self.irc.config["discord"]["guild_id"]))

    async def on_message(self, message):
        if not message.guild or message.guild != self.guild:
            return

        if message.channel.type == discord.ChannelType.text:
            channel = self.irc.channels.get(message.channel.name)
            if channel:
                for line in message.clean_content.splitlines():
                    channel.message(line, sender=UserProxy(message.author))
                for att in message.attachments:
                    line = "%s (%s - %s)" % (
                        att.url,
                        att.filename,
                        filesize(att.size),
                    )
                    channel.message(line, sender=UserProxy(message.author))
            # Potentially log the message.
            await self.irc.log(message)
            # Handle chat commands.
            if message.content.startswith("!") and message.author != self.user:
                cmd, *args = shlex.split(message.content[1:])
                if cmd in self.commands:
                    options = self.commands[cmd].copy()
                    module_path = options.pop(
                        "module", "iridium.commands.{}.handle".format(cmd)
                    )
                    mod_name, attr_name = module_path.rsplit(".", 1)
                    try:
                        mod = importlib.import_module(mod_name)
                        mod = importlib.reload(mod)
                        handler = getattr(mod, attr_name, None)
                        if handler:
                            await handler(message, *args, **options)
                    except ImportError:
                        pass
                    except Exception:
                        pass
        print (message.content)

    async def on_message_edit(self, before, after):
        after.content = f"* {after.content}"
        await self.on_message(after)

    async def on_guild_channel_delete(self, channel):
        await self.irc.reconfigure()

    async def on_guild_channel_create(self, channel):
        await self.irc.reconfigure()

    async def on_guild_channel_update(self, before, after):
        await self.irc.sync_channels()

    async def on_member_join(self, member):
        await self.irc.sync_channels()

    async def on_member_remove(self, member):
        await self.irc.sync_channels()

    async def on_member_update(self, before, after):
        old_nickname = UserProxy(before).nickname
        new_nickname = UserProxy(after).nickname
        if old_nickname != new_nickname:
            for session in self.irc.sessions:
                if session.authenticated:
                    session.write("NICK", new_nickname, prefix=old_nickname)
        await self.irc.sync_channels()

    async def on_reaction_add(self, reaction, member):
        message = reaction.message
        if message.channel.type == discord.ChannelType.text:
            channel = self.irc.channels.get(message.channel.name)
            if channel:
                target = str(message.author.name)
                source = UserProxy(member)
                content = reaction.emoji
                if not isinstance(reaction.emoji, str):
                    content = reaction.emoji.url
                channel.message(f"{target}: {content}", sender=source)
