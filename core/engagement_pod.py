"""
Engagement Pod Engine (Mutual Retweet, Like, and AI Commenting)
Coordinates multiple X accounts to naturally boost tweets without detection.
"""

import time
import random
from typing import List, Dict, Any, Optional
from core.browser import TwitterBrowserManager
from core.twitter_actions import TwitterActions, human_delay
from core.ai_generator import BISTContentGenerator
from core.market_data import BISTMarketData


class EngagementPodManager:
    def __init__(self, browser_mgr: TwitterBrowserManager, ai_gen: BISTContentGenerator):
        self.browser_mgr = browser_mgr
        self.ai_gen = ai_gen
        self.market_data = BISTMarketData()

    def boost_tweet(
        self,
        tweet_url: str,
        helper_accounts: List[str],
        do_like: bool = True,
        do_retweet: bool = True,
        do_comment: bool = True,
        headless: bool = True,
        parent_tweet_text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Takes a target tweet URL and uses helper accounts to Like, RT, and Comment on it.
        """
        results = []
        print(f"\n========================================================")
        print(f"[+] ETKİLEŞİM HAVUZU (BOOST) BAŞLATILIYOR")
        print(f"[*] Hedef Tweet: {tweet_url}")
        print(f"[*] Katılacak Hesap Sayısı: {len(helper_accounts)}")
        print(f"========================================================\n")

        for idx, acc in enumerate(helper_accounts):
            print(f"\n>>> [{idx + 1}/{len(helper_accounts)}] Hesap Devreye Giriyor: @{acc}")
            
            if not self.browser_mgr.has_session(acc):
                print(f"[!] HATA: @{acc} için oturum çerezi bulunamadı. Lütfen önce giriş yapın.")
                results.append({"account": acc, "status": "no_session"})
                continue

            # Random jitter before logging in
            if idx > 0:
                wait_time = random.uniform(10, 25)
                print(f"[⏳] Hesaplar arası doğal bekleme süresi: {round(wait_time, 1)} saniye...")
                time.sleep(wait_time)

            context = None
            try:
                context = self.browser_mgr.launch_context(acc, headless=headless)
                page = context.new_page()
                actions = TwitterActions(page)

                acc_result = {
                    "account": acc,
                    "liked": False,
                    "retweeted": False,
                    "commented": False
                }

                # 1. Beğeni (Like)
                if do_like:
                    like_res = actions.like_tweet(tweet_url)
                    acc_result["liked"] = like_res.get("success", False)
                    human_delay(2, 5)

                # 2. Retweet
                if do_retweet:
                    rt_res = actions.retweet(tweet_url)
                    acc_result["retweeted"] = rt_res.get("success", False)
                    human_delay(3, 6)

                # 3. Yorum (AI Comment)
                if do_comment:
                    comment_text = self.ai_gen.generate_reply(parent_tweet_text or "Borsa analizi")
                    reply_res = actions.reply_tweet(tweet_url, comment_text)
                    acc_result["commented"] = reply_res.get("success", False)
                    acc_result["comment_text"] = comment_text

                results.append(acc_result)
                print(f"[✓] @{acc} etkileşimleri tamamladı: Like: {acc_result['liked']} | RT: {acc_result['retweeted']} | Yorum: {acc_result['commented']}")

            except Exception as e:
                print(f"[!] @{acc} işlemi sırasında hata oluştu: {e}")
                results.append({"account": acc, "error": str(e)})
            finally:
                if context:
                    try:
                        context.close()
                    except Exception:
                        pass
                self.browser_mgr.stop()

        print(f"\n[✓] Etkileşim havuzu görevi tamamlandı!\n")
        return results

    def post_and_cross_boost(
        self,
        poster_account: str,
        helper_accounts: List[str],
        custom_tweet: Optional[str] = None,
        media_path: Optional[str] = None,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        1. poster_account posts a fresh AI-generated BIST tweet (with optional image/chart).
        2. helper_accounts immediately like, retweet, and reply to it.
        """
        print(f"\n========================================================")
        print(f"[*] BIST TWEET VE KARSILIKLI ETKİLEŞİM AKISI")
        print(f"[*] Tweet Atacak Hesap: @{poster_account}")
        print(f"[*] Destekleyecek Hesaplar: {', '.join('@' + a for a in helper_accounts)}")
        if media_path:
            print(f"[*] Eklenecek Fotoğraf: {media_path}")
        print(f"========================================================\n")

        # Step 1: Generate Content
        if custom_tweet:
            tweet_text = custom_tweet
        else:
            print("[+] Canli BIST verileri cekiliyor...")
            m_data = self.market_data.get_market_overview()
            print("[+] BIST Analist Yapay Zekasi ozgun tweet uretiyor...")
            tweet_text = self.ai_gen.generate_bist_tweet(m_data)

        print(f"\n[*] Hazirlanan Tweet Metni ({len(tweet_text)} karakter):\n\"{tweet_text}\"\n")

        # Step 2: Post the Tweet
        if not self.browser_mgr.has_session(poster_account):
            print(f"[!] HATA: @{poster_account} için kayıtlı oturum bulunamadı.")
            return {"success": False, "error": "No session for poster"}

        posted_url = None
        context = None
        try:
            context = self.browser_mgr.launch_context(poster_account, headless=headless)
            page = context.new_page()
            actions = TwitterActions(page)

            post_res = actions.post_tweet(tweet_text, media_path=media_path)
            if not post_res.get("success"):
                print(f"[!] Tweet paylaşılamadı: {post_res.get('error')}")
                return {"success": False, "error": post_res.get("error")}

            print("[✓] Tweet başarıyla paylaşıldı!")
            human_delay(3, 5)

            # Retrieve published tweet URL
            print(f"[+] @{poster_account} profilinden paylaşılan tweet URL'si alınıyor...")
            posted_url = actions.get_latest_tweet_url_of_user(poster_account)
            if posted_url:
                print(f"[✓] Yeni Tweet URL: {posted_url}")
            else:
                print("[!] Tweet URL doğrudan tespit edilemedi, profil URL'si üzerinden kontrol edilebilir.")
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            self.browser_mgr.stop()

        # Step 3: Helper accounts boost the tweet
        boost_results = []
        if posted_url and helper_accounts:
            boost_results = self.boost_tweet(
                tweet_url=posted_url,
                helper_accounts=helper_accounts,
                do_like=True,
                do_retweet=True,
                do_comment=True,
                headless=headless,
                parent_tweet_text=tweet_text
            )

        return {
            "success": True,
            "tweet_text": tweet_text,
            "tweet_url": posted_url,
            "boost_results": boost_results
        }
