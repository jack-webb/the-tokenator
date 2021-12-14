import asyncio
import base64
import logging
import os
import re
import sys

import aiohttp
import discord
import yarl
import binascii
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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
    tokens = [token for token in TOKEN_REGEX.findall(message.content) if _validate_token(token)]
    if tokens and message.author.id != bot.user.id:
        gist_id = await create_gist('\n'.join(tokens), description='Invalidating discord token...')

        # todo Quarantine or ban the user here
        # todo Add an alert message

        await asyncio.sleep(60)
        await delete_gist(gist_id)


def _validate_token(token):
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


async def _github_request(method, url, *, params=None, data=None, headers=None):
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
                return await _github_request(method, url, params=params, data=data, headers=headers)
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

    response = await _github_request('POST', 'gists', data=data, headers=headers)
    return response['id']


async def delete_gist(gist_id):
    headers = {'Accept': 'application/vnd.github.v3+json'}
    await _github_request('DELETE', f'gists/{gist_id}', headers=headers)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
