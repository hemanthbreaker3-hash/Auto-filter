"""Persistent manager for additional MongoDB file-storage nodes."""
from datetime import datetime, timezone
import uuid
from pymongo import MongoClient
from info import OTHER_DB_URI, DATABASE_NAME, FILE_DB_URI, SEC_FILE_DB_URI

_registry_client = MongoClient(OTHER_DB_URI, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
_registry = _registry_client[DATABASE_NAME]["managed_file_mongo_nodes"]


def _normal_uri(uri):
    uri = str(uri or "").strip()
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("Mongo URI must start with mongodb:// or mongodb+srv://")
    if len(uri) > 2048 or any(ch.isspace() for ch in uri):
        raise ValueError("Invalid MongoDB URI format.")
    return uri


def list_nodes(include_disabled=True):
    query = {} if include_disabled else {"enabled": True}
    return list(_registry.find(query).sort("created_at", 1))


def add_node(uri, label=None):
    uri = _normal_uri(uri)
    if uri in {FILE_DB_URI, SEC_FILE_DB_URI, OTHER_DB_URI}:
        raise ValueError("This URI is already configured as a built-in database.")
    existing = _registry.find_one({"uri": uri})
    if existing:
        raise ValueError("This MongoDB URI is already registered.")
    test_client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    try:
        test_client.admin.command("ping")
    finally:
        test_client.close()
    node_id = uuid.uuid4().hex[:10]
    _registry.insert_one({"_id": node_id, "uri": uri, "label": (label or f"Mongo #{node_id}")[:64],
                          "enabled": True, "created_at": datetime.now(timezone.utc)})
    return node_id


def set_node_enabled(node_id, enabled):
    result = _registry.update_one({"_id": str(node_id)}, {"$set": {"enabled": bool(enabled)}})
    return bool(result.modified_count or result.matched_count)


def remove_node(node_id):
    return bool(_registry.delete_one({"_id": str(node_id)}).deleted_count)


def all_node_uris():
    return [(str(row["_id"]), row["uri"], row.get("label") or f"Mongo #{row['_id']}", bool(row.get("enabled", True)))
            for row in list_nodes(True)]


def active_node_uris():
    return [(node_id, uri, label) for node_id, uri, label, enabled in all_node_uris() if enabled]


def mask_uri(uri):
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(uri)
        if "@" in parts.netloc:
            host = parts.netloc.rsplit("@", 1)[1]
            return urlunsplit((parts.scheme, f"•••@{host}", parts.path, parts.query, parts.fragment))
    except Exception:
        pass
    return "mongodb://•••"
