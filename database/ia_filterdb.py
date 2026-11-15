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
        collection.create_index([("source_chat_id", ASCENDING), ("source_message_id", ASCENDING)], background=True)
        collection.create_index([("source_refs.chat_id", ASCENDING), ("source_refs.message_id", ASCENDING)], background=True)
        collection.create_index([("source_chat_id", ASCENDING), ("source_message_id", ASCENDING)], background=True)
        collection.create_index([("source_refs.chat_id", ASCENDING), ("source_refs.message_id", ASCENDING)], background=True)
    except Exception:
        pass


def _extract_caption_text(caption_obj):
    """Preserve the original plain caption text without modifying it."""
    if not caption_obj:
        return None
    text = str(caption_obj)
    return text if text.strip() else None


def _make_file_document(media, source_chat_id=None, source_message_id=None):
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
        'caption': raw_caption,
        'source_chat_id': int(source_chat_id) if source_chat_id is not None else None,
        'source_message_id': int(source_message_id) if source_message_id is not None else None,
        'source_refs': ([{
            'chat_id': int(source_chat_id),
            'message_id': int(source_message_id),
        }] if source_chat_id is not None and source_message_id is not None else []),
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
            refs = item.get("source_refs") or []
            # Refresh existing records when the same file is indexed again.
            identity = {"file_id": fid} if fid in existing_ids else ({"file_name": fname, "file_size": fsize} if name_size else {"file_id": fid})
            for collection in all_collections:
                try:
                    update = {"$set": {
                        "file_name": fname,
                        "file_size": fsize,
                        "caption": item.get("caption"),
                    }}
                    if refs:
                        update["$addToSet"] = {"source_refs": {"$each": refs}}
                        update["$set"]["source_chat_id"] = refs[-1].get("chat_id")
                        update["$set"]["source_message_id"] = refs[-1].get("message_id")
                    collection.update_many(identity, update)
                except Exception as exc:
                    print(f"[MongoDB] Could not refresh existing indexed file {fid[:12]}: {exc}")
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


def delete_files_by_source_message(chat_id, message_id):
    """Remove a deleted source reference and delete records with no remaining known sources."""
    ref = {"chat_id": int(chat_id), "message_id": int(message_id)}
    deleted = 0
    for collection in _unique_collections():
        try:
            collection.update_many(
                {"source_refs": ref},
                {"$set": {"_source_cleanup_candidate": True},
                 "$pull": {"source_refs": ref}}
            )
            result = collection.delete_many({
                "_source_cleanup_candidate": True,
                "source_refs": {"$size": 0},
            })
            deleted += result.deleted_count
            collection.update_many(
                {"_source_cleanup_candidate": True},
                {"$unset": {"_source_cleanup_candidate": ""}}
            )
            # Backward-compatible cleanup for records created before source_refs existed.
            result = collection.delete_many({
                "source_chat_id": int(chat_id),
                "source_message_id": int(message_id),
                "source_refs": {"$exists": False},
            })
            deleted += result.deleted_count
        except Exception as exc:
            print(f"[MongoDB] Could not clean deleted source message {chat_id}/{message_id}: {exc}")
    _FILE_DETAILS_CACHE.clear()
    return deleted


def prepare_source_range_for_reindex(chat_id, first_message_id, last_message_id):
    """Remove stale references for a range before re-indexing that source range.

    Records referenced by other channels are retained. Legacy records without
    source_refs are removed only when their original source falls in this range.
    """
    chat_id = int(chat_id)
    first_message_id = int(first_message_id)
    last_message_id = int(last_message_id)
    removed = 0
    for collection in _unique_collections():
        try:
            criteria = {"source_refs": {"$elemMatch": {
                "chat_id": chat_id,
                "message_id": {"$gte": first_message_id, "$lte": last_message_id},
            }}}
            collection.update_many(
                criteria,
                {"$set": {"_reindex_cleanup_candidate": True},
                 "$pull": {"source_refs": {
                     "chat_id": chat_id,
                     "message_id": {"$gte": first_message_id, "$lte": last_message_id},
                 }}},
            )
            result = collection.delete_many({
                "_reindex_cleanup_candidate": True,
                "source_refs": {"$size": 0},
            })
            removed += result.deleted_count
            collection.update_many(
                {"_reindex_cleanup_candidate": True},
                {"$unset": {"_reindex_cleanup_candidate": ""}},
            )
            legacy = collection.delete_many({
                "source_chat_id": chat_id,
                "source_message_id": {"$gte": first_message_id, "$lte": last_message_id},
                "source_refs": {"$exists": False},
            })
            removed += legacy.deleted_count
        except Exception as exc:
            print(f"[MongoDB] Re-index cleanup skipped a file store: {exc}")
            raise
    _FILE_DETAILS_CACHE.clear()
    return removed


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


async def save_files_batch(media_items, source_chat_id=None, source_message_id=None):
    """Save multiple Telegram media objects with batched MongoDB operations."""
    docs, invalid = [], 0
    for item in media_items:
        media = item
        item_chat_id, item_message_id = source_chat_id, source_message_id
        if isinstance(item, (tuple, list)) and len(item) == 3:
            media, item_chat_id, item_message_id = item
        if not media or not getattr(media, 'file_id', None):
            invalid += 1
            continue
        try:
            docs.append(_make_file_document(media, item_chat_id, item_message_id))
        except Exception:
            invalid += 1
    if not docs:
        return 0, 0, invalid
    saved, duplicates, failed = await asyncio.to_thread(_save_documents_sync, docs)
    return saved, duplicates, failed + invalid


async def save_file(media, source_chat_id=None, source_message_id=None):
    """Backward-compatible single-file save API."""
    try:
        saved, duplicates, errors = await save_files_batch([media], source_chat_id, source_message_id)
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
    "kor": "(?:korean|kor|한국어|조선말)",
    "korean": "(?:korean|kor|한국어|조선말)",
    "jap": "(?:japanese|jap|jpn|日本語)",
    "japanese": "(?:japanese|jap|jpn|日本語)",
    "hindi": "(?:hindi|hin|हिन्दी|हिंदी)", "hin": "(?:hindi|hin|हिन्दी|हिंदी)",
    "telugu": "(?:telugu|tel|తెలుగు)", "tel": "(?:telugu|tel|తెలుగు)",
    "tamil": "(?:tamil|tam|தமிழ்)", "tam": "(?:tamil|tam|தமிழ்)",
    "malayalam": "(?:malayalam|mal|മലയാളം)", "mal": "(?:malayalam|mal|മലയാളം)",
    "kannada": "(?:kannada|kan|ಕನ್ನಡ)", "kan": "(?:kannada|kan|ಕನ್ನಡ)",
    "bengali": "(?:bengali|bangla|ben|বাংলা)", "bangla": "(?:bengali|bangla|ben|বাংলা)",
    "english": "(?:english|eng)", "eng": "(?:english|eng)",
    "marathi": "(?:marathi|mar|मराठी)", "mar": "(?:marathi|mar|मराठी)",
    "punjabi": "(?:punjabi|pun|ਪੰਜਾਬੀ)", "gujarati": "(?:gujarati|guj|ગુજરાતી)",
    "arabic": "(?:arabic|ara|العربية)", "russian": "(?:russian|rus|русский)",
    "french": "(?:french|fra|français)", "spanish": "(?:spanish|spa|español)",
    "chinese": "(?:chinese|chi|中文|汉语|普通话)",
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
            escaped_words.append(rf"(?:season\s*[:=\-\._\s]*0*{s_num}(?![A-Za-z0-9])|s0*{s_num}(?:\b|e|\s|_|\.))")
            continue
        m_ep = re.fullmatch(r"__episode_(\d+)__|e(?:p)?0*(\d{1,4})", w_low)
        if m_ep:
            e_num = int(m_ep.group(1) or m_ep.group(2))
            escaped_words.append(rf"(?:(?:episode|ep\.?)\s*[:=\-\._\s]*0*{e_num}(?![A-Za-z0-9])|e0*{e_num}(?![A-Za-z0-9]))")
            continue
        m_se_both = re.fullmatch(r"s0*(\d{1,2})e(?:p)?0*(\d{1,4})", w_low)
        if m_se_both:
            s_num, e_num = int(m_se_both.group(1)), int(m_se_both.group(2))
            escaped_words.append(
                rf"(?:s0*{s_num}\s*[\.\-_\s]*e(?:p)?\s*0*{e_num}(?![A-Za-z0-9])|season\s*[:=\-\._\s]*0*{s_num}.*(?:episode|ep|e)\s*[:=\-\._\s]*0*{e_num}(?![A-Za-z0-9]))"
            )
            continue
        m_se_x = re.fullmatch(r"(\d{1,2})x0*(\d{1,4})", w_low)
        if m_se_x:
            s_num, e_num = int(m_se_x.group(1)), int(m_se_x.group(2))
            escaped_words.append(rf"(?:0*{s_num}x0*{e_num}(?![A-Za-z0-9])|season\s*0*{s_num}.*(?:episode|ep)\s*0*{e_num}(?![A-Za-z0-9]))")
            continue
        if w_low in _LANG_SHORT_MAP:
            escaped_words.append(r"(?<![A-Za-z0-9])" + _LANG_SHORT_MAP[w_low] + r"(?![A-Za-z0-9])")
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


def _query_fallbacks(query):
    """Return progressively broader but still meaningful title/metadata combinations."""
    normalized = re.sub(r"[_\-\.+:＿]+", " ", str(query or ""))
    tokens = re.findall(r"[\w]+", normalized, flags=re.UNICODE)
    if len(tokens) <= 1:
        return []
    # Keep year, language, Sxx and Exx tokens in the candidate pool; try all
    # triples, then pairs, then single terms, preserving original order.
    import itertools
    candidates = []
    for size in (3, 2, 1):
        if len(tokens) < size:
            continue
        for combo in itertools.combinations(tokens, size):
            candidate = " ".join(combo)
            if candidate.lower() not in {query.lower(), *(x.lower() for x in candidates)}:
                candidates.append(candidate)
    return candidates


def _progressive_query_candidates(query):
    """Search full query first, then bounded 3-, 2-, and 1-term combinations.

    Each fallback tier gets its own budget so long queries cannot consume the
    entire search budget with triples and prevent pair/single-token fallbacks.
    Metadata terms (year, language, season, episode) are prioritized per tier.
    """
    from itertools import combinations
    normalized = re.sub(r"[_\-\.+:＿]+", " ", str(query or "")).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return []
    normalized = re.sub(r"(?i)\bseason\s*0*(\d{1,2})\b", r"season_\1", normalized)
    normalized = re.sub(r"(?i)\b(?:episode|ep)\s*0*(\d{1,4})\b", r"episode_\1", normalized)
    tokens = normalized.split()
    candidates = [normalized.replace("season_", "season ").replace("episode_", "episode ")]
    metadata_token = re.compile(
        r"(?i)(?:19|20)\d{2}|season_?\d|episode_?\d|s\d{1,2}e(?:p)?\d{1,4}|"
        r"\d{1,2}x\d{1,4}|telugu|tamil|hindi|malayalam|kannada|english|bengali|"
        r"japanese|korean|marathi|punjabi|gujarati|arabic|russian|french|spanish|"
        r"german|italian|portuguese|turkish|indonesian|thai|vietnamese|urdu|"
        r"हिंदी|हिन्दी|தமிழ்|తెలుగు|മലയാളം|ಕನ್ನಡ|বাংলা|日本語|한국어|中文|اردو"
    )
    tier_budgets = {3: 24, 2: 24, 1: 20}
    for size in (3, 2, 1):
        if len(tokens) < size:
            continue
        groups = list(combinations(tokens, size))
        metadata_groups = [group for group in groups if any(metadata_token.search(token) for token in group)]
        ordered_groups = metadata_groups + [group for group in groups if group not in metadata_groups]
        added = 0
        for group in ordered_groups:
            candidate = " ".join(group).replace("season_", "season ").replace("episode_", "episode ")
            if candidate not in candidates:
                candidates.append(candidate)
                added += 1
            if added >= tier_budgets[size]:
                break
    return candidates


async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """Search exact query first, then progressively relax to 3/2/1 terms."""
    query = str(query or "").strip()
    collections = _unique_collections()
    fetch_limit = offset + max_results
    files, total_results = [], 0
    for candidate in _progressive_query_candidates(query):
        try:
            regex = _build_search_regex(candidate, relax_year=False)
        except Exception:
            regex = re.compile(re.escape(candidate), flags=re.IGNORECASE)
        criteria = {'$or': [{'file_name': regex}, {'caption': regex}]} if USE_CAPTION_FILTER else {'file_name': regex}
        files, total_results = await asyncio.to_thread(_execute_search_collections, collections, criteria, fetch_limit)
        if total_results:
            break
        if re.search(r"\b(?:19|20)\d{2}\b", candidate):
            try:
                relaxed_regex = _build_search_regex(candidate, relax_year=True)
                relaxed_criteria = {'$or': [{'file_name': relaxed_regex}, {'caption': relaxed_regex}]} if USE_CAPTION_FILTER else {'file_name': relaxed_regex}
                files, total_results = await asyncio.to_thread(_execute_search_collections, collections, relaxed_criteria, fetch_limit)
                if total_results:
                    break
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
