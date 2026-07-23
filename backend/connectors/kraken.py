import hashlib
import hmac
import base64
import time
import urllib.parse
import httpx
import os


API_URL = "https://api.kraken.com"


def _sign(urlpath: str, data: dict, secret: str) -> str:
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data["nonce"]) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode()


def _private(endpoint: str, data: dict | None = None) -> dict:
    key = os.environ["KRAKEN_API_KEY"]
    secret = os.environ["KRAKEN_API_SECRET"]
    urlpath = f"/0/private/{endpoint}"
    data = data or {}
    data["nonce"] = str(int(time.time() * 1000))
    headers = {"API-Key": key, "API-Sign": _sign(urlpath, data, secret)}
    resp = httpx.post(API_URL + urlpath, data=data, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("error"):
        raise RuntimeError(f"Kraken error: {result['error']}")
    return result["result"]


def get_balances() -> dict[str, float]:
    raw = _private("Balance")
    return {asset: float(amount) for asset, amount in raw.items() if float(amount) > 0}


def get_open_positions() -> list[dict]:
    raw = _private("OpenPositions", {"docalcs": "true"})
    return list(raw.values())
