"""
FastAPI Web Management Dashboard & API for X BIST Bot
Provides a modern Web UI to manage accounts, live news, charts, and auto-engagement.
"""

import os
import sys
import json
import time
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Turkey Timezone (UTC+3, constant year-round)
TURKEY_TZ = timezone(timedelta(hours=3))

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
from core.watchlist_monitor import WatchlistMonitor
from core.telegram_bridge import TelegramBridgeManager

CONFIG_FILE = ROOT_DIR / "config" / "config.json"
STATIC_DIR = ROOT_DIR / "web" / "static"
TEMPLATES_DIR = ROOT_DIR / "web" / "templates"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "charts").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "telegram_media").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="𝕏 BIST 100 AI Automation & Engagement Pod")

# Enable CORS so Bookmarklet / Chrome Extensions can push sessions directly to localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Global Services
browser_mgr = TwitterBrowserManager()
market_data = BISTMarketData()
news_service = BISTNewsService()
chart_service = BISTChartService()
watchlist_monitor = None

def get_watchlist_monitor() -> WatchlistMonitor:
    global watchlist_monitor
    if not watchlist_monitor:
        ai_gen = get_ai_generator()
        watchlist_monitor = WatchlistMonitor(browser_mgr, ai_gen)
    return watchlist_monitor

# Ensure UTF-8 output encoding across all platforms
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Global Activity Logs (in-memory circular buffer)
activity_logs = []

def log_event(message: str, level: str = "info"):
    timestamp = time.strftime("%H:%M:%S")
    entry = {"time": timestamp, "message": message, "level": level}
    activity_logs.insert(0, entry)
    if len(activity_logs) > 100:
        activity_logs.pop()
    try:
        print(f"[{timestamp}] [{level.upper()}] {message}")
    except Exception:
        safe_msg = message.encode("ascii", errors="replace").decode("ascii")
        print(f"[{timestamp}] [{level.upper()}] {safe_msg}")

log_event("Sistem başlatıldı, servisler hazır.")

# Default Configuration for Smart Scheduler
DEFAULT_SCHEDULER = {
    "enabled": False,
    "mode": "times",  # "times" (belirli saatler) or "interval" (dakika aralığı)
    "times": ["09:45", "13:00", "18:15"],
    "frequency": "every_day",  # "every_day", "weekdays", "every_x_days"
    "every_x_days": 2,
    "interval_minutes": 60,
    "attach_chart": True,
    "auto_boost": True,
    "persona": "rotate",  # "rotate" or specific persona
    "stock_symbol": "auto_rotate",  # "auto_rotate" or specific symbol
    "last_run_epoch": 0
}

def get_config() -> dict:
    if not CONFIG_FILE.exists():
        return {
            "accounts": [],
            "ai_settings": {},
            "autopilot": {"enabled": False, "interval_minutes": 60},
            "scheduler": DEFAULT_SCHEDULER
        }
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        if "scheduler" not in cfg:
            cfg["scheduler"] = DEFAULT_SCHEDULER
        return cfg

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def ensure_sessions_restored():
    """
    Ensures session cookies on disk match accounts in config.json.
    Essential for Render container restarts where local storage is fresh.
    """
    cfg = get_config()
    for a in cfg.get("accounts", []):
        u = a.get("username")
        token = a.get("auth_token")
        ct0 = a.get("ct0")
        if u and token and not browser_mgr.has_session(u):
            browser_mgr.create_session_from_cookies(u, token, ct0)
            log_event(f"Oturum çerezleri otomatik oluşturuldu: @{u}", "success")

# Ensure sessions on boot
ensure_sessions_restored()

def get_ai_generator() -> BISTContentGenerator:
    cfg = get_config()
    ai_settings = cfg.get("ai_settings", {})
    provider = ai_settings.get("provider", "auto")
    gemini_key = ai_settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    groq_key = ai_settings.get("groq_api_key") or os.getenv("GROQ_API_KEY")
    return BISTContentGenerator(provider=provider, api_key=gemini_key or groq_key)

# ----------------- ADVANCED SCHEDULER & AUTOPILOT ENGINE -----------------

POPULAR_STOCKS = ["THYAO", "ASELS", "EREGL", "TUPRS", "AKBNK", "BIMAS", "XU100", "SASA"]
PERSONAS = ["kurumsal_analist", "agresif_trader", "temkinli_yatirimci", "sevecen_dost"]
rotation_counter = 0

telegram_bridge = None

def get_telegram_bridge() -> TelegramBridgeManager:
    global telegram_bridge
    if not telegram_bridge:
        telegram_bridge = TelegramBridgeManager(
            browser_mgr=browser_mgr,
            ai_gen=get_ai_generator(),
            get_config_fn=get_config,
            save_config_fn=save_config,
            log_event_fn=log_event
        )
    return telegram_bridge

def execute_scheduled_task(source: str = "Zamanlayıcı") -> dict:
    """
    Executes automated chart generation, AI analysis, tweet posting and cross-boosting.
    Supports smart mix:
    - Candlestick chart analysis (with photo)
    - Stock focus market insight (without photo)
    - Friendly community tweets ('Günaydın millet', 'Seans kapanışı', 'Borsada sabır') (without photo)
    """
    global rotation_counter
    ensure_sessions_restored()
    cfg = get_config()
    accounts = cfg.get("accounts", [])
    if not accounts:
        log_event(f"[{source}] Paylaşım yapacak hesap bulunamadı.", "warning")
        return {"success": False, "error": "Hesap bulunamadı"}

    sched = cfg.get("scheduler", DEFAULT_SCHEDULER)
    analyst = next((a.get("username") for a in accounts if a.get("role") == "analyst"), accounts[0].get("username"))
    helpers = [a.get("username") for a in accounts if a.get("username") != analyst and browser_mgr.has_session(a.get("username"))]

    if not browser_mgr.has_session(analyst):
        log_event(f"[{source}] @{analyst} için oturum hazır değil.", "error")
        return {"success": False, "error": f"@{analyst} için oturum hazır değil"}

    # 1. Select Stock Symbol
    stock_sym = sched.get("stock_symbol", "auto_rotate")
    if stock_sym == "auto_rotate" or not stock_sym:
        stock_sym = POPULAR_STOCKS[rotation_counter % len(POPULAR_STOCKS)]

    # 2. Select Persona
    persona_key = sched.get("persona", "rotate")
    if persona_key == "rotate" or not persona_key:
        persona_key = PERSONAS[rotation_counter % len(PERSONAS)]

    rotation_counter += 1

    # 3. Determine Post Type & Media Attachment
    post_style = sched.get("post_style", "smart_mix")  # "smart_mix", "always_chart", "text_only"
    now_tr = datetime.now(TURKEY_TZ)
    hour = now_tr.hour

    ai_gen = get_ai_generator()
    media_path = None
    tweet_kind = "chart"

    if post_style == "smart_mix":
        # Morning slot (07:30 - 10:30): 55% chance of a warm "Günaydın millet" tweet
        if 7 <= hour <= 10 and (rotation_counter % 2 == 0):
            tweet_kind = "community_morning"
        # Evening slot (17:30 - 21:00): 45% chance of a closing/community tweet
        elif 17 <= hour <= 21 and (rotation_counter % 2 == 1):
            tweet_kind = "community_closing"
        # Midday: 35% chance of pure-text market insight or psychology (no photo)
        elif (rotation_counter % 3 == 0):
            tweet_kind = "text_only"
    elif post_style == "text_only":
        tweet_kind = "text_only"

    if tweet_kind == "community_morning":
        tweet_text = ai_gen.generate_casual_community_tweet("morning", persona_key=persona_key)
        media_path = None
        log_event(f"⏰ [{source}] @{analyst} samimi 'Günaydın millet' tweeti paylaşıyor (Fotoğrafsız)...", "info")
    elif tweet_kind == "community_closing":
        tweet_text = ai_gen.generate_casual_community_tweet("closing", persona_key=persona_key)
        media_path = None
        log_event(f"⏰ [{source}] @{analyst} samimi seans kapanış tweeti paylaşıyor (Fotoğrafsız)...", "info")
    elif tweet_kind == "text_only":
        analysis = chart_service.analyze_symbol(stock_sym)
        tweet_text = ai_gen.generate_chart_tweet(analysis, persona_key=persona_key)
        media_path = None
        log_event(f"⏰ [{source}] @{analyst} #{stock_sym} piyasa analizi paylaşıyor (Fotoğrafsız salt metin)...", "info")
    else:
        # Chart Analysis with Candlestick Image
        chart_url = chart_service.generate_chart_image(stock_sym)
        if chart_url:
            filename = os.path.basename(chart_url.split("?")[0])
            media_path = str(STATIC_DIR / "charts" / filename)
        analysis = chart_service.analyze_symbol(stock_sym)
        tweet_text = ai_gen.generate_chart_tweet(analysis, persona_key=persona_key)
        log_event(f"⏰ [{source}] @{analyst} #{stock_sym} TradingView mum grafiğiyle analiz paylaşıyor...", "info")

    # 4. Post & Cross-Boost
    auto_boost = sched.get("auto_boost", True)
    pod_mgr = EngagementPodManager(browser_mgr, ai_gen)
    if auto_boost and helpers:
        res = pod_mgr.post_and_cross_boost(analyst, helpers, custom_tweet=tweet_text, media_path=media_path, headless=True)
        log_event(f"✅ [{source}] Tweet paylaşıldı ve {len(helpers)} hesapla karşılıklı kasıldı!", "success")
    else:
        ctx = browser_mgr.launch_context(analyst, headless=True)
        try:
            page = ctx.new_page()
            actions = TwitterActions(page)
            res = actions.post_tweet(tweet_text, media_path=media_path)
            if res.get("success"):
                log_event(f"✅ [{source}] Tweet başarıyla paylaşıldı!", "success")
        finally:
            ctx.close()

    # 5. Check Watchlist Targets
    watchlist = cfg.get("watchlist", [])
    if watchlist and helpers:
        monitor = get_watchlist_monitor()
        for target in watchlist:
            target_user = target.get("username") if isinstance(target, dict) else str(target)
            monitor.check_and_engage_target(target_user, helpers, headless=True)

    # Update last run
    sched["last_run_epoch"] = time.time()
    sched["last_run_str"] = datetime.now(TURKEY_TZ).strftime("%Y-%m-%d %H:%M")
    cfg["scheduler"] = sched
    save_config(cfg)

    return {"success": True, "tweet": tweet_text, "stock": stock_sym, "persona": persona_key}

scheduler_thread = None
scheduler_running = False

def scheduler_worker():
    global scheduler_running
    log_event("⏰ Akıllı Zamanlayıcı (Scheduler) arka plan iş parçacığı aktif.", "success")
    last_executed_minute = ""

    while scheduler_running:
        try:
            now_tr = datetime.now(TURKEY_TZ)
            current_minute_str = now_tr.strftime("%Y-%m-%d %H:%M")
            current_time_str = now_tr.strftime("%H:%M")

            if current_minute_str != last_executed_minute:
                cfg = get_config()
                sched = cfg.get("scheduler", DEFAULT_SCHEDULER)

                if sched.get("enabled", False):
                    mode = sched.get("mode", "times")
                    freq = sched.get("frequency", "every_day")

                    # Check Day qualification
                    is_day_qualified = False
                    if freq == "every_day":
                        is_day_qualified = True
                    elif freq == "weekdays":
                        is_day_qualified = now_tr.weekday() < 5  # Mon-Fri
                    elif freq == "every_x_days":
                        interval_days = max(1, int(sched.get("every_x_days", 2)))
                        is_day_qualified = (now_tr.date().toordinal() % interval_days) == 0

                    if is_day_qualified:
                        if mode == "times":
                            scheduled_times = sched.get("times", ["09:45", "13:00", "18:15"])
                            if current_time_str in scheduled_times:
                                last_executed_minute = current_minute_str
                                log_event(f"⏰ Planlanan Saat Geldi ({current_time_str})! Otomatik tweet ve kasma başlıyor...", "info")
                                execute_scheduled_task(source=f"Zamanlayıcı ({current_time_str})")
                        elif mode == "interval":
                            interval_mins = max(10, int(sched.get("interval_minutes", 60)))
                            last_run = sched.get("last_run_epoch", 0)
                            if (time.time() - last_run) >= (interval_mins * 60):
                                last_executed_minute = current_minute_str
                                log_event(f"⏰ Aralıklı Görev Süresi Doldu ({interval_mins} dk)! Paylaşılıyor...", "info")
                                execute_scheduled_task(source=f"Aralıklı Pilot ({interval_mins} dk)")

            time.sleep(15)  # Check every 15 seconds
        except Exception as e:
            log_event(f"Zamanlayıcı döngü hatası: {e}", "error")
            time.sleep(30)

def start_scheduler_worker():
    global scheduler_thread, scheduler_running
    if not scheduler_running:
        scheduler_running = True
        scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
        scheduler_thread.start()

def stop_scheduler_worker():
    global scheduler_running
    scheduler_running = False

# Auto-start scheduler and telegram bridge if enabled on server boot
@app.on_event("startup")
async def startup_event():
    ensure_sessions_restored()
    cfg = get_config()
    if cfg.get("scheduler", {}).get("enabled", False):
        start_scheduler_worker()
    if cfg.get("telegram", {}).get("enabled", False):
        get_telegram_bridge().start()

# ----------------- ROUTES -----------------

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/status")
async def get_system_status():
    ensure_sessions_restored()
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

    now_tr = datetime.now(TURKEY_TZ)
    return {
        "accounts": account_status,
        "autopilot": cfg.get("autopilot", {"enabled": False, "interval_minutes": 60}),
        "scheduler": cfg.get("scheduler", DEFAULT_SCHEDULER),
        "scheduler_running": scheduler_running,
        "current_time_tr": now_tr.strftime("%H:%M"),
        "current_date_tr": now_tr.strftime("%Y-%m-%d"),
        "ai_settings": cfg.get("ai_settings", {}),
        "total_accounts": len(accounts),
        "active_sessions": sum(1 for a in account_status if a["connected"])
    }

@app.get("/api/scheduler")
async def get_scheduler_endpoint():
    cfg = get_config()
    now_tr = datetime.now(TURKEY_TZ)
    return {
        "scheduler": cfg.get("scheduler", DEFAULT_SCHEDULER),
        "scheduler_running": scheduler_running,
        "current_time_tr": now_tr.strftime("%H:%M"),
        "current_date_tr": now_tr.strftime("%Y-%m-%d")
    }

class SchedulerSavePayload(BaseModel):
    enabled: bool
    mode: str = "times"  # "times" or "interval"
    times: List[str] = ["09:45", "13:00", "18:15"]
    frequency: str = "every_day"  # "every_day", "weekdays", "every_x_days"
    every_x_days: int = 2
    interval_minutes: int = 60
    post_style: str = "smart_mix"  # "smart_mix", "always_chart", "text_only"
    attach_chart: bool = True
    auto_boost: bool = True
    persona: str = "rotate"
    stock_symbol: str = "auto_rotate"

@app.post("/api/scheduler/save")
async def save_scheduler_endpoint(payload: SchedulerSavePayload):
    cfg = get_config()
    sched = {
        "enabled": payload.enabled,
        "mode": payload.mode,
        "times": [t.strip() for t in payload.times if t.strip()],
        "frequency": payload.frequency,
        "every_x_days": max(1, payload.every_x_days),
        "interval_minutes": max(10, payload.interval_minutes),
        "post_style": payload.post_style,
        "attach_chart": payload.attach_chart,
        "auto_boost": payload.auto_boost,
        "persona": payload.persona,
        "stock_symbol": payload.stock_symbol,
        "last_run_epoch": cfg.get("scheduler", {}).get("last_run_epoch", 0),
        "last_run_str": cfg.get("scheduler", {}).get("last_run_str", "")
    }
    cfg["scheduler"] = sched
    cfg["autopilot"] = {
        "enabled": payload.enabled,
        "interval_minutes": payload.interval_minutes
    }
    save_config(cfg)

    if payload.enabled:
        start_scheduler_worker()
        log_event(f"⏰ Akıllı Zamanlayıcı AÇILDI ({payload.mode} modu, {payload.frequency}, tarz: {payload.post_style})", "success")
    else:
        stop_scheduler_worker()
        log_event("⏰ Akıllı Zamanlayıcı KAPATILDI", "warning")

    return {"success": True, "scheduler": sched, "scheduler_running": scheduler_running}

@app.post("/api/scheduler/trigger_now")
async def trigger_scheduler_now(background_tasks: BackgroundTasks):
    ensure_sessions_restored()
    log_event("⚡ Manuel tetikleme alındı: Otomatik BIST analizi ve kasma başlatılıyor...", "info")
    background_tasks.add_task(execute_scheduled_task, "Manuel Tetikleme")
    return {"success": True, "message": "Zamanlanmış analiz görevi hemen başlatıldı!"}

# ----------------- TELEGRAM BRIDGE ENDPOINTS -----------------

@app.get("/api/telegram")
async def get_telegram_status():
    tb = get_telegram_bridge()
    tg_cfg = tb.get_telegram_config()
    pending_count = len(tb.current_batch.items) if (tb.current_batch and tb.current_batch.items) else 0
    return {
        "config": tg_cfg,
        "running": tb.running,
        "pending_messages": pending_count,
        "batch_window_minutes": int(tg_cfg.get("batch_window_seconds", 300)) // 60
    }

class TelegramSavePayload(BaseModel):
    enabled: bool
    bot_token: str
    channel_id: str
    batch_window_minutes: int = 5
    auto_boost: bool = True
    account: str = "Borsagenci"

@app.post("/api/telegram/save")
async def save_telegram_endpoint(payload: TelegramSavePayload):
    tb = get_telegram_bridge()
    tg_cfg = {
        "enabled": payload.enabled,
        "bot_token": payload.bot_token.strip(),
        "channel_id": payload.channel_id.strip(),
        "batch_window_seconds": max(60, payload.batch_window_minutes * 60),
        "auto_boost": payload.auto_boost,
        "account": payload.account.strip().lstrip("@"),
        "last_update_id": tb.get_telegram_config().get("last_update_id", 0)
    }
    tb.save_telegram_config(tg_cfg)

    if payload.enabled:
        tb.start()
        log_event(f"📡 Telegram Köprüsü AÇILDI ({payload.batch_window_minutes} dk gruplama penceresi)", "success")
    else:
        tb.stop()
        log_event("📡 Telegram Köprüsü DURDURULDU", "warning")

    return {"success": True, "config": tg_cfg, "running": tb.running}

@app.post("/api/telegram/flush_now")
async def flush_telegram_now(background_tasks: BackgroundTasks):
    tb = get_telegram_bridge()
    background_tasks.add_task(tb.force_flush_now)
    return {"success": True, "message": "Bekleyen Telegram mesaj havuzunu hemen tweetleme görevi başlatıldı!"}

@app.post("/api/telegram/test_check")
async def test_telegram_connection():
    tb = get_telegram_bridge()
    tg_cfg = tb.get_telegram_config()
    token = tg_cfg.get("bot_token", "").strip()
    if not token:
        return JSONResponse({"success": False, "error": "Bot token girilmemiş."}, status_code=400)
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if r.status_code == 200:
            bot_info = r.json().get("result", {})
            return {"success": True, "bot": bot_info, "message": f"Bağlantı başarılı: @{bot_info.get('username')}"}
        else:
            return JSONResponse({"success": False, "error": f"Telegram API Hatası: {r.text}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)

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

class QuickConnectPayload(BaseModel):
    username: Optional[str] = ""
    auth_token: str
    ct0: Optional[str] = ""
    role: str = "helper"

@app.post("/api/accounts/quick_connect")
async def quick_connect(payload: QuickConnectPayload):
    """
    Called by 1-Click Browser Bookmarklet or external extension.
    Instantly registers session without opening devtools or typing keys.
    """
    token = payload.auth_token.strip()
    if not token:
        return JSONResponse({"success": False, "error": "auth_token bulunamadı"}, status_code=400)

    uname = payload.username.strip().lstrip("@") if payload.username else ""
    if not uname:
        uname = f"x_user_{int(time.time()) % 100000}"

    browser_mgr.create_session_from_cookies(uname, token, payload.ct0)

    cfg = get_config()
    accs = cfg.get("accounts", [])
    existing = next((a for a in accs if a.get("username") == uname), None)
    if existing:
        existing["role"] = payload.role
        existing["auth_token"] = token
        existing["ct0"] = payload.ct0 or ""
    else:
        accs.append({
            "username": uname,
            "role": payload.role,
            "auth_token": token,
            "ct0": payload.ct0 or ""
        })
    cfg["accounts"] = accs
    save_config(cfg)
    log_event(f"⚡ 1-Tıkla Bağlantı: @{uname} hesabı anında sisteme kaydedildi!", "success")
    return {"success": True, "message": f"@{uname} hesabı tek tıkla başarıyla bağlandı!", "username": uname}

class InteractiveLoginPayload(BaseModel):
    username: Optional[str] = ""

@app.post("/api/accounts/interactive_login")
async def interactive_login_endpoint(payload: InteractiveLoginPayload):
    """
    Launches a visible browser window for the user to log in manually.
    Automatically detects success, extracts cookies and saves the session.
    """
    uname = payload.username.strip().lstrip("@") if payload.username else ""
    log_event(f"🖥️ Canlı giriş tarayıcısı açılıyor ({uname or 'Otomatik Algılama'})...", "info")

    result = await asyncio.to_thread(browser_mgr.interactive_login, uname)

    if result.get("success"):
        detected_user = result.get("username")
        auth_token = result.get("auth_token", "")
        ct0 = result.get("ct0", "")

        cfg = get_config()
        accs = cfg.get("accounts", [])
        existing = next((a for a in accs if a.get("username") == detected_user), None)
        if existing:
            existing["auth_token"] = auth_token
            existing["ct0"] = ct0
        else:
            accs.append({
                "username": detected_user,
                "role": "helper",
                "auth_token": auth_token,
                "ct0": ct0
            })
        cfg["accounts"] = accs
        save_config(cfg)
        log_event(f"✅ @{detected_user} canlı tarayıcıdan başarıyla bağlandı ve kaydedildi!", "success")
        return {"success": True, "username": detected_user, "message": f"@{detected_user} başarıyla bağlandı!"}
    else:
        log_event(f"❌ Canlı giriş başarısız: {result.get('error')}", "error")
        return JSONResponse({"success": False, "error": result.get("error", "Giriş başarısız")}, status_code=400)

class AutoLoginPayload(BaseModel):
    username_or_email: str
    password: str
    verify_credential: Optional[str] = None
    role: str = "helper"

@app.post("/api/accounts/auto_login")
async def auto_login_endpoint(payload: AutoLoginPayload):
    """
    Automated credential login (Username/Email + Password + verification challenge).
    """
    user_cred = payload.username_or_email.strip()
    if not user_cred or not payload.password:
        return JSONResponse({"success": False, "error": "Kullanıcı adı ve şifre zorunludur"}, status_code=400)

    log_event(f"🤖 @{user_cred} için otomatik giriş başlatılıyor...", "info")
    result = await asyncio.to_thread(
        browser_mgr.automated_login,
        user_cred,
        payload.password,
        payload.verify_credential,
        False  # Show browser window so user can watch if needed
    )

    if result.get("success"):
        uname = result.get("username")
        auth_token = result.get("auth_token", "")
        ct0 = result.get("ct0", "")

        cfg = get_config()
        accs = cfg.get("accounts", [])
        existing = next((a for a in accs if a.get("username") == uname), None)
        if existing:
            existing["role"] = payload.role
            existing["auth_token"] = auth_token
            existing["ct0"] = ct0
        else:
            accs.append({
                "username": uname,
                "role": payload.role,
                "auth_token": auth_token,
                "ct0": ct0
            })
        cfg["accounts"] = accs
        save_config(cfg)
        log_event(f"✅ @{uname} otomatik şifreli giriş ile bağlandı!", "success")
        return {"success": True, "username": uname, "message": f"@{uname} başarıyla bağlandı!"}
    else:
        log_event(f"❌ Otomatik giriş başarısız: {result.get('error')}", "error")
        return JSONResponse({"success": False, "error": result.get("error")}, status_code=400)

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

class BulkImportPayload(BaseModel):
    raw_data: str  # Format: JSON array (Cookie-Editor), or username:auth_token, or username:password:email
    role: str = "helper"

@app.post("/api/accounts/bulk_import")
async def bulk_import_accounts(payload: BulkImportPayload):
    raw = payload.raw_data.strip()
    if not raw:
        return JSONResponse({"success": False, "error": "İçe aktarılacak veri bulunamadı"}, status_code=400)

    cfg = get_config()
    accs = cfg.get("accounts", [])
    imported_count = 0

    # 1. Check if input is a JSON array exported from Cookie-Editor / EditThisCookie
    if raw.startswith("[") and raw.endswith("]"):
        try:
            cookie_list = json.loads(raw)
            if isinstance(cookie_list, list):
                auth_token = next((c.get("value") for c in cookie_list if c.get("name") == "auth_token"), None)
                ct0 = next((c.get("value") for c in cookie_list if c.get("name") == "ct0"), "")
                twid = next((c.get("value") for c in cookie_list if c.get("name") == "twid"), "")
                
                if auth_token:
                    # Generate or deduce username
                    uname = f"cookie_acc_{int(time.time()) % 100000}"
                    browser_mgr.create_session_from_cookies(uname, auth_token, ct0)
                    accs.append({
                        "username": uname,
                        "role": payload.role,
                        "auth_token": auth_token,
                        "ct0": ct0
                    })
                    imported_count = 1
                    cfg["accounts"] = accs
                    save_config(cfg)
                    log_event(f"🍪 Cookie-Editor JSON formatından @{uname} başarıyla aktarıldı!", "success")
                    return {"success": True, "imported_count": 1, "total_accounts": len(accs)}
        except Exception as e:
            pass

    # 2. Line by line parsing (username:auth_token[:ct0] or plain auth_token)
    lines = raw.splitlines()
    for line in lines:
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#"):
            continue

        parts = []
        if ":" in clean_line:
            parts = clean_line.split(":")
        elif "," in clean_line:
            parts = clean_line.split(",")
        elif "\t" in clean_line:
            parts = clean_line.split("\t")
        elif len(clean_line) >= 30 and " " not in clean_line:
            # Single plain auth_token pasted directly
            parts = [f"acc_{int(time.time()) % 10000}_{imported_count}", clean_line]

        if len(parts) >= 2:
            uname = parts[0].strip().lstrip("@")
            token_or_pass = parts[1].strip()
            ct0_or_email = parts[2].strip() if len(parts) >= 3 else ""

            # If token_or_pass looks like a 40-char hex auth_token
            if len(token_or_pass) >= 25:
                auth_token = token_or_pass
                ct0 = ct0_or_email
                browser_mgr.create_session_from_cookies(uname, auth_token, ct0)
                
                existing = next((a for a in accs if a.get("username") == uname), None)
                if existing:
                    existing["auth_token"] = auth_token
                    existing["ct0"] = ct0
                else:
                    accs.append({
                        "username": uname,
                        "role": payload.role,
                        "auth_token": auth_token,
                        "ct0": ct0
                    })
                imported_count += 1

    cfg["accounts"] = accs
    save_config(cfg)
    log_event(f"Toplu içe aktarma tamamlandı: {imported_count} yeni hesap sisteme bağlandı!", "success")
    return {"success": True, "imported_count": imported_count, "total_accounts": len(accs)}

# Watchlist Endpoints
@app.get("/api/watchlist")
async def get_watchlist():
    cfg = get_config()
    return {"watchlist": cfg.get("watchlist", [])}

class WatchlistAddPayload(BaseModel):
    username: str

@app.post("/api/watchlist/add")
async def add_watchlist(payload: WatchlistAddPayload):
    uname = payload.username.strip().lstrip("@")
    if not uname:
        return JSONResponse({"success": False, "error": "Kullanıcı adı boş olamaz"}, status_code=400)
    cfg = get_config()
    watchlist = cfg.get("watchlist", [])
    if uname not in watchlist:
        watchlist.append(uname)
        cfg["watchlist"] = watchlist
        save_config(cfg)
        log_event(f"@{uname} sabit izleme listesine (Watchlist) eklendi.", "success")
    return {"success": True, "watchlist": watchlist}

@app.post("/api/watchlist/delete")
async def delete_watchlist(payload: WatchlistAddPayload):
    uname = payload.username.strip().lstrip("@")
    cfg = get_config()
    watchlist = [w for w in cfg.get("watchlist", []) if w != uname]
    cfg["watchlist"] = watchlist
    save_config(cfg)
    log_event(f"@{uname} izleme listesinden çıkarıldı.", "info")
    return {"success": True, "watchlist": watchlist}

@app.post("/api/watchlist/check_now")
async def check_watchlist_now(background_tasks: BackgroundTasks):
    cfg = get_config()
    watchlist = cfg.get("watchlist", [])
    accounts = cfg.get("accounts", [])
    helpers = [a.get("username") for a in accounts if browser_mgr.has_session(a.get("username"))]

    if not watchlist:
        return JSONResponse({"success": False, "error": "İzleme listesinde hesap yok."}, status_code=400)
    if not helpers:
        return JSONResponse({"success": False, "error": "Kasma işlemi yapacak aktif oturumlu hesap yok."}, status_code=400)

    def run_check():
        monitor = get_watchlist_monitor()
        for target in watchlist:
            log_event(f"Anlık hedef kontrolü: @{target}...", "info")
            monitor.check_and_engage_target(target, helpers, headless=True)

    background_tasks.add_task(run_check)
    return {"success": True, "message": f"{len(watchlist)} hedef hesap için anlık kontrol başlatıldı"}

# Comment Studio Settings Endpoints
@app.get("/api/settings/comments")
async def get_comment_settings():
    cfg = get_config()
    return cfg.get("comment_settings", {
        "mode": "hybrid",
        "custom_prompt": "",
        "custom_pool": [
            "Güzel analiz, hacim tarafı da bu hareketi teyit ediyor. Emeğinize sağlık.",
            "Destek seviyesi oldukça sağlam çalışmış görünüyor. Takipteyiz.",
            "BIST100 genel yönü belirlese de hisse bazlı ayrışmalar devam edecektir.",
            "Katılıyorum, özellikle kurumsal alımlar bu seviyeyi destekliyor.",
            "Kısa vadeli düzeltmeler ana trendi bozmadığı sürece fırsat sunabilir."
        ]
    })

class CommentSettingsPayload(BaseModel):
    mode: str = "hybrid"  # 'ai', 'custom_pool', 'hybrid'
    custom_prompt: Optional[str] = None
    custom_pool: List[str] = []

@app.post("/api/settings/comments")
async def save_comment_settings(payload: CommentSettingsPayload):
    cfg = get_config()
    cfg["comment_settings"] = {
        "mode": payload.mode,
        "custom_prompt": payload.custom_prompt or "",
        "custom_pool": [c.strip() for c in payload.custom_pool if c.strip()]
    }
    save_config(cfg)
    log_event("Yorum Stüdyosu ayarları kaydedildi.", "success")
    return {"success": True, "comment_settings": cfg["comment_settings"]}

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
    persona: str = "kurumsal_analist"

@app.post("/api/chart/generate")
async def generate_chart_tweet(payload: GenerateChartTweetPayload):
    analysis = chart_service.analyze_symbol(payload.symbol)
    ai_gen = get_ai_generator()
    tweet_text = ai_gen.generate_chart_tweet(analysis, persona_key=payload.persona)
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
        cmt_cfg = cfg.get("comment_settings", {})
        custom_pool = cmt_cfg.get("custom_pool")
        custom_prompt = cmt_cfg.get("custom_prompt")
        pod_mgr.boost_tweet(
            url, 
            helpers, 
            do_like=True, 
            do_retweet=True, 
            do_comment=True, 
            custom_comments=custom_pool,
            custom_prompt=custom_prompt,
            headless=True
        )
        log_event(f"{url} için etkileşim havuzu görevi başarıyla tamamlandı!", "success")

    background_tasks.add_task(run_boost)
    return {"success": True, "message": f"{len(helpers)} hesapla etkileşim başlatıldı"}

@app.post("/api/pod/mutual_ring")
async def mutual_ring_boost(background_tasks: BackgroundTasks):
    cfg = get_config()
    accounts = [a.get("username") for a in cfg.get("accounts", []) if browser_mgr.has_session(a.get("username"))]
    if len(accounts) < 2:
        return JSONResponse({"success": False, "error": "Karşılıklı kasma için en az 2 aktif oturumlu hesap gereklidir"}, status_code=400)

    log_event(f"Karşılıklı Hesap Kasma Çemberi ({len(accounts)} hesap) başlatılıyor...", "info")

    def run_ring():
        ai_gen = get_ai_generator()
        pod_mgr = EngagementPodManager(browser_mgr, ai_gen)
        cmt_cfg = cfg.get("comment_settings", {})
        custom_pool = cmt_cfg.get("custom_pool")
        custom_prompt = cmt_cfg.get("custom_prompt")

        for acc in accounts:
            ctx = browser_mgr.launch_context(acc, headless=True)
            latest_url = None
            try:
                page = ctx.new_page()
                actions = TwitterActions(page)
                latest_url = actions.get_latest_tweet_url_of_user(acc)
            except Exception:
                pass
            finally:
                ctx.close()
                browser_mgr.stop()

            if latest_url:
                helpers = [h for h in accounts if h.lower() != acc.lower()]
                log_event(f"@{acc} son tweeti diğer {len(helpers)} hesapla kasılıyor: {latest_url}", "info")
                pod_mgr.boost_tweet(
                    latest_url, 
                    helpers, 
                    do_like=True, 
                    do_retweet=True, 
                    do_comment=True, 
                    custom_comments=custom_pool,
                    custom_prompt=custom_prompt,
                    headless=True
                )
                time.sleep(random.uniform(20, 45))

        log_event("Karşılıklı hesap kasma çemberi başarıyla tamamlandı!", "success")

    background_tasks.add_task(run_ring)
    return {"success": True, "message": f"{len(accounts)} hesap için karşılıklı kasma çemberi başlatıldı"}

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
