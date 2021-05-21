Iridium
=======

Iridium is the Discord to IRC bridge that is the Least Annoying to IRC users. Discord text channels are mapped directly to IRC channels, and members are shown in the IRC userlist. It includes an internal sqlite log of messages, and support for attachments, commands, reactions and message edits, prioritizing a reasonable expression of rich formats in IRC.

You must create a Discord Application and Bot User, and provide its token in the configuration file. You must also supply the `guild_id` of the Discord server you would like to bridge, and invite the Bot User to the server.

Usage
-----

```
git clone https://github.com/avaraline/iridium.git
cd iridium
pip install -r requirements.txt
cp iridium.example.toml iridium.toml
# Edit iridium.toml to your liking
python -m iridium
```