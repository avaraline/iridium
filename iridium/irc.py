import asyncio
import logging

from .constants import ERR, RPL


def escape(text):
    # TODO: escape stuff
    if " " in text:
        return ":" + text
    return text


def try_decode(text, default=None):
    try:
        return text.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return text.decode("latin-1")
        except UnicodeDecodeError:
            pass
    return default


class IRCSession(asyncio.Protocol):
    def __init__(self, server):
        self.server = server
        self.transport = None
        self.address = None
        self.port = None
        self.buffer = b""
        self.username = ""
        self.nickname = ""
        self.realname = ""
        self.hostname = ""
        self.password = None
        self.authenticated = False
        self.quit_reason = "Quit"

    def __str__(self):
        return f"{self.nickname}!{self.username}@{self.hostname}"

    def connection_made(self, transport):
        self.transport = transport
        self.address, self.port = transport.get_extra_info("peername")
        self.hostname = self.address
        if hasattr(self.server, "connected"):
            asyncio.create_task(self.server.connected(self))

    def connection_lost(self, exc):
        if hasattr(self.server, "disconnected"):
            asyncio.create_task(self.server.disconnected(self))

    def data_received(self, data):
        self.buffer += data
        *lines, self.buffer = self.buffer.split(b"\r\n")
        for line in lines:
            line = try_decode(line)
            if not line:
                continue
            prefix = None
            if line.startswith(":"):
                prefix, line = line[1:].split(None, 1)
            parts = line.split(" :", 1)
            if not parts or not parts[0].strip():
                continue
            cmd, *params = parts[0].split()
            if len(parts) > 1:
                params.append(parts[1])
            handler = getattr(self, "handle_{}".format(cmd.upper()), None)
            if handler:
                # TODO: check authentication for non-login-related commands
                asyncio.create_task(handler(*params, prefix=prefix))
            else:
                self.write(
                    ERR.UNKNOWNCOMMAND, self.nickname or "*", cmd, "Unknown command"
                )
                logging.debug('Unknown IRC command "%s" with params: %s', cmd, params)

    def write(self, code, *params, prefix=None):
        start = ":{}".format(prefix or self.server.name)
        line = "{} {} {}\r\n".format(start, code, " ".join(escape(p) for p in params))
        self.transport.write(line.encode("utf-8"))

    def message(self, content, sender=None, channel=None):
        if channel:
            # Channel message
            if sender.nickname != self.nickname:
                # Don't echo messages back to the sender.
                self.write("PRIVMSG", channel.irc_name, content, prefix=sender)
        else:
            # Direct message
            self.write("PRIVMSG", str(self), content, prefix=sender.nickname)

    def join(self, user, channel):
        self.write("JOIN", channel.irc_name, prefix=user)

    def part(self, user, channel, reason):
        self.write("PART", channel.irc_name, reason, prefix=user)

    def quit(self, user, reason):
        self.write("QUIT", reason, prefix=user)

    async def check_login(self, sasl=False):
        if self.authenticated:
            return
        if self.username and self.nickname:
            if self.server.password and self.server.password != self.password:
                self.write(
                    "NOTICE",
                    "AUTH",
                    "*** You are not logged in, please use PASS to authenticate",
                )
                return
            self.authenticated = True
            self.write(
                RPL.WELCOME,
                self.nickname,
                "Welcome to {}! The public chat room for this server is {}".format(
                    self.server.name, self.server.default_channel.irc_name
                ),
            )

    async def handle_PING(self, *params, prefix=None):
        self.write("PONG", self.server.name, " ".join(params))

    async def handle_PASS(self, *params, prefix=None):
        self.password = params[0]
        await self.check_login()

    async def handle_USER(self, *params, prefix=None):
        self.username = params[0]
        self.realname = params[3]
        await self.check_login()

    async def handle_NICK(self, *params, prefix=None):
        if not params or params[0] == self.nickname:
            return
        if self.server.valid_nick(params[0]):
            old_nickname = self.nickname
            self.nickname = params[0]
            if not self.authenticated:
                await self.check_login()
            elif self.nickname != old_nickname:
                for session in self.server.sessions:
                    session.write("NICK", self.nickname, prefix=old_nickname)
        else:
            self.write(ERR.NICKNAMEINUSE, "*", "Nickname is already in use.")

    async def handle_JOIN(self, *params, prefix=None):
        channel = self.server.channels.get(params[0][1:])
        if not channel:
            self.write(ERR.NOSUCHCHANNEL, params[0], "No such channel")
            return
        if self in channel.sessions:
            return
        channel.join(self)
        if channel.topic:
            self.write(RPL.TOPIC, self.nickname, channel.irc_name, channel.topic)
        else:
            self.write(RPL.NOTOPIC, self.nickname, channel.irc_name)
        # Channels: = for public, * for private, @ for secret
        # Users: @ for ops, + for voiced
        self.write(
            RPL.NAMREPLY,
            self.nickname,
            "=",
            channel.irc_name,
            " ".join(u.nickname for u in channel.users()),
        )
        self.write(RPL.ENDOFNAMES, self.nickname, channel.irc_name, "End of NAMES list")

    async def handle_PART(self, *params, prefix=None):
        reason = params[1] if len(params) > 1 else "Leaving"
        for name in params[0].split(","):
            channel = self.server.channels.get(name[1:])
            if channel and self in channel.sessions:
                channel.part(self, reason)

    async def handle_PRIVMSG(self, *params, prefix=None):
        if params[0].startswith("#"):
            channel = self.server.channels.get(params[0][1:])
            if channel:
                channel.message(params[1], sender=self)
        else:
            user = self.server.user(params[0])
            if user:
                user.message(params[1], sender=self)

    async def handle_MODE(self, *params, prefix=None):
        pass

    async def handle_WHO(self, *params, prefix=None):
        if params and params[0].startswith("#"):
            channel = self.server.channels.get(params[0][1:])
            for user in channel.users():
                self.write(
                    RPL.WHOREPLY,
                    self.nickname,
                    channel.irc_name,
                    user.username,
                    user.hostname,
                    self.server.name,
                    user.nickname,
                    "H",
                    "0 " + user.realname,
                )
            self.write(RPL.ENDOFWHO, self.nickname, channel.irc_name, "End of WHO list")

    async def handle_LIST(self, *params, prefix=None):
        self.write(RPL.LISTSTART, self.nickname, "Channel Users Topic")
        for channel in self.server.channels.values():
            self.write(
                RPL.LIST,
                self.nickname,
                channel.irc_name,
                str(channel.num_users),
                channel.topic,
            )
        self.write(RPL.LISTEND, self.nickname, "End of LIST")

    async def handle_QUIT(self, *params, prefix=None):
        if params:
            self.quit_reason = params[0]
        self.write("ERROR", "Bye for now!")
        self.transport.close()
