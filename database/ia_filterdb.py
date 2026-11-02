# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import re
import base64
import json
import asyncio
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from struct import pack
from pyrogram.file_id import FileId
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER, MAX_B_TN
from database.mongo_nodes import active_node_uris, all_node_uris

# First Database For File Saving
client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

# Second Database For File Saving
sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]

_GENERIC_NAME_RE = re.compile(
    r"^(?:video|audio|document|media|file|mp4|mkv|avi|mov|flv|webm|mp3|aac|flac|wav|ogg|m4a|\d+|\s)+$",
    re.IGNORECASE,
)

_NODE_CLIENTS = {}
_INDEXED_COLLECTIONS = set()
_SEARCH_EXECUTOR = ThreadPoolExecutor(max_workers=8)

# Fast in-memory LRU cache for file details so button clicks resolve instantly
_FILE_DETAILS_CACHE = OrderedDict()
_FILE_CACHE_MAX = 4000


def _cache_file_doc(doc):
    if not doc or not isinstance(doc, dict):
        return
    fid = doc.get("file_id")
    if not fid:
        return
    _FILE_DETAILS_CACHE[fid] = doc
    _FILE_DETAILS_CACHE.move_to_end(fid)
    while len(_FILE_DETAILS_CACHE) > _FILE_CACHE_MAX:
        _FILE_DETAILS_CACHE.popitem(last=False)


def _ensure_collection_indexes(collection):
    coll_id = id(collection)
    if coll_id in _INDEXED_COLLECTIONS:
        return
    _INDEXED_COLLECTIONS.add(coll_id)
    try:
        collection.create_index([("file_id", ASCENDING)], background=True)
        collection.create_index([("file_name", ASCENDING)], background=True)
    except Exception:
        pass


def _extract_caption_text(caption_obj):
    """Preserve the original plain caption text without modifying it."""
    if not caption_obj:
        return None
    text = str(caption_obj)
    return text if text.strip() else None


def _make_file_document(media):
    """Use file captions and filenames for rich movie/series metadata indexing."""
    file_id = unpack_new_file_id(media.file_id)
    raw_caption = _extract_caption_text(getattr(media, 'caption', None))
    raw_file_name = getattr(media, 'file_name', None)

    caption_index_name = ""
    if raw_caption or raw_file_name:
        try:
            from TechVJ.util.auto_post import parse_movie_caption
            parsed = parse_movie_caption(raw_caption, file_name=raw_file_name)
            if parsed and parsed.get("search_index_name"):
                caption_index_name = clean_file_name(parsed["search_index_name"])
        except Exception:
            pass
        if not caption_index_name and raw_caption:
            first_line = next((line.strip() for line in raw_caption.splitlines() if line.strip()), "")
            if first_line:
                caption_index_name = clean_file_name(first_line[:200])

    cleaned_file_name = clean_file_name(raw_file_name) if raw_file_name else ""

    if caption_index_name and not _GENERIC_NAME_RE.match(caption_index_name):
        if cleaned_file_name and not _GENERIC_NAME_RE.match(cleaned_file_name):
            # Combine any extra tokens from cleaned_file_name that aren't already in caption_index_name
            existing_lower = set(caption_index_name.lower().split())
            extra = [t for t in cleaned_file_name.split() if t.lower() not in existing_lower]
            merged = f"{caption_index_name} {' '.join(extra)}".strip() if extra else caption_index_name
            file_name = merged[:240]
        else:
            file_name = caption_index_name
    elif cleaned_file_name and not _GENERIC_NAME_RE.match(cleaned_file_name):
        file_name = cleaned_file_name
    else:
        file_name = caption_index_name or cleaned_file_name or f"media {file_id[:12]}"

    doc = {
        'file_id': file_id,
        'file_name': f"@MoviesZoneFlix {file_name}",
        'file_size': getattr(media, 'file_size', 0) or 0,
        'caption': raw_caption
    }
    _cache_file_doc(doc)
    return doc


def _unique_collections():
    """Return every registered file collection, including disabled nodes for reads."""
    collections = []
    seen = set()
    for uri, collection in ((FILE_DB_URI, col), (SEC_FILE_DB_URI, sec_col)):
        if not uri:
            continue
        key = (uri, DATABASE_NAME, COLLECTION_NAME)
        if key not in seen:
            seen.add(key)
            _ensure_collection_indexes(collection)
            collections.append(collection)
    for node_id, uri, label, enabled in all_node_uris():
        key = (uri, DATABASE_NAME, COLLECTION_NAME)
        if key in seen:
            continue
        node_client = _NODE_CLIENTS.get(node_id)
        if node_client is None:
            node_client = MongoClient(uri, serverSelectionTimeoutMS=6000, connectTimeoutMS=6000)
            _NODE_CLIENTS[node_id] = node_client
        node_col = node_client[DATABASE_NAME][COLLECTION_NAME]
        _ensure_collection_indexes(node_col)
        collections.append(node_col)
        seen.add(key)
    return collections


def _save_documents_sync(documents):
    """Deduplicate globally, then distribute new documents across all active nodes."""
    if not documents:
        return 0, 0, 0
    all_collections = _unique_collections()
    enabled_ids = {node_id for node_id, _uri, _label in active_node_uris()}
    collections = [
        collection for collection in all_collections
        if collection.database.client is client
        or collection.database.client is sec_client
        or any(
            _NODE_CLIENTS.get(node_id) is collection.database.client and node_id in enabled_ids
            for node_id, _uri, _label, _enabled in all_node_uris()
        )
    ]
    file_ids = list({item['file_id'] for item in documents})
    file_names = list({item['file_name'] for item in documents})
    existing_ids, existing_name_sizes = set(), set()
    for collection in all_collections:
        try:
            existing_ids.update(
                row['file_id'] for row in collection.find(
                    {'file_id': {'$in': file_ids}}, {'file_id': 1}
                )
            )
            existing_name_sizes.update(
                (row.get('file_name'), row.get('file_size'))
                for row in collection.find({'file_name': {'$in': file_names}}, {'file_name': 1, 'file_size': 1})
                if row.get('file_size')
            )
        except Exception as exc:
            print(f"[MongoDB] Skipping unreachable node during duplicate check: {exc}")
    unique, seen_ids, seen_name_sizes = [], set(), set()
    duplicates = 0
    for item in documents:
        fid, fname, fsize = item['file_id'], item['file_name'], item.get('file_size')
        name_size = (fname, fsize) if fsize else None
        if fid in existing_ids or fid in seen_ids or (name_size and (name_size in existing_name_sizes or name_size in seen_name_sizes)):
            duplicates += 1
            continue
        seen_ids.add(fid)
        if name_size:
            seen_name_sizes.add(name_size)
        unique.append(item)
    if not unique:
        return 0, duplicates, 0
    if not collections:
        return 0, duplicates, len(unique)

    buckets = [[] for _ in collections]
    for index, item in enumerate(unique):
        buckets[index % len(collections)].append(item)
    saved = failures = 0
    for target_index, batch in enumerate(buckets):
        if not batch:
            continue
        try:
            result = collections[target_index].insert_many(batch, ordered=False)
            saved += len(result.inserted_ids)
        except Exception as exc:
            details = getattr(exc, 'details', {}) or {}
            failed_indices = {entry.get('index') for entry in details.get('writeErrors', [])}
            if details:
                saved += max(0, len(batch) - len(failed_indices))
                failures += len(failed_indices)
            else:
                remaining = batch
                for fallback_index in range(len(collections)):
                    if fallback_index == target_index or not remaining:
                        continue
                    try:
                        result = collections[fallback_index].insert_many(remaining, ordered=False)
                        saved += len(result.inserted_ids)
                        remaining = []
                    except Exception as fallback_exc:
                        fallback_details = getattr(fallback_exc, 'details', {}) or {}
                        if fallback_details:
                            failed = {entry.get('index') for entry in fallback_details.get('writeErrors', [])}
                            saved += max(0, len(remaining) - len(failed))
                            remaining = [doc for i, doc in enumerate(remaining) if i in failed]
                failures += len(remaining)
    return saved, duplicates, failures


def get_file_collections():
    return _unique_collections()


def count_all_file_documents():
    total = 0
    for collection in _unique_collections():
        try:
            total += collection.estimated_document_count()
        except Exception:
            try:
                total += collection.count_documents({})
            except Exception as exc:
                print(f"[MongoDB] Count skipped an unreachable node: {exc}")
    return total


def delete_file_everywhere(criteria, many=False):
    deleted = 0
    if isinstance(criteria, dict) and "file_id" in criteria:
        _FILE_DETAILS_CACHE.pop(criteria["file_id"], None)
    else:
        _FILE_DETAILS_CACHE.clear()
    for collection in _unique_collections():
        try:
            result = collection.delete_many(criteria) if many else collection.delete_one(criteria)
            deleted += result.deleted_count
        except Exception as exc:
            print(f"[MongoDB] Delete skipped an unreachable node: {exc}")
    return deleted


def drop_all_file_collections():
    _FILE_DETAILS_CACHE.clear()
    dropped = failed = 0
    for collection in _unique_collections():
        try:
            collection.drop()
            dropped += 1
        except Exception as exc:
            failed += 1
            print(f"[MongoDB] Could not clear an unreachable file store: {exc}")
    return dropped, failed


async def save_files_batch(media_items):
    """Save multiple Telegram media objects with batched MongoDB operations."""
    docs, invalid = [], 0
    for media in media_items:
        if not media or not getattr(media, 'file_id', None):
            invalid += 1
            continue
        try:
            docs.append(_make_file_document(media))
        except Exception:
            invalid += 1
    if not docs:
        return 0, 0, invalid
    saved, duplicates, failed = await asyncio.to_thread(_save_documents_sync, docs)
    return saved, duplicates, failed + invalid


async def save_file(media):
    """Backward-compatible single-file save API."""
    try:
        saved, duplicates, errors = await save_files_batch([media])
    except Exception:
        return False, 2
    if saved:
        return True, 1
    if duplicates:
        return False, 0
    return False, 2 if errors else 0


def clean_file_name(file_name):
    """Clean and format the file name while ignoring underscores and special separators."""
    if not file_name:
        return ""
    raw = str(file_name)
    raw = re.sub(r"https?://\S+|www\.\S+|t\.me/\S+", " ", raw)
    raw = re.sub(r"\.(?:mkv|mp4|avi|mov|webm|flv|m4v|ts|mp3|aac|flac)\b", " ", raw, flags=re.I)
    cleaned = re.sub(r"[_\-\.\+＿]+", " ", raw)
    for char in ('[', ']', '(', ')', '{', '}'):
        cleaned = cleaned.replace(char, ' ')
    tokens = cleaned.split()
    filtered_tokens = [
        x for x in tokens
        if not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me')
    ]
    if not filtered_tokens and tokens:
        filtered_tokens = [x.lstrip('@') for x in tokens if x.lstrip('@')]
    old_file_name = ' '.join(filtered_tokens)
    new_file_name = add_space_between_e_and_number(old_file_name)
    return re.sub(r"\s+", " ", new_file_name).strip()


def add_space_between_e_and_number(input_string):
    # Preserve S01E01 while also allowing space-separated matching
    return input_string


def is_file_already_saved(file_id, file_name):
    """Check if the file is already saved in any collection."""
    if file_id in _FILE_DETAILS_CACHE:
        return True
    found1 = {'file_name': file_name}
    found = {'file_id': file_id}
    for collection in _unique_collections():
        if collection.find_one(found1) or collection.find_one(found):
            return True
    return False


_LANG_SHORT_MAP = {
    "tel": "(?:telugu|tel)",
    "telugu": "(?:telugu|tel)",
    "tam": "(?:tamil|tam)",
    "tamil": "(?:tamil|tam)",
    "hin": "(?:hindi|hin)",
    "hindi": "(?:hindi|hin)",
    "mal": "(?:malayalam|mal)",
    "malayalam": "(?:malayalam|mal)",
    "kan": "(?:kannada|kan)",
    "kannada": "(?:kannada|kan)",
    "eng": "(?:english|eng)",
    "english": "(?:english|eng)",
    "ben": "(?:bengali|bangla|ben)",
    "bengali": "(?:bengali|bangla|ben)",
    "mar": "(?:marathi|mar)",
    "marathi": "(?:marathi|mar)",
    "pun": "(?:punjabi|pun)",
    "punjabi": "(?:punjabi|pun)",
    "guj": "(?:gujarati|guj)",
    "gujarati": "(?:gujarati|guj)",
    "kor": "(?:korean|kor)",
    "korean": "(?:korean|kor)",
    "jap": "(?:japanese|jap|jpn)",
    "japanese": "(?:japanese|jap|jpn)",
}


def _build_search_regex(query: str, relax_year: bool = False):
    """Build a smart regex that matches across spaces/underscores/dots and handles Season/Episode/Language aliases."""
    normalized = re.sub(r"[_\-\.\+:＿]+", " ", str(query or "")).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return re.compile(r".", flags=re.IGNORECASE)

    # Combine "season <num>" and "episode <num>" into single tokens before splitting
    normalized = re.sub(r"(?i)\bseason\s+(\d{1,3})\b", r"__SEASON_\1__", normalized)
    normalized = re.sub(r"(?i)\b(?:episode|ep)\s+(\d{1,4})\b", r"__EPISODE_\1__", normalized)

    words = normalized.split(" ")
    escaped_words = []
    for w in words:
        w_low = w.lower()
        m_seas = re.fullmatch(r"__season_(\d+)__|s0*(\d{1,2})", w_low)
        if m_seas:
            s_num = int(m_seas.group(1) or m_seas.group(2))
            escaped_words.append(rf"(?:season\s*[:=\-\._\s]*0*{s_num}\b|s0*{s_num}(?:\b|e|\s|_|\.))")
            continue
        m_ep = re.fullmatch(r"__episode_(\d+)__|e(?:p)?0*(\d{1,4})", w_low)
        if m_ep:
            e_num = int(m_ep.group(1) or m_ep.group(2))
            escaped_words.append(rf"(?:(?:episode|ep\.?)\s*[:=\-\._\s]*0*{e_num}\b|e0*{e_num}\b)")
            continue
        m_se_both = re.fullmatch(r"s0*(\d{1,2})e(?:p)?0*(\d{1,4})", w_low)
        if m_se_both:
            s_num, e_num = int(m_se_both.group(1)), int(m_se_both.group(2))
            escaped_words.append(
                rf"(?:s0*{s_num}\s*[\.\-_\s]*e(?:p)?\s*0*{e_num}\b|season\s*[:=\-\._\s]*0*{s_num}.*(?:episode|ep|e)\s*[:=\-\._\s]*0*{e_num}\b)"
            )
            continue
        if w_low in _LANG_SHORT_MAP:
            escaped_words.append(_LANG_SHORT_MAP[w_low] + r"\b")
            continue
        if relax_year and re.fullmatch(r"(?:19|20)\d{2}", w):
            escaped_words.append(re.escape(w[:3]) + r"\d?")
        else:
            escaped_words.append(re.escape(w))

    if len(escaped_words) == 1:
        raw_pattern = r"(?:\b|[\.\+\-_])" + escaped_words[0]
    else:
        raw_pattern = r".*".join(escaped_words)
    return re.compile(raw_pattern, flags=re.IGNORECASE | re.DOTALL)


def _query_single_collection(collection, criteria, fetch_limit):
    try:
        total = collection.count_documents(criteria)
        if total == 0:
            return [], 0
        cursor = collection.find(criteria).sort('$natural', -1)
        if fetch_limit is not None:
            cursor = cursor.limit(fetch_limit)
        docs = list(cursor)
        return docs, total
    except Exception as exc:
        print(f"[MongoDB] Search skipped an unreachable node: {exc}")
        return [], 0


def _execute_search_collections(collections, criteria, fetch_limit=None):
    if not collections:
        return [], 0
    if len(collections) == 1:
        docs, total = _query_single_collection(collections[0], criteria, fetch_limit)
        for d in docs:
            _cache_file_doc(d)
        return docs, total

    futures = [
        _SEARCH_EXECUTOR.submit(_query_single_collection, col_obj, criteria, fetch_limit)
        for col_obj in collections
    ]
    total_results = 0
    files = []
    for fut in futures:
        docs, total = fut.result()
        total_results += total
        for d in docs:
            _cache_file_doc(d)
        files.extend(docs)
    return files, total_results


async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """Search all active file databases in parallel threads without blocking the event loop."""
    query = str(query or "").strip()
    try:
        regex = _build_search_regex(query, relax_year=False)
    except Exception:
        regex = re.compile(re.escape(query), flags=re.IGNORECASE)

    criteria = {'$or': [{'file_name': regex}, {'caption': regex}]} if USE_CAPTION_FILTER else {'file_name': regex}
    collections = _unique_collections()
    fetch_limit = offset + max_results
    files, total_results = await asyncio.to_thread(_execute_search_collections, collections, criteria, fetch_limit)

    if total_results == 0 and re.search(r"\b(?:19|20)\d{2}\b", re.sub(r"[_\-\.\+]+", " ", query)):
        try:
            relaxed_regex = _build_search_regex(query, relax_year=True)
            relaxed_criteria = {'$or': [{'file_name': relaxed_regex}, {'caption': relaxed_regex}]} if USE_CAPTION_FILTER else {'file_name': relaxed_regex}
            files, total_results = await asyncio.to_thread(_execute_search_collections, collections, relaxed_criteria, fetch_limit)
        except Exception:
            pass

    files.sort(key=lambda item: item.get('_id'), reverse=True)
    page = files[offset:offset + max_results]
    next_offset = '' if offset + max_results >= total_results else offset + max_results
    return page, next_offset, total_results


async def get_bad_files(query, file_type=None, use_filter=False):
    query = str(query or "").strip()
    try:
        regex = _build_search_regex(query, relax_year=False)
    except re.error:
        return [], 0
    filter_criteria = {'$or': [{'file_name': regex}, {'caption': regex}]} if USE_CAPTION_FILTER else {'file_name': regex}
    collections = _unique_collections()
    files, total_results = await asyncio.to_thread(_execute_search_collections, collections, filter_criteria, None)
    return files, total_results


def _find_file_sync(query):
    for collection in _unique_collections():
        try:
            result = collection.find_one({'file_id': query})
            if result:
                return result
        except Exception as exc:
            print(f"[MongoDB] File lookup skipped an unreachable node: {exc}")
    return None


async def get_file_details(query):
    cached = _FILE_DETAILS_CACHE.get(query)
    if cached is not None:
        _FILE_DETAILS_CACHE.move_to_end(query)
        return cached
    result = await asyncio.to_thread(_find_file_sync, query)
    if result:
        _cache_file_doc(result)
    return result


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Return file_id"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id
