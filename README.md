# Sistema Multi-Agente de Trading — PAPER TRADING

Sistema de bots que se comunican entre sí mediante un bus de mensajes, operando
con **precios reales de Binance y dinero 100% ficticio**. Sin claves API, sin
riesgo real.

## Arquitectura

```
DataFeed (Binance) ──CANDLE──► 3 Bots de estrategia ──SIGNAL──► RiskAgent ──ORDER──► ExecutionAgent ──FILL──► Portfolio
                                  │ momentum (cruce EMAs)          │ sizing 0.5%/trade      │ comisión 0.10%
                                  │ mean_reversion (RSI)           │ máx 4 posiciones       │ slippage 0.03%
                                  │ breakout (Donchian)            │ stop diario -2%        │ vigilancia de stops
                                                                   │ stop mensual -5%
```

Ningún bot ejecuta nada por su cuenta: **todas** las señales pasan por el
gestor de riesgo, que dimensiona la posición según el stop y puede parar el
sistema entero si se superan los límites de pérdida.

## Uso

```powershell
cd C:\Users\Sergi\trading-bots

# 1. Validar las estrategias con histórico real (365 días por defecto)
python backtest.py
python backtest.py 180     # o los días que quieras

# 2. Paper trading en vivo (déjalo corriendo; Ctrl+C para parar)
python live.py

# 3. Dashboard (en otra terminal)
python dashboard.py        # -> http://localhost:8800
```

## Sobre el objetivo de rentabilidad

- **1% mensual (~12.7% anual)**: ambicioso pero defendible si el backtest y el
  paper trading lo confirman durante meses.
- **3% mensual sostenido (~42% anual)**: territorio de élite mundial. Techo de
  meses buenos, no expectativa.
- Regla de oro: si no es rentable en papel durante 2-3 meses, **no** lo será
  con dinero real. Las comisiones y el slippage ya están descontados aquí.

## Configuración

Todo en `config.py`: símbolos, intervalo, capital ficticio, límites de riesgo.
Los datos se guardan en `data/` (SQLite + estado del dashboard).
