# TGBOXOFFICE Admin Panel & Database Backup

## Interactive panel

- `/panel` — open the private admin dashboard.
- Dashboard sections: admin management, file channels, live statistics and backup help.
- `/panel add -100123456789` — add a database-managed file channel.
- `/panel remove -100123456789` — remove a database-managed file channel. Channels supplied through deployment environment settings remain protected.
- `/panel admin add 123456789` — grant admin access.
- `/panel admin remove 123456789` — revoke a database-managed admin.
- `/panel admin` — show admin management usage.

Only IDs configured as deployment admins (`ADMINS` / `ADMIN_ID`) can grant or revoke administrators. Those deployment admins cannot be removed from the panel. Database-managed admins are loaded on startup and the runtime admin filter makes their permissions effective immediately after they are added or removed.

## Backup and restore

- `/add save` — export collections from the configured user, file, secondary-file, auxiliary and clone-user MongoDB stores into a compressed `.json.gz` document.
- Reply to that backup document with `/add load` to see the restore warning.
- Reply to the same document with `/add load confirm` to restore it.

Restore replaces matching collections. Make a fresh backup first. Backups may contain private user records, clone-bot tokens and other sensitive database values; store them securely and share them only with trusted owners. Deployment environment variables, source files, Telegram chat history and files stored outside the configured MongoDB databases are not included.

## Telegram rich messages and button styles

The `TechVJ.util.telegram_rich` module exposes the rich HTML/Markdown and styled inline-keyboard helpers through the official HTTPS Bot API. The admin panel attempts the rich-message endpoint first, then native `primary`, `success` and `danger` button styles, and finally standard Pyrogram buttons if Telegram or the bot's API layer does not support a newer field. Telegram controls the available styles; arbitrary HEX/RGB button colours are not supported by this helper.
