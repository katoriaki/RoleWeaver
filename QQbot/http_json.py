import json
from typing import Dict, Optional
from urllib import request


def post_json(url: str, payload: Dict, timeout: float, headers: Optional[Dict[str, str]] = None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        content = resp.read()
        content_type = resp.headers.get("Content-Type", "")
    if "json" in content_type:
        return json.loads(content.decode("utf-8"))
    return content


def get_text(url: str, timeout: float):
    with request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")
