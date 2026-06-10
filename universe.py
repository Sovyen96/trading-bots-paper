"""Universo dinámico: selecciona las criptos más líquidas de Binance.

En lugar de una lista fija, cada ejecución toma el top N de pares USDT por
volumen de negociación de 24h, excluyendo stablecoins y tokens apalancados.
Así el sistema cubre automáticamente las altcoins relevantes del momento, y
evita microcaps ilíquidas donde la simulación de slippage sería irreal.
"""
from config import UNIVERSE_SIZE, MIN_QUOTE_VOLUME
from data_feed import _get

# Bases que no son inversión direccional: stablecoins y wrapped/fiat
EXCLUDED_BASES = {
    "USDC", "FDUSD", "TUSD", "DAI", "USDP", "EUR", "EURI", "AEUR", "XUSD",
    "USD1", "BUSD", "UST", "USTC", "PAXG", "XAUT", "WBTC", "WBETH", "BFUSD",
    "RLUSD", "USDE", "USDS",
}
# Sufijos de tokens apalancados (históricos) que jamás deben entrar
EXCLUDED_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


def get_universe(top_n=UNIVERSE_SIZE, min_volume=MIN_QUOTE_VOLUME):
    """Top N símbolos USDT por volumen 24h, filtrados por liquidez mínima."""
    tickers = _get("/api/v3/ticker/24hr", {})
    candidates = []
    for t in tickers:
        sym = t["symbol"]
        if not sym.endswith("USDT") or sym.endswith(EXCLUDED_SUFFIXES):
            continue
        base = sym[:-4]
        if base in EXCLUDED_BASES:
            continue
        vol = float(t["quoteVolume"])
        if vol < min_volume:
            continue
        candidates.append((sym, vol))
    candidates.sort(key=lambda x: -x[1])
    return [sym for sym, _ in candidates[:top_n]]
