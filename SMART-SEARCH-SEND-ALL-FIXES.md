# Smart Search and Send All fixes

- Search tries the complete query first, then all three-token combinations, then two-token combinations, then individual tokens. Search still uses both file names and captions when caption filtering is enabled.
- Search regex recognizes common language aliases and season/episode notation; result captions summarize detected seasons, episode numbers, release years, and languages, including common native-script language tags.
- Send All now combines the related search variants into one deduplicated file list and starts one delivery queue instead of launching several overlapping queues.
- Sequential Send All shortlink creation falls back to the valid bot deep link if the shortener API is temporarily unavailable, so a shortener outage does not prevent the queue from starting. The exception is logged.
- Verified Python syntax with `python -m compileall`.

Note: Live Telegram delivery and external shortener API behavior require testing with the deployment's actual bot token, MongoDB, and shortener credentials.
