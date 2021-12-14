# discord-token-abuse-killer
Ban or quarantine users who post tokens, and invalidate those tokens. Based on code from [Rapptz/RoboDanny](https://github.com/Rapptz/RoboDanny).

# Requirements and setup

Requires Python 3.9 and Poetry

1. Install dependencies with `poetry install`
2. Create a `.env` file with a `DISCORD_TOKEN` and `GITHUB_TOKEN` (GitHub token is a PAT)
3. Run with `poetry run python -m main`