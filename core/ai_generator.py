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
    PERSONAS,
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

    def generate_bist_tweet(self, market_data: Dict[str, Any], target_symbol: Optional[str] = None, persona_key: str = "kurumsal_analist") -> str:
        """
        Generates an authentic BIST analysis tweet strictly synchronized with the chosen stock and persona.
        """
        index = market_data.get("index") or {}
        stocks = market_data.get("stocks") or []
        sentiment = market_data.get("sentiment", "Yatay")

        persona_data = PERSONAS.get(persona_key, PERSONAS.get("kurumsal_analist"))
        system_prompt = persona_data["system_prompt"]

        # Ensure STRICT synchronization: If target_symbol is provided, find it!
        stock = None
        if target_symbol:
            clean_sym = target_symbol.upper().replace(".IS", "")
            stock = next((s for s in stocks if s.get("symbol", "").upper() == clean_sym), None)
            if not stock:
                # Fetch on demand to ensure accurate data
                from core.market_data import BISTMarketData
                bmd = BISTMarketData()
                stock = bmd.get_ticker_data(clean_sym)

        if not stock:
            stock = stocks[0] if stocks else {
                "symbol": "THYAO",
                "price": 273.5,
                "change": -2.5,
                "change_pct": -0.9,
                "day_high": 277.0,
                "day_low": 271.0
            }

        sym = stock.get("symbol", "THYAO")
        price = stock.get("price", 270.0)
        chg_pct = stock.get("change_pct", 0.0)

        # Context prompt strictly for this stock
        context_prompt = f"""
Canlı Borsa İstanbul Piyasa Verileri:
- BIST 100 Endeksi: {index.get('price', '11.720')} TL (Değişim: %{index.get('change_pct', 0)})
- Genel Piyasa Havası: {sentiment}
- Analiz Edilen Hisse: {sym} ({price} TL, Değişim: %{chg_pct}%, Gün İçi: {stock.get('day_low')} - {stock.get('day_high')} TL)

Karakter Görevi: Karakterine ve üslubuna tam uyarak #{sym} için X (Twitter) analizi yaz. Mutlaka #{sym} hissesinden bahset, başka hisse uydurma. Sonuna (YTD) ekle.
"""

        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(context_prompt, system_prompt)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(context_prompt, system_prompt)

        if ai_response:
            return ai_response

        # Use persona-specific fallback templates
        support = round(price * 0.965, 2)
        resistance = round(price * 1.035, 2)
        templates = persona_data.get("fallback_templates", FALLBACK_TEMPLATES)
        template = random.choice(templates)
        
        return template.format(
            symbol=sym,
            price=price,
            change_pct=chg_pct,
            support=support,
            resistance=resistance,
            day_high=stock.get("day_high", round(price * 1.02, 2)),
            day_low=stock.get("day_low", round(price * 0.98, 2)),
            trend_label=sentiment,
            index_price=index.get("price", "11.720"),
            index_change_pct=index.get("change_pct", "-0.5")
        )

    def generate_chart_tweet(self, indicators: Dict[str, Any], persona_key: str = "kurumsal_analist") -> str:
        """
        Generates technical commentary strictly synchronized with the given chart indicators and persona across all asset classes.
        """
        sym = indicators.get("symbol", "THYAO")
        price = indicators.get("current_price", 0)
        rsi = indicators.get("rsi", 50)
        ema9 = indicators.get("ema9", price)
        ema21 = indicators.get("ema21", price)
        support = indicators.get("support", price)
        resistance = indicators.get("resistance", price)
        trend = indicators.get("trend", "Nötr")
        asset_type = indicators.get("asset_type", "Piyasa Varlığı")
        c_unit = indicators.get("currency_unit", "TL")

        persona_data = PERSONAS.get(persona_key, PERSONAS.get("kurumsal_analist"))
        system_prompt = persona_data["system_prompt"]

        market_term = "kripto para / coin terimleri" if "Kripto" in asset_type else ("altın / emtia terimleri" if "Emtia" in asset_type else ("forex / kur paritesi terimleri" if "Döviz" in asset_type or "Forex" in asset_type else "hisse senedi / borsa terimleri"))

        prompt = f"""
Grafik & Teknik Analiz Verileri:
- Varlık / Enstrüman: #{sym} ({asset_type})
- Güncel Fiyat: {price:,.2f} {c_unit}
- RSI (14): {rsi}
- EMA 9: {ema9:,.2f} {c_unit} | EMA 21: {ema21:,.2f} {c_unit}
- Destek Seviyesi: {support:,.2f} {c_unit} | Direnç Seviyesi: {resistance:,.2f} {c_unit}
- Genel Trend: {trend}

Görev: Bu teknik mum grafiği göstergelerine dayanarak #{sym} ({asset_type}) için seçilen karaktere tam uygun, profesyonel ve etkileyici bir tweet yaz. 
Varlığın türüne ({asset_type}) göre doğru piyasa terimlerini ({market_term}) kullan. 
Mutlaka #{sym} etiketinden ve destek/direnç seviyelerinden bahset. Fiyat birimini ({c_unit}) doğru kullan. Sonuna (YTD) ekle.
"""
        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(prompt, system_prompt)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(prompt, system_prompt)

        if ai_response:
            return ai_response

        # Fallback templates for this persona
        templates = persona_data.get("fallback_templates", FALLBACK_TEMPLATES)
        template = random.choice(templates)
        formatted = template.format(
            symbol=sym,
            price=price,
            change_pct=round(((price - ema9) / ema9) * 100, 2) if ema9 else 0.0,
            support=support,
            resistance=resistance,
            day_high=resistance,
            day_low=support,
            trend_label=trend,
            rsi=rsi,
            ema9=ema9,
            ema21=ema21
        )
        if "Kripto" in asset_type:
            formatted = formatted.replace("BIST 100 öncü hisselerinden", "Kripto para piyasasında")
            formatted = formatted.replace("hisselerinde", "kripto piyasasında")
            formatted = formatted.replace("hissesinde", "grafiğinde")
        elif "Emtia" in asset_type:
            formatted = formatted.replace("BIST 100 öncü hisselerinden", "Küresel emtia piyasasında")
            formatted = formatted.replace("hisselerinde", "emtia piyasasında")
            formatted = formatted.replace("hissesinde", "grafiğinde")
        elif "Döviz" in asset_type or "Forex" in asset_type:
            formatted = formatted.replace("BIST 100 öncü hisselerinden", "Döviz ve parite piyasasında")
            formatted = formatted.replace("hisselerinde", "kurlarda")
            formatted = formatted.replace("hissesinde", "paritesinde")

        if c_unit != "TL":
            formatted = formatted.replace(" TL", f" {c_unit}")
        return formatted

    def generate_reply(
        self, 
        parent_tweet_text: str, 
        custom_pool: Optional[List[str]] = None, 
        custom_system_prompt: Optional[str] = None,
        persona_key: str = "kurumsal_analist"
    ) -> str:
        """
        Generates an authentic BIST reply to engage on a tweet using the specified persona or custom pool.
        """
        # If user defined a custom comment pool and wants to use it
        if custom_pool and len(custom_pool) > 0 and random.random() < 0.6:
            return random.choice(custom_pool)

        persona_data = PERSONAS.get(persona_key, PERSONAS.get("kurumsal_analist"))
        system_prompt = custom_system_prompt or persona_data.get("reply_prompt", BIST_REPLY_PROMPT)
        
        prompt = f"Şu tweete cevap yaz:\n\"{parent_tweet_text}\""
        
        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(prompt, system_prompt)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(prompt, system_prompt)

        if ai_response:
            return ai_response

        # Fallback to custom pool if provided, else persona-specific fallback replies
        if custom_pool and len(custom_pool) > 0:
            return random.choice(custom_pool)

        replies = persona_data.get("fallback_replies", FALLBACK_REPLIES)
        return random.choice(replies)

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

    def generate_casual_community_tweet(self, category: str = "auto", persona_key: str = "sevecen_dost") -> str:
        """
        Generates friendly, human community tweets without charts:
        - Morning greetings ("Günaydın millet...")
        - Midday market checks
        - Closing / evening farewells
        - Market psychology / patience / discipline
        """
        now_hour = 10
        try:
            from datetime import datetime, timezone, timedelta
            now_hour = datetime.now(timezone(timedelta(hours=3))).hour
        except Exception:
            pass

        if category == "auto":
            if 7 <= now_hour <= 11:
                category = "morning"
            elif 12 <= now_hour <= 15:
                category = "midday"
            elif 17 <= now_hour <= 21:
                category = "closing"
            else:
                category = "sentiment"

        system_prompt = f"""
Sen Borsa İstanbul yatırımcı topluluğuyla samimi ve içten bağ kuran bir Türk borsa fenomenisin.
Karakter: {persona_key}
Görevin: Takipçilerine sıcak, samimi, esprili ve doğal bir Türkçe ile etkileşim tweeti yazmak. Asla bot gibi veya resmi konuşma.
Kategori: {category}
Kurallar:
- Emojileri yerinde ve doğal kullan.
- "Günaydın millet", "Bereketli seanslar", "Nasıl gidiyor borsa dostları" gibi doğal hitaplar kullan.
- Maksimum 180-240 karakter olsun.
"""
        prompt = f"Lütfen '{category}' temalı samimi bir topluluk tweeti yaz."

        ai_response = None
        if self.provider == "gemini":
            ai_response = self._call_gemini_api(prompt, system_prompt)
        elif self.provider == "groq":
            ai_response = self._call_groq_api(prompt, system_prompt)

        if ai_response:
            return ai_response

        # Rich algorithmic fallback templates
        morning_pool = [
            "Günaydın millet! ☀️ Kahveler hazır mı? Borsa İstanbul'da bol kazançlı, yeşillerin bol olduğu bereketli bir seans olsun herkese. Disiplin ve planımıza sadık kalıyoruz. #BIST100 #günaydın",
            "Herkese günaydın borsa dostları! Yeni gün, yeni fırsatlar. Açılış öncesi sakinliğimizi koruyup destek seviyelerine dikkat ediyoruz. Bereketli seanslar olsun! ☕📈 #BIST100",
            "Günaydın millet! 🚀 Seans başlamak üzere. Panik yapmadan, acele etmeden stratejimizi uyguluyoruz. Bugünün kazananı sabredenler olsun! #borsa #günaydın",
            "Günaydın herkese! ☕ Ekran başına geçenlere selam olsun. Moraller yüksek, hedefler net. Bol yeşilli bir seans dilerim dostlar! #BIST100"
        ]

        midday_pool = [
            "Öğle arası geldi millet. Endekste testere piyasası devam ediyor, gün içi dalgalara kapılıp stopsuz iş yapmayın. Çaylar kahveler tazelensin! ☕📊 #BIST100",
            "Piyasa tam bir sabır sınavı veriyor bugün. Hacim tarafı kritik seviyelerde. Sizde durumlar nasıl millet, seans nasıl geçiyor? 💬 #borsa #hisse",
            "Öğle arası molası! Portföylere çok takılıp stres yapmayın millet, plan tıkır tıkır işliyorsa arkana yaslan. Bereketli ikinci yarı olsun! 🥪☕ #BIST100"
        ]

        closing_pool = [
            "Zil çaldı, bugünkü seansı da geride bıraktık millet! Kapanış rakamlarını sindirme zamanı. Kazananlara afiyet olsun, zararda olanlar moral bozmasın, borsa fırsat bitmez. İyi akşamlar! 🌙 #BIST100",
            "Kapanış geldi dostlar. Günün yorgunluğunu atalım, akşam analizleri için ekran başına geçeriz. Herkese huzurlu ve keyifli bir akşam dilerim! ☕✨ #borsa",
            "Günü kapattık millet. Kimisi kar realize etti, kimisi sabırla beklemeye devam ediyor. Günün özeti: Sakin kalan kazanır. Herkese iyi akşamlar! 🌆 #BIST100"
        ]

        sentiment_pool = [
            "Borsada en büyük sermaye para değil, sabırdır millet. Trend senin dostundur, trende karşı inatlaşan kaybeder. Planına sadık kal, arkana yaslan. 💎🙌 #BIST100 #borsa",
            "Her gün işlem açmak zorunda değilsin millet. Bazen nakitte beklemek veya kenarda izlemek en karlı hamledir. Psikolojiyi sağlam tutan kazanır! 🧠📈 #hisse #borsa",
            "Düşerken panikle satan, çıkarken FOMO ile tepeden alan olmayın dostlar. Planınız varsa borsa stres değil, keyif verir. Bereketiniz bol olsun! 🎯 #BIST100"
        ]

        if category == "morning":
            return random.choice(morning_pool)
        elif category == "midday":
            return random.choice(midday_pool)
        elif category == "closing":
            return random.choice(closing_pool)
        else:
            return random.choice(sentiment_pool)



if __name__ == "__main__":
    from market_data import BISTMarketData
    bist = BISTMarketData()
    m_data = bist.get_market_overview()
    gen = BISTContentGenerator(provider="auto")
    tweet = gen.generate_bist_tweet(m_data)
    reply = gen.generate_reply(tweet)
    print("Generated Tweet:\n", tweet)
    print("\nGenerated Reply:\n", reply)
