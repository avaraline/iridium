import importlib
import re
import shlex
from collections import deque

import discord

EMOJI_URL = "https://cdn.discordapp.com/emojis/"


def filesize(size, decimal_places=1):
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            break
        size /= 1024.0
    if unit == "bytes":
        decimal_places = 0
    return f"{size:.{decimal_places}f} {unit}"


def ircquote(message):
    author = message.author.name
    msgtxt = message.clean_content.splitlines()
    msgtxt = f"{msgtxt[0]}[...]" if len(msgtxt) > 1 else msgtxt[0]
    return f"<{author}> {msgtxt}"


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


def get_user_proxies(channel):
    return {m.name: UserProxy(m) for m in channel.members}


class BridgeClient(discord.Client):
    def __init__(self, server, **options):
        self.irc = server
        self.guild = None
        self.commands = self.irc.config.get("commands", {})
        # store ids and authors of messages we send
        # so that reply quotes aren't sent if the quoted
        # message just occurred
        self.msg_id_buffa = deque([], 2)
        self.msg_author_buffa = deque([], 2)
        # Make sure we add the members intent, so we can access member information.
        intents = discord.Intents.default()
        intents.members = True
        options["intents"] = intents
        super().__init__(**options)

    def is_old(self, msg):
        # check ring buffers for msg id and author
        return (
            msg.id not in self.msg_id_buffa and msg.author not in self.msg_author_buffa
        )

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
                source = UserProxy(message.author)

                # send text to the IRC channel
                def send(text):
                    # replace "<:emoji:biglongidnumber>" with a link to an image
                    custom_emoji = re.findall(r"(<a?:(\w*):(\d*)>)", text)
                    for ce in custom_emoji:
                        text = text.replace(ce[0], f"{EMOJI_URL}{ce[2]}.png")
                    channel.message(text, sender=source)
                    self.msg_id_buffa.append(message.id)
                    self.msg_author_buffa.append(message.author)

                # send a message to the IRC channel
                def sendmsg(message):
                    for line in message.clean_content.splitlines():
                        send(line)

                # a message is a reply if it has a reference
                # pins also have references, but they are system type
                is_reply = message.reference is not None
                is_reply = is_reply and not message.is_system()

                if is_reply:
                    # check if the original message is cached or
                    # was loaded by the API
                    original = message.reference.resolved
                    if original is not None:
                        # only send a quote if it wasn't in the last
                        # couple messages.
                        if self.is_old(original):
                            send(ircquote(original))
                        sendmsg(message)
                    else:
                        # did not find original message for reply
                        # whatever, just send the message
                        sendmsg(message)
                else:
                    # not a reply, send the message
                    sendmsg(message)

                # send links to attachments
                for att in message.attachments:
                    send(f"{att.url} ({att.filename} - {att.size})")

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

    async def on_message_edit(self, before, after):
        if before.content != after.content:
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
                source = UserProxy(member)
                content = reaction.emoji
                # content is either a custom emoji object
                # or just a UTF character that we can simply send
                if not isinstance(reaction.emoji, str):
                    content = reaction.emoji.url
                # everyone on IRC must know what the reaction is to!
                if self.is_old(message):
                    channel.message(ircquote(message), sender=source)
                channel.message(content, sender=source)
