import asyncio
import base64
import logging
import os
import re
import sys
from datetime import datetime

import aiohttp
import discord
import yarl
import binascii

from discord import Colour, Embed
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
QUARANTINE_ROLE_ID = int(os.getenv("QUARANTINE_ROLE_ID"))
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

logging.basicConfig(level=logging.DEBUG)

description = os.getenv("DESCRIPTION", default=None)

intents = discord.Intents.default()
intents.members = True

TOKEN_REGEX = re.compile(r'[a-zA-Z0-9_-]{23,28}\.[a-zA-Z0-9_-]{6,7}\.[a-zA-Z0-9_-]{27}')


class BotWithSession(commands.Bot):
    async def start(self, *args, **kwargs):
        async with aiohttp.ClientSession() as self.session:
            await super().start(*args, **kwargs)


bot = BotWithSession(command_prefix=os.getenv("PREFIX", default="!"), description=description, intents=intents)
_req_lock = asyncio.Lock(loop=bot.loop)


@bot.event
async def on_ready():
    print("=====================")
    print("Discord Token Abuse Killer, by Jack Webb")
    print("https://github.com/jack-webb/discord-token-abuse-killer/")
    print(f"Python version {sys.version}")
    print(f"discord.py version {discord.__version__}")
    print(f"Ready, logged in as {bot.user}")
    print("=====================")


@bot.listen("on_message")
async def log_on_message(message: discord.Message):
    tokens = [token for token in TOKEN_REGEX.findall(message.content) if validate_token(token)]
    if tokens and message.author.id != bot.user.id:
        await message.delete()

        gist_id = await create_gist('\n'.join(tokens), description='Invalidating discord token...')

        await quarantine(message.author)
        await send_alert(message)

        await asyncio.sleep(20)
        await delete_gist(gist_id)


async def quarantine(member: discord.Member):
    role = member.guild.get_role(QUARANTINE_ROLE_ID)
    await member.add_roles(
        role,
        reason=f"User sent a Discord token in their message"
    )

async def send_alert(message: discord.Message):
    alert_channel = bot.get_channel(ALERT_CHANNEL_ID)

    embed = build_embed(message.guild,
                        "User Quarantined - Discord Token",
                        f"User {message.author} was quarantined for posting a Discord bot token in #{message.channel}. "
                        f"The message has been deleted and the token has been invalidated.")

    await alert_channel.send(embed=embed)


def validate_token(token):
    try:
        # Just check if the first part validates as a user ID
        (user_id, _, _) = token.split('.')
        user_id = int(base64.b64decode(user_id, validate=True))
    except (ValueError, binascii.Error):
        return False
    else:
        return True


class GithubError(commands.CommandError):
    pass


async def github_request(method, url, *, params=None, data=None, headers=None):
    hdrs = {
        'Accept': 'application/vnd.github.inertia-preview+json',
        'User-Agent': 'Discord Token Abuse Killer for Buildapc',
        'Authorization': f'token {GITHUB_TOKEN}'
    }

    req_url = yarl.URL('https://api.github.com') / url

    if headers is not None and isinstance(headers, dict):
        hdrs.update(headers)

    await _req_lock.acquire()
    try:
        async with bot.session.request(method, req_url, params=params, json=data, headers=hdrs) as r:
            remaining = r.headers.get('X-Ratelimit-Remaining')
            response = await r.json()
            if r.status == 429 or remaining == '0':
                # wait before we release the lock
                delta = discord.utils._parse_ratelimit_header(r)
                await asyncio.sleep(delta)
                _req_lock.release()
                return await github_request(method, url, params=params, data=data, headers=headers)
            elif 300 > r.status >= 200:
                return response
            else:
                raise GithubError(response['message'])
    finally:
        if _req_lock.locked():
            _req_lock.release()


async def create_gist(content, *, description=None, filename=None, public=True):
    headers = {
        'Accept': 'application/vnd.github.v3+json',
    }

    filename = filename or 'token'
    data = {
        'public': public,
        'files': {
            filename: {
                'content': content
            }
        }
    }

    if description:
        data['description'] = description

    response = await github_request('POST', 'gists', data=data, headers=headers)
    return response['id']


async def delete_gist(gist_id):
    headers = {'Accept': 'application/vnd.github.v3+json'}
    await github_request('DELETE', f'gists/{gist_id}', headers=headers)


def build_embed(server: discord.Guild, title: str, message: str):
    embed = Embed(
        colour=Colour.gold(),
        title=title,
        description=message
    )

    return decorate(embed, server)


def decorate(embed: discord.Embed, server: discord.Guild):
    embed.timestamp = datetime.now()
    return embed.set_footer(icon_url=server.icon_url, text=f"From: {server.name}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
