"""
Real-Time BIST & Financial News Service
Fetches live breaking news from Google News RSS, Bloomberg HT, and Turkish financial sources without any API cost.
"""

import xml.etree.ElementTree as ET
import requests
import html
import re
import time
import warnings
from typing import List, Dict, Any, Optional

warnings.filterwarnings("ignore")

RSS_FEEDS = [
    {
        "name": "Borsa & BIST",
        "url": "https://news.google.com/rss/search?q=BIST+OR+Borsa+Istanbul+OR+hisse+when:1d&hl=tr&gl=TR&ceid=TR:tr"
    },
    {
        "name": "KAP & Şirket Haberleri",
        "url": "https://news.google.com/rss/search?q=KAP+OR+BIST+bilanco+OR+temettu+when:1d&hl=tr&gl=TR&ceid=TR:tr"
    },
    {
        "name": "Ekonomi & TCMB",
        "url": "https://news.google.com/rss/search?q=Merkez+Bankasi+OR+faiz+OR+enflasyon+OR+dolar+when:1d&hl=tr&gl=TR&ceid=TR:tr"
    }
]

class BISTNewsService:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        self.cached_news = []
        self.last_fetch = 0
        self.cache_ttl = 180  # 3 minutes

    def clean_text(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', raw_html)
        return html.unescape(clean).strip()

    def fetch_latest_news(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Fetches the freshest BIST and finance news headlines.
        """
        now = time.time()
        if self.cached_news and (now - self.last_fetch < self.cache_ttl):
            return self.cached_news[:limit]

        all_news = []
        seen_titles = set()

        for feed in RSS_FEEDS:
            try:
                resp = requests.get(feed["url"], headers=self.headers, timeout=8)
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item"):
                    raw_title = item.find("title").text or ""
                    link = item.find("link").text or ""
                    pub_date = item.find("pubDate").text or ""
                    
                    title = self.clean_text(raw_title)
                    # Deduplicate
                    norm_title = re.sub(r'[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ]', '', title.lower())
                    if norm_title in seen_titles:
                        continue
                    seen_titles.add(norm_title)

                    # Extract source if available (e.g. "Başlık - Kaynak Adı")
                    source = feed["name"]
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0]
                        source = parts[1]

                    all_news.append({
                        "title": title,
                        "source": source,
                        "link": link,
                        "pub_date": pub_date,
                        "category": feed["name"]
                    })
            except Exception:
                continue

        if all_news:
            self.cached_news = all_news
            self.last_fetch = now

        return self.cached_news[:limit]

    def generate_news_commentary_prompt(self, news_item: Dict[str, Any]) -> str:
        """
        Creates a structured prompt for AI to analyze a specific news event.
        """
        return f"""
Haber Başlığı: {news_item.get('title')}
Kaynak: {news_item.get('source')}

Görev: Bu haberi Borsa İstanbul (BIST 100), sektörler ve hisseler üzerindeki olası etkileri açısından değerlendiren profesyonel, çarpıcı ve teknik bir X (Twitter) analizi yaz.
Kurallar:
1. Uzunluk: 200 - 260 karakter arasında olsun.
2. Üslup: Ciddi, rasyonel, piyasa uzmanı dili.
3. İlgili hisse ve borsa etiketleri ekle (örn: #BIST100 #borsa).
4. Sonuna mutlaka (YTD) ekle.
"""

if __name__ == "__main__":
    service = BISTNewsService()
    news = service.fetch_latest_news(5)
    print("Latest News:")
    for n in news:
        print(f"- [{n['source']}] {n['title']}")
