# Send All sequential shortlink + credits fix

- Send All now creates a MongoDB-backed queue for the selected result page.
- In Credits mode, each successfully delivered file costs exactly 1 credit.
- Only one shortlink is shown at a time. After a file is delivered, the next file's shortlink is sent.
- When the user's balance reaches zero, the bot requests verification and resumes the same queue after verification.
- In Link mode, files are also unlocked one-by-one through sequential shortlinks.
- Re-opening a used file link does not charge another credit or send the same file again (per-index MongoDB reservation/delivery markers).
- Missing/deleted file IDs are skipped without consuming a credit.
- Premium users and modes that do not require shortlinks keep direct Send All behavior.

Validation performed: Python syntax compilation and ZIP integrity checks. Live MongoDB/Telegram shortener behavior must be verified after deployment.
