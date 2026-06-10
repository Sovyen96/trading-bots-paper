"""Bot 2 — Reversión a la media: RSI sobrevendido en tendencia alcista.

Compra cuando el RSI(14) cae por debajo de 30 mientras el precio sigue por
encima de la EMA(200) (corrección dentro de tendencia alcista, no cuchillo
cayendo). Sale cuando el RSI recupera 55 o por stop ATR.
"""
from .base import StrategyAgent


class MeanReversionAgent(StrategyAgent):
    name = "mean_reversion"

    RSI_BUY, RSI_EXIT, TREND = 30, 55, 200
    WARMUP = 220

    def evaluate(self, symbol, candle):
        price = candle["close"]
        ts = candle["ts"]

        rsi = self.rsi(symbol, price)
        _, trend = self.ema(symbol, self.TREND, price)
        atr = self.atr(symbol, candle)

        if self.count[symbol] < self.WARMUP or rsi is None or atr is None:
            return None

        in_pos = self.has_position(symbol)

        if not in_pos and rsi < self.RSI_BUY and price > trend:
            return {
                "symbol": symbol, "side": "BUY", "ts": ts, "price": price,
                "stop": price - 2.0 * atr,
                "reason": f"RSI={rsi:.1f} sobrevendido sobre EMA{self.TREND}",
            }
        if in_pos and rsi > self.RSI_EXIT:
            return {
                "symbol": symbol, "side": "SELL", "ts": ts, "price": price,
                "stop": None, "reason": f"RSI={rsi:.1f} recuperado",
            }
        return None
