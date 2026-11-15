# MoviesZoneFlix — VPS deploy (export credentials + ./deploy.vps)

## One-shot flow

```bash
unzip movieszoneflix-READY.zip -d movieszoneflix
cd movieszoneflix
# Run from the project root containing bot.py and deploy.sh

export BOT_TOKEN="123456:AA..."
export API_HASH="7d0b85b4146034511b8776ed7ff99de4"
export APP_ID="22266643"
export API_ID="22266643"
export CHANNEL_ID="-1003748914288"
export CHANNELS="-1003748914288"
export DATABASE_URI="mongodb+srv://..."
export ADMINS="123456789"

chmod +x deploy.vps one-click-deploy.sh
./deploy.vps
```

`./deploy.vps` will:
- use your **exported** shell credentials (no secrets required inside the repo)
- install deps with **zero APT wait**
- write them into `.env` for systemd
- start service **`auto-filter`** (24/7)

Same entry points:
- `./deploy.vps`
- `./one-click-deploy.sh`
- `./deploy-now.sh`

## Get exports from a running bot

Private chat (admin):

```
/exportcreds
```

Then on VPS:

```bash
source credentials.export.XXXX.sh
cd movieszoneflix   # project root with bot.py
chmod +x deploy.vps
./deploy.vps
```

## Aliases

| Export | Used as |
|--------|---------|
| `APP_ID` | `API_ID` |
| `CHANNEL_ID` | `CHANNELS` |
| `ADMIN_ID` | `ADMINS` |
| `MONGO_URI` | `DATABASE_URI` |
| `TOKEN` | `BOT_TOKEN` |

## APT lock stuck

```bash
FORCE_APT_UNLOCK=1 ./deploy.vps
# or
sudo FORCE_APT_UNLOCK=1 -E ./deploy.vps
```

## Service

```bash
systemctl status auto-filter
journalctl -u auto-filter -f
```

## Python 3.12 note
Requires `motor>=3.3` and `pymongo>=4.6` (motor 2.x crashes with ImportError: coroutine).


### Telegram channel/group access validation

At startup the bot checks configured destinations using the official Telegram Bot API
(`getChat`, `getChatMember`, `sendMessage`, and `deleteMessage`). It briefly posts a
probe message and immediately deletes it. The bot must already be a member of each
private channel/group; for channel posting and probe deletion it needs the relevant
administrator permissions. The Bot API avoids Pyrogram's local peer-cache dependency,
but cannot grant access to a chat the bot has not joined or been authorized to use.

Newly indexed source records retain their originating chat/message reference. When
Telegram reports that a source message was deleted, the corresponding source reference
is removed from the file database; a file record is deleted only when it has no other
known source references.
