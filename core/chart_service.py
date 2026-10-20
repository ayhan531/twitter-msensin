"""
TradingView Pro Style Dark Candlestick Chart & Indicator Service
Generates professional Japanese Candlestick charts with EMA, Volume, and RSI sub-panels.
"""

import os
import requests
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional
import matplotlib
matplotlib.use("Agg")  # Headless backend for web / cloud servers
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

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
            current = closes[-1] if closes else 0.0
            return {"rsi": 50.0, "ema9": current, "ema21": current, "trend": "Nötr", "current_price": current, "support": current, "resistance": current}

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
        def calc_ema(series, period):
            k = 2 / (period + 1)
            val = series[0]
            res = [val]
            for x in series[1:]:
                val = (x * k) + (val * (1 - k))
                res.append(val)
            return res

        ema9_series = calc_ema(closes, 9)
        ema21_series = calc_ema(closes, 21) if len(closes) >= 21 else calc_ema(closes, len(closes))

        current_price = closes[-1]
        support = round(min(closes[-15:]), 2)
        resistance = round(max(closes[-15:]), 2)

        # Determine trend
        if current_price > ema9_series[-1] > ema21_series[-1]:
            trend = "Güçlü Boğa (Yükseliş Trendi)"
        elif current_price < ema9_series[-1] < ema21_series[-1]:
            trend = "Satıcılı (Düşüş Trendi)"
        elif current_price > ema21_series[-1]:
            trend = "Pozitif Toparlanma"
        else:
            trend = "Yatay / Kararsız"

        return {
            "current_price": round(current_price, 2),
            "rsi": rsi,
            "ema9": round(ema9_series[-1], 2),
            "ema21": round(ema21_series[-1], 2),
            "ema9_series": ema9_series,
            "ema21_series": ema21_series,
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
        """
        Generates a stunning TradingView Pro style Candlestick (Mum) chart with
        Volume bars and RSI(14) indicator.
        """
        hist = self.fetch_history(symbol, range_str="1mo", interval="1d")
        if not hist:
            return None

        quotes = hist.get("indicators", {}).get("quote", [{}])[0]
        timestamps = hist.get("timestamp", [])
        
        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        volumes = quotes.get("volume", [])

        # Filter out None values
        valid_indices = [i for i in range(len(closes)) if closes[i] is not None and opens[i] is not None]
        if len(valid_indices) < 5:
            return None

        opens = [opens[i] for i in valid_indices]
        highs = [highs[i] for i in valid_indices]
        lows = [lows[i] for i in valid_indices]
        closes = [closes[i] for i in valid_indices]
        volumes = [volumes[i] if volumes[i] else 0 for i in valid_indices]
        
        N = len(closes)
        x_indices = list(range(N))

        # Indicators
        indicators = self.calculate_indicators(closes)
        ema9_vals = indicators.get("ema9_series", [])
        ema21_vals = indicators.get("ema21_series", [])
        current_price = closes[-1]
        prev_close = closes[-2] if N > 1 else current_price
        change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)
        trend_label = indicators.get("trend", "Nötr")

        # Color scheme - TradingView Pro Dark
        BG_COLOR = "#131722"
        PANEL_COLOR = "#1e222d"
        GRID_COLOR = "#2a2e39"
        TEXT_COLOR = "#d1d4dc"
        GREEN_COLOR = "#089981"  # Bullish candle
        RED_COLOR = "#f23645"    # Bearish candle
        EMA9_COLOR = "#ff9800"   # Orange
        EMA21_COLOR = "#2962ff"  # Royal Blue
        RSI_COLOR = "#ab47bc"    # Purple

        fig, (ax_main, ax_rsi) = plt.subplots(
            2, 1, 
            figsize=(11, 6.5), 
            gridspec_kw={'height_ratios': [3.5, 1.2]}, 
            facecolor=BG_COLOR
        )

        # ---------------- 1. MAIN CANDLESTICK PANEL ----------------
        ax_main.set_facecolor(PANEL_COLOR)
        
        for i in range(N):
            op = opens[i]
            hi = highs[i]
            lo = lows[i]
            cl = closes[i]
            
            color = GREEN_COLOR if cl >= op else RED_COLOR
            
            # Draw wick (high to low)
            ax_main.vlines(x=i, ymin=lo, ymax=hi, color=color, linewidth=1.2, alpha=0.9)
            
            # Draw candle body
            body_bottom = min(op, cl)
            body_height = max(abs(cl - op), 0.05)  # Min height for doji
            ax_main.bar(x=i, height=body_height, bottom=body_bottom, width=0.68, color=color, edgecolor=color, linewidth=0.5)

        # Plot EMAs
        if len(ema9_vals) == N:
            ax_main.plot(x_indices, ema9_vals, color=EMA9_COLOR, linewidth=1.5, label='EMA 9 (Kısa Vade)', alpha=0.9)
        if len(ema21_vals) == N:
            ax_main.plot(x_indices, ema21_vals, color=EMA21_COLOR, linewidth=1.5, label='EMA 21 (Trend)', alpha=0.9)

        # Horizontal Support & Resistance lines
        supp = indicators.get("support", min(lows))
        ress = indicators.get("resistance", max(highs))
        ax_main.axhline(y=supp, color='#10b981', linestyle=':', linewidth=1.2, alpha=0.7, label=f'Destek: {supp} TL')
        ax_main.axhline(y=ress, color='#ef4444', linestyle=':', linewidth=1.2, alpha=0.7, label=f'Direnç: {ress} TL')

        # Current Price Badge on the right
        price_badge_color = GREEN_COLOR if change_pct >= 0 else RED_COLOR
        ax_main.text(
            N - 0.5, current_price, f" {current_price:.2f} TL (%{change_pct:+.2f})",
            color='#ffffff', fontsize=9, fontweight='bold',
            verticalalignment='center',
            bbox=dict(boxstyle='square,pad=0.25', facecolor=price_badge_color, edgecolor='none')
        )

        # Title / Watermark Header
        clean_sym = symbol.upper().replace(".IS", "")
        ax_main.set_title(
            f"  {clean_sym} • 1 Günlük Mum Grafiği • Son: {current_price:.2f} TL  |  Görünüm: {trend_label}",
            color=TEXT_COLOR, fontsize=12, fontweight='bold', loc='left', pad=12
        )

        ax_main.grid(True, color=GRID_COLOR, linestyle='--', linewidth=0.6, alpha=0.7)
        ax_main.tick_params(colors=TEXT_COLOR, labelsize=9)
        ax_main.legend(loc='upper left', facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

        # ---------------- 2. RSI(14) PANEL ----------------
        ax_rsi.set_facecolor(PANEL_COLOR)
        
        # Calculate rolling RSI values for plotting
        rsi_series = []
        for end_idx in range(1, N + 1):
            sub_closes = closes[:end_idx]
            sub_ind = self.calculate_indicators(sub_closes)
            rsi_series.append(sub_ind.get("rsi", 50.0))

        ax_rsi.plot(x_indices, rsi_series, color=RSI_COLOR, linewidth=1.6, label='RSI (14)')
        ax_rsi.axhline(70, color=RED_COLOR, linestyle='--', linewidth=0.8, alpha=0.7)
        ax_rsi.axhline(30, color=GREEN_COLOR, linestyle='--', linewidth=0.8, alpha=0.7)
        ax_rsi.fill_between(x_indices, 30, 70, color=RSI_COLOR, alpha=0.08)
        
        current_rsi = rsi_series[-1] if rsi_series else 50.0
        ax_rsi.set_title(f"RSI (14): {current_rsi}  [ Aşırı Satım: 30 / Aşırı Alım: 70 ]", color=TEXT_COLOR, fontsize=8, loc='left', pad=4)
        ax_rsi.set_ylim(15, 85)
        ax_rsi.grid(True, color=GRID_COLOR, linestyle='--', linewidth=0.6, alpha=0.7)
        ax_rsi.tick_params(colors=TEXT_COLOR, labelsize=8)

        # Hide X-ticks on main, format bottom
        ax_main.set_xticks([])
        ax_rsi.set_xticks([0, N // 4, N // 2, 3 * N // 4, N - 1])
        ax_rsi.set_xticklabels(["1 Ay Önce", "3 Hafta Önce", "2 Hafta Önce", "1 Hafta Önce", "Bugün"])

        plt.tight_layout()
        filename = f"chart_{clean_sym.lower()}.png"
        filepath = CHART_DIR / filename
        plt.savefig(filepath, dpi=140, facecolor=BG_COLOR, edgecolor='none')
        plt.close(fig)

        return f"/static/charts/{filename}"


if __name__ == "__main__":
    service = BISTChartService()
    img = service.generate_chart_image("THYAO")
    print("Generated Candlestick Chart:", img)
