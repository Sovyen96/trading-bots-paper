"""Agente de riesgo: la única puerta entre las señales y el dinero.

Reglas duras (config.py):
  - Riesgo máx. por trade: 0.5% del equity (calculado contra el stop)
  - Posición máx.: 25% del equity
  - Máx. 4 posiciones abiertas simultáneas
  - Pérdida diaria máx. 2%  -> sistema parado hasta el día siguiente
  - Drawdown mensual máx. 5% -> sistema parado hasta el mes siguiente
"""
import datetime as dt

from bus import SIGNAL, ORDER, REJECT
from config import (
    RISK_PER_TRADE, MAX_POSITION_PCT, MAX_OPEN_POSITIONS,
    MAX_DAILY_LOSS_PCT, MAX_MONTHLY_DD_PCT,
)


class RiskAgent:
    def __init__(self, bus, portfolio, regime=None):
        self.bus = bus
        self.portfolio = portfolio
        self.regime = regime  # RegimeFilter opcional: bloquea compras en mercado bajista
        self.day_start_equity = None
        self.month_peak_equity = None
        self.current_day = None
        self.current_month = None
        self.halted_until_day = None
        self.halted_until_month = None
        self.rejections = []
        bus.subscribe(SIGNAL, self.on_signal)

    def _roll_periods(self, ts):
        d = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc)
        day, month = d.strftime("%Y-%m-%d"), d.strftime("%Y-%m")
        eq = self.portfolio.equity()
        if day != self.current_day:
            self.current_day = day
            self.day_start_equity = eq
        if month != self.current_month:
            self.current_month = month
            self.month_peak_equity = eq
        self.month_peak_equity = max(self.month_peak_equity or eq, eq)
        return day, month

    def _reject(self, signal, reason):
        self.rejections.append({"signal": signal, "reason": reason})
        self.bus.publish(REJECT, {"signal": signal, "reason": reason})

    def on_signal(self, signal):
        day, month = self._roll_periods(signal["ts"])
        eq = self.portfolio.equity()

        # Las ventas (cierres) se dejan pasar siempre: reducir riesgo nunca se bloquea.
        if signal["side"] == "SELL":
            pos = self.portfolio.position(signal["strategy"], signal["symbol"])
            if pos is None:
                return
            self.bus.publish(ORDER, {**signal, "qty": pos["qty"]})
            return

        # --- Filtro de régimen: en mercado bajista, solo cash ---
        if self.regime and not self.regime.risk_on(signal["ts"]):
            return self._reject(signal, "régimen bajista (BTC < SMA200 diaria): solo cash")

        # --- Cortacircuitos ---
        if self.halted_until_day == day:
            return self._reject(signal, "parada diaria activa (pérdida > 2% hoy)")
        if self.halted_until_month == month:
            return self._reject(signal, "parada mensual activa (drawdown > 5% este mes)")
        if self.day_start_equity and eq < self.day_start_equity * (1 - MAX_DAILY_LOSS_PCT):
            self.halted_until_day = day
            return self._reject(signal, "límite de pérdida diaria alcanzado")
        if self.month_peak_equity and eq < self.month_peak_equity * (1 - MAX_MONTHLY_DD_PCT):
            self.halted_until_month = month
            return self._reject(signal, "límite de drawdown mensual alcanzado")

        # --- Límites de exposición ---
        if self.portfolio.open_position_count() >= MAX_OPEN_POSITIONS:
            return self._reject(signal, f"ya hay {MAX_OPEN_POSITIONS} posiciones abiertas")
        if self.portfolio.position(signal["strategy"], signal["symbol"]):
            return self._reject(signal, "esta estrategia ya tiene posición en el símbolo")

        # --- Dimensionado por riesgo (position sizing) ---
        price, stop = signal["price"], signal.get("stop")
        if not stop or stop >= price:
            return self._reject(signal, "señal sin stop válido")
        risk_amount = eq * RISK_PER_TRADE           # ej. 0.5% de 10.000 = 50 USDT
        qty = risk_amount / (price - stop)          # tamaño tal que stop = -50 USDT
        max_qty = (eq * MAX_POSITION_PCT) / price   # techo del 25% del equity
        qty = min(qty, max_qty)
        if qty * price < 10:
            return self._reject(signal, "tamaño resultante por debajo del mínimo (10 USDT)")
        if qty * price > self.portfolio.cash:
            qty = self.portfolio.cash * 0.98 / price
            if qty * price < 10:
                return self._reject(signal, "sin cash disponible")

        self.bus.publish(ORDER, {**signal, "qty": round(qty, 6)})
