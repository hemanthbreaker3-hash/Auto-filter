# GitHub Button Fix — 2026-11-15

## Fixed

- GitHub setup buttons now use a dedicated callback handler with priority `group=-2`, ahead of the general callback handler.
- Private-chat ownership is checked using Pyrogram's `enums.ChatType.PRIVATE` enum and the callback user's ID.
- Replaced the `client.ask()` dependency with a per-user setup state machine. The next private text message is consumed as the requested username or token; `/cancel` exits setup.
- GitHub username and PAT remain per-user in MongoDB; the PAT is encrypted before storage and token messages are deleted where Telegram permits.
- Added `/github` and `/uploadto` to the Telegram command menu.
- Corrected URL encoding for branch names containing `/`.
- Hardened ZIP path validation against traversal and absolute/drive paths, including single-file archives.
- Escaped user/API-provided values before placing them in HTML status messages.

## Verification

- Full project Python compilation passed.
- GitHub helper tests passed for repository URL parsing, nested branch URL encoding, wrapper-folder handling, and ZIP traversal/absolute-path rejection.
- Static checks confirm the GitHub setup no longer calls `client.ask()` and the callback handler is registered ahead of the catch-all handler.
- ZIP integrity check passed.

Live GitHub API publishing still requires a valid PAT and a writable test repository; no credentials were available in this build environment.
