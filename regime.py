"""Filtro de régimen de mercado: ¿estamos en mercado alcista o bajista?

Regla: si BTC cierra por debajo de su media simple de 200 días, el sistema
entero se pone en modo defensivo — no se abren compras nuevas (las ventas y
stops siguen funcionando). Es el filtro que históricamente más mejora los
sistemas de tendencia: evita operar en mercados bajistas.
"""
import datetime as dt

from config import REGIME_SYMBOL, REGIME_SMA_DAYS
from data_feed import fetch_history


class RegimeFilter:
    def __init__(self, daily_candles, period=REGIME_SMA_DAYS):
        """daily_candles: velas 1d de BTC, cronológicas, con al menos period+1."""
        self.by_date = {}
        closes = []
        for c in daily_candles:
            closes.append(c["close"])
            if len(closes) >= period:
                sma = sum(closes[-period:]) / period
                date = dt.datetime.fromtimestamp(
                    c["ts"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
                self.by_date[date] = c["close"] > sma
        self._dates = sorted(self.by_date)

    @classmethod
    def fetch(cls, extra_days=0):
        """Construye el filtro descargando el histórico diario necesario."""
        candles = fetch_history(REGIME_SYMBOL, "1d", REGIME_SMA_DAYS + 30 + extra_days)
        return cls(candles)

    def risk_on(self, ts):
        """True si el día ANTERIOR a ts cerró en régimen alcista.

        Se usa el día anterior porque la vela diaria del día en curso aún no
        ha cerrado. Si no hay dato (histórico insuficiente), devuelve True
        para no bloquear, pero eso solo ocurre en los primeros días.
        """
        d = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc) - dt.timedelta(days=1)
        for _ in range(7):  # buscar hacia atrás por si falta algún día
            key = d.strftime("%Y-%m-%d")
            if key in self.by_date:
                return self.by_date[key]
            d -= dt.timedelta(days=1)
        return True
