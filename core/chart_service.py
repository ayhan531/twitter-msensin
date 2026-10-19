"""
Technical Chart & Indicator Analysis Service
Calculates RSI, EMAs, Support/Resistance, and renders dark-mode financial charts using Matplotlib.
"""

import os
import requests
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional
import matplotlib
matplotlib.use("Agg")  # Headless backend for web / cloud servers
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

CHART_DIR = Path(__file__).resolve().parent.parent / "web" / "static" / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)

class BISTChartService:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }

    def fetch_history(self, symbol: str, range_str: str = "1mo", interval: str = "1d") -> Optional[Dict[str, Any]]:
        clean_symbol = symbol.upper()
        if not clean_symbol.endswith(".IS") and not clean_symbol.startswith("^"):
            clean_symbol = f"{clean_symbol}.IS"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_symbol}?range={range_str}&interval={interval}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return None
            return result[0]
        except Exception:
            return None

    def calculate_indicators(self, closes: List[float]) -> Dict[str, Any]:
        """Calculates RSI, EMA9, EMA21, Support, Resistance"""
        if not closes or len(closes) < 14:
            return {"rsi": 50.0, "ema9": closes[-1] if closes else 0, "ema21": closes[-1] if closes else 0, "trend": "Nötr"}

        # 1. RSI (14)
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:14]) / 14
        avg_loss = sum(losses[:14]) / 14

        for i in range(14, len(deltas)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14

        rs = (avg_gain / avg_loss) if avg_loss != 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)

        # 2. EMAs
        def ema(series, period):
            k = 2 / (period + 1)
            ema_val = series[0]
            for val in series[1:]:
                ema_val = (val * k) + (ema_val * (1 - k))
            return round(ema_val, 2)

        ema9 = ema(closes, 9)
        ema21 = ema(closes, 21) if len(closes) >= 21 else ema(closes, len(closes))

        current_price = closes[-1]
        support = round(min(closes[-15:]), 2)
        resistance = round(max(closes[-15:]), 2)

        # Determine trend
        if current_price > ema9 > ema21:
            trend = "Güçlü Yükseliş (Boğa)"
        elif current_price < ema9 < ema21:
            trend = "Düşüş Eğilimi (Ayı)"
        elif current_price > ema21:
            trend = "Pozitif Toparlanma"
        else:
            trend = "Yatay / Kararsız"

        return {
            "current_price": round(current_price, 2),
            "rsi": rsi,
            "ema9": ema9,
            "ema21": ema21,
            "support": support,
            "resistance": resistance,
            "trend": trend
        }

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """Performs full technical calculation and prepares summary for AI"""
        hist = self.fetch_history(symbol, range_str="1mo", interval="1d")
        if not hist:
            return {"symbol": symbol, "error": "Veri alinamadi"}

        quotes = hist.get("indicators", {}).get("quote", [{}])[0]
        raw_closes = quotes.get("close", [])
        closes = [c for c in raw_closes if c is not None]

        indicators = self.calculate_indicators(closes)
        indicators["symbol"] = symbol.upper().replace(".IS", "")
        return indicators

    def generate_chart_image(self, symbol: str) -> Optional[str]:
        """Generates a professional dark-themed technical chart and saves to disk"""
        hist = self.fetch_history(symbol, range_str="1mo", interval="1d")
        if not hist:
            return None

        quotes = hist.get("indicators", {}).get("quote", [{}])[0]
        closes = [c for c in quotes.get("close", []) if c is not None]
        if not closes or len(closes) < 5:
            return None

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 5.5), gridspec_kw={'height_ratios': [3, 1]}, facecolor='#111827')
        
        # Upper Price Plot
        ax1.set_facecolor('#1f2937')
        ax1.plot(closes, color='#38bdf8', linewidth=2, label=f'{symbol} Kapanış')
        
        # EMAs
        if len(closes) >= 9:
            ema9_vals = []
            k = 2 / 10
            e = closes[0]
            for c in closes:
                e = (c * k) + (e * (1 - k))
                ema9_vals.append(e)
            ax1.plot(ema9_vals, color='#f59e0b', linestyle='--', label='EMA 9')

        ax1.set_title(f"{symbol} 1 Aylık Teknik Fiyat Grafiği & Trend", color='#f3f4f6', fontsize=12, pad=10)
        ax1.tick_params(colors='#9ca3af')
        ax1.grid(True, color='#374151', linestyle=':', alpha=0.6)
        ax1.legend(facecolor='#111827', edgecolor='#4b5563', labelcolor='#f3f4f6')

        # Lower Volume / Dummy indicator Plot
        ax2.set_facecolor('#1f2937')
        volumes = quotes.get("volume", [])
        clean_vols = [v if v else 0 for v in volumes[-len(closes):]]
        ax2.bar(range(len(clean_vols)), clean_vols, color='#10b981', alpha=0.6, width=0.7)
        ax2.set_ylabel("Hacim", color='#9ca3af', fontsize=9)
        ax2.tick_params(colors='#9ca3af')
        ax2.grid(True, color='#374151', linestyle=':', alpha=0.4)

        plt.tight_layout()
        filename = f"chart_{symbol.lower().replace('.is', '')}.png"
        filepath = CHART_DIR / filename
        plt.savefig(filepath, dpi=120, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        return f"/static/charts/{filename}"

if __name__ == "__main__":
    service = BISTChartService()
    analysis = service.analyze_symbol("THYAO")
    print("THYAO Analysis:", analysis)
    img_path = service.generate_chart_image("THYAO")
    print("Saved Chart Image:", img_path)
