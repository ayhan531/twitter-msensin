"""
X (Twitter) Organic Growth & Follower Engine
Drives 1000+ organic Turkish finance & crypto followers to target account
via niche follower targeting, smart auto-engagement, and algorithmic visibility.

THREADING NOTE: Each public method creates its own sync_playwright() context.
This avoids the greenlet thread-switching error when called from background threads.
"""

import os
import json
import time
import random
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.twitter_actions import safe_print, human_delay

DATA_DIR = Path(__file__).resolve().parent.parent / "config"
SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"
GROWTH_STATE_FILE = DATA_DIR / "growth_state.json"

# Hardcoded fallback credentials for @Borsagenci
BORSAGENCI_AUTH_TOKEN = "70bcacd3a39523f1f1fdbff3411eaa63ce996e50"
BORSAGENCI_CT0 = "53ae1c20158dc02db9fe4db6a02a32e62d0bdf2890c4ef440b7bd58041244f3e953399efbda013a2808e0ebe1c0bd377610d0179ce0f371775fbb19c395f628422f55c8323c40acfc13b6148cc2da459"

DEFAULT_FINANCE_TARGETS = [
    "e507",
    "mert_basaran",
    "TuncayTurssucu",
    "ali_persembe",
    "kriptoemre",
    "uzmancoin",
    "AhmetMergen",
    "stratejist_dr"
]

NICHE_KEYWORDS = [
    "#BIST100",
    "#THYAO",
    "#borsa",
    "#altin",
    "#BTC",
    "borsa istanbul",
    "hisse analizi"
]


def _get_session_cookies(account_name: str) -> List[dict]:
    """
    Reads stored session cookies from disk for the given account.
    Falls back to hardcoded Borsagenci credentials if not found.
    """
    # Try Render persistent disk first
    for base in ["/var/data/x_bist_bot/sessions", "/data/x_bist_bot/sessions"]:
        p = Path(base) / f"session_{account_name}.json"
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("cookies", [])
            except Exception:
                pass

    # Local sessions dir
    p = SESSIONS_DIR / f"session_{account_name}.json"
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("cookies", [])
        except Exception:
            pass

    # Fallback: build cookies from hardcoded token
    safe_print(f"[!] Session file not found for @{account_name}, using hardcoded token fallback")
    token = BORSAGENCI_AUTH_TOKEN
    ct0 = BORSAGENCI_CT0
    far_future = int(time.time()) + 315360000
    cookies = []
    for domain in [".x.com", ".twitter.com"]:
        cookies += [
            {"name": "auth_token", "value": token, "domain": domain, "path": "/",
             "expires": far_future, "httpOnly": True, "secure": True, "sameSite": "None"},
            {"name": "ct0", "value": ct0, "domain": domain, "path": "/",
             "expires": far_future, "httpOnly": False, "secure": True, "sameSite": "Lax"},
        ]
    return cookies


class OrganicGrowthEngine:
    def __init__(self, browser_mgr=None, ai_gen=None):
        # browser_mgr kept for compatibility but NOT used for page creation
        self.browser_mgr = browser_mgr
        self.ai_gen = ai_gen
        self.running = False
        self._load_state()

    def _load_state(self):
        if GROWTH_STATE_FILE.exists():
            try:
                with open(GROWTH_STATE_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.state = {**self._default_state(), **loaded}
            except Exception:
                self.state = self._default_state()
        else:
            self.state = self._default_state()

    def _default_state(self) -> dict:
        return {
            "total_followed": 0,
            "total_liked": 0,
            "total_replied": 0,
            "cycles_run": 0,
            "current_followers": 0,
            "last_activity": "Henuz aktivite yok.",
            "followed_users": [],
            "daily_history": {},
            "targets": DEFAULT_FINANCE_TARGETS,
            "auto_growth_enabled": False
        }

    def _save_state(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(GROWTH_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            safe_print(f"[!] State kayit hatasi: {e}")

    def _open_page(self, pw, account_name: str):
        """
        Opens a fresh Chromium browser + context with the account's session cookies.
        Returns (browser, context, page).
        """
        cookies = _get_session_cookies(account_name)
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        return browser, context, page

    def follow_target_followers(self, account_name: str, target_profile: str, max_follows: int = 10) -> Dict[str, Any]:
        """
        Opens its own playwright instance and follows followers of the target finance account.
        Thread-safe: no shared playwright state.
        """
        from playwright.sync_api import sync_playwright

        clean_target = target_profile.lstrip("@")
        safe_print(f"[+] @{clean_target} takipcileri taranıyor (Hesap: @{account_name})...")

        followed_now = []

        try:
            with sync_playwright() as pw:
                browser, context, page = self._open_page(pw, account_name)
                try:
                    # Try verified followers first, fall back to regular
                    for followers_url in [
                        f"https://x.com/{clean_target}/verified_followers",
                        f"https://x.com/{clean_target}/followers"
                    ]:
                        page.goto(followers_url, wait_until="domcontentloaded", timeout=45000)
                        human_delay(3, 6)
                        btns = page.locator("button[data-testid*='-follow']:not([data-testid*='unfollow'])").all()
                        if len(btns) > 0:
                            break

                    # Check if logged in
                    if "login" in page.url or "i/flow" in page.url:
                        return {"success": False, "error": "Oturum gecersiz, login sayfasina yonlendirildi", "count": 0, "followed": []}

                    for _scroll in range(6):
                        follow_buttons = page.locator(
                            "button[data-testid*='-follow']:not([data-testid*='unfollow'])"
                        ).all()

                        for btn in follow_buttons:
                            if len(followed_now) >= max_follows:
                                break
                            try:
                                if not btn.is_visible():
                                    continue
                                aria = btn.get_attribute("aria-label") or ""
                                uname = (aria.replace("Follow @", "")
                                             .replace("Takip et @", "")
                                             .replace("Follow", "")
                                             .replace("Takip et", "")
                                             .strip().lstrip("@"))

                                if uname and uname in self.state.get("followed_users", []):
                                    continue

                                btn.scroll_into_view_if_needed()
                                btn.click()
                                human_delay(12, 25)

                                followed_now.append(uname or f"user_{len(followed_now)+1}")
                                if uname:
                                    self.state.setdefault("followed_users", []).append(uname)
                                self.state["total_followed"] = self.state.get("total_followed", 0) + 1
                                safe_print(f"[OK] @{uname or 'kullanici'} takip edildi!")

                            except Exception:
                                continue

                        if len(followed_now) >= max_follows:
                            break
                        page.mouse.wheel(0, 800)
                        human_delay(2, 4)

                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
                    try:
                        browser.close()
                    except Exception:
                        pass

            self._save_state()
            return {"success": True, "count": len(followed_now), "followed": followed_now}

        except Exception as e:
            safe_print(f"[!] follow_target_followers hatasi: {e}")
            return {"success": False, "error": str(e), "count": len(followed_now), "followed": followed_now}

    def engage_niche_search(self, account_name: str, keyword: str = "#BIST100", max_likes: int = 8) -> Dict[str, Any]:
        """
        Opens its own playwright instance and likes niche finance tweets.
        Thread-safe: no shared playwright state.
        """
        from playwright.sync_api import sync_playwright

        safe_print(f"[+] '{keyword}' aramasinda aktif yatirimci tweetleri begeniliyor...")
        liked_count = 0

        try:
            with sync_playwright() as pw:
                browser, context, page = self._open_page(pw, account_name)
                try:
                    encoded = keyword.replace("#", "%23").replace(" ", "%20")
                    search_url = f"https://x.com/search?q={encoded}&f=live"
                    page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                    human_delay(3, 5)

                    if "login" in page.url or "i/flow" in page.url:
                        return {"success": False, "error": "Oturum gecersiz", "liked_count": 0}

                    for _ in range(5):
                        like_buttons = page.locator("button[data-testid='like']:visible").all()
                        for btn in like_buttons:
                            if liked_count >= max_likes:
                                break
                            try:
                                btn.scroll_into_view_if_needed()
                                btn.click()
                                liked_count += 1
                                self.state["total_liked"] = self.state.get("total_liked", 0) + 1
                                safe_print(f"[OK] Tweet begenildi ({liked_count}/{max_likes})")
                                human_delay(4, 9)
                            except Exception:
                                continue

                        if liked_count >= max_likes:
                            break
                        page.mouse.wheel(0, 800)
                        human_delay(2, 4)

                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
                    try:
                        browser.close()
                    except Exception:
                        pass

            self._save_state()
            return {"success": True, "liked_count": liked_count}

        except Exception as e:
            safe_print(f"[!] engage_niche_search hatasi: {e}")
            return {"success": False, "error": str(e), "liked_count": liked_count}

    def run_full_organic_growth_cycle(self, account_name: str) -> Dict[str, Any]:
        """
        Full 2-step growth sprint — thread-safe, each step has its own playwright.
        Step 1: Follow 8-14 followers of target finance influencer.
        Step 2: Like 6-10 niche finance tweets.
        """
        safe_print(f"\n=======================================================")
        safe_print(f">>> @{account_name} ICIN ORGANIK TAKIPCI KASMA BASLADI")
        safe_print(f"=======================================================\n")

        targets = self.state.get("targets", DEFAULT_FINANCE_TARGETS)
        chosen_target = random.choice(targets)
        chosen_kw = random.choice(NICHE_KEYWORDS)

        # Step 1: Follow target's followers
        res_follow = self.follow_target_followers(
            account_name, chosen_target, max_follows=random.randint(8, 14)
        )
        follows_sent = res_follow.get("count", 0)
        safe_print(f"[STEP1] Takip sonucu: {follows_sent} kisi takip edildi | Hata: {res_follow.get('error','Yok')}")

        # Cooling pause between steps
        human_delay(20, 40)

        # Step 2: Like niche tweets
        res_like = self.engage_niche_search(
            account_name, chosen_kw, max_likes=random.randint(6, 10)
        )
        likes_sent = res_like.get("liked_count", 0)
        safe_print(f"[STEP2] Begeni sonucu: {likes_sent} tweet begenildi | Hata: {res_like.get('error','Yok')}")

        # Update cycle stats
        self.state["cycles_run"] = self.state.get("cycles_run", 0) + 1
        self.state["last_activity"] = (
            f"[{datetime.datetime.now().strftime('%H:%M')}] "
            f"@{chosen_target} takipcilerinden {follows_sent} takip + "
            f"{chosen_kw} aramasinda {likes_sent} begeni. "
            f"(Toplam {self.state['total_followed']} takip / {self.state['total_liked']} begeni)"
        )
        self._save_state()

        summary = {
            "target": chosen_target,
            "keyword": chosen_kw,
            "follows_sent": follows_sent,
            "likes_sent": likes_sent,
            "total_followed_all_time": self.state.get("total_followed", 0),
            "total_liked_all_time": self.state.get("total_liked", 0),
            "cycles_run": self.state.get("cycles_run", 0),
            "follow_error": res_follow.get("error"),
            "like_error": res_like.get("error"),
        }
        safe_print(f"[DONE] Buyume dongusu #{summary['cycles_run']} tamamlandi!\n")
        return summary
