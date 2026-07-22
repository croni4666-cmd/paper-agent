"""RePEc / IDEAS 端点测试 (no API key)"""
import sys, os
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
import urllib.request as ur, urllib.parse, json

def fetch(url, label, timeout=30):
    print(f"\n=== {label} ===")
    print(f"  URL: {url}")
    headers = {"User-Agent": "Mozilla/5.0 paper-agent/3.9.8.1 (Mavis)"}
    try:
        req = ur.Request(url, headers=headers)
        resp = ur.urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        print(f"  status: {resp.status}, body length: {len(body)}")
        if resp.status == 200 and len(body) < 5000:
            print(f"  body (first 800): {body[:800]}")
        elif resp.status == 200:
            print(f"  body preview: {body[:300]}...")
        return body
    except Exception as e:
        print(f"  ERR: {type(e).__name__}: {e}")
        return None

# 1. IDEAS HTD2 JSON 端点 (公开可用, 不需 key)
fetch("https://ideas.repec.org/cgi-bin/htd2?q=digital+finance&fmt=json", "IDEAS HTD2 search: digital finance")

# 2. 试中文 query
fetch("https://ideas.repec.org/cgi-bin/htd2?q=%E6%95%B0%E5%AD%97%E6%99%AE%E6%83%A0%E9%87%91%E8%9E%8D&fmt=json", "IDEAS HTD2 search: digital finance (zh)")

# 3. RePEc API 公开端点
fetch("https://api.repec.org/working_papers?handle=RePEc:bon:bonedp:bgse12_2012", "RePEc working papers endpoint")
