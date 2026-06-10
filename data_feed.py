"""Agente de datos: descarga velas reales de Binance (API pública, sin clave)."""
import json
import time
import urllib.request
import urllib.parse

from config import BINANCE_HOSTS

INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}


def _get(path, params):
    last_err = None
    for host in BINANCE_HOSTS:
        url = f"{host}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "paper-bot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            last_err = e
    raise last_err


def fetch_klines(symbol, interval, start_ms=None, end_ms=None, limit=1000):
    """Devuelve velas como dicts: ts, open, high, low, close, volume."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_ms:
        params["startTime"] = start_ms
    if end_ms:
        params["endTime"] = end_ms
    raw = _get("/api/v3/klines", params)
    return [
        {
            "symbol": symbol,
            "ts": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in raw
    ]


def fetch_history(symbol, interval, days):
    """Descarga 'days' días de velas paginando la API (máx. 1000 por petición)."""
    step = INTERVAL_MS[interval]
    end = int(time.time() * 1000)
    start = end - days * 86_400_000
    out = []
    cursor = start
    while cursor < end:
        batch = fetch_klines(symbol, interval, start_ms=cursor, limit=1000)
        if not batch:
            break
        out.extend(batch)
        cursor = batch[-1]["ts"] + step
        time.sleep(0.15)  # respetar rate limits
    # descartar la última vela si aún no ha cerrado
    if out and out[-1]["ts"] + step > int(time.time() * 1000):
        out.pop()
    return out


def fetch_price(symbol):
    return float(_get("/api/v3/ticker/price", {"symbol": symbol})["price"])
