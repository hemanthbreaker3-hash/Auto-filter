"""Small Telegraph API client. Telegraph accounts are created without API keys."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.telegra.ph/"


def _post(method, params, timeout=15):
    payload = urlencode(params).encode("utf-8")
    request = Request(API + method, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Telegraph API request failed"))
    return result.get("result") or {}


def create_account(short_name="MoviesZoneFlix", author_name="MoviesZoneFlix"):
    """Create a Telegraph account; no user-supplied token is needed."""
    result = _post("createAccount", {
        "short_name": short_name[:32],
        "author_name": author_name[:64],
    })
    token = result.get("access_token")
    if not token:
        raise RuntimeError("Telegraph did not return an access token")
    return {"access_token": token, "short_name": result.get("short_name", short_name),
            "author_name": result.get("author_name", author_name),
            "author_url": result.get("author_url", "")}


def create_page(token, title, lines, author_name="MoviesZoneFlix"):
    content = [{"tag": "p", "children": [str(line)[:3000]]} for line in lines if line]
    result = _post("createPage", {
        "access_token": token,
        "title": title[:256],
        "author_name": author_name[:64],
        "content": json.dumps(content, ensure_ascii=False),
        "return_content": "false",
    })
    return result["url"]
