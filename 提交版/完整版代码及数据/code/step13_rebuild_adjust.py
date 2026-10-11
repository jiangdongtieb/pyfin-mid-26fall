# -*- coding: utf-8 -*-
"""
step13 自己构造复权价，并与东财后复权、CSMAR后复权、东财前复权做三方核对
做法（课上 Class03 「数据清洗与准备」的标准套路）：
  1) 从分红送转明细算出每个除权除息日的「除权除息参考价」
       P_ref(t) = (P(t-1) - 每股现金红利) / (1 + 每10股转增比例/10)
  2) 真实日收益率（含红利再投资）= P(t) / P_ref(t) - 1
  3) 复权因子 F(t) = F(t-1) × P(t-1) / P_ref(t)，后复权价 = 原始价 × F(t)
  4) 前复权价 = 原始价 × F(t) / F(最后一天)   （把基准挪到今天，方便和现价对照）
  5) 与三个现成序列比收益率，看谁和我构造的一致
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd

MINE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\data_raw"
THEIRS = r"C:\Users\35632\Desktop\python期中大作业\data"
OUT = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\output"
R = []


def log(m=""):
    print(m, flush=True)
    R.append(str(m))


bfq = pd.read_csv(MINE + r"\em_002714_bfq.csv", parse_dates=["日期"]).set_index("日期").sort_index()
hfq = pd.read_csv(MINE + r"\em_002714_hfq.csv", parse_dates=["日期"]).set_index("日期").sort_index()
qfq = pd.read_csv(MINE + r"\em_002714_qfq.csv", parse_dates=["日期"]).set_index("日期").sort_index()
tq = pd.concat([pd.read_csv(THEIRS + "\\" + f, parse_dates=["TradingDate"]) for f in
                ["TRD_BwardQuotation.csv", "TRD_BwardQuotation_2022_2025.csv",
                 "TRD_BwardQuotation_2026_2026.csv"]]).drop_duplicates("TradingDate").set_index("TradingDate").sort_index()
dv = pd.read_csv(MINE + r"\fhps_002714.csv", parse_dates=["EX_DIVIDEND_DATE", "EQUITY_RECORD_DATE"])

# ---------- 0. 先看清东财后复权到底哪里不一致 ----------
r_bfq = bfq["收盘"].pct_change()
r_hfq = hfq["收盘"].pct_change()
diff = (r_hfq - r_bfq).abs()
bad = diff[diff > 5e-4]
log("东财 hfq 与原始价收益不一致的日子：%d 天，首日 %s，末日 %s" %
    (len(bad), bad.index.min().date() if len(bad) else "-", bad.index.max().date() if len(bad) else "-"))
log("  其中 2026-06 之后占 %d 天；hfq收益/bfq收益 的中位数 %.4f" %
    (int((bad.index >= "2026-06-01").sum()), (r_hfq / r_bfq).replace([np.inf, -np.inf], np.nan).dropna().median()))

# ---------- 1. 自建除权除息参考价 ----------
dv = dv.copy()
dv["ex_dt"] = dv["EX_DIVIDEND_DATE"].dt.normalize()
dv["每股派息"] = dv["PRETAX_BONUS_RMB"] / 10.0
dv["每股转增"] = dv["BONUS_IT_RATIO"].fillna(0) / 10.0
dv = dv.sort_values("ex_dt")
log("\n分红送转明细（除权除息日 / 每股派息 / 每股转增）：")
log(dv[["ex_dt", "每股派息", "每股转增", "IMPL_PLAN_PROFILE"]].to_string(index=False)[:1600])

# 只保留落在我们行情区间内的除权日
events = dv[(dv["ex_dt"] >= bfq.index.min()) & (dv["ex_dt"] <= bfq.index.max())]
log("\n落在行情区间内的除权除息日：%d 个 -> %s" %
    (len(events), [str(d.date()) for d in events["ex_dt"]]))
missing_in_price = [d for d in events["ex_dt"] if d not in bfq.index]
log("其中在行情里找不到对应日期的：%s" % ([str(d.date()) for d in missing_in_price] or "无"))

# ---------- 2. 逐日推复权因子 ----------
close_raw = bfq["收盘"]
factor = pd.Series(1.0, index=bfq.index)
ref_price = close_raw.shift(1)          # 默认除权除息参考价 = 昨收盘
detail = []
for _, row in events.iterrows():
    d = row["ex_dt"]
    if d not in close_raw.index:
        # 除权日不是交易日时，顺延到下一个交易日
        loc = close_raw.index.searchsorted(d)
        if loc >= len(close_raw.index):
            continue
        d = close_raw.index[loc]
        detail.append("除权日 %s 非交易日，顺延到 %s" % (row["ex_dt"].date(), d.date()))
    prev_idx = close_raw.index.get_loc(d) - 1
    if prev_idx < 0:
        continue
    p_prev = close_raw.iloc[prev_idx]
    p_ref = (p_prev - row["每股派息"]) / (1.0 + row["每股转增"])
    ref_price.loc[d] = p_ref
    detail.append("%s  昨收 %.2f  派息 %.4f  转增 %.2f  参考价 %.4f" %
                  (d.date(), p_prev, row["每股派息"], row["每股转增"], p_ref))

# 复权因子：F(t) = F(t-1) * P(t-1) / P_ref(t)
ratio = (close_raw.shift(1) / ref_price).fillna(1.0)
ratio.iloc[0] = 1.0
factor = ratio.cumprod()

adj_close = close_raw * factor                                   # 后复权（含红利再投资）
adj_close_qfq = close_raw * factor / factor.iloc[-1]             # 前复权
true_ret = (close_raw / ref_price) - 1.0                         # 真实日收益率（含红利再投资）

log("\n除权除息参考价明细：")
for x in detail:
    log("  " + x)

# ---------- 3. 三方核对 ----------
log("\n" + "=" * 78)
log("收益率口径核对（相关系数 / 平均绝对差 / 不一致天数(>0.05%)）")
log("=" * 78)
csmar_ret = tq["ClosePrice"].pct_change().reindex(bfq.index)
r_qfq = qfq["收盘"].pct_change()
series = {"我构造(含红利)": true_ret, "东财hfq": r_hfq, "东财qfq": r_qfq,
          "东财原始收盘": r_bfq, "CSMAR后复权": csmar_ret}
pairs = list(series.items())
rows = []
for i in range(len(pairs)):
    for k in range(i + 1, len(pairs)):
        n1, s1 = pairs[i]
        n2, s2 = pairs[k]
        d = pd.concat([s1.rename("a"), s2.rename("b")], axis=1).dropna()
        if len(d) < 100:
            continue
        dd = (d["a"] - d["b"]).abs()
        rows.append({"A": n1, "B": n2, "相关系数": round(d["a"].corr(d["b"]), 8),
                     "平均绝对差": round(dd.mean(), 8), "最大绝对差": round(dd.max(), 6),
                     "差>0.05%天数": int((dd > 5e-4).sum())})
cmp_df = pd.DataFrame(rows)
log(cmp_df.to_string(index=False))
cmp_df.to_csv(OUT + r"\compare_price_conventions.csv", index=False, encoding="utf-8-sig")

# 在除权日上具体看差异
log("\n除权除息日前后收益率对照（我构造 / 东财hfq / CSMAR / 原始）：")
for d in events["ex_dt"]:
    if d in true_ret.index:
        log("  %s  我构造 %+.4f%%  东财hfq %+.4f%%  CSMAR %+.4f%%  原始 %+.4f%%" %
            (d.date(), true_ret.loc[d] * 100,
             r_hfq.get(d, np.nan) * 100, csmar_ret.get(d, np.nan) * 100, r_bfq.get(d, np.nan) * 100))

# ---------- 4. 落盘：干净的日度面板 ----------
panel = pd.DataFrame({
    "trade_date": bfq.index,
    "close_raw": close_raw.values,
    "open_raw": bfq["开盘"].values,
    "high_raw": bfq["最高"].values,
    "low_raw": bfq["最低"].values,
    "volume_hand": bfq["成交量"].values,
    "amount_yuan": bfq["成交额"].values,
    "turnover_pct": bfq["换手率"].values,
    "pct_chg_ex": bfq["涨跌幅"].values,
    "ref_price": ref_price.values,
    "adj_factor": factor.values,
    "close_hfq": adj_close.values,
    "close_qfq": adj_close_qfq.values,
    "ret_daily": true_ret.values,
    "em_hfq_close": hfq["收盘"].reindex(bfq.index).values,
    "csmar_bward_close": tq["ClosePrice"].reindex(bfq.index).values,
    "csmar_total_share": tq["TotalShare"].reindex(bfq.index).values,
    "csmar_market_value": tq["MarketValue"].reindex(bfq.index).values,
    "csmar_turnover": tq["TurnoverRate1"].reindex(bfq.index).values,
})
panel.to_csv(OUT + r"\panel_daily_raw_check.csv", index=False, encoding="utf-8-sig")
log("\n面板已保存 panel_daily_raw_check.csv  %d 行 x %d 列" % (len(panel), panel.shape[1]))
log("最后一个复权因子 %.4f；最后收盘价 原始 %.2f / 后复权 %.2f / 前复权 %.2f" %
    (factor.iloc[-1], close_raw.iloc[-1], adj_close.iloc[-1], adj_close_qfq.iloc[-1]))

with open(r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\log\step13_复权重建.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(R))
