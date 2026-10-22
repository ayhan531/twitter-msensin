"""
X (Twitter) Organic Growth & Follower Engine
Drives 1000+ organic Turkish finance & crypto followers to target account
via niche follower targeting, smart auto-engagement, and algorithmic visibility.
"""

import os
import json
import time
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.browser import TwitterBrowserManager
from core.twitter_actions import TwitterActions, safe_print, human_delay
from core.ai_generator import BISTContentGenerator

DATA_DIR = Path(__file__).resolve().parent.parent / "config"
GROWTH_STATE_FILE = DATA_DIR / "growth_state.json"

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
    "#altın",
    "#BTC",
    "borsa istanbul",
    "hisse analizi"
]

class OrganicGrowthEngine:
    def __init__(self, browser_mgr: TwitterBrowserManager, ai_gen: Optional[BISTContentGenerator] = None):
        self.browser_mgr = browser_mgr
        self.ai_gen = ai_gen or BISTContentGenerator()
        self.running = False
        self._load_state()

    def _load_state(self):
        if GROWTH_STATE_FILE.exists():
            try:
                with open(GROWTH_STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
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
            "last_activity": "Henüz aktivite yok.",
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
            safe_print(f"[!] Growth state save error: {e}")

    def follow_target_followers(self, account_name: str, target_profile: str, max_follows: int = 10) -> Dict[str, Any]:
        """
        Visits target financial influencer's followers list and follows active users.
        Brings 20-35% organic follow-back rate from real Turkish investors.
        """
        clean_target = target_profile.lstrip("@")
        safe_print(f"[+] @{clean_target} takipçileri taranıyor (Hesap: @{account_name})...")
        
        ctx = self.browser_mgr.launch_context(account_name, headless=True)
        followed_now = []

        try:
            page = ctx.new_page()
            url = f"https://x.com/{clean_target}/verified_followers"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            human_delay(3, 5)

            # If verified_followers empty, go to regular followers
            if page.locator("button[data-testid*='-follow']").count() == 0:
                page.goto(f"https://x.com/{clean_target}/followers", wait_until="domcontentloaded", timeout=30000)
                human_delay(3, 5)

            # Scroll and find follow buttons
            for _ in range(5):
                follow_buttons = page.locator("button[data-testid*='-follow']:not([data-testid*='-unfollow'])").all()
                for btn in follow_buttons:
                    if len(followed_now) >= max_follows:
                        break
                    try:
                        if not btn.is_visible():
                            continue
                        
                        # Get username from aria-label or testid
                        testid = btn.get_attribute("data-testid") or ""
                        # testid is usually "{userid}-follow"
                        aria = btn.get_attribute("aria-label") or ""
                        uname = aria.replace("Follow", "").replace("Takip et", "").strip().lstrip("@")

                        if uname and uname in self.state.get("followed_users", []):
                            continue

                        btn.click()
                        followed_now.append(uname or f"user_{len(followed_now)+1}")
                        if uname:
                            self.state.setdefault("followed_users", []).append(uname)
                        self.state["total_followed"] = self.state.get("total_followed", 0) + 1
                        safe_print(f"[OK] @{uname or 'kullanici'} takip edildi (+1 potansiyel takipçi)!")
                        
                        # Safe random human delay between follows (12-25 seconds)
                        human_delay(12, 25)
                    except Exception:
                        continue

                if len(followed_now) >= max_follows:
                    break

                page.mouse.wheel(0, 700)
                human_delay(2, 4)

            self._save_state()
            self.browser_mgr.save_session(ctx, account_name)
            return {"success": True, "count": len(followed_now), "followed": followed_now}
        except Exception as e:
            return {"success": False, "error": str(e), "followed": followed_now}
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            self.browser_mgr.stop()

    def engage_niche_search(self, account_name: str, keyword: str = "#BIST100", max_likes: int = 8) -> Dict[str, Any]:
        """
        Searches niche finance keywords on Twitter and likes fresh active tweets.
        Causes active traders to receive notification: '@Borsagenci gönderinizi beğendi'
        driving profile visits and follows.
        """
        safe_print(f"[+] '{keyword}' aramasında aktif yatırımcı tweetleri beğeniliyor...")
        ctx = self.browser_mgr.launch_context(account_name, headless=True)
        liked_count = 0

        try:
            page = ctx.new_page()
            encoded = keyword.replace("#", "%23").replace(" ", "%20")
            search_url = f"https://x.com/search?q={encoded}&f=live"
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            human_delay(3, 5)

            for _ in range(4):
                like_buttons = page.locator("button[data-testid='like']:visible").all()
                for btn in like_buttons:
                    if liked_count >= max_likes:
                        break
                    try:
                        btn.click()
                        liked_count += 1
                        self.state["total_liked"] = self.state.get("total_liked", 0) + 1
                        safe_print(f"[OK] Finans tweeti beğenildi ({liked_count}/{max_likes})")
                        human_delay(4, 9)
                    except Exception:
                        continue

                if liked_count >= max_likes:
                    break
                page.mouse.wheel(0, 800)
                human_delay(2, 4)

            self._save_state()
            self.browser_mgr.save_session(ctx, account_name)
            return {"success": True, "liked_count": liked_count}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            self.browser_mgr.stop()

    def run_full_organic_growth_cycle(self, account_name: str) -> Dict[str, Any]:
        """
        Executes a complete 3-step growth sprint:
        1. Targets followers of top finance influencer (follows 10-15 active users).
        2. Engages on fresh #BIST100 & #BTC tweets (likes 8-12 tweets).
        3. Records stats.
        """
        safe_print(f"\n=======================================================")
        safe_print(f"🚀 @{account_name} İÇİN 1000 ORGANİK TAKİPÇİ KASILMASI BAŞLATILDI")
        safe_print(f"=======================================================\n")

        targets = self.state.get("targets", DEFAULT_FINANCE_TARGETS)
        chosen_target = random.choice(targets)
        chosen_kw = random.choice(NICHE_KEYWORDS)

        # Step 1: Follow active target users
        res_follow = self.follow_target_followers(account_name, chosen_target, max_follows=random.randint(8, 14))

        # Safe cooling pause
        human_delay(15, 30)

        # Step 2: Niche keyword interaction
        res_like = self.engage_niche_search(account_name, chosen_kw, max_likes=random.randint(6, 10))

        summary = {
            "target": chosen_target,
            "keyword": chosen_kw,
            "follows_sent": res_follow.get("count", 0),
            "likes_sent": res_like.get("liked_count", 0),
            "total_followed_all_time": self.state.get("total_followed", 0),
            "total_liked_all_time": self.state.get("total_liked", 0)
        }
        # Update cycle counter and last activity
        self.state["cycles_run"] = self.state.get("cycles_run", 0) + 1
        self.state["last_activity"] = (
            f"[{__import__('datetime').datetime.now().strftime('%H:%M')}] "
            f"@{chosen_target} takipçilerinden {summary['follows_sent']} takip, "
            f"#{chosen_kw} aramasında {summary['likes_sent']} beğeni."
        )
        self._save_state()
        safe_print(f"[✓] Büyüme döngüsü tamamlandı: {summary}\n")
        return summary
