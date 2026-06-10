"""Clase base de los agentes de estrategia.

Cada estrategia escucha velas (CANDLE), mantiene sus indicadores y publica
señales (SIGNAL). Nunca ejecuta nada directamente: la decisión final es del
gestor de riesgo. Solo posiciones largas (spot).
"""
from collections import defaultdict, deque

from bus import CANDLE, SIGNAL


class StrategyAgent:
    name = "base"
    lookback = 200  # velas que conserva por símbolo

    def __init__(self, bus, portfolio):
        self.bus = bus
        self.portfolio = portfolio
        self.candles = defaultdict(lambda: deque(maxlen=self.lookback))
        bus.subscribe(CANDLE, self.on_candle)

    def on_candle(self, c):
        self.candles[c["symbol"]].append(c)
        signal = self.evaluate(c["symbol"])
        if signal:
            signal["strategy"] = self.name
            self.bus.publish(SIGNAL, signal)

    def has_position(self, symbol):
        return self.portfolio.position(self.name, symbol) is not None

    def evaluate(self, symbol):
        """Devuelve un dict señal o None. Implementado por cada estrategia."""
        raise NotImplementedError

    # --- Indicadores compartidos ---
    @staticmethod
    def ema(values, period):
        if len(values) < period:
            return None
        k = 2 / (period + 1)
        e = sum(values[:period]) / period
        for v in values[period:]:
            e = v * k + e * (1 - k)
        return e

    @staticmethod
    def rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        avg_g = sum(gains[:period]) / period
        avg_l = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_g = (avg_g * (period - 1) + gains[i]) / period
            avg_l = (avg_l * (period - 1) + losses[i]) / period
        if avg_l == 0:
            return 100.0
        return 100 - 100 / (1 + avg_g / avg_l)

    @staticmethod
    def atr(candles, period=14):
        if len(candles) < period + 1:
            return None
        trs = []
        for i in range(1, len(candles)):
            h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        a = sum(trs[:period]) / period
        for t in trs[period:]:
            a = (a * (period - 1) + t) / period
        return a
