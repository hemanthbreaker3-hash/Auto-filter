# GitHub ZIP uploader

## Configure once

In a private chat with the bot, run `/github` and use the buttons to set:

1. Your GitHub username.
2. A GitHub Personal Access Token.

For a fine-grained PAT, grant access to the target repository with **Contents: Read and write** (Metadata read is provided automatically). The configured username must match the account that owns the token. The token is encrypted before it is stored in the bot's MongoDB `bot_config` collection. It is never included in status messages or logs.

## Upload a ZIP

Reply to a Telegram ZIP document with:

`/uploadto https://github.com/OWNER/REPOSITORY branch-name`

You can also use `OWNER/REPOSITORY` instead of the full URL. If the branch does not exist, it is created from the repository's default branch. If it exists, the bot creates a normal commit on that branch. Files at matching paths are replaced by the ZIP contents; files not present in the ZIP and all other branches/repositories are left untouched. The bot does not force-push, delete unrelated files, or rewrite other branches.

## Limits and safety

- ZIP maximum: 50 MB; unpacked maximum: 150 MB; maximum 500 files.
- Individual files are limited to 95 MB to stay below GitHub's 100 MB blob limit.
- ZIP path traversal, symlinks, and `.git` contents are rejected/ignored.
- Uploads use GitHub's Git Data API and update only the selected branch.
- If the branch changes concurrently, the upload fails safely instead of force-pushing.
- Credential records are per Telegram user. Removing credentials is available from `/github`.

The encryption key is derived from the deployment's bot token and database URI. Keep those deployment secrets stable to retain access to saved encrypted tokens; changing either value requires users to configure their GitHub token again.

## Button setup troubleshooting / current implementation

The `/github` buttons are handled by a dedicated high-priority callback handler. Selecting a field sets a per-user pending setup state; the next private text message is validated and saved. This avoids relying on a non-core `Client.ask()` extension. Callback ownership is checked against the private chat user ID. The GitHub command handlers are also registered in the Telegram command menu.
