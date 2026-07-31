# AMiner 30-day 评估报告 (2026-08-01)

**触发**: cron `aminer-30day-eval`, 2026-08-01 00:00 (token 17 days into 60-day TTL)
**目标**: 验证 AMiner 引用覆盖率提升是否仍 ≥ +7pp, 决定 API 续费
**测试方法**: 复用 v3.9.8.0 baseline 的 3 个 query, 同条件重测 (clash 7897 代理)

## 1. 测试结果 (DEDUP cite% 对比)

| Query (经济学方向) | 域 | Baseline (5 engines) | With AMiner | Δ cite% |
|---|---|---|---|---|
| 数字普惠金融 家庭消费 | 经济学 | 48.1% (n=27) | 58.8% (n=34) | **+10.7pp** |
| 长期护理保险 人口老龄化 | 保险学 | 34.0% (n=47) | 41.5% (n=53) | **+7.5pp** |
| 金融科技 中小银行 | 金融学 | 52.7% (n=55) | 55.9% (n=59) | **+3.2pp** |
| **平均** | | | | **+7.1pp** |

vs 2026-07-15 baseline (17 days 前): **+10.9pp**
vs 2026-08-01 today: **+7.1pp**

✅ **仍超过 +7pp 阈值** (虽然比初始 baseline 略降, 但 lift 仍是正数)

## 2. AMiner 单独指标 (不变)

| Query | n | cite>0% | abstract% | top1 cite |
|---|---|---|---|---|
| 数字普惠金融 家庭消费 | 7 | 100% | 0% | 30 (11-50 桶) |
| 长期护理保险 人口老龄化 | 6 | 100% | 0% | 30 (11-50 桶) |
| 金融科技 中小银行 | 4 | 100% | 0% | 30 (11-50 桶) |

**AMiner 仍 100% cite 覆盖** (因为 bucketed 字段, 最低 1-10 桶也算 cite>0)
**0% abstract** (一如既往, 已知 limitation)
**top-1 稳定 30 (11-50 桶)** — AMiner 中文 paper 的引用追踪是稳定强项

## 3. Token 状态 & 消耗估算

- **Token TTL**: 60 天 (2026-07-15 → 2026-09-13), 当前 17 天, 还剩 43 天
- **免费 quota**: 3880 calls 一次性体验金
- **已消耗估算** (v3.9.8.0 验证 + 30-day eval × 2):
  - 2026-07-15 baseline: ~15 calls
  - 2026-08-01 today: ~6 calls (with-AMiner run only)
  - **累计 ≈ 21 calls** (远低于 3880 quota)
- **平均每 query 消耗**: ~2-3 calls (含 query splitter 拆分)

**结论**: 3880 免费 quota 还没用完, **Token 充值决策可以推迟**。

## 4. 新增发现 (与 7-15 baseline 对比)

1. **S2 engine 复活了**: 2026-07-15 时 S2 = EMPTY (429 限流), 今天 S2 = 20 results 25-30% cite.
   - 原因: 加了 clash 7897 代理后, S2 限流被绕过 (v3.9.8.2 proxy support)
2. **Crossref 中文数据变差**: 2026-07-15 时 crossref 25-30% cite, 今天 25-45% cite (样本波动)
3. **OpenAlex 数字普惠金融 query**: 7-15 时 100% cite (n=3), 今天 100% cite (n=4) — 稳定
4. **DEDUP 总数增多**: 3 个 query DEDUP 总数从 baseline 25-55 → with-AMiner 53-59 (说明 AMiner 找到的 paper 不重复)

## 5. 决策建议

| 选项 | 评估 |
|---|---|
| **A. 维持现状** (继续用 AMiner, 不充值) | ✅ 推荐 |
| **B. 立刻充值** (锁定 60 天 Token) | ❌ 3880 quota 还剩 3859+, 没必要 |
| **C. 撤掉 AMiner** ([P1-7] 移除) | ❌ +7.1pp lift 仍超阈值, 价值明显 |

**推荐 A**, 但加一个 60-day 后续监控:
- 2026-09-13 token 到期前再跑一次 eval
- 那时如果 quota 还没用完, 决策"自然续期 vs 撤掉"
- 如果 quota 在 09-13 前用完, 决策"充值 vs 撤掉"

**长期路径** (ROADMAP 已记):
- [P1-7] AMiner 标记 ✅ DONE in v3.9.8.0
- 持续 cite% lift ≥ +7pp = 续费, < +7pp = 撤掉
- 撤掉后走 [P1-8] `pa fetch` 全文路径 (Unpaywall 兜底)

## 6. cron 行为建议

`aminer-30day-eval` 当前 schedule `0 0 */30 * *` 没问题, 30 天周期足够.
下次自动触发: 2026-08-31 00:00 (距今 30 天).

如果想提早触发 (例如 quota 突然见底), 用:
```
mavis cron trigger aminer-30day-eval
```

## 7. 诚实 caveat

- 30-day eval 只跑了 3 个 query (跟 baseline 一致), 样本小 (n=27-59)
- +7.1pp 是均值, 个别 query 涨 +10.7pp / 跌 +3.2pp 不等
- AMiner 中文 paper 优势 100% cite 是 bucketed 字段假象, 真实粒度比 OpenAlex/Crossref 粗
- "3880 calls quota" 是 AMiner 文档说法, 实际可能有 undocumented soft cap (用户没观察到)

**最终**: 维持现状 ✅
