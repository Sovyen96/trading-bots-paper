"""Configuración central del sistema de trading multi-agente (PAPER TRADING)."""

# --- Mercado ---
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "LINKUSDT", "ADAUSDT", "DOGEUSDT",
]
INTERVAL = "1h"          # velas de 1 hora: suficiente señal, poco ruido, comisiones bajas
# Hosts de la API pública (en orden de preferencia). data-api.binance.vision es
# el espejo oficial de datos de mercado, accesible también desde EE.UU. (GitHub Actions).
BINANCE_HOSTS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]

# --- Filtro de régimen de mercado ---
# Solo se permiten COMPRAS cuando BTC cierra por encima de su media de 200 días.
# En régimen bajista el sistema se queda en cash (las ventas siempre se permiten).
REGIME_SYMBOL = "BTCUSDT"
REGIME_SMA_DAYS = 200

# --- Capital simulado ---
INITIAL_CAPITAL = 10_000.0   # USDT ficticios

# --- Costes reales (Binance spot) ---
FEE_RATE = 0.001         # 0.10% taker por operación
SLIPPAGE = 0.0003        # 0.03% de deslizamiento estimado por orden

# --- Gestión de riesgo (límites duros) ---
RISK_PER_TRADE = 0.005       # arriesga máx. 0.5% del equity por trade (vía stop)
MAX_POSITION_PCT = 0.25      # ninguna posición supera el 25% del equity
MAX_OPEN_POSITIONS = 6       # posiciones simultáneas máximas en todo el sistema
MAX_DAILY_LOSS_PCT = 0.02    # si el día pierde 2%, el sistema se detiene hasta mañana
MAX_MONTHLY_DD_PCT = 0.05    # si el mes pierde 5% desde el pico, se detiene hasta el mes siguiente

# --- Objetivo ---
# Objetivo realista validable: 0.5%–1.5% mensual neto. 3% mensual sostenido NO es
# una expectativa razonable; trátalo como techo de meses excepcionales.

# --- Rutas ---
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "paper.db")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
