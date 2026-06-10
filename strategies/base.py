"""Clase base de los agentes de estrategia.

Cada estrategia escucha velas (CANDLE), mantiene sus indicadores y publica
señales (SIGNAL). Nunca ejecuta nada directamente: la decisión final es del
gestor de riesgo. Solo posiciones largas (spot).

Los indicadores son INCREMENTALES (O(1) por vela): imprescindible para que el
sistema escale a 50+ símbolos sin recalcular el histórico completo cada vez.
"""
from collections import defaultdict, deque

from bus import CANDLE, SIGNAL


class StrategyAgent:
    name = "base"
    lookback = 60  # velas que conserva por símbolo (para máximos/mínimos de ventana)

    def __init__(self, bus, portfolio):
        self.bus = bus
        self.portfolio = portfolio
        self.candles = defaultdict(lambda: deque(maxlen=self.lookback))
        self.count = defaultdict(int)        # velas vistas por símbolo
        self._ind = defaultdict(dict)        # estado incremental por símbolo
        bus.subscribe(CANDLE, self.on_candle)

    def on_candle(self, c):
        sym = c["symbol"]
        self.candles[sym].append(c)
        self.count[sym] += 1
        signal = self.evaluate(sym, c)
        if signal:
            signal["strategy"] = self.name
            self.bus.publish(SIGNAL, signal)

    def has_position(self, symbol):
        return self.portfolio.position(self.name, symbol) is not None

    def evaluate(self, symbol, candle):
        """Devuelve un dict señal o None. Implementado por cada estrategia.
        DEBE actualizar todos sus indicadores en cada llamada (una por vela)."""
        raise NotImplementedError

    # --- Indicadores incrementales (llamar exactamente una vez por vela) ---

    def ema(self, symbol, period, close):
        """EMA incremental. Devuelve (valor_anterior, valor_actual)."""
        st = self._ind[symbol]
        key = f"ema{period}"
        prev = st.get(key)
        if prev is None:
            st[key] = close  # semilla; converge tras ~2-3x period velas
        else:
            k = 2 / (period + 1)
            st[key] = close * k + prev * (1 - k)
        return prev, st[key]

    def rsi(self, symbol, close, period=14):
        """RSI de Wilder incremental. None hasta tener datos suficientes."""
        st = self._ind[symbol]
        prev_close = st.get("rsi_pc")
        st["rsi_pc"] = close
        if prev_close is None:
            return None
        gain, loss = max(close - prev_close, 0), max(prev_close - close, 0)
        if "rsi_g" not in st:
            st.setdefault("rsi_seed", []).append((gain, loss))
            if len(st["rsi_seed"]) < period:
                return None
            st["rsi_g"] = sum(g for g, _ in st["rsi_seed"]) / period
            st["rsi_l"] = sum(l for _, l in st["rsi_seed"]) / period
            del st["rsi_seed"]
        else:
            st["rsi_g"] = (st["rsi_g"] * (period - 1) + gain) / period
            st["rsi_l"] = (st["rsi_l"] * (period - 1) + loss) / period
        if st["rsi_l"] == 0:
            return 100.0
        return 100 - 100 / (1 + st["rsi_g"] / st["rsi_l"])

    def atr(self, symbol, candle, period=14):
        """ATR de Wilder incremental. None hasta tener datos suficientes."""
        st = self._ind[symbol]
        pc = st.get("atr_pc")
        st["atr_pc"] = candle["close"]
        if pc is None:
            return None
        tr = max(candle["high"] - candle["low"],
                 abs(candle["high"] - pc), abs(candle["low"] - pc))
        if "atr" not in st:
            st.setdefault("atr_seed", []).append(tr)
            if len(st["atr_seed"]) < period:
                return None
            st["atr"] = sum(st["atr_seed"]) / period
            del st["atr_seed"]
        else:
            st["atr"] = (st["atr"] * (period - 1) + tr) / period
        return st["atr"]
