# Probe: legacy search.cnki.net / .com.cn cite/dl availability
**Date**: 2026-07-15 12:33:45
**Cookie age**: 1.9h

**Keyword**: `东数西算` (4-char Chinese, 强制 URL encode)

---

**Loaded cookies**: 4 entries

## Step 1: xueshu789 bootstrap

After bootstrap, final URL: `https://www.xueshu789.com/dbItem/1`

## Step 2: search.cnki.net (post-2017)

**Request**: `https://search.cnki.net/search.aspx?q=东数西算&rank=citeNumber&cluster=all&val=CDFDTOTAL&p=0`

❌ Request failed: Page.goto: Download is starting
Call log:
  - navigating to "https://search.cnki.net/search.aspx?q=%E4%B8%9C%E6%95%B0%E8%A5%BF%E7%AE%97&rank=citeNumber&cluster=all&val=CDFDTOTAL&p=0", waiting until "domcontentloaded"


---

## Step 2: search.cnki.com.cn (pre-2017)

**Request**: `https://search.cnki.com.cn/Search.aspx?q=东数西算&rank=citeNumber&cluster=all&val=&p=0`

**HTTP status**: 404

**Landed at**: `https://search.cnki.com.cn/Search.aspx?q=%E4%B8%9C%E6%95%B0%E8%A5%BF%E7%AE%97&rank=citeNumber&cluster=all&val=&p=0`

**HTML length**: 148 bytes

**Raw HTML saved**: `_probe_old_search_search_cnki_com_cn.html`

**Field indicators in HTML**:

- · `被引`: 0 occurrences
- · `下载`: 0 occurrences
- · `引用次数`: 0 occurrences
- · `被引次数`: 0 occurrences
- · `下载次数`: 0 occurrences
- · `cite`: 0 occurrences
- · `download`: 0 occurrences
- · `captcha`: 0 occurrences
- · `登录`: 0 occurrences

**Page title**: `404 Not Found`

---

## Verdict

**Read this to decide:**

1. If `Landed at` for both endpoints is `kns.cnki.net/...` → 302'd, **old interface dead**, fall back to v3.9.7.5 list (no cite).
2. If `被引` / `引用次数` / `下载次数` HTML count > 0 AND `cite` field appears in saved HTML → **old interface alive**, can wire cite/dl into v3.9.7.6.
3. If `captcha` / `安全验证` > 0 → blocked, need different cookie set.

