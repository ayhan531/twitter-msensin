"""
FastAPI Web Management Dashboard & API for X BIST Bot
Provides a modern Web UI to manage accounts, live news, charts, and auto-engagement.
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.browser import TwitterBrowserManager
from core.ai_generator import BISTContentGenerator
from core.market_data import BISTMarketData
from core.news_service import BISTNewsService
from core.chart_service import BISTChartService
from core.engagement_pod import EngagementPodManager
from core.twitter_actions import TwitterActions

CONFIG_FILE = ROOT_DIR / "config" / "config.json"
STATIC_DIR = ROOT_DIR / "web" / "static"
TEMPLATES_DIR = ROOT_DIR / "web" / "templates"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "charts").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="𝕏 BIST 100 AI Automation & Engagement Pod")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Global Services
browser_mgr = TwitterBrowserManager()
market_data = BISTMarketData()
news_service = BISTNewsService()
chart_service = BISTChartService()

# Global Activity Logs (in-memory circular buffer)
activity_logs = []

def log_event(message: str, level: str = "info"):
    timestamp = time.strftime("%H:%M:%S")
    entry = {"time": timestamp, "message": message, "level": level}
    activity_logs.insert(0, entry)
    if len(activity_logs) > 100:
        activity_logs.pop()
    print(f"[{timestamp}] [{level.upper()}] {message}")

log_event("Sistem başlatıldı, servisler hazır.")

def get_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"accounts": [], "ai_settings": {}, "autopilot": {"enabled": False, "interval_minutes": 60}}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_ai_generator() -> BISTContentGenerator:
    cfg = get_config()
    ai_settings = cfg.get("ai_settings", {})
    provider = ai_settings.get("provider", "auto")
    gemini_key = ai_settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    groq_key = ai_settings.get("groq_api_key") or os.getenv("GROQ_API_KEY")
    return BISTContentGenerator(provider=provider, api_key=gemini_key or groq_key)

# Autopilot Background Worker
autopilot_thread = None
autopilot_running = False

def autopilot_worker():
    global autopilot_running
    log_event("Otomatik Pilot iş parçacığı aktif.", "success")
    while autopilot_running:
        try:
            cfg = get_config()
            interval = cfg.get("autopilot", {}).get("interval_minutes", 60) * 60
            accounts = cfg.get("accounts", [])
            
            if accounts and any(browser_mgr.has_session(a.get("username", "")) for a in accounts):
                analyst = next((a.get("username") for a in accounts if a.get("role") == "analyst"), accounts[0].get("username"))
                helpers = [a.get("username") for a in accounts if a.get("username") != analyst and browser_mgr.has_session(a.get("username"))]

                log_event(f"Otomatik Pilot döngüsü tetiklendi: @{analyst} analiz paylaşacak...", "info")
                ai_gen = get_ai_generator()
                pod_mgr = EngagementPodManager(browser_mgr, ai_gen)
                pod_mgr.post_and_cross_boost(analyst, helpers, headless=True)
                log_event(f"Otomatik Pilot döngüsü tamamlandı. Sonraki döngü: {interval // 60} dakika sonra.", "success")
            else:
                log_event("Otomatik Pilot: Aktif oturumlu hesap bulunamadı, bekleniyor...", "warning")

            # Sleep in small slices to allow rapid cancellation
            for _ in range(int(interval // 5)):
                if not autopilot_running:
                    break
                time.sleep(5)
        except Exception as e:
            log_event(f"Otomatik Pilot hatası: {e}", "error")
            time.sleep(60)

# ----------------- ROUTES -----------------

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_system_status():
    cfg = get_config()
    accounts = cfg.get("accounts", [])
    account_status = []
    for a in accounts:
        uname = a.get("username", "")
        has_session = browser_mgr.has_session(uname)
        account_status.append({
            "username": uname,
            "role": a.get("role", "helper"),
            "connected": has_session,
            "has_token": bool(a.get("auth_token"))
        })

    return {
        "accounts": account_status,
        "autopilot": cfg.get("autopilot", {"enabled": False, "interval_minutes": 60}),
        "ai_settings": cfg.get("ai_settings", {}),
        "total_accounts": len(accounts),
        "active_sessions": sum(1 for a in account_status if a["connected"])
    }

class AddAccountPayload(BaseModel):
    username: str
    role: str = "helper"
    auth_token: str
    ct0: Optional[str] = None

@app.post("/api/accounts/add")
async def add_account(payload: AddAccountPayload):
    uname = payload.username.strip().lstrip("@")
    if not uname or not payload.auth_token:
        return JSONResponse({"success": False, "error": "Kullanıcı adı ve auth_token zorunludur"}, status_code=400)

    # Save session cookie
    browser_mgr.create_session_from_cookies(uname, payload.auth_token, payload.ct0)
    
    cfg = get_config()
    accs = cfg.get("accounts", [])
    # Update or append
    existing = next((a for a in accs if a.get("username") == uname), None)
    if existing:
        existing["role"] = payload.role
        existing["auth_token"] = payload.auth_token
        existing["ct0"] = payload.ct0 or ""
    else:
        accs.append({
            "username": uname,
            "role": payload.role,
            "auth_token": payload.auth_token,
            "ct0": payload.ct0 or ""
        })
    cfg["accounts"] = accs
    save_config(cfg)
    log_event(f"@{uname} hesabı oturum çerezleriyle sisteme eklendi.", "success")
    return {"success": True, "message": f"@{uname} başarıyla bağlandı"}

class DeleteAccountPayload(BaseModel):
    username: str

@app.post("/api/accounts/delete")
async def delete_account(payload: DeleteAccountPayload):
    uname = payload.username.strip().lstrip("@")
    cfg = get_config()
    cfg["accounts"] = [a for a in cfg.get("accounts", []) if a.get("username") != uname]
    save_config(cfg)
    session_file = browser_mgr.get_session_file(uname)
    if session_file.exists():
        try:
            session_file.unlink()
        except Exception:
            pass
    log_event(f"@{uname} hesabı silindi.", "info")
    return {"success": True}

@app.get("/api/market")
async def get_market():
    return market_data.get_market_overview()

@app.get("/api/news")
async def get_news():
    return news_service.fetch_latest_news(limit=15)

class GenerateNewsTweetPayload(BaseModel):
    title: str
    source: str

@app.post("/api/news/generate")
async def generate_news_tweet(payload: GenerateNewsTweetPayload):
    ai_gen = get_ai_generator()
    tweet_text = ai_gen.generate_news_tweet({"title": payload.title, "source": payload.source})
    return {"success": True, "tweet": tweet_text}

@app.get("/api/chart/{symbol}")
async def get_chart_analysis(symbol: str):
    analysis = chart_service.analyze_symbol(symbol)
    chart_url = chart_service.generate_chart_image(symbol)
    analysis["chart_url"] = chart_url
    return analysis

class GenerateChartTweetPayload(BaseModel):
    symbol: str

@app.post("/api/chart/generate")
async def generate_chart_tweet(payload: GenerateChartTweetPayload):
    analysis = chart_service.analyze_symbol(payload.symbol)
    ai_gen = get_ai_generator()
    tweet_text = ai_gen.generate_chart_tweet(analysis)
    return {"success": True, "tweet": tweet_text, "analysis": analysis}

class PostTweetPayload(BaseModel):
    account: str
    text: str
    auto_boost: bool = True
    attach_chart: bool = False
    chart_symbol: Optional[str] = "THYAO"

@app.post("/api/tweet/post")
async def post_tweet_endpoint(payload: PostTweetPayload, background_tasks: BackgroundTasks):
    uname = payload.account.strip().lstrip("@")
    if not browser_mgr.has_session(uname):
        return JSONResponse({"success": False, "error": f"@{uname} için aktif oturum yok. Önce bağlayın."}, status_code=400)

    # Prepare chart image if requested
    media_file_path = None
    if payload.attach_chart and payload.chart_symbol:
        chart_url = chart_service.generate_chart_image(payload.chart_symbol)
        if chart_url:
            filename = os.path.basename(chart_url.split("?")[0])
            media_file_path = str(STATIC_DIR / "charts" / filename)

    log_event(f"@{uname} üzerinden tweet gönderimi başlatılıyor{' (Grafikli)' if media_file_path else ''}...", "info")

    def run_post_and_boost():
        cfg = get_config()
        helpers = [a.get("username") for a in cfg.get("accounts", []) if a.get("username") != uname and browser_mgr.has_session(a.get("username"))]
        ai_gen = get_ai_generator()
        pod_mgr = EngagementPodManager(browser_mgr, ai_gen)
        
        if payload.auto_boost and helpers:
            res = pod_mgr.post_and_cross_boost(uname, helpers, custom_tweet=payload.text, media_path=media_file_path, headless=True)
            log_event(f"Tweet paylaşıldı ve {len(helpers)} hesapla kasıldı!", "success")
        else:
            context = browser_mgr.launch_context(uname, headless=True)
            try:
                page = context.new_page()
                actions = TwitterActions(page)
                res = actions.post_tweet(payload.text, media_path=media_file_path)
                if res.get("success"):
                    log_event(f"Tweet başarıyla paylaşıldı: {payload.text[:50]}...", "success")
                else:
                    log_event(f"Tweet gönderilemedi: {res.get('error')}", "error")
            finally:
                context.close()
                browser_mgr.stop()

    background_tasks.add_task(run_post_and_boost)
    return {"success": True, "message": "Tweet gönderim ve kasma işlemi arka planda başlatıldı"}

class PersonaSettingsPayload(BaseModel):
    preset: str = "analyst"  # 'analyst', 'trader', 'guru', 'custom'
    custom_prompt: Optional[str] = None

@app.post("/api/settings/persona")
async def save_persona_settings(payload: PersonaSettingsPayload):
    cfg = get_config()
    cfg["persona_settings"] = {
        "preset": payload.preset,
        "custom_prompt": payload.custom_prompt or ""
    }
    save_config(cfg)
    log_event(f"Yapay Zeka karakteri güncellendi: {payload.preset}", "success")
    return {"success": True, "persona_settings": cfg["persona_settings"]}

class BoostTweetPayload(BaseModel):
    tweet_url: str
    exclude_account: Optional[str] = None

@app.post("/api/pod/boost")
async def boost_tweet_endpoint(payload: BoostTweetPayload, background_tasks: BackgroundTasks):
    url = payload.tweet_url.strip()
    if not url or ("x.com" not in url and "twitter.com" not in url):
        return JSONResponse({"success": False, "error": "Geçerli bir X/Twitter URL'si giriniz."}, status_code=400)

    cfg = get_config()
    exclude = (payload.exclude_account or "").strip().lstrip("@").lower()
    helpers = [a.get("username") for a in cfg.get("accounts", []) if a.get("username").lower() != exclude and browser_mgr.has_session(a.get("username"))]

    if not helpers:
        return JSONResponse({"success": False, "error": "Etkileşim yapacak oturumu açık hesap bulunamadı"}, status_code=400)

    log_event(f"{url} için {len(helpers)} hesapla etkileşim havuzu başlatılıyor...", "info")

    def run_boost():
        ai_gen = get_ai_generator()
        pod_mgr = EngagementPodManager(browser_mgr, ai_gen)
        pod_mgr.boost_tweet(url, helpers, do_like=True, do_retweet=True, do_comment=True, headless=True)
        log_event(f"{url} için etkileşim havuzu görevi başarıyla tamamlandı!", "success")

    background_tasks.add_task(run_boost)
    return {"success": True, "message": f"{len(helpers)} hesapla etkileşim başlatıldı"}

class AutopilotTogglePayload(BaseModel):
    enabled: bool
    interval_minutes: int = 60

@app.post("/api/autopilot/toggle")
async def toggle_autopilot(payload: AutopilotTogglePayload):
    global autopilot_thread, autopilot_running
    cfg = get_config()
    cfg["autopilot"] = {
        "enabled": payload.enabled,
        "interval_minutes": payload.interval_minutes
    }
    save_config(cfg)

    if payload.enabled and not autopilot_running:
        autopilot_running = True
        autopilot_thread = threading.Thread(target=autopilot_worker, daemon=True)
        autopilot_thread.start()
        log_event(f"Otomatik Pilot AÇILDI ({payload.interval_minutes} dakikada bir paylaşım)", "success")
    elif not payload.enabled and autopilot_running:
        autopilot_running = False
        log_event("Otomatik Pilot KAPATILDI", "warning")

    return {"success": True, "autopilot": cfg["autopilot"]}

@app.get("/api/logs")
async def get_logs():
    return {"logs": activity_logs}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n[🚀] X BIST Bot Web Paneli Başlatılıyor: http://localhost:{port}\n")
    uvicorn.run("web.app:app", host="0.0.0.0", port=port, reload=False)
