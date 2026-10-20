"""
Target Watchlist Monitor (Hesap Sabitleme & Otomatik İzleme)
Monitors specific target accounts (e.g. @Borsagenci), detects new tweets,
and automatically triggers the engagement pod (Like + RT + AI Comment).
"""

import time
from typing import List, Dict, Any, Optional
from core.browser import TwitterBrowserManager
from core.twitter_actions import TwitterActions
from core.engagement_pod import EngagementPodManager
from core.ai_generator import BISTContentGenerator

class WatchlistMonitor:
    def __init__(self, browser_mgr: TwitterBrowserManager, ai_gen: BISTContentGenerator):
        self.browser_mgr = browser_mgr
        self.ai_gen = ai_gen
        self.pod_mgr = EngagementPodManager(browser_mgr, ai_gen)
        # Store seen tweet URLs to avoid duplicate engagement
        self.seen_tweets = set()

    def check_and_engage_target(
        self,
        target_username: str,
        helper_accounts: List[str],
        do_like: bool = True,
        do_retweet: bool = True,
        do_comment: bool = True,
        headless: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Visits target_username profile with a helper account, finds their latest tweet,
        and if it's new, commands all helper accounts to like, RT, and comment!
        """
        clean_target = target_username.strip().lstrip("@")
        if not helper_accounts:
            return None

        # Pick one helper account to inspect the target profile
        scanner_acc = helper_accounts[0]
        if not self.browser_mgr.has_session(scanner_acc):
            return None

        print(f"\n[👀] Hedef Hesap Taranıyor: @{clean_target} (Tarayıcı: @{scanner_acc})")
        context = None
        latest_url = None
        try:
            context = self.browser_mgr.launch_context(scanner_acc, headless=headless)
            page = context.new_page()
            actions = TwitterActions(page)
            latest_url = actions.get_latest_tweet_url_of_user(clean_target)
        except Exception as e:
            print(f"[!] Hedef taranırken hata: {e}")
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            self.browser_mgr.stop()

        if not latest_url:
            print(f"[-] @{clean_target} için tweet URL'si tespit edilemedi.")
            return None

        if latest_url in self.seen_tweets:
            print(f"[i] Son tweet zaten kasılmış: {latest_url}")
            return {"status": "already_engaged", "url": latest_url}

        print(f"[🔥] YENİ TWEET TESPİT EDİLDİ: {latest_url}")
        self.seen_tweets.add(latest_url)

        # Trigger boost across all helper accounts (excluding the target itself)
        active_helpers = [a for a in helper_accounts if a.lower() != clean_target.lower()]
        boost_res = self.pod_mgr.boost_tweet(
            tweet_url=latest_url,
            helper_accounts=active_helpers,
            do_like=do_like,
            do_retweet=do_retweet,
            do_comment=do_comment,
            headless=headless
        )

        return {
            "status": "boosted",
            "target": clean_target,
            "url": latest_url,
            "results": boost_res
        }
