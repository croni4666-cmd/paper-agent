# PDF 批量下载指南 (paper-agent v3.9.8.3 batch)

输入: 5 个 DOI
成功搜索到 metadata: 5 篇
未找到: 0 篇
错误: 0 篇

## 准备 (5 分钟一次性)

1. 打开 Edge，访问 https://www.xueshu789.com/dbList/1
2. 点 '**知网 [PDF格式 最好用]**' 按钮（'中文数据库' 区）
3. 跳到知网搜索页后，按 **F12** → '**控制台**' tab
4. 把下面 JS 整个粘进去，按 Enter：

```javascript
// 1. Find all doDownload links
const links = Array.from(document.querySelectorAll('a[href*="/doDownload/"]'))
                     .map(a => a.href)
                     .filter(href => !href.startsWith('javascript:'));

// 2. Display count and sample
console.log('Found ' + links.length + ' doDownload URLs');
links.slice(0, 3).forEach((url, i) => console.log('[' + (i+1) + '] ' + url.substring(0, 80) + '...'));

// 3. Copy to clipboard (one URL per line)
const text = links.join('\n');
navigator.clipboard.writeText(text).then(() => {
  console.log('\n[OK] Copied ' + links.length + ' URLs to clipboard. Paste into fetch_urls.txt');
});

// 4. Also open first 5 URLs in new tabs (for batch verification)
links.slice(0, 5).forEach((url, i) => {
  setTimeout(() => window.open(url, '_blank'), i * 300);
});
console.log('\n[OK] Opened first 5 URLs in new tabs. Solve CAPTCHA per tab, PDFs download automatically.');

```

JS 会自动打开搜索框（无）— 你需要**手动输入 query** 触发 search，
然后 search result 页面出现后，**再跑一次** 这个 JS：
JS 会：(a) 找所有 /doDownload/ 链接 (b) 复制到剪贴板 (c) 自动开 5 个新 tab

## 论文列表

| # | Title | DOI | Year | Status | xueshu789 Search |
|---|-------|-----|------|--------|------------------|
| 1 | 数字普惠金融对经济高质量发展的影响研究 | 10.3969/j.issn.1003-9031.2022.04.008 | 2022 | found | https://www.xueshu789.com/dbItem/2?keyValue=%E6%95%B0%E5%AD%97%E6%99%AE%E6%83%A0%E9%87%91%E8%9E%8D%E5%AF%B9%E7%BB%8F%E6%B5%8E%E9%AB%98%E8%B4%A8%E9%87%8F%E5%8F%91%E5%B1%95%E7%9A%84%E5%BD%B1%E5%93%8D%E7%A0%94%E7%A9%B6 |
| 2 | 数字普惠金融与共同富裕:理论机制与经验事实 |  | 2022 | found | https://www.xueshu789.com/dbItem/2?keyValue=%E6%95%B0%E5%AD%97%E6%99%AE%E6%83%A0%E9%87%91%E8%9E%8D%E4%B8%8E%E5%85%B1%E5%90%8C%E5%AF%8C%E8%A3%95%3A%E7%90%86%E8%AE%BA%E6%9C%BA%E5%88%B6%E4%B8%8E%E7%BB%8F%E9%AA%8C%E4%BA%8B%E5%AE%9E |
| 3 | 数字普惠金融、科技创新与制造业产业结构升级 | 10.16525/j.cnki.14-1362/n.2022.08.004 | 2022 | found | https://www.xueshu789.com/dbItem/2?keyValue=%E6%95%B0%E5%AD%97%E6%99%AE%E6%83%A0%E9%87%91%E8%9E%8D%E3%80%81%E7%A7%91%E6%8A%80%E5%88%9B%E6%96%B0%E4%B8%8E%E5%88%B6%E9%80%A0%E4%B8%9A%E4%BA%A7%E4%B8%9A%E7%BB%93%E6%9E%84%E5%8D%87%E7%BA%A7 |
| 4 | 数字金融发展与家庭消费碳排放 | 10.3969/j.issn.1000-8306.2022.04.009 | 2022 | found | https://www.xueshu789.com/dbItem/2?keyValue=%E6%95%B0%E5%AD%97%E9%87%91%E8%9E%8D%E5%8F%91%E5%B1%95%E4%B8%8E%E5%AE%B6%E5%BA%AD%E6%B6%88%E8%B4%B9%E7%A2%B3%E6%8E%92%E6%94%BE |
| 5 | 互联网使用与城乡家庭消费——来自CGSS数据的证据 | 10.19820/j.cnki.ISSN2096-7411.2022.05.006 | 2022 | found | https://www.xueshu789.com/dbItem/2?keyValue=%E4%BA%92%E8%81%94%E7%BD%91%E4%BD%BF%E7%94%A8%E4%B8%8E%E5%9F%8E%E4%B9%A1%E5%AE%B6%E5%BA%AD%E6%B6%88%E8%B4%B9%0D%E2%80%94%E2%80%94%E6%9D%A5%E8%87%AACGSS%E6%95%B0%E6%8D%AE%E7%9A%84%E8%AF%81%E6%8D%AE |

## 操作流程

### A. 对每篇 paper，**手动走一次**这套流程：

1. 在 xueshu789 知网搜索页 输入 **论文标题**（或 DOI）
2. 找到 search result 列表页
3. 在 Console 再跑一次上面的 JS
4. JS 自动复制所有 doDownload URL 到剪贴板
5. JS 自动开前 5 个 tab → 你**手动** verify CAPTCHA
6. 每个 tab 的 PDF 自动下载到 Edge 的 `Downloads/` 目录
7. 全部 verify 完成后，看 Downloads/ 找新下载的 PDF 文件

### B. 或者**半批量**做法（10+ 篇一次）：

1. 在 xueshu789 搜索一次（如 '数字普惠金融 家庭消费'）
2. search result 列表有 10-20 篇相关 paper
3. 在 Console 跑 JS，**所有 doDownload URL 都到剪贴板**
4. 粘到 `fetch_urls.txt`
5. 用这个命令打开全部：

```powershell
# PowerShell: 打开 fetch_urls.txt 里的所有 URL
Get-Content fetch_urls.txt | ForEach-Object { Start-Process msedge $_ }
```

6. 每个 tab 手动 verify CAPTCHA
7. Edge 自动下载所有 PDF

## 限制

- **xueshu789 cookies 4-8h 过期** — 超过需要重新 export
- **bar.cnki.net vLevel=5 CAPTCHA** 必须人手动过（无 AI 绕过）
- **proxy IP 不稳定** — xueshu789.com 偶尔换 IP，4 cookies 可能失效
- **一次 verify 有效期短** — 同一 session 多次 verify 可能需要重新点

## 失败时怎么办

| 失败现象 | 原因 | 解决 |
|----------|------|------|
| console 没找 doDownload 链接 | xueshu789 search 用 POST，URL 不在 HTML | 触发 search 后 JS 才能找 |
| verify 页面没出现 / 直接跳 PDF | cookies 还新鲜，bar.cnki.net 信任你 | 继续下 |
| verify 一直过不去 | cookies 过期了 | 重跑 `pa fetch --export-cookies` |
| '安全验证' / vLevel 跳 5 | bar.cnki.net 检测到异常 | 24h 后再试（IP 池刷新）|

## 自动化的真正瓶颈

paper-agent 在 v3.9.8.3 试过 4 种方法全失败（v3.9.8.3 commit bdaa9a6）：

1. ❌ 直接 urllib 下载 — 触发 vLevel=5
2. ❌ playwright + 4 cookies — 触发 vLevel=5
3. ❌ playwright + user profile — 需要关 Edge + 弹窗
4. ❌ playwright + browser fingerprint spoofing — TLS 指纹暴露

**CAPTCHA vLevel=5 是 anti-bot 终极防御**，hobbyist 范围内无解。
User 手动 Edge + JS 批量抓是**目前最快**的方案。