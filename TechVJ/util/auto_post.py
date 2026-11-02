"""Caption & filename-driven MoviesZoneFlix quality aggregation and automatic posting for Movies & Series."""
import re
import html
import logging
from datetime import datetime, timezone
try:
    from database.users_chats_db import db, normalize_channel_id
except Exception:
    db = None
    def normalize_channel_id(value):
        return value

logger = logging.getLogger(__name__)

# Comprehensive quality regex supporting resolution and rip/source tags
QUALITY_RE = re.compile(
    r'(?<!\d)(4320p|2160p|1440p|1080p|720p|576p|540p|480p|360p|240p|144p|8k|4k|2k|uhd|fhd|hdrip|web-dl|webdl|webrip|bluray|brrip|bdrip|dvdrip|hdts|hdcam|camrip|predvd|hd)(?!\w)',
    re.I,
)

QUALITY_ORDER = {
    "144p": 144,
    "240p": 240,
    "360p": 360,
    "480p": 480,
    "540p": 540,
    "576p": 576,
    "hd": 700,
    "720p": 720,
    "fhd": 1000,
    "1080p": 1080,
    "2k": 1400,
    "1440p": 1440,
    "uhd": 2100,
    "4k": 2150,
    "2160p": 2160,
    "8k": 4300,
    "4320p": 4320,
    "camrip": 5000,
    "hdcam": 5010,
    "hdts": 5020,
    "predvd": 5030,
    "dvdrip": 5040,
    "hdrip": 5050,
    "webrip": 5060,
    "webdl": 5070,
    "web-dl": 5070,
    "brrip": 5080,
    "bdrip": 5085,
    "bluray": 5090,
}

# Canonical languages and their common aliases/codes
LANGUAGE_ALIASES = [
    ("Telugu", ("telugu", "tel")),
    ("Tamil", ("tamil", "tam")),
    ("Hindi", ("hindi", "hin")),
    ("Malayalam", ("malayalam", "mal")),
    ("Kannada", ("kannada", "kan")),
    ("English", ("english", "eng")),
    ("Bengali", ("bengali", "bangla", "ben")),
    ("Marathi", ("marathi", "mar")),
    ("Punjabi", ("punjabi", "pun")),
    ("Gujarati", ("gujarati", "guj")),
    ("Odia", ("odia", "oriya")),
    ("Urdu", ("urdu", "urd")),
    ("Bhojpuri", ("bhojpuri", "bho")),
    ("Assamese", ("assamese", "asm")),
    ("Korean", ("korean", "kor")),
    ("Japanese", ("japanese", "jap", "jpn")),
    ("Chinese", ("chinese", "mandarin", "cantonese", "chi", "zho")),
    ("Spanish", ("spanish", "spa", "esp")),
    ("French", ("french", "fre", "fra")),
    ("German", ("german", "ger", "deu")),
    ("Russian", ("russian", "rus")),
    ("Italian", ("italian", "ita")),
    ("Portuguese", ("portuguese", "por")),
    ("Arabic", ("arabic", "ara")),
    ("Turkish", ("turkish", "tur")),
    ("Thai", ("thai", "tha")),
    ("Indonesian", ("indonesian", "ind")),
    ("Vietnamese", ("vietnamese", "vie")),
]

YEAR_RE = re.compile(r'\b(19\d{2}|20[0-3]\d)\b')
URL_RE = re.compile(r'https?://\S+|t\.me/\S+|telegram\.me/\S+', re.I)

# Series Season + Episode patterns (ordered from most specific to general)
_S_E_COMBINED_RE = re.compile(
    r'(?i)(?:\bseason\s*[:=\-\._\s]*(\d{1,3})\s*[\-\._\s,/]*\b(?:episode|ep|e)\s*[:=\-\._\s]*(\d{1,4})(?:\s*[\-&to]+\s*(?:e|ep|episode)?\s*(\d{1,4}))?\b'
    r'|\bS(\d{1,3})\s*[\.\-_\s]*E(?:P)?\s*(\d{1,4})(?:\s*[\-&to]+\s*E?(?:P)?\s*(\d{1,4}))?\b'
    r'|\b(\d{1,2})x(\d{1,3})(?!\d|[a-z])\b)'
)
_SEASON_ONLY_RE = re.compile(
    r'(?i)(?:\bseason\s*[:=\-\._\s]*(\d{1,3})\b|\bS(\d{1,2})\b(?!\s*[a-z0-9]))'
)
_EPISODE_ONLY_RE = re.compile(
    r'(?i)(?:\b(?:episode|ep\.?)\s*[:=\-\._\s]*(\d{1,4})(?:\s*[\-&to]+\s*(?:ep\.?|episode|e)?\s*(\d{1,4}))?\b'
    r'|\bE(\d{1,4})(?:\s*[\-&]\s*E?(\d{1,4}))?\b)'
)
_EXPLICIT_SERIES_LINE_RE = re.compile(r'(?im)^\s*(?:series|show|web\s*series|tv\s*series)\s*[:=\-]\s*(.+)$')
_EXPLICIT_MOVIE_LINE_RE = re.compile(r'(?im)^\s*(?:movie(?:\s*name)?|title|film)\s*[:=\-]\s*(.+)$')
_EXPLICIT_SEASON_LINE_RE = re.compile(r'(?im)^\s*season\s*[:=\-]\s*(\d{1,3})\b')
_EXPLICIT_EPISODE_LINE_RE = re.compile(r'(?im)^\s*episode\s*[:=\-]\s*(\d{1,4}(?:\s*[\-&]\s*\d{1,4})?)\b')
_EXPLICIT_LANG_LINE_RE = re.compile(r'(?im)^\s*(?:languages?|audio)\s*[:=\-]\s*(.+)$')


def _normalize_quality(q: str) -> str:
    q_low = q.strip().lower()
    if q_low == "webdl":
        return "web-dl"
    return q_low


def _quality_sort_key(q: str):
    q_norm = _normalize_quality(q)
    return (QUALITY_ORDER.get(q_norm, 99999), q_norm)


def sort_qualities(qualities) -> list:
    normed = {_normalize_quality(q) for q in (qualities or []) if q and str(q).strip()}
    return sorted(normed, key=_quality_sort_key)


def format_qualities_text(qualities) -> str:
    """Format qualities list as '480p,720p and 1080p'."""
    qs = sort_qualities(qualities)
    if not qs:
        return "HD"
    if len(qs) == 1:
        return qs[0]
    if len(qs) == 2:
        return f"{qs[0]} and {qs[1]}"
    return f"{','.join(qs[:-1])} and {qs[-1]}"


def extract_languages(text: str) -> list:
    """Detect all languages from caption/filename while preserving discovery order."""
    if not text:
        return []
    found = []
    seen = set()

    def _add(canonical):
        if canonical not in seen:
            seen.add(canonical)
            found.append(canonical)

    # 1. Check explicit Language / Languages / Audio lines first for exact order
    for m in _EXPLICIT_LANG_LINE_RE.finditer(text):
        lang_line = m.group(1)
        for token in re.split(r'[,/&+|\s\[\]\(\)\-]+', lang_line):
            tok_low = token.strip().lower()
            if not tok_low:
                continue
            for canonical, aliases in LANGUAGE_ALIASES:
                if tok_low in aliases:
                    _add(canonical)
                    break

    # 2. Scan the full text for full language names (ordered by position in text)
    full_matches = []
    for canonical, aliases in LANGUAGE_ALIASES:
        full_name = aliases[0]
        for m in re.finditer(rf'(?<![A-Za-z]){re.escape(full_name)}(?![A-Za-z])', text, re.I):
            full_matches.append((m.start(), canonical))
    for _pos, canonical in sorted(full_matches, key=lambda x: x[0]):
        _add(canonical)

    # 3. Scan for short 3-letter language codes inside brackets, parens, or separated by + / - / , / _ / .
    short_matches = []
    for canonical, aliases in LANGUAGE_ALIASES:
        for short_code in aliases[1:]:
            # Avoid matching common English words like 'mar', 'ind', 'ger' unless bounded by typical media separators or audio context
            pattern = rf'(?:[\[\(\+\-_,/]|(?i:\baudio\b|\blang(?:uages?)?\b|\bdub(?:bed)?\b)[\s:=\-\[\(]*)\s*(?<![A-Za-z]){re.escape(short_code)}(?![A-Za-z])\s*(?=[\]\)\+\-_,/\s]|$)'
            for m in re.finditer(pattern, text, re.I):
                short_matches.append((m.start(), canonical))
    for _pos, canonical in sorted(short_matches, key=lambda x: x[0]):
        _add(canonical)

    return found


def format_languages_line(languages: list) -> tuple:
    """Return (label, value) where label is 'Language' for 1 language and 'Languages' for multiple."""
    clean = [str(l).strip() for l in (languages or []) if str(l).strip()]
    if not clean:
        return "Language", "Unknown"
    if len(clean) == 1:
        return "Language", clean[0]
    return "Languages", ",".join(clean)


def extract_season_episode(text: str):
    """Extract (season_str, episode_str, match_span) from text if present."""
    if not text:
        return None, None, None

    # Check explicit lines first (e.g. Season : 10 \n EPISODE : 1)
    exp_s = _EXPLICIT_SEASON_LINE_RE.search(text)
    exp_e = _EXPLICIT_EPISODE_LINE_RE.search(text)
    if exp_e:
        ep_raw = exp_e.group(1)
        ep_parts = [str(int(p)) for p in re.findall(r'\d+', ep_raw)]
        ep_str = "-".join(ep_parts) if ep_parts else ep_raw.strip()
        s_str = str(int(exp_s.group(1))) if exp_s else None
        if not s_str:
            s_only = _SEASON_ONLY_RE.search(text)
            if s_only:
                s_str = str(int(s_only.group(1) or s_only.group(2)))
        return (s_str or "1"), ep_str, exp_e.span()

    # Check combined S01E01 / Season 1 Episode 1 / 1x01 patterns
    m = _S_E_COMBINED_RE.search(text)
    if m:
        if m.group(1) and m.group(2):
            s_num = str(int(m.group(1)))
            e_start = str(int(m.group(2)))
            e_end = str(int(m.group(3))) if m.group(3) else None
            e_num = f"{e_start}-{e_end}" if e_end else e_start
            return s_num, e_num, m.span()
        if m.group(4) and m.group(5):
            s_num = str(int(m.group(4)))
            e_start = str(int(m.group(5)))
            e_end = str(int(m.group(6))) if m.group(6) else None
            e_num = f"{e_start}-{e_end}" if e_end else e_start
            return s_num, e_num, m.span()
        if m.group(7) and m.group(8):
            s_num = str(int(m.group(7)))
            e_num = str(int(m.group(8)))
            return s_num, e_num, m.span()

    # Check separate Season + Episode occurrences anywhere in text
    ep_match = _EPISODE_ONLY_RE.search(text)
    if ep_match:
        s_match = _SEASON_ONLY_RE.search(text)
        s_num = str(int(s_match.group(1) or s_match.group(2))) if s_match else "1"
        e_start = str(int(ep_match.group(1) or ep_match.group(3)))
        e_end_raw = ep_match.group(2) or ep_match.group(4)
        e_end = str(int(e_end_raw)) if e_end_raw else None
        e_num = f"{e_start}-{e_end}" if e_end else e_start
        span_start = min(s_match.start(), ep_match.start()) if s_match else ep_match.start()
        span_end = max(s_match.end(), ep_match.end()) if s_match else ep_match.end()
        return s_num, e_num, (span_start, span_end)

    return None, None, None


def _clean_title_segment(raw_line: str) -> str:
    line = URL_RE.sub(' ', raw_line)
    # Strip file extensions first
    line = re.sub(r'\.(?:mkv|mp4|avi|mov|webm|flv|m4v|ts|srt|sub)\b', ' ', line, flags=re.I)
    # Strip explicit metadata labels
    line = re.sub(
        r'(?i)\b(series|movie(?:\s*name)?|season|episode|language|languages|quality|qualities|duration|size|file|format|audio|video|codec|subtitle|subtitles)\s*[:=].*$',
        ' ',
        line,
    )
    # Strip season/episode markers and everything after them on the same filename line
    line = re.sub(
        r'(?i)\b(?:season\s*[:=\-\._\s]*\d+|s\d{1,3}\s*[\.\-_\s]*e(?:p)?\s*\d+|s\d{1,2}\b|(?:episode|ep\.?)\s*[:=\-\._\s]*\d+|\be\d{1,4}\b|\d{1,2}x\d{1,3}\b).*$',
        ' ',
        line,
    )
    line = QUALITY_RE.sub(' ', line)
    for _canon, aliases in LANGUAGE_ALIASES:
        for alias in aliases:
            if len(alias) >= 4:
                line = re.sub(rf'(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])', ' ', line, flags=re.I)
    line = re.sub(
        r'\b(?:mkv|mp4|avi|mov|webm|hevc|x265|x264|h\.?264|h\.?265|avc|aac|ddp?\s*\d(?:\.\d)?|eac3|ac3|atmos|hdr10\+?|dv|10bit|8bit|esub|esubs|msub|msubs|dual\s*audio|multi\s*audio|uncut|org|proper|repack|amzn|nf|dsnp|zee5|sonyliv|aha|hotstar|jio|voot|ullu)\b',
        ' ',
        line,
        flags=re.I,
    )
    line = re.sub(r'[🎬📺🌐⏱️📁💾🔊📝⭐️✅❌🔥💥✨🎭]', ' ', line)
    line = re.sub(r'[@#][\w.-]+', ' ', line)
    line = re.sub(r'\[[^\]]*\]|\([^\)]*\)', ' ', line)
    line = re.sub(r'[_|•\.\-\+]+', ' ', line)
    line = re.sub(r'\s+', ' ', line).strip(' -:,.')
    return line


def parse_movie_caption(caption, file_name=None):
    """Parse movie or series metadata from caption and/or filename.

    Supports both Movies and Series (with Season, Episode, multiple Qualities,
    and single or multiple Languages).
    """
    combined_parts = []
    if caption and str(caption).strip():
        combined_parts.append(str(caption).replace('\u200b', ' ').strip())
    if file_name and str(file_name).strip():
        fn_str = str(file_name).replace('\u200b', ' ').strip()
        if fn_str not in combined_parts:
            combined_parts.append(fn_str)
    if not combined_parts:
        return None

    full_text = "\n".join(combined_parts)
    normalized_text = re.sub(r'[_\.]+', ' ', full_text)

    # Extract qualities
    quality_matches = QUALITY_RE.findall(normalized_text)
    qualities = sort_qualities(quality_matches)

    # Extract languages
    languages = extract_languages(normalized_text)

    # Extract season & episode
    season, episode, _se_span = extract_season_episode(normalized_text)
    is_series = bool(episode is not None)

    # Extract year (avoid matching episode numbers like 1999 unless not part of episode)
    text_without_se = _S_E_COMBINED_RE.sub(' ', normalized_text)
    text_without_se = _EPISODE_ONLY_RE.sub(' ', text_without_se)
    year_match = YEAR_RE.search(text_without_se)
    year = year_match.group(1) if (year_match and not is_series) else None

    # Extract explicit Series / Movie title if present
    explicit_title = None
    m_series = _EXPLICIT_SERIES_LINE_RE.search(full_text)
    m_movie = _EXPLICIT_MOVIE_LINE_RE.search(full_text)
    if m_series:
        explicit_title = _clean_title_segment(m_series.group(1))
        is_series = True
    elif m_movie:
        explicit_title = _clean_title_segment(m_movie.group(1))

    name = explicit_title or ""
    if not name:
        candidate_lines = []
        for raw_line in full_text.splitlines():
            cleaned = _clean_title_segment(raw_line)
            if not is_series and year:
                cleaned = re.sub(rf'\b{re.escape(year)}\b', ' ', cleaned).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -()[]')
            if cleaned and len(cleaned) >= 2 and not re.search(
                r'^(?:https?|duration|size|language|languages|quality|qualities|season|episode|join|subscribe|channel|uploaded|download|support)\b',
                cleaned,
                re.I,
            ):
                candidate_lines.append(cleaned)
        name = next((line for line in candidate_lines if len(line) >= 2), "")

    if not name:
        return None

    # Clean up trailing year from title
    name = re.sub(r'\b(19\d{2}|20[0-3]\d)\b', '', name).strip(' -()[]')
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return None

    base_key = re.sub(r'[^a-z0-9]+', ' ', name.lower()).strip()
    if not base_key:
        return None

    if is_series:
        season_str = str(season or "1")
        episode_str = str(episode or "1")
        s_pad = f"S{int(season_str):02d}" if season_str.isdigit() else f"S{season_str}"
        e_first = episode_str.split("-")[0]
        e_pad = f"E{int(e_first):02d}" if e_first.isdigit() else f"E{episode_str}"
        display_name = f"{name} {s_pad}{e_pad}"
        # Rich search index name so Season, Episode, Quality, and Language filters all match
        meta_tokens = [
            name,
            f"Season {season_str}",
            s_pad,
            f"Episode {episode_str}",
            e_pad,
            *qualities,
            *languages,
        ]
        search_index_name = " ".join(dict.fromkeys(tok for tok in meta_tokens if tok))
        key = f"series:{base_key}:s{season_str}:e{episode_str}"
        return {
            "is_series": True,
            "series_name": name,
            "movie_name": display_name,
            "search_index_name": search_index_name,
            "key": key,
            "base_key": base_key,
            "season": season_str,
            "episode": episode_str,
            "year": year,
            "qualities": qualities,
            "languages": languages,
        }

    display_name = f"{name} ({year})" if year else name
    meta_tokens = [display_name, *qualities, *languages]
    search_index_name = " ".join(dict.fromkeys(tok for tok in meta_tokens if tok))
    key = re.sub(r'[^a-z0-9]+', ' ', display_name.lower()).strip()
    return {
        "is_series": False,
        "series_name": None,
        "movie_name": display_name,
        "search_index_name": search_index_name,
        "key": key,
        "base_key": base_key,
        "season": None,
        "episode": None,
        "year": year,
        "qualities": qualities,
        "languages": languages,
    }


def format_auto_post_message(parsed_or_doc: dict) -> str:
    """Format the destination channel post for either a Series episode or a Movie."""
    is_series = bool(parsed_or_doc.get("is_series"))
    qualities = sort_qualities(parsed_or_doc.get("qualities", []))
    languages = list(parsed_or_doc.get("languages", []))
    quality_str = format_qualities_text(qualities)
    lang_label, lang_val = format_languages_line(languages)

    if is_series:
        series_name = html.escape(str(parsed_or_doc.get("series_name") or parsed_or_doc.get("movie_name") or "").strip())
        season = html.escape(str(parsed_or_doc.get("season") or "1"))
        episode = html.escape(str(parsed_or_doc.get("episode") or "1"))
        return (
            f"<b>Series : {series_name}\n"
            f"Season : {season}\n"
            f"EPISODE : {episode}\n"
            f"QUALITY : {html.escape(quality_str)}\n"
            f"{lang_label} : {html.escape(lang_val)}</b>"
        )

    movie_name = html.escape(str(parsed_or_doc.get("movie_name") or "").strip())
    return (
        f"🎬 <b>Movie : {movie_name}</b>\n"
        f"📺 <b>QUALITY : {html.escape(quality_str)}</b>\n"
        f"🌐 <b>{lang_label} : {html.escape(lang_val)}</b>"
    )


async def process_caption_for_auto_post(bot, caption=None, source_chat_id=None, file_name=None):
    """Aggregate caption/filename metadata and publish to destination channel when 3 qualities are found.

    For Series, each (Series, Season, Episode) is tracked independently so every 1 episode
    posts automatically as soon as its 3 qualities (e.g. 480p, 720p, 1080p) are detected.
    """
    if not caption and not file_name:
        return None
    try:
        parsed = parse_movie_caption(caption, file_name=file_name)
        if not parsed or not parsed.get("qualities"):
            return None

        settings = await db.get_auto_post_settings()
        if not settings.get("auto_index", False):
            return None
        target = settings.get("post_channel_id")
        if not target:
            return None

        if parsed.get("is_series") and not settings.get("series_enabled", True):
            return None
        if not parsed.get("is_series") and not settings.get("movies_enabled", True):
            return None

        # Restrict auto-post input to configured index channels when configured.
        managed = set(await db.get_managed_channels())
        if managed and source_chat_id is not None:
            norm_src = normalize_channel_id(source_chat_id)
            if norm_src not in managed and source_chat_id not in managed:
                return None

        min_qualities = max(1, int(settings.get("min_qualities", 3) or 3))
        agg = db.config
        key = parsed["key"]
        doc_id = f"auto_post:{key}" if parsed.get("is_series") else f"auto_movie:{key}"

        current = await agg.find_one({"_id": doc_id}) or {
            "qualities": [],
            "languages": [],
            "posted": False,
        }

        qualities = sort_qualities(set(current.get("qualities", [])) | set(parsed["qualities"]))
        # Preserve language order while merging
        merged_languages = list(current.get("languages", []))
        for lang in parsed["languages"]:
            if lang not in merged_languages:
                merged_languages.append(lang)

        doc_payload = {
            "is_series": bool(parsed.get("is_series")),
            "series_name": parsed.get("series_name"),
            "movie_name": parsed.get("movie_name"),
            "season": parsed.get("season"),
            "episode": parsed.get("episode"),
            "qualities": qualities,
            "languages": merged_languages,
            "updated_at": datetime.now(timezone.utc),
            "source_chat_id": source_chat_id,
        }
        await agg.update_one({"_id": doc_id}, {"$set": doc_payload}, upsert=True)

        text = format_auto_post_message(doc_payload)
        from info import GRP_LNK, SUPPORT_CHAT
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from TechVJ.util.telegram_rich import ButtonStyle
        search_url = GRP_LNK or f"https://t.me/{str(SUPPORT_CHAT or 'movieszoneflixsearch').strip().lstrip('@')}"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Search & Download Here", url=search_url, style=ButtonStyle.SUCCESS)]
        ])

        # If already posted and new quality/language arrived, update existing post seamlessly
        if current.get("posted"):
            posted_msg_id = current.get("posted_msg_id")
            if posted_msg_id and (
                set(qualities) != set(current.get("qualities", []))
                or set(merged_languages) != set(current.get("languages", []))
            ):
                try:
                    await bot.edit_message_text(
                        int(target),
                        int(posted_msg_id),
                        text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
            return {"posted": False, "already_posted": True, "qualities": qualities, "languages": merged_languages}

        if len(qualities) < min_qualities:
            return {"posted": False, "qualities": qualities, "languages": merged_languages}

        # Atomically claim posting to prevent duplicate posts from concurrent updates.
        claim = await agg.update_one(
            {"_id": doc_id, "posted": {"$ne": True}},
            {"$set": {"posted": True, "posted_at": datetime.now(timezone.utc)}},
        )
        if not claim.modified_count:
            return {"posted": False, "duplicate": True, "qualities": qualities}

        try:
            sent = await bot.send_message(
                int(target),
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            if sent and getattr(sent, "id", None):
                await agg.update_one({"_id": doc_id}, {"$set": {"posted_msg_id": int(sent.id)}})
        except Exception:
            await agg.update_one({"_id": doc_id}, {"$set": {"posted": False}})
            raise

        return {
            "posted": True,
            "is_series": bool(parsed.get("is_series")),
            "qualities": qualities,
            "languages": merged_languages,
            "text": text,
        }
    except Exception:
        logger.exception("MoviesZoneFlix auto-post processing failed")
        return None
