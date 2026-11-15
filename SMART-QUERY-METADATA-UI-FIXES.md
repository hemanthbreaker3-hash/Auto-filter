# Smart Query, Metadata, UI and Font Fixes

- Search now tries the complete query first, then progressive three-, two- and one-token combinations.
- Season, episode, year and supported language terms receive priority during relaxed matching.
- Language search recognizes common abbreviations and native scripts (Hindi, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, Punjabi, Gujarati, Japanese, Korean, Chinese, Arabic, Russian, French and Spanish).
- Search-result metadata summarizes available files, seasons, episode numbers, years, languages, resolutions, codecs and source tags.
- Common mathematical Unicode font variants were normalized in user-facing utility/command text. Search filter buttons use readable labels instead of small-cap/bold Unicode glyphs.
- Existing commands, callback identifiers and settings are preserved.

Search matching remains metadata-dependent: the bot can only report fields present in indexed filenames/captions.
