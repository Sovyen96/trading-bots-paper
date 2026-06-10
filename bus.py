"""Bus de mensajes: el canal por el que los agentes se comunican entre sí.

Flujo de eventos:
    DataAgent  --CANDLE-->  Estrategias  --SIGNAL-->  RiskAgent  --ORDER-->  ExecutionAgent  --FILL-->  Portfolio
"""
from collections import defaultdict


class MessageBus:
    def __init__(self):
        self._subscribers = defaultdict(list)
        self.history = []  # registro de todos los eventos (auditoría)

    def subscribe(self, topic, handler):
        self._subscribers[topic].append(handler)

    def publish(self, topic, message):
        self.history.append((topic, message))
        for handler in self._subscribers[topic]:
            handler(message)


# Tópicos estándar
CANDLE = "CANDLE"    # nueva vela cerrada: {symbol, ts, open, high, low, close, volume}
SIGNAL = "SIGNAL"    # propuesta de una estrategia: {strategy, symbol, side, ts, price, stop, reason}
ORDER = "ORDER"      # orden aprobada por riesgo: {strategy, symbol, side, qty, price, stop, ts}
FILL = "FILL"        # ejecución simulada: {strategy, symbol, side, qty, fill_price, fee, ts}
REJECT = "REJECT"    # señal rechazada por el gestor de riesgo: {signal, reason}
