"""Agente de ejecución simulada: convierte órdenes en fills de papel.

Aplica los costes reales que tendría la orden en Binance spot:
  - comisión taker (0.10%)
  - slippage estimado (0.03%) en contra siempre
También vigila los stops: si una vela toca el stop de una posición, la cierra.
"""
from bus import CANDLE, ORDER, FILL
from config import FEE_RATE, SLIPPAGE


class ExecutionAgent:
    def __init__(self, bus, portfolio):
        self.bus = bus
        self.portfolio = portfolio
        bus.subscribe(ORDER, self.on_order)
        bus.subscribe(CANDLE, self.check_stops)

    def on_order(self, order):
        side = order["side"]
        slip = 1 + SLIPPAGE if side == "BUY" else 1 - SLIPPAGE
        fill_price = order["price"] * slip
        fee = order["qty"] * fill_price * FEE_RATE
        self.bus.publish(FILL, {
            "strategy": order["strategy"],
            "symbol": order["symbol"],
            "side": side,
            "qty": order["qty"],
            "fill_price": fill_price,
            "fee": fee,
            "stop": order.get("stop"),
            "ts": order["ts"],
            "reason": order.get("reason", ""),
        })

    def check_stops(self, candle):
        """Si el mínimo de la vela perfora el stop de una posición, cierre forzoso."""
        symbol = candle["symbol"]
        for (strategy, sym), pos in list(self.portfolio.positions.items()):
            if sym != symbol or not pos.get("stop"):
                continue
            if candle["low"] <= pos["stop"]:
                exit_price = min(pos["stop"], candle["open"])  # gap bajista: sales peor
                fill_price = exit_price * (1 - SLIPPAGE)
                fee = pos["qty"] * fill_price * FEE_RATE
                self.bus.publish(FILL, {
                    "strategy": strategy, "symbol": sym, "side": "SELL",
                    "qty": pos["qty"], "fill_price": fill_price, "fee": fee,
                    "ts": candle["ts"], "reason": "STOP LOSS",
                })
