"""
Free AI Content Generator for BIST Tweets & Engagement Comments
Supports Google Gemini Free API, Groq Free API, or dynamic algorithmic fallback.
"""

import os
import random
import json
import warnings
import requests
from typing import Dict, Any, Optional, List

warnings.filterwarnings("ignore")

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.persona_prompts import (
    BIST_ANALYST_SYSTEM_PROMPT,
    BIST_REPLY_PROMPT,
    FALLBACK_TEMPLATES,
    FALLBACK_REPLIES
)


class BISTContentGenerator:
    def __init__(self, provider: str = "auto", api_key: Optional[str] = None):
        """
        provider: 'gemini', 'groq', 'openai', or 'auto' (checks env or falls back)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("AI_API_KEY")
        self.provider = provider.lower()
        
        if self.provider == "auto":
            if os.getenv("GEMINI_API_KEY"):
                self.provider = "gemini"
            elif os.getenv("GROQ_API_KEY"):
                self.provider = "groq"
            elif self.api_key:
                self.provider = "gemini" if "AIza" in self.api_key else "groq"
            else:
                self.provider = "fallback"

    def _call_gemini_api(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Call Google Gemini Free API endpoint"""
        if not self.api_key:
            return None
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 300
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text.replace('"', '').replace("'", "")
        except Exception as e:
            # Fallback to smart generator if API fails
            pass
        return None

    def _call_groq_api(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Call Groq Free API endpoint"""
        if not self.api_key:
            return None
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200,
            "temperature": 0.7
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                return text.replace('"', '').replace("'", "")
        except Exception:
            pass
        return None

    def generate_bist_tweet(self, market_data: Dict[str, Any]) -> str:
        """
        Generates a complete, authentic BIST analysis tweet using AI or smart algorithmic fallback.
        """
        index = market_data.get("index") or {}
        stocks = market_data.get("stocks") or []
        sentiment = market_data.get("sentiment", "Yatay")

        stock = random.choice(stocks) if stocks else {
            "symbol": "THYAO",
            "price": 273.5,
            "change": -2.5,
            "change_pct": -0.9,
            "day_high": 277.0,
            "day_low": 271.0
        }

        # Format context for AI
        context_prompt = f"""
Canlı Borsa İstanbul Piyasa Verileri:
- BIST 100 Endeksi: {index.get('price', '11.720')} TL (Değişim: %{index.get('change_pct', 0)})
- Genel Piyasa Havası: {sentiment}
- Öne Çıkan Hisse: {stock.get('symbol')} ({stock.get('price')} TL, Değişim: %{stock.get('change_pct')}%, Gün İçi Aralık: {stock.get('day_low')} - {stock.get('day_high')} TL)

Görev: Bu verilere dayanarak X (Twitter) için çarpıcı, teknik terimler içeren, 200-260 karakterlik orijinal bir borsa yorumu yaz. Sonuna (YTD) ekle.
"""

        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(context_prompt, BIST_ANALYST_SYSTEM_PROMPT)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(context_prompt, BIST_ANALYST_SYSTEM_PROMPT)

        if ai_response:
            return ai_response

        # High-quality dynamic fallback template if AI is offline or key not provided
        sym = stock.get("symbol", "THYAO")
        price = stock.get("price", 270.0)
        chg_pct = stock.get("change_pct", 0.0)
        chg_text = f"günü %{abs(chg_pct)} primle sürdürüyor" if chg_pct >= 0 else f"ara düzeltmeyle %{abs(chg_pct)} eksiye çekildi"
        support = round(price * 0.965, 2)
        resistance = round(price * 1.035, 2)
        
        template = random.choice(FALLBACK_TEMPLATES)
        text = template.format(
            symbol=sym,
            price=price,
            change_text=chg_text,
            change_pct=chg_pct,
            support=support,
            resistance=resistance,
            day_high=stock.get("day_high", round(price * 1.02, 2)),
            index_price=index.get("price", "11.720"),
            index_change_pct=index.get("change_pct", "-0.5"),
            sentiment_desc=sentiment,
            stock_sym=sym,
            stock_price=price
        )
        return text

    def generate_reply(self, parent_tweet_text: str, custom_pool: Optional[List[str]] = None, custom_system_prompt: Optional[str] = None) -> str:
        """
        Generates an authentic BIST reply to engage on a tweet.
        Can use custom user comment pool, custom AI persona, or standard fallback.
        """
        # If user defined a custom comment pool and wants to use it
        if custom_pool and len(custom_pool) > 0 and random.random() < 0.6:
            return random.choice(custom_pool)

        prompt = f"Şu tweete cevap yaz:\n\"{parent_tweet_text}\""
        system_prompt = custom_system_prompt or BIST_REPLY_PROMPT
        
        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(prompt, system_prompt)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(prompt, system_prompt)

        if ai_response:
            return ai_response

        # Fallback to custom pool if provided, else standard fallback
        if custom_pool and len(custom_pool) > 0:
            return random.choice(custom_pool)

        return random.choice(FALLBACK_REPLIES)

    def generate_news_tweet(self, news_item: Dict[str, Any]) -> str:
        """
        Generates an analytical tweet interpreting breaking BIST / finance news.
        """
        title = news_item.get("title", "")
        source = news_item.get("source", "Piyasa")
        prompt = f"""
Önemli Gelişme: {title}
Kaynak: {source}

Görev: Bu haberi Borsa İstanbul (BIST), sektörler ve hisseler üzerindeki olası etkileri açısından yorumlayan, 200-260 karakterlik profesyonel bir X (Twitter) analizi yaz. Sonuna (YTD) ekle.
"""
        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(prompt, BIST_ANALYST_SYSTEM_PROMPT)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(prompt, BIST_ANALYST_SYSTEM_PROMPT)

        if ai_response:
            return ai_response

        # High-quality dynamic fallback for news
        templates = [
            f"Gündem: \"{title[:75]}...\" haberi piyasada fiyatlanıyor. BIST tarafında sektörel bazda volatilite yaratabilir. Kısa vadeli destek/direnç seviyeleri yakından izlenmeli. #BIST100 #borsa (YTD)",
            f"Son Dakika: {title[:80]}. Bu gelişmenin endeks ve öncü hisseler üzerindeki takas ve para giriş/çıkış etkileri kritik olacak. Pozisyonlarda temkinli kalmakta fayda var. #hisse #ekonomi (YTD)",
            f"Piyasa Notu: {title[:85]}. Gelişmenin orta vadeli bilançolara yansıması belirleyici olacaktır. Trend kırılımlarına dikkat edilmeli. #BIST100 #borsa (YTD)"
        ]
        return random.choice(templates)

    def generate_chart_tweet(self, indicators: Dict[str, Any]) -> str:
        """
        Generates technical commentary from indicators (RSI, EMA, support/resistance, trend).
        """
        sym = indicators.get("symbol", "THYAO")
        price = indicators.get("current_price", 0)
        rsi = indicators.get("rsi", 50)
        ema9 = indicators.get("ema9", price)
        ema21 = indicators.get("ema21", price)
        support = indicators.get("support", price)
        resistance = indicators.get("resistance", price)
        trend = indicators.get("trend", "Nötr")

        prompt = f"""
Hisse/Grafik: {sym}
Son Fiyat: {price} TL
RSI (14): {rsi}
EMA (9): {ema9} TL | EMA (21): {ema21} TL
Destek: {support} TL | Direnç: {resistance} TL
Teknik Görünüm: {trend}

Görev: Bu teknik göstergelere dayanarak grafiği yorumlayan 200-260 karakterlik uzman bir teknik analiz tweeti yaz. Sonuna (YTD) ekle.
"""
        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(prompt, BIST_ANALYST_SYSTEM_PROMPT)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(prompt, BIST_ANALYST_SYSTEM_PROMPT)

        if ai_response:
            return ai_response

        # Technical chart fallback
        rsi_comment = "RSI aşırı satım bölgesinden tepki arayışında" if rsi < 35 else ("RSI aşırı alım bölgesinde dinlenme sinyali veriyor" if rsi > 70 else f"RSI {rsi} seviyesinde dengeli")
        return f"#{sym} {price} TL. {rsi_comment}. EMA9 ({ema9} TL) ve EMA21 ({ema21} TL) takibimizde. {support} TL destek, {resistance} TL üzeri kapanışlar momentum kazandırır. Trend: {trend}. #BIST100 #teknikanaliz (YTD)"



if __name__ == "__main__":
    from market_data import BISTMarketData
    bist = BISTMarketData()
    m_data = bist.get_market_overview()
    gen = BISTContentGenerator(provider="auto")
    tweet = gen.generate_bist_tweet(m_data)
    reply = gen.generate_reply(tweet)
    print("Generated Tweet:\n", tweet)
    print("\nGenerated Reply:\n", reply)
