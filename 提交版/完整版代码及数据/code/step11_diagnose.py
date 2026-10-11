# -*- coding: utf-8 -*-
"""
step11 诊断两件事：
1) 我和对方的后复权价为什么在大波动日出现 1% 级别差异（复权口径：是否含现金红利再投资）
2) 总市值口径：用 不复权收盘价 × 总股本（按股本变动表前向填充）自己算，再和对方 CSMAR 的 MarketValue 比
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd

MINE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\data_raw"
THEIRS = r"C:\Users\35632\Desktop\python期中大作业\data"
R = []


def log(m=""):
    print(m, flush=True)
    R.append(str(m))


hfq = pd.read_csv(MINE + r"\em_002714_hfq.csv", parse_dates=["日期"]).set_index("日期")
bfq = pd.read_csv(MINE + r"\em_002714_bfq.csv", parse_dates=["日期"]).set_index("日期")
tq = pd.concat([pd.read_csv(THEIRS + "\\" + f, parse_dates=["TradingDate"]) for f in
                ["TRD_BwardQuotation.csv", "TRD_BwardQuotation_2022_2025.csv",
                 "TRD_BwardQuotation_2026_2026.csv"]]).drop_duplicates("TradingDate").set_index("TradingDate").sort_index()

log("=" * 74)
log("1) 逐日核对：我方三种口径 vs 对方后复权")
log("=" * 74)
for win in [("2026-06-24", "2026-07-03"), ("2023-10-16", "2023-10-23")]:
    a = hfq.loc[win[0]:win[1], ["收盘", "涨跌幅"]]
    b = bfq.loc[win[0]:win[1], ["收盘"]]
    c = tq.loc[win[0]:win[1], ["ClosePrice", "ChangeRatio"]]
    m = a.join(b.rename(columns={"收盘": "不复权收盘"})).join(c.rename(columns={"ClosePrice": "对方后复权收盘",
                                                                             "ChangeRatio": "对方ChangeRatio"}))
    m["我方hfq收益%"] = m["收盘"].pct_change() * 100
    m["我方bfq收益%"] = m["不复权收盘"].pct_change() * 100
    m["对方收益%"] = m["对方后复权收盘"].pct_change() * 100
    log("\n--- %s ~ %s ---" % win)
    log(m[["不复权收盘", "收盘", "对方后复权收盘", "涨跌幅", "对方ChangeRatio",
           "我方hfq收益%", "我方bfq收益%", "对方收益%"]].round(4).to_string())

log("\n对方数据里多出来的 250 天（非交易日）长什么样：")
extra = tq.loc[~tq.index.isin(bfq.index)]
log("  行数 %d，其中收盘价为空的 %d 行，成交量为0或空的 %d 行" %
    (len(extra), int(extra["ClosePrice"].isna().sum()),
     int(((extra["Volume"].isna()) | (extra["Volume"] == 0)).sum())))
log(extra.head(6).to_string()[:600])

log("\n" + "=" * 74)
log("2) 总市值口径核对")
log("=" * 74)
sc = pd.read_csv(MINE + r"\em_share_change.csv", parse_dates=["变更日期"]).sort_values("变更日期")
shares = sc.set_index("变更日期")["总股本"]
daily_shares = shares.reindex(bfq.index, method="ffill")
log("股本变动表覆盖 %s ~ %s；对齐到交易日后缺失 %d 天" %
    (shares.index.min().date(), shares.index.max().date(), int(daily_shares.isna().sum())))
cap_mine = bfq["收盘"] * daily_shares
cap_theirs = tq["MarketValue"].reindex(bfq.index)
cmp = pd.DataFrame({"我方市值(亿)": cap_mine / 1e8, "对方MarketValue": cap_theirs,
                    "对方/1e8": cap_theirs / 1e8,
                    "对方总股本": tq["TotalShare"].reindex(bfq.index)}).dropna()
cmp["对方市值/我方市值"] = cmp["对方/1e8"] / cmp["我方市值(亿)"]
log(cmp.tail(6).round(4).to_string())
log("\n比值 (对方MarketValue / 我方不复权收盘×总股本)：中位数 %.4f  均值 %.4f  标准差 %.4f" %
    (cmp["对方市值/我方市值"].median(), cmp["对方市值/我方市值"].mean(), cmp["对方市值/我方市值"].std()))
log("对数收益率相关系数（我方市值 vs 对方市值）%.6f" %
    np.corrcoef(np.log(cmp["我方市值(亿)"]).diff().dropna(), np.log(cmp["对方/1e8"]).diff().dropna())[0, 1])
log("对方 TotalShare 与我方股本表 ffill 的一致比例 %.4f" %
    (cmp["对方总股本"].values == daily_shares.reindex(cmp.index).values).mean()
    if "对方总股本" in cmp else float("nan"))
log("最近一日：我方总股本 %s，对方总股本 %s" % (shares.iloc[-1], tq["TotalShare"].dropna().iloc[-1]))

with open(r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\log\step11_诊断.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(R))
