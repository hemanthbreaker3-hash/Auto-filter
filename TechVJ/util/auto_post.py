"""Caption & filename-driven MoviesZoneFlix quality aggregation and automatic posting for Movies & Series."""
import re
import html
import logging
from difflib import SequenceMatcher
from datetime import datetime, timezone
try:
    from database.users_chats_db import db, normalize_channel_id
except Exception:
    db = None
    def normalize_channel_id(value):
        return value

from TechVJ.util.telegram_rich import api_request, make_inline_keyboard

logger = logging.getLogger(__name__)

# Accept numeric video resolutions from 144p through 4880p, including every
# integer step from 480p through 600p and common 240p/360p/720p/1080p variants.
QUALITY_RE = re.compile(r'(?<!\d)(\d{3,4})p(?!\w)', re.I)
SUPPORTED_QUALITY_HEIGHTS = set(range(144, 4881))


def _quality_height(value):
    match = re.fullmatch(r"\s*(\d{3,4})p\s*", str(value or ""), re.I)
    if not match:
        return None
    height = int(match.group(1))
    return height if height in SUPPORTED_QUALITY_HEIGHTS else None

# Extra tags stripped from titles only (never counted as quality)
_TITLE_JUNK_QUALITY_RE = re.compile(
    r'(?<!\d)(4320p|2160p|1440p|576p|540p|360p|240p|144p|8k|4k|2k|uhd|fhd|hdrip|web-dl|webdl|webrip|bluray|brrip|bdrip|dvdrip|hdts|hdcam|camrip|predvd|pre-dvd|predvdrip|hq\s*predvd|hq|hd)(?!\w)',
    re.I,
)

# Canonical languages and their common aliases/codes
LANGUAGE_ALIASES = [
    # Indian languages (Latin + native scripts)
    ("Telugu", ("telugu", "tel", "తెలుగు", "తెలుగ", "తెలుగులో")),
    ("Tamil", ("tamil", "tam", "தமிழ்", "தமிழ", "தமிழில்")),
    ("Hindi", ("hindi", "hin", "हिंदी", "हिन्दी", "हिन्दि", "हिंदीमें")),
    ("Malayalam", ("malayalam", "mal", "മലയാളം", "മലയാള")),
    ("Kannada", ("kannada", "kan", "ಕನ್ನಡ", "ಕನ್ನಡದಲ್ಲಿ")),
    ("English", ("english", "eng", "ఇంగ్లీష్", "इंग्लिश", "ஆங்கிலம்")),
    ("Bengali", ("bengali", "bangla", "ben", "বাংলা", "বাঙালি")),
    ("Marathi", ("marathi", "mar", "मराठी")),
    ("Punjabi", ("punjabi", "pun", "ਪੰਜਾਬੀ", "पंजाबी")),
    ("Gujarati", ("gujarati", "guj", "ગુજરાતી")),
    ("Odia", ("odia", "oriya", "ଓଡ଼ିଆ", "ଓଡିଆ")),
    ("Urdu", ("urdu", "urd", "اردو")),
    ("Bhojpuri", ("bhojpuri", "bho", "भोजपुरी")),
    ("Assamese", ("assamese", "asm", "অসমীয়া")),
    # International
    ("Korean", ("korean", "kor", "한국어", "한국")),
    ("Japanese", ("japanese", "jap", "jpn", "日本語", "にほんご")),
    ("Chinese", ("chinese", "mandarin", "cantonese", "chi", "zho", "中文", "普通话", "粵語")),
    ("Spanish", ("spanish", "spa", "esp", "español")),
    ("French", ("french", "fre", "fra", "français")),
    ("German", ("german", "ger", "deu", "deutsch")),
    ("Russian", ("russian", "rus", "русский")),
    ("Italian", ("italian", "ita", "italiano")),
    ("Portuguese", ("portuguese", "por", "português")),
    ("Arabic", ("arabic", "ara", "العربية", "عربي")),
    ("Turkish", ("turkish", "tur", "türkçe")),
    ("Thai", ("thai", "tha", "ไทย")),
    ("Indonesian", ("indonesian", "ind", "bahasa")),
    ("Vietnamese", ("vietnamese", "vie", "tiếng việt")),
]

YEAR_RE = re.compile(r'\b(19\d{2}|20[0-3]\d)\b')
URL_RE = re.compile(r'https?://\S+|t\.me/\S+|telegram\.me/\S+', re.I)

_DURATION_LINE_RE = re.compile(
    r'(?im)^\s*[^A-Za-z0-9]*duration\s*[:=\-]\s*(.+)$'
)

def extract_duration(text: str):
    """Extract a human-readable duration from channel metadata."""
    if not text:
        return None
    match = _DURATION_LINE_RE.search(text)
    candidate = match.group(1).strip() if match else ""
    if not candidate:
        # Also accept an unlabelled clock-style duration in the caption.
        clock = re.search(r'(?<!\d)(\d{1,2}:\d{2}:\d{2})(?!\d)', text)
        if clock:
            candidate = clock.group(1)
    if not candidate:
        return None
    clock = re.fullmatch(r'(\d{1,2}):(\d{2}):(\d{2})', candidate)
    if clock:
        h, m, sec = map(int, clock.groups())
        return f"{h}h {m}m {sec}s"
    h = re.search(r'(\d+)\s*h(?:ours?)?', candidate, re.I)
    m = re.search(r'(\d+)\s*m(?:in(?:utes?)?)?', candidate, re.I)
    sec = re.search(r'(\d+)\s*s(?:ec(?:onds?)?)?', candidate, re.I)
    if h or m or sec:
        parts = []
        if h:
            parts.append(f"{int(h.group(1))}h")
        if m:
            parts.append(f"{int(m.group(1))}m")
        if sec:
            parts.append(f"{int(sec.group(1))}s")
        return " ".join(parts)
    return candidate[:80]

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
# Allow optional leading emoji / symbols before labels (common in channel captions)
_EXPLICIT_PREFIX = r'(?:[\U0001F300-\U0001FAFF\u2600-\u27BF⭐️✅❌🔥💥✨🎭♨️♨🎬📺🌐⏱️📁💾🔊📝📅📆]\s*)*'
_EXPLICIT_SERIES_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}(?:series|show|web\s*series|tv\s*series)\s*[:=\-]\s*(.+)$'
)
_EXPLICIT_MOVIE_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}(?:movie(?:\s*name)?|title|film|name)\s*[:=\-]\s*(.+)$'
)
_EXPLICIT_SEASON_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}season\s*[:=\-]\s*(\d{{1,3}})\b'
)
_EXPLICIT_EPISODE_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}episode\s*[:=\-]\s*(\d{{1,4}}(?:\s*[\-&]\s*\d{{1,4}})?)\b'
)
_EXPLICIT_LANG_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}(?:languages?|audio|lang)\s*[:=\-]\s*(.+)$'
)
_EXPLICIT_YEAR_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}(?:year|released?)\s*[:=\-]\s*(19\d{{2}}|20[0-3]\d)\b'
)
_EXPLICIT_QUALITY_LINE_RE = re.compile(
    rf'(?im)^\s*{_EXPLICIT_PREFIX}(?:qualities?|resolution|format)\s*[:=\-]\s*(.+)$'
)


def _normalize_quality(q: str) -> str:
    """Keep numeric resolution labels from 144p through 4880p."""
    height = _quality_height(q)
    return f"{height}p" if height is not None else ""


def _quality_sort_key(q: str):
    q_norm = _normalize_quality(q)
    return (int(q_norm[:-1]) if q_norm else 99999, q_norm)


def sort_qualities(qualities) -> list:
    """Return supported numeric resolutions in ascending order."""
    normed = {_normalize_quality(q) for q in (qualities or [])}
    normed.discard("")
    return sorted(normed, key=_quality_sort_key)


def format_qualities_text(qualities) -> str:
    """Format all detected resolution labels in ascending order."""
    qs = sort_qualities(qualities)
    if not qs:
        return "—"
    if len(qs) == 1:
        return qs[0]
    if len(qs) == 2:
        return f"{qs[0]} and {qs[1]}"
    return f"{', '.join(qs[:-1])} and {qs[-1]}"


def extract_languages(text: str) -> list:
    """Detect all languages from caption/filename while preserving discovery order.

    Supports Latin names, short codes, and native scripts (తెలుగు, हिंदी, தமிழ், etc.).
    """
    if not text:
        return []
    found = []
    seen = set()

    def _add(canonical):
        if canonical not in seen:
            seen.add(canonical)
            found.append(canonical)

    # 1. Explicit Language / Languages / Audio / 🌐 Language lines
    for m in _EXPLICIT_LANG_LINE_RE.finditer(text):
        lang_line = m.group(1)
        for token in re.split(r'[,/&+|\s\[\]\(\)\-]+', lang_line):
            tok = token.strip()
            if not tok:
                continue
            tok_low = tok.lower()
            for canonical, aliases in LANGUAGE_ALIASES:
                alias_low = [a.lower() for a in aliases]
                if tok_low in alias_low or tok in aliases:
                    _add(canonical)
                    break

    # 2. Full language names + native scripts anywhere in text (position-ordered)
    full_matches = []
    for canonical, aliases in LANGUAGE_ALIASES:
        for alias in aliases:
            if any(ord(c) > 127 for c in alias):
                for m in re.finditer(re.escape(alias), text):
                    full_matches.append((m.start(), canonical))
            else:
                for m in re.finditer(rf'(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])', text, re.I):
                    full_matches.append((m.start(), canonical))
    for _pos, canonical in sorted(full_matches, key=lambda x: x[0]):
        _add(canonical)

    # 3. Short 3-letter codes in brackets / separators / audio context
    short_matches = []
    for canonical, aliases in LANGUAGE_ALIASES:
        for short_code in aliases[1:]:
            if any(ord(c) > 127 for c in short_code):
                continue
            if len(short_code) > 4:
                continue
            pattern = (
                rf'(?:[\[\(\+\-_,/]|(?i:\baudio\b|\blang(?:uages?)?\b|\bdub(?:bed)?\b)[\s:=\-\[\(]*)'
                rf'\s*(?<![A-Za-z]){re.escape(short_code)}(?![A-Za-z])\s*(?=[\]\)\+\-_,/\s]|$)'
            )
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
    line = _TITLE_JUNK_QUALITY_RE.sub(' ', line)
    for _canon, aliases in LANGUAGE_ALIASES:
        for alias in aliases:
            if len(alias) >= 3:  # also strip short codes like tel, tam, hin when cleaning title
                line = re.sub(rf'(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])', ' ', line, flags=re.I)
    # Strip codecs, sources, common release tags, and file size
    line = re.sub(
        r'\b(?:mkv|mp4|avi|mov|webm|hevc|x265|x264|h\.?264|h\.?265|avc|aac|ddp?\s*\d(?:\.\d)?|eac3|ac3|atmos|hdr10\+?|dv|10bit|8bit|esub|esubs|msub|msubs|dual\s*audio|multi\s*audio|uncut|org|proper|repack|remux|hybrid|clean|hq\s*clean|hq|amzn|nf|dsnp|zee5|sonyliv|aha|hotstar|jio|voot|ullu|predvd|pre-dvd|predvdrip)\b',
        ' ',
        line,
        flags=re.I,
    )
    # File sizes like 400MB, 1.4GB, 2.8 GB
    line = re.sub(r'\b\d+(?:\.\d+)?\s*(?:MB|GB|TB|mb|gb|tb)\b', ' ', line, flags=re.I)
    # Common emoji / symbols used in release names (including ♨️)
    line = re.sub(r'[🎬📺🌐⏱️📁💾🔊📝⭐️✅❌🔥💥✨🎭♨️♨]', ' ', line)
    line = re.sub(r'[@#][\w.-]+', ' ', line)
    line = re.sub(r'\[[^\]]*\]|\([^\)]*\)', ' ', line)
    # Normalize separators but keep intentional dots in acronyms by converting only runs of dots mixed with other seps
    line = re.sub(r'[_|•\-\+]+', ' ', line)
    # Convert isolated dotted acronyms "G.O.A.T" -> "G O A T" (common in Indian releases)
    line = re.sub(r'\.', ' ', line)
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

    # Prefer resolution metadata in the Telegram caption (including a standalone
    # line such as "540p") over a contradictory release tag in the filename.
    # If the caption has no supported resolution, fall back to the filename.
    caption_text = str(caption or "").replace("\u200b", " ")
    filename_text = str(file_name or "").replace("\u200b", " ")

    def _supported_tokens(source):
        return [f"{m.group(1)}p" for m in QUALITY_RE.finditer(source or "")
                if _quality_height(f"{m.group(1)}p") is not None]

    caption_quality_matches = []
    for m in _EXPLICIT_QUALITY_LINE_RE.finditer(caption_text):
        caption_quality_matches.extend(_supported_tokens(m.group(1)))
    # A bare resolution on its own line is common in channel metadata blocks.
    for line in caption_text.splitlines():
        if re.fullmatch(r"\s*(\d{3,4})p\s*", line, re.I):
            caption_quality_matches.extend(_supported_tokens(line))
    if not caption_quality_matches:
        caption_quality_matches = _supported_tokens(caption_text)
    quality_matches = caption_quality_matches or _supported_tokens(filename_text or normalized_text)
    # Support explicitly labelled quality metadata in the filename/text fallback too.
    if not quality_matches:
        for m in _EXPLICIT_QUALITY_LINE_RE.finditer(full_text):
            quality_matches.extend(_supported_tokens(m.group(1)))
    qualities = sort_qualities(quality_matches)

    # Detect languages across the ENTIRE caption and filename.  Some channel
    # captions put language names in the release title (e.g. "Telugu HQ PreDVD")
    # while an Audio/Languages line may mention additional tracks (e.g. English).
    # Keep explicitly-labelled audio languages first, then merge every other
    # recognized language found anywhere in the caption/filename without dupes.
    explicit_language_text = "\n".join(
        match.group(1) for match in _EXPLICIT_LANG_LINE_RE.finditer(full_text)
    )
    languages = extract_languages(explicit_language_text)
    for detected_language in extract_languages(normalized_text):
        if detected_language not in languages:
            languages.append(detected_language)
    duration = extract_duration(full_text)

    # Extract season & episode
    season, episode, _se_span = extract_season_episode(normalized_text)
    is_series = bool(episode is not None)

    # Extract year — prefer explicit "Year : 2026" lines, then any year token
    year = None
    m_year_line = _EXPLICIT_YEAR_LINE_RE.search(full_text)
    if m_year_line:
        year = m_year_line.group(1)
    if not year:
        text_without_se = _S_E_COMBINED_RE.sub(' ', normalized_text)
        text_without_se = _EPISODE_ONLY_RE.sub(' ', text_without_se)
        year_match = YEAR_RE.search(text_without_se)
        if year_match and not is_series:
            year = year_match.group(1)

    # Extract explicit Series / Movie title if present (supports emoji prefixes)
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
        # Scan every line of the total caption+filename and pick the best title-like line
        _LABEL_START_RE = re.compile(
            r'^(?:https?|duration|size|language|languages|quality|qualities|season|episode|'
            r'join|subscribe|channel|uploaded|download|support|year|released?|audio|format|'
            r'codec|subtitle|subtitles|file|video|info|note|link|group|bot)\b',
            re.I,
        )
        candidate_lines = []
        for raw_line in full_text.splitlines():
            cleaned = _clean_title_segment(raw_line)
            if year:
                cleaned = re.sub(rf'\b{re.escape(year)}\b', ' ', cleaned).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -()[]')
            if not cleaned or len(cleaned) < 2:
                continue
            if _LABEL_START_RE.search(cleaned):
                continue
            # Skip lines that are only numbers / size leftovers
            if re.fullmatch(r'[\d\s\.]+', cleaned):
                continue
            candidate_lines.append(cleaned)
        # Prefer longer title-like lines (first substantial one is usually the name)
        if candidate_lines:
            # Prefer the candidate that looks most like a title (more letters, fewer pure digits)
            def _title_score(s):
                letters = sum(c.isalpha() for c in s)
                return (letters, len(s))
            candidate_lines.sort(key=_title_score, reverse=True)
            name = candidate_lines[0]

    if not name:
        return None

    # Clean up trailing/embedded year from title
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
            "duration": duration,
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
        "duration": duration,
        "qualities": qualities,
        "languages": languages,
    }


def format_auto_post_message(parsed_or_doc: dict) -> str:
    """Format the destination channel post for either a Series episode or a Movie.

    Qualities include numeric resolutions from 144p through 4880p, including every integer resolution between 480p and 600p.
    Series and movies use separate templates so fields never mix.
    """
    is_series = bool(parsed_or_doc.get("is_series"))
    qualities = sort_qualities(parsed_or_doc.get("qualities", []))
    languages = list(parsed_or_doc.get("languages", []))
    quality_str = format_qualities_text(qualities)
    lang_label, lang_val = format_languages_line(languages)

    if is_series:
        series_name = html.escape(str(parsed_or_doc.get("series_name") or "").strip())
        if not series_name:
            # strip SxxExx suffix if movie_name was used as fallback
            raw = str(parsed_or_doc.get("movie_name") or "").strip()
            series_name = html.escape(re.sub(r"\s*S\d{1,3}E\d{1,4}.*$", "", raw, flags=re.I).strip() or raw)
        season = html.escape(str(parsed_or_doc.get("season") or "1"))
        episode = html.escape(str(parsed_or_doc.get("episode") or "1"))
        duration = parsed_or_doc.get("duration")
        duration_line = f"\n⏱ Duration : {html.escape(str(duration))}" if duration else ""
        return (
            f"<b>Series : {series_name}\n"
            f"Season : {season}\n"
            f"EPISODE : {episode}\n"
            f"QUALITY : {html.escape(quality_str)}{duration_line}\n"
            f"{lang_label} : {html.escape(lang_val)}</b>"
        )

    movie_name = html.escape(str(parsed_or_doc.get("movie_name") or "").strip())
    year = parsed_or_doc.get("year")
    year_line = f"\n📅 <b>Year : {html.escape(str(year))}</b>" if year else ""
    duration = parsed_or_doc.get("duration")
    duration_line = f"\n⏱ <b>Duration : {html.escape(str(duration))}</b>" if duration else ""
    return (
        f"🎬 <b>Movie : {movie_name}</b>{year_line}{duration_line}\n"
        f"📺 <b>QUALITY : {html.escape(quality_str)}</b>\n"
        f"🌐 <b>{lang_label} : {html.escape(lang_val)}</b>"
    )


async def process_caption_for_auto_post(bot, caption=None, source_chat_id=None, file_name=None):
    """Aggregate caption/filename metadata and publish when the configured quality count is met.

    For Series, each (Series, Season, Episode) is tracked independently. Supported qualities
    are numeric resolutions from 144p through 4880p, including every 480p–600p value.
    """
    if not caption and not file_name:
        return None
    try:
        parsed = parse_movie_caption(caption, file_name=file_name)
        if not parsed:
            logger.info("/auto skipped: could not parse metadata (source=%s, caption=%r, filename=%r)", source_chat_id, (caption or "")[:160], file_name)
            return None
        if not parsed.get("qualities"):
            logger.info("/auto skipped: no supported quality found (source=%s, title=%s)", source_chat_id, parsed.get("movie_name") or parsed.get("series_name"))
            return None
        if db is None:
            logger.error("/auto unavailable: database module did not initialize")
            return None

        settings = await db.get_auto_post_settings()
        if not settings.get("auto_index", False):
            logger.info("/auto skipped: auto_index is OFF (source=%s)", source_chat_id)
            return None
        target = settings.get("post_channel_id")
        if not target:
            logger.warning("/auto skipped: no post_channel_id is configured")
            return None

        if parsed.get("is_series") and not settings.get("series_enabled", True):
            logger.info("/auto skipped: series posting is disabled (source=%s)", source_chat_id)
            return None
        if not parsed.get("is_series") and not settings.get("movies_enabled", True):
            logger.info("/auto skipped: movie posting is disabled (source=%s)", source_chat_id)
            return None

        # Restrict auto-post input to configured index channels when configured.
        managed = set(await db.get_managed_channels())
        if managed and source_chat_id is not None:
            norm_src = normalize_channel_id(source_chat_id)
            if norm_src not in managed and source_chat_id not in managed:
                logger.info("/auto skipped: source channel %s is not in configured index channels %s", source_chat_id, sorted(managed))
                return None

        # Auto-post is intentionally triggered by any three distinct supported qualities.
        # Ignore older panel values so the threshold stays consistent.
        min_qualities = 3
        agg = db.config
        key = parsed["key"]
        doc_id = f"auto_post:{key}" if parsed.get("is_series") else f"auto_movie:{key}"

        # Captions sometimes append a truncated release word to the title
        # (e.g. "Donga Naa Koduku Cle" vs "Donga Naa Koduku"). Keep these
        # qualities together when the year matches and the only difference is
        # one short trailing token. This avoids splitting one film into two
        # independent aggregation documents.
        if not parsed.get("is_series") and parsed.get("year"):
            try:
                candidates = await agg.find({
                    "is_series": False,
                    "year": str(parsed["year"]),
                }).to_list(length=500)
                incoming_name = re.sub(r"\(\d{4}\)$", "", str(parsed.get("movie_name") or "")).strip()
                incoming_tokens = set(re.findall(r"[a-z0-9]+", incoming_name.lower()))
                best = None
                for candidate in candidates:
                    candidate_id = str(candidate.get("_id") or "")
                    if not candidate_id.startswith("auto_movie:") or candidate_id == doc_id:
                        continue
                    candidate_name = re.sub(r"\(\d{4}\)$", "", str(candidate.get("movie_name") or "")).strip()
                    candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate_name.lower()))
                    if not incoming_tokens or not candidate_tokens:
                        continue
                    extras = incoming_tokens ^ candidate_tokens
                    common = incoming_tokens & candidate_tokens
                    # Only tolerate one short extra token; do not merge titles
                    # that merely share a few common words.
                    if len(extras) > 1 or len(common) < 2 or any(len(t) > 4 for t in extras):
                        continue
                    score = SequenceMatcher(None, incoming_name.lower(), candidate_name.lower()).ratio()
                    if score >= 0.86 and (best is None or score > best[0]):
                        best = (score, candidate, candidate_id)
                if best:
                    _, matched_doc, matched_id = best
                    logger.info(
                        "/auto title matched existing aggregation: incoming=%r canonical=%r score=%.3f",
                        parsed.get("movie_name"), matched_doc.get("movie_name"), best[0]
                    )
                    doc_id = matched_id
                    key = matched_id.removeprefix("auto_movie:")
                    # Use the established display title to keep the output stable.
                    parsed["movie_name"] = matched_doc.get("movie_name") or parsed.get("movie_name")
                    parsed["key"] = key
            except Exception as match_exc:
                logger.warning("/auto fuzzy title matching unavailable; using exact title key: %s", match_exc)

        current = await agg.find_one({"_id": doc_id}) or {
            "qualities": [],
            "languages": [],
            "posted": False,
        }

        qualities = sort_qualities(set(current.get("qualities", [])) | set(parsed["qualities"]))
        logger.info("/auto aggregation: title=%s source=%s incoming=%s aggregate=%s target=%s", parsed.get("movie_name") or parsed.get("series_name"), source_chat_id, parsed.get("qualities"), qualities, target)
        # Preserve language order while merging
        merged_languages = list(current.get("languages", []))
        for lang in parsed["languages"]:
            if lang not in merged_languages:
                merged_languages.append(lang)

        doc_payload = {
            "is_series": bool(parsed.get("is_series")),
            "series_name": parsed.get("series_name") if parsed.get("is_series") else None,
            "movie_name": parsed.get("movie_name"),
            "season": parsed.get("season") if parsed.get("is_series") else None,
            "episode": parsed.get("episode") if parsed.get("is_series") else None,
            "year": parsed.get("year") if not parsed.get("is_series") else None,
            "duration": parsed.get("duration") or current.get("duration"),
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
            logger.info(
                "/auto already posted: title=%s target=%s message_id=%s qualities=%s",
                doc_payload.get("movie_name") or doc_payload.get("series_name"),
                target, posted_msg_id, qualities
            )
            if posted_msg_id and (
                set(qualities) != set(current.get("qualities", []))
                or set(merged_languages) != set(current.get("languages", []))
            ):
                try:
                    await api_request(bot, "editMessageText", {
                        "chat_id": int(target),
                        "message_id": int(posted_msg_id),
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                        "reply_markup": make_inline_keyboard(reply_markup),
                    })
                except Exception as edit_exc:
                    logger.warning("Auto-post edit failed for destination %s: %s", target, edit_exc)
            return {"posted": False, "already_posted": True, "qualities": qualities, "languages": merged_languages}

        if len(qualities) < min_qualities:
            logger.info("/auto waiting for qualities: %s/%s for %s (source=%s)", len(qualities), min_qualities, doc_payload.get("movie_name"), source_chat_id)
            return {"posted": False, "qualities": qualities, "languages": merged_languages}

        # Atomically claim posting to prevent duplicate posts from concurrent updates.
        claim = await agg.update_one(
            {"_id": doc_id, "posted": {"$ne": True}},
            {"$set": {"posted": True, "posted_at": datetime.now(timezone.utc)}},
        )
        if not claim.modified_count:
            return {"posted": False, "duplicate": True, "qualities": qualities}

        try:
            sent = await api_request(bot, "sendMessage", {
                "chat_id": int(target),
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": make_inline_keyboard(reply_markup),
            })
            if sent and sent.get("message_id"):
                await agg.update_one({"_id": doc_id}, {"$set": {"posted_msg_id": int(sent["message_id"])}})
                logger.info("/auto POSTED successfully: title=%s target=%s message_id=%s qualities=%s", doc_payload.get("movie_name"), target, sent.get("message_id"), qualities)
            else:
                await agg.update_one({"_id": doc_id}, {"$set": {"posted": False}, "$unset": {"posted_at": ""}})
                logger.error("/auto sendMessage returned no message_id; posting claim released (target=%s, title=%s)", target, doc_payload.get("movie_name"))
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
