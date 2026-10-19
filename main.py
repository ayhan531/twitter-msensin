"""
X (Twitter) BIST 100 AI Automation & Engagement Pod System
100% Free - No Twitter Developer API Required - Anti-Bot Stealth Architecture
"""

import os
import sys
import json
import argparse
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Force UTF-8 on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.browser import TwitterBrowserManager
from core.ai_generator import BISTContentGenerator
from core.market_data import BISTMarketData
from core.engagement_pod import EngagementPodManager
from core.twitter_actions import TwitterActions

CONFIG_FILE = ROOT_DIR / "config" / "config.json"

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def print_banner():
    banner = r"""
========================================================================
        X BIST 100 YAPAY ZEKA OTOMASYON & HESAP KASMA SISTEMI           
    API'siz Tarayici Otomasyonu * BIST Canli Veri * Ucretsiz AI Motoru   
========================================================================
    """
    print(banner)

def list_accounts_status(browser_mgr: TwitterBrowserManager):
    cfg = load_config()
    accounts = cfg.get("accounts", [])
    print("\n--- KAYITLI HESAPLAR VE OTURUM DURUMLARI ---")
    if not accounts:
        print("[!] Henuz kayitli hesap yok. config/config.json dosyasini duzenleyin veya menuden ekleyin.")
        return

    for idx, acc in enumerate(accounts, 1):
        uname = acc.get("username", "")
        role = acc.get("role", "helper")
        has_sess = browser_mgr.has_session(uname)
        status_icon = "[+] Aktif (Oturum Hazir)" if has_sess else "[-] Giris Yapilmadi"
        print(f" {idx}. @{uname:<15} Rol: {role:<10} | {status_icon}")
    print("--------------------------------------------\n")

def menu_login(browser_mgr: TwitterBrowserManager):
    uname = input("\nGiriş yapılacak X kullanıcı adını yazın (@ olmadan): ").strip().lstrip("@")
    if not uname:
        return
    print("\n[!] Tarayıcı açılıyor. Lütfen hesabınıza giriş yapın...")
    success = browser_mgr.interactive_login(uname)
    if success:
        # Add to config if not present
        cfg = load_config()
        accs = cfg.get("accounts", [])
        if not any(a.get("username") == uname for a in accs):
            role = "analyst" if len(accs) == 0 else "helper"
            accs.append({"username": uname, "role": role})
            cfg["accounts"] = accs
            save_config(cfg)
            print(f"[✓] @{uname} hesap listesine ({role} rolüyle) eklendi.")

def menu_add_cookie(browser_mgr: TwitterBrowserManager):
    uname = input("\nHesap kullanıcı adı (@ olmadan): ").strip().lstrip("@")
    if not uname:
        return
    auth_token = input("auth_token çerez değeri: ").strip()
    if not auth_token:
        print("[!] auth_token boş olamaz.")
        return
    ct0 = input("ct0 çerez değeri (isteğe bağlı, Enter ile geçebilirsiniz): ").strip()
    
    session_file = browser_mgr.create_session_from_cookies(uname, auth_token, ct0)
    print(f"\n[✓] Oturum çerezi başarıyla oluşturuldu: {session_file}")

    # Add to config if not present
    cfg = load_config()
    accs = cfg.get("accounts", [])
    if not any(a.get("username") == uname for a in accs):
        role = "analyst" if len(accs) == 0 else "helper"
        accs.append({"username": uname, "role": role, "auth_token": auth_token, "ct0": ct0})
        cfg["accounts"] = accs
        save_config(cfg)
        print(f"[✓] @{uname} listeye kaydedildi.")

def menu_show_market():
    print("\n[+] Canlı BIST piyasa verileri çekiliyor...")
    bist = BISTMarketData()
    data = bist.get_market_overview()
    idx = data.get("index") or {}
    print(f"\n📊 BIST 100 ENDEKSİ: {idx.get('price')} TL ({idx.get('change_pct')}%) | Hava: {data.get('sentiment')}")
    print("------------------------------------------------------------------")
    for s in data.get("stocks", []):
        sym = s.get("symbol")
        p = s.get("price")
        chg = s.get("change_pct")
        sign = "+" if chg >= 0 else ""
        print(f" • {sym:<8} : {p:>7.2f} TL  ({sign}{chg:>5.2f}%)  Aralık: {s.get('day_low')} - {s.get('day_high')} TL")
    print("------------------------------------------------------------------\n")

def menu_boost_url(pod_mgr: EngagementPodManager):
    url = input("\nKasılacak (beğeni/RT/yorum atılacak) Tweet URL'sini girin: ").strip()
    if not url or "x.com" not in url and "twitter.com" not in url:
        print("[!] Geçerli bir X/Twitter URL'si giriniz.")
        return

    cfg = load_config()
    accounts = [a.get("username") for a in cfg.get("accounts", []) if a.get("username")]
    if not accounts:
        print("[!] Hiç hesap tanımlı değil.")
        return

    print(f"\nMevcut hesaplar: {', '.join('@' + a for a in accounts)}")
    exclude = input("Bu tweeti atan hesabınız varsa yazın (onunla etkileşim yapılmaz, yoksa Enter): ").strip().lstrip("@")
    helper_accounts = [a for a in accounts if a.lower() != exclude.lower()]

    if not helper_accounts:
        print("[!] Etkileşim yapacak başka hesap kalmadı.")
        return

    headless_inp = input("Tarayıcı arkaplanda (gizli) mi çalışsın? [E/h]: ").strip().lower()
    headless = False if headless_inp == 'h' else True

    pod_mgr.boost_tweet(
        tweet_url=url,
        helper_accounts=helper_accounts,
        do_like=True,
        do_retweet=True,
        do_comment=True,
        headless=headless
    )

def menu_full_automated_cycle(pod_mgr: EngagementPodManager):
    cfg = load_config()
    accounts = cfg.get("accounts", [])
    if not accounts:
        print("[!] Lütfen önce en az 2 hesap tanımlayın.")
        return

    # Find analyst account or use first account
    analyst_acc = None
    for a in accounts:
        if a.get("role") == "analyst":
            analyst_acc = a.get("username")
            break
    if not analyst_acc:
        analyst_acc = accounts[0].get("username")

    helpers = [a.get("username") for a in accounts if a.get("username") and a.get("username") != analyst_acc]

    print(f"\n[🚀] Otomatik Döngü Planı:")
    print(f"  • Ana Paylaşımcı: @{analyst_acc}")
    print(f"  • Destek/Kasacak Hesaplar: {', '.join('@' + h for h in helpers)}")
    
    headless_inp = input("Tarayıcı arkaplanda (gizli) mi çalışsın? [E/h]: ").strip().lower()
    headless = False if headless_inp == 'h' else True

    pod_mgr.post_and_cross_boost(
        poster_account=analyst_acc,
        helper_accounts=helpers,
        headless=headless
    )

def interactive_loop():
    print_banner()
    cfg = load_config()
    ai_settings = cfg.get("ai_settings", {})
    provider = ai_settings.get("provider", "auto")
    gemini_key = ai_settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    groq_key = ai_settings.get("groq_api_key") or os.getenv("GROQ_API_KEY")
    
    ai_gen = BISTContentGenerator(provider=provider, api_key=gemini_key or groq_key)
    browser_mgr = TwitterBrowserManager()
    pod_mgr = EngagementPodManager(browser_mgr, ai_gen)

    while True:
        list_accounts_status(browser_mgr)
        print("LÜTFEN BİR İŞLEM SEÇİN:")
        print(" [1] Yeni Hesaba Giriş Yap (Tarayıcı açıp 1 kez giriş yap)")
        print(" [2] auth_token Çerezi ile Hızlı Oturum Ekle")
        print(" [3] Canlı BİST Verilerini Görüntüle")
        print(" [4] AI BİST Tweet'i Üret (Önizleme)")
        print(" [5] Belirli Bir Tweet'i Kas (URL vererek Beğen + RT + AI Yorumu)")
        print(" [6] TAM DÖNGÜ: BIST Analizi Tweetle + Diğer Hesaplarla Birbirini Kas")
        print(" [7] Çıkış")
        
        choice = input("\nSeçiminiz [1-7]: ").strip()

        if choice == "1":
            menu_login(browser_mgr)
        elif choice == "2":
            menu_add_cookie(browser_mgr)
        elif choice == "3":
            menu_show_market()
        elif choice == "4":
            bist = BISTMarketData()
            m = bist.get_market_overview()
            tw = ai_gen.generate_bist_tweet(m)
            print(f"\n--- ÜRETİLEN BİST TWEETİ ({len(tw)} karakter) ---")
            print(tw)
            print("--------------------------------------------------\n")
        elif choice == "5":
            menu_boost_url(pod_mgr)
        elif choice == "6":
            menu_full_automated_cycle(pod_mgr)
        elif choice == "7":
            print("\nÇıkış yapılıyor...")
            browser_mgr.stop()
            break
        else:
            print("[!] Geçersiz seçim.")

        input("\nDevam etmek için Enter'a basın...")

def main():
    parser = argparse.ArgumentParser(description="X BIST Bot & Mutual Engagement Pod")
    parser.add_argument("--login", type=str, help="Kullanıcı adı ile manuel tarayıcı girişi yapıp oturumu kaydeder")
    parser.add_argument("--set-cookie", nargs="+", help="Kullanıcı adı ve auth_token [ct0] ile oturum kaydeder")
    parser.add_argument("--post-bist", action="store_true", help="Canlı BIST verisiyle tweet atar")
    parser.add_argument("--account", type=str, help="İşlem yapılacak hesap adı")
    parser.add_argument("--boost", type=str, help="Verilen tweet URL'sini diğer hesaplarla kasar")
    parser.add_argument("--status", action="store_true", help="Hesap oturum durumlarını listeler")
    parser.add_argument("--headless", action="store_true", default=True, help="Tarayıcıyı arkaplanda çalıştırır")

    args = parser.parse_args()

    cfg = load_config()
    ai_settings = cfg.get("ai_settings", {})
    provider = ai_settings.get("provider", "auto")
    gemini_key = ai_settings.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    groq_key = ai_settings.get("groq_api_key") or os.getenv("GROQ_API_KEY")

    ai_gen = BISTContentGenerator(provider=provider, api_key=gemini_key or groq_key)
    browser_mgr = TwitterBrowserManager()
    pod_mgr = EngagementPodManager(browser_mgr, ai_gen)

    if args.status:
        list_accounts_status(browser_mgr)
    elif args.login:
        browser_mgr.interactive_login(args.login)
    elif args.set_cookie:
        uname = args.set_cookie[0]
        token = args.set_cookie[1] if len(args.set_cookie) > 1 else ""
        ct0 = args.set_cookie[2] if len(args.set_cookie) > 2 else None
        browser_mgr.create_session_from_cookies(uname, token, ct0)
    elif args.boost:
        accounts = [a.get("username") for a in cfg.get("accounts", []) if a.get("username")]
        pod_mgr.boost_tweet(args.boost, accounts, headless=args.headless)
    elif args.post_bist:
        acc = args.account or (cfg.get("accounts", [{}])[0].get("username"))
        helpers = [a.get("username") for a in cfg.get("accounts", []) if a.get("username") != acc]
        pod_mgr.post_and_cross_boost(acc, helpers, headless=args.headless)
    else:
        interactive_loop()

if __name__ == "__main__":
    main()
