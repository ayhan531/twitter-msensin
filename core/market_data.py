"""
Market Data Service for Borsa Istanbul (BIST)
Fetches live market data and price changes completely free from Yahoo Finance API.
"""

import requests
from typing import Dict, Any, List, Optional
import time

POPULAR_BIST_STOCKS = [
    "XU100.IS",  # BIST 100 Endeksi
    "THYAO.IS",  # Türk Hava Yolları
    "EREGL.IS",  # Ereğli Demir Çelik
    "ASELS.IS",  # Aselsan
    "TUPRS.IS",  # Tüpraş
    "AKBNK.IS",  # Akbank
    "ISCTR.IS",  # İş Bankası
    "BIMAS.IS",  # BİM Birleşik Mağazalar
    "SISE.IS",   # Şişecam
    "KCHOL.IS",  # Koç Holding
    "SAHOL.IS",  # Sabancı Holding
    "FROTO.IS",  # Ford Otosan
    "PGSUS.IS",  # Pegasus
    "SASA.IS",   # Sasa Polyester
    "HEKTS.IS"   # Hektaş
]

class BISTMarketData:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        self.cache = {}
        self.cache_ttl = 60  # 1 minute cache

    def get_ticker_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch real-time data for a single symbol (e.g. THYAO.IS)"""
        clean_symbol = symbol.upper()
        if not clean_symbol.endswith(".IS") and not clean_symbol.startswith("^"):
            clean_symbol = f"{clean_symbol}.IS"

        now = time.time()
        if clean_symbol in self.cache:
            cached_time, cached_data = self.cache[clean_symbol]
            if now - cached_time < self.cache_ttl:
                return cached_data

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_symbol}?interval=1d&range=5d"
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            result = data.get("chart", {}).get("result")
            if not result or len(result) == 0:
                return None

            meta = result[0].get("meta", {})
            current_price = meta.get("regularMarketPrice", 0.0)
            prev_close = meta.get("chartPreviousClose", current_price)
            day_high = meta.get("regularMarketDayHigh", current_price)
            day_low = meta.get("regularMarketDayLow", current_price)
            
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0.0

            parsed = {
                "symbol": clean_symbol.replace(".IS", ""),
                "price": round(current_price, 2),
                "prev_close": round(prev_close, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "day_high": round(day_high, 2),
                "day_low": round(day_low, 2),
                "currency": meta.get("currency", "TRY"),
                "timestamp": now
            }
            self.cache[clean_symbol] = (now, parsed)
            return parsed
        except Exception as e:
            # Fallback safe error handling
            return None

    def get_market_overview(self) -> Dict[str, Any]:
        """Fetch BIST 100 index and top active stocks"""
        index_data = self.get_ticker_data("XU100.IS")
        
        stocks_sample = ["THYAO.IS", "ASELS.IS", "EREGL.IS", "TUPRS.IS", "AKBNK.IS", "BIMAS.IS"]
        stocks_data = []
        for sym in stocks_sample:
            s_data = self.get_ticker_data(sym)
            if s_data:
                stocks_data.append(s_data)

        # Determine general sentiment
        index_pct = index_data.get("change_pct", 0) if index_data else 0
        if index_pct > 1.0:
            sentiment = "Güçlü Alıcılı (Boğa)"
        elif index_pct > 0.0:
            sentiment = "Pozitif / Alıcılı"
        elif index_pct < -1.0:
            sentiment = "Satıcılı / Düşüş Eğilimli (Ayı)"
        elif index_pct < 0.0:
            sentiment = "Hafif Satıcılı"
        else:
            sentiment = "Yatay / Kararsız"

        return {
            "index": index_data,
            "sentiment": sentiment,
            "stocks": stocks_data
        }

if __name__ == "__main__":
    bist = BISTMarketData()
    overview = bist.get_market_overview()
    print("Market Overview:", overview)
