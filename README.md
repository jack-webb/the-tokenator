# discord-token-abuse-killer
Quarantine users who post tokens, and invalidate those tokens by posting them to a public GitHub gist. Based on code from [Rapptz/RoboDanny](https://github.com/Rapptz/RoboDanny).

# Requirements and setup

Requires Python 3.9 and Poetry

1. Install dependencies with `poetry install`
2. Create and populate a `.env` file
3. Run with `poetry run python -m main`

# Environment variables

All variables are required.

- `DISCORD_TOKEN` - Your Discord bot's token
- `GITHUB_TOKEN` - Your GitHub [Personal Access Token](https://github.com/settings/tokens)
- `QUARANTINE_ROLE_ID` - The role to apply to users posting tokens
- `ALERT_CHANNEL_ID` - The channel to post alerts to