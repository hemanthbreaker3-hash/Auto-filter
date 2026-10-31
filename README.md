# TGBoxOffice

TGBoxOffice is a Telegram bot for automatic file filtering, media search, file indexing, group utilities, and optional streaming integrations.

## Features

- Automatic and manual file filtering
- MongoDB-backed file indexing
- Inline search and configurable result buttons
- Group settings, force-subscription, and welcome messages
- Admin tools, broadcasts, and user management
- Optional IMDb metadata, spell checking, and media utilities
- Optional stream/short-link integrations
- Premium membership and referral features

## Requirements

- Python 3.12 (used by the Docker image)
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- Telegram API ID and API hash from [my.telegram.org](https://my.telegram.org)
- MongoDB connection URI
- A Telegram channel where the bot can read indexed files (and a log channel)

## Configuration

Set these environment variables in your hosting dashboard or in a local `.env` file. Do not commit secrets.

| Variable | Required | Description |
|---|---:|---|
| `API_ID` | Yes | Telegram API ID |
| `API_HASH` | Yes | Telegram API hash |
| `BOT_TOKEN` | Yes | Bot token from BotFather |
| `ADMINS` | Yes | Space-separated Telegram user IDs |
| `DATABASE_URI` | Yes | MongoDB connection URI |
| `DATABASE_NAME` | No | Database name (default: `TGBoxOffice`) |
| `CHANNELS` | Yes | Space-separated file/database channel IDs or usernames |
| `LOG_CHANNEL` | Yes | Log channel ID; make the bot an administrator |
| `OWNER_ID` | Recommended | Owner's Telegram user ID |
| `BOT_NAME` | No | Display name (default: `TGBoxOffice`) |
| `BOT_USERNAME` | No | Bot username without `@` (default: `TGBoxOfficeBot`) |
| `AUTH_CHANNEL` | No | Force-subscription channel ID |
| `STREAM_SITE` / `STREAM_API` | No | Optional stream shortener host and API key |
| `SHORTLINK_URL` / `SHORTLINK_API` | No | Optional verification shortener host and API key |
| `GOOGLE_API_KEY` | No | Optional Google AI key |
| `OPENAI_API` | No | Optional OpenAI-compatible API key |
| `PORT` | No | Web health-server port (default: `10000`) |

The bot username, support links, channel links, and optional API integrations must be set to resources you own. The defaults are branding placeholders, not working Telegram accounts or API credentials.

## Run locally

```bash
git clone <your-repository-url>
cd <repository-folder>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

On Windows, activate the virtual environment with `.venv\\Scripts\\activate`.

## Deploy

The repository includes a `Dockerfile`, `Procfile`, `render.yaml`, and platform manifests. Configure all required environment variables in your hosting provider before deploying. Keep the web service port supplied by the host through `PORT`.

## Important setup notes

1. Add the bot to the file/database channel and grant the permissions needed to read messages.
2. Add the bot as an administrator in the log channel.
3. Use a MongoDB URI with network access enabled for your hosting provider.
4. Configure optional shortener and AI credentials only if you use those features.
5. Never share `BOT_TOKEN`, `API_HASH`, database credentials, or API keys.

## Troubleshooting

- **Missing configuration:** confirm `API_ID`, `API_HASH`, and `BOT_TOKEN` are set.
- **Database connection errors:** check the MongoDB URI, database user permissions, and network allowlist.
- **Channel access errors:** verify the exact channel ID/username and ensure the bot is a member with the required permissions.
- **Missing media results:** confirm the indexed channel is configured and the bot can read its history.

## Credits and license

This project builds on the upstream AutoFilter/Lucy codebase and its contributors. Preserve the upstream license and attribution notices in `LICENSE`.


## Render Free Web Service (Docker)

This repository includes a Docker-based Render Blueprint. Create a new Render service from the repository and select the `render.yaml` Blueprint, or create a **Web Service** using the Docker runtime and the repository root as the Docker context. Render will build `./Dockerfile` and run `python -u bot.py`.

### Required environment variables

Set these in the Render dashboard (never commit secrets):

- `API_ID` — Telegram API ID
- `API_HASH` — Telegram API hash
- `BOT_TOKEN` — bot token from BotFather
- `DATABASE_URI` — MongoDB connection URI
- `OWNER_ID` — Telegram numeric owner ID
- `ADMINS` — space-separated Telegram numeric admin IDs
- `LOG_CHANNEL` — numeric log-channel ID; make the bot an administrator there
- `CHANNELS` — space-separated source channel IDs/usernames, if used by your configuration

Optional settings can be copied from `.env.example`. `PORT` is supplied by Render (the Blueprint defaults it to `10000`). The web server binds to `0.0.0.0` and `/` is the health-check endpoint.

### Free-tier limitations

Render Free web services can spin down after 15 minutes without inbound traffic, take about a minute to wake, may restart, and have an ephemeral filesystem. Use MongoDB or another external database for persistent bot data; do not rely on local files or SQLite for durable storage. Free-tier availability and usage limits are controlled by Render, so continuous uptime cannot be guaranteed.

### Deploy checks

1. Confirm all required environment variables are set in Render.
2. Confirm the bot is an administrator in its log/source channels as required.
3. Confirm the MongoDB URI allows connections from Render.
4. Deploy and inspect the build and runtime logs. A successful image build alone does not validate Telegram credentials or database connectivity.
## Owner/Admin Management Panel

Open the private bot chat and send `/panel` as the configured owner or an authorized admin. The panel can list and remove source channels and authorized admins. Use these commands to add or remove entries:

- `/panel addchannel -1001234567890`
- `/panel delchannel -1001234567890`
- `/panel addadmin 123456789`
- `/panel deladmin 123456789`

Channel changes are stored in MongoDB and take effect without restarting the bot. The bot must be an administrator in each source channel to receive channel posts. The configured `OWNER_ID` cannot be removed. The configured `ADMINS` and `CHANNELS` entries can be disabled through the panel; their original environment values remain unchanged.
