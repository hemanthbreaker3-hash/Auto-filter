# MoviesZoneFlix — Full Upgrade & Fixes (2026-11-15)

## Smart search
- Searches the complete query first, then bounded 3-term, 2-term, and 1-term fallback combinations.
- Gives each fallback tier its own candidate budget so long queries do not prevent pair/single-term attempts.
- Prioritizes year, language, season, and episode tokens in fallback combinations.
- Supports `S01E05`, `S01EP05`, `S01 E05`, `Season 1 Episode 5`, and `1x05` search notation.
- Handles language aliases and native-script terms in underscore/dot-delimited filenames.

## Result metadata
- Comma-separated episodes, seasons, qualities, languages, and years.
- Also detects codecs, release sources, audio formats, HDR tags, and subtitle tags.
- Expands episode packs such as `S01E01-E12` to show the episode range.
- Shows total indexed files and how many files were scanned for metadata (the scan is capped at 10,000 records per search to protect database performance).
- Telegraph pages split long inventories into multiple readable sections.

## Telegraph
- Uses Telegraph's public `createAccount` endpoint; no user-supplied API key is required.
- Stores the generated access token in MongoDB.
- Reuses a cached Telegraph page for identical query/metadata results to reduce duplicate page creation.
- Keeps the existing `/panel telegraph` controls for setup, enable/disable, and regeneration.

## Send All
- Deduplicates file IDs before creating a batch.
- Corrects protected-content handling for `allfilesp` batches and direct Send All delivery.
- Improves user-facing Send All error wording while preserving the bot deep-link fallback when a shortener is unavailable.

## Validation
- Python source compilation checked.
- Metadata parsing tested against underscore-delimited names, native-language labels, season/episode formats, quality, year, codec, source, audio, HDR, and subtitle tags.
- Search-regex tests cover underscore-delimited titles, language tags, years, `S01E05`, `S01EP05`, `1x05`, and `Season 1 Episode 5`.
