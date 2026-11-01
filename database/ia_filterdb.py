# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

import re, base64, json, asyncio
from struct import pack
from pyrogram.file_id import FileId
from pymongo import MongoClient
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


def _make_file_document(media):
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_file_name(media.file_name)
    return {
        'file_id': file_id,
        'file_name': f"@TGBoxOffice {file_name}",
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }


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
            collections.append(collection)
    for node_id, uri, label, enabled in all_node_uris():
        key = (uri, DATABASE_NAME, COLLECTION_NAME)
        if key in seen:
            continue
        node_client = _NODE_CLIENTS.get(node_id)
        if node_client is None:
            node_client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
            _NODE_CLIENTS[node_id] = node_client
        collections.append(node_client[DATABASE_NAME][COLLECTION_NAME])
        seen.add(key)
    return collections

_NODE_CLIENTS = {}


def _save_documents_sync(documents):
    """Deduplicate globally, then distribute new documents across all active nodes."""
    if not documents:
        return 0, 0, 0
    all_collections = _unique_collections()
    enabled_ids = {node_id for node_id, _uri, _label in active_node_uris()}
    collections = [collection for collection in all_collections
                   if collection.database.client is client or collection.database.client is sec_client or any(
                       _NODE_CLIENTS.get(node_id) is collection.database.client and node_id in enabled_ids
                       for node_id, _uri, _label, _enabled in all_node_uris())]
    file_ids = list({item['file_id'] for item in documents})
    file_names = list({item['file_name'] for item in documents})
    existing_ids, existing_names = set(), set()
    for collection in all_collections:
        try:
            existing_ids.update(row['file_id'] for row in collection.find(
                {'file_id': {'$in': file_ids}}, {'file_id': 1}))
            existing_names.update(row['file_name'] for row in collection.find(
                {'file_name': {'$in': file_names}}, {'file_name': 1}))
        except Exception as exc:
            print(f"[MongoDB] Skipping unreachable node during duplicate check: {exc}")
    unique, seen_ids, seen_names = [], set(), set()
    duplicates = 0
    for item in documents:
        fid, fname = item['file_id'], item['file_name']
        if fid in existing_ids or fname in existing_names or fid in seen_ids or fname in seen_names:
            duplicates += 1
            continue
        seen_ids.add(fid); seen_names.add(fname); unique.append(item)
    if not unique:
        return 0, duplicates, 0
    if not collections:
        return 0, duplicates, len(unique)

    # Round-robin distribution guarantees every enabled MongoDB receives work.
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
                # A node may be temporarily unreachable; retry this batch on
                # other enabled stores rather than losing the index operation.
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
            total += collection.count_documents({})
        except Exception as exc:
            print(f"[MongoDB] Count skipped an unreachable node: {exc}")
    return total


def delete_file_everywhere(criteria, many=False):
    deleted = 0
    for collection in _unique_collections():
        try:
            result = collection.delete_many(criteria) if many else collection.delete_one(criteria)
            deleted += result.deleted_count
        except Exception as exc:
            print(f"[MongoDB] Delete skipped an unreachable node: {exc}")
    return deleted


def drop_all_file_collections():
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
    """Clean and format the file name."""
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(file_name)) 
    unwanted_chars = ['[', ']', '(', ')', '{', '}']
    
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')
        
    old_file_name = ' '.join(filter(lambda x: not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me'), file_name.split()))
    new_file_name = add_space_between_e_and_number(old_file_name)
    return new_file_name

def add_space_between_e_and_number(input_string):
    # Use regex to find 'e' or 'E' followed by a digit and add a space
    output_string = re.sub(r'(e|E)([0-9])', r'\1 \2', input_string)
    return output_string
    
def is_file_already_saved(file_id, file_name):
    """Check if the file is already saved in either collection."""
    found1 = {'file_name': file_name}
    found = {'file_id': file_id}

    for collection in _unique_collections():
        if collection.find_one(found1) or collection.find_one(found):
            print(f"{file_name} is already saved.")
            return True
            
    return False

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """Search all active file databases and paginate the merged results."""
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except Exception:
        regex = query
    criteria = {'file_name': regex}
    collections = _unique_collections()
    total_results = 0
    files = []
    fetch_limit = offset + max_results
    for collection in collections:
        try:
            total_results += collection.count_documents(criteria)
            files.extend(list(collection.find(criteria).sort('$natural', -1).limit(fetch_limit)))
        except Exception as exc:
            print(f"[MongoDB] Search skipped an unreachable node: {exc}")
    files.sort(key=lambda item: item.get('_id'), reverse=True)
    page = files[offset:offset + max_results]
    next_offset = '' if offset + max_results >= total_results else offset + max_results
    return page, next_offset, total_results

async def get_bad_files(query, file_type=None, use_filter=False):
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = rf'(\b|[.+-_]){query}(\b|[.+-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s.+-_]')
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        return [], 0
    filter_criteria = {'file_name': regex}
    if USE_CAPTION_FILTER:
        filter_criteria = {'$or': [filter_criteria, {'caption': regex}]}
    collections = _unique_collections()
    total_results = 0
    files = []
    for collection in collections:
        try:
            total_results += collection.count_documents(filter_criteria)
            files.extend(list(collection.find(filter_criteria)))
        except Exception as exc:
            print(f"[MongoDB] Bad-file search skipped an unreachable node: {exc}")
    return files, total_results

async def get_file_details(query):
    for collection in _unique_collections():
        try:
            result = collection.find_one({'file_id': query})
            if result:
                return result
        except Exception as exc:
            print(f"[MongoDB] File lookup skipped an unreachable node: {exc}")
    return None

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
    

