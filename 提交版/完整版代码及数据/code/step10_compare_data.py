# -*- coding: utf-8 -*-
"""
step10 数据源比对：我下载的数据 vs 另一个 agent 下载的数据（只比原始数据，不看对方的分析结果）
比对项：
  A. 交易日覆盖 / 行数 / 重复
  B. 后复权收盘价：日收益率是否一致（复权基准不同不影响收益率）
  C. 收盘价×总股本 得到的总市值 vs 对方 CSMAR 的 MarketValue
  D. 沪深300 指数点位与收益率
  E. 三张财务报表 + 公告日期：同源代码是否完全一致（我自己下的 vs 对方下的）
输出 log/step10_数据比对结果.txt + output/compare_data_sources.csv
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import pandas as pd

MINE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\data_raw"
THEIRS = r"C:\Users\35632\Desktop\python期中大作业\data"
OUT = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\output"
REPORT = []


def log(m=""):
    print(m, flush=True)
    REPORT.append(str(m))


# ---------------- A. 行情主体 ----------------
mine_hfq = pd.read_csv(MINE + r"\em_002714_hfq.csv", parse_dates=["日期"])
mine_bfq = pd.read_csv(MINE + r"\em_002714_bfq.csv", parse_dates=["日期"])
their_q = [pd.read_csv(os.path.join(THEIRS, f), parse_dates=["TradingDate"])
           for f in ["TRD_BwardQuotation.csv", "TRD_BwardQuotation_2022_2025.csv",
                     "TRD_BwardQuotation_2026_2026.csv"]]
their_daily = pd.read_csv(THEIRS + r"\muyuan_daily.csv", parse_dates=["TradingDate"])

log("=" * 78)
log("A. 行情数据覆盖情况")
log("=" * 78)
log("我的（东财直连，后复权）  %d 行  %s ~ %s" % (len(mine_hfq), mine_hfq["日期"].min().date(), mine_hfq["日期"].max().date()))
log("对方 muyuan_daily          %d 行  %s ~ %s  重复日期 %d 条" %
    (len(their_daily), their_daily["TradingDate"].min().date(), their_daily["TradingDate"].max().date(),
     their_daily["TradingDate"].duplicated().sum()))
for f, d in zip(["TRD_BwardQuotation", "TRD_BwardQuotation_2022_2025", "TRD_BwardQuotation_2026_2026"], their_q):
    log("  对方分片 %-32s %d 行  %s ~ %s" % (f, len(d), d["TradingDate"].min().date(), d["TradingDate"].max().date()))
log("  对方三分片合计 %d 行；去重后 %d 行" %
    (sum(len(d) for d in their_q), len(pd.concat(their_q).drop_duplicates(subset=["TradingDate"]))))

merge_q = pd.concat(their_q, ignore_index=True).drop_duplicates(subset=["TradingDate"]).sort_values("TradingDate")
both = set(mine_hfq["日期"].dt.date) & set(merge_q["TradingDate"].dt.date)
only_mine = set(mine_hfq["日期"].dt.date) - set(merge_q["TradingDate"].dt.date)
only_theirs = set(merge_q["TradingDate"].dt.date) - set(mine_hfq["日期"].dt.date)
log("交易日交集 %d 天；只有我有 %d 天；只有对方有 %d 天" % (len(both), len(only_mine), len(only_theirs)))
if only_mine:
    log("  只有我有的日期（前10）: %s" % sorted([str(d) for d in only_mine])[:10])
if only_theirs:
    log("  只有对方有的日期（前10）: %s" % sorted([str(d) for d in only_theirs])[:10])

# ---------------- B. 后复权价与日收益率 ----------------
log("")
log("=" * 78)
log("B. 后复权收盘价 / 日收益率一致性")
log("=" * 78)
a = mine_hfq.set_index("日期")[["收盘", "开盘", "最高", "最低", "成交量", "成交额", "换手率"]].copy()
b = merge_q.set_index("TradingDate")[["ClosePrice", "OpenPrice", "HighPrice", "LowPrice",
                                      "Volume", "Amount", "TurnoverRate1"]].copy()
j = a.join(b, how="inner")
j["r_mine"] = j["收盘"].pct_change()
j["r_theirs"] = j["ClosePrice"].pct_change()
ratio = j["收盘"] / j["ClosePrice"]
log("可比交易日 %d 天" % len(j))
log("收盘价比值 我/对方：均值 %.6f  标准差 %.6g  （后复权基准不同，比值应近似常数）" % (ratio.mean(), ratio.std()))
log("日收益率相关系数 %.8f" % j[["r_mine", "r_theirs"]].corr().iloc[0, 1])
d = (j["r_mine"] - j["r_theirs"]).abs()
log("日收益率绝对差：均值 %.3e   中位数 %.3e   最大 %.3e（%s）" % (d.mean(), d.median(), d.max(), d.idxmax().date() if pd.notna(d.idxmax()) else "-"))
log("绝对差 > 1e-4 的天数：%d" % int((d > 1e-4).sum()))
big = d.sort_values(ascending=False).head(6)
for dt, v in big.items():
    log("  差异较大 %s  我 %.4f%% 对方 %.4f%%" % (dt.date(), j.loc[dt, "r_mine"] * 100, j.loc[dt, "r_theirs"] * 100))

vol_ratio = (j["成交量"] / j["Volume"]).replace([np.inf, -np.inf], np.nan).dropna()
log("成交量比值 我/对方：均值 %.4f  （东财单位是手=100股，CSMAR 单位看数值）" % vol_ratio.median())

# ---------------- C. 总市值 ----------------
log("")
log("=" * 78)
log("C. 总市值（我用 不复权收盘价×总股本 自己算 vs 对方 CSMAR MarketValue）")
log("=" * 78)
sc = pd.read_csv(MINE + r"\em_share_change.csv")
log("我的股本变动表列：%s" % list(sc.columns))
log(sc.head(3).to_string()[:500])
mv_theirs = merge_q.set_index("TradingDate")["MarketValue"]
mv_theirs_b = mv_theirs / mv_theirs.iloc[0]
close_bfq = mine_bfq.set_index("日期")["收盘"]
close_bfq_b = close_bfq.reindex(mv_theirs.index)
close_bfq_b = close_bfq_b / close_bfq_b.dropna().iloc[0]
cc = pd.concat([mv_theirs_b.rename("对方市值(标准化)"), close_bfq_b.rename("我的不复权收盘(标准化)")], axis=1).dropna()
log("标准化后相关系数 %.6f  （股本不变期间应接近1；有增发/送转处会出现台阶）" % cc.corr().iloc[0, 1])

# ---------------- D. 指数 ----------------
log("")
log("=" * 78)
log("D. 沪深300 指数（我：东财 vs 对方：CSMAR TRD_Index）")
log("=" * 78)
ti = pd.read_csv(THEIRS + r"\TRD_Index.csv", parse_dates=["Trddt"])
mi = pd.read_csv(MINE + r"\em_index_000300.csv", parse_dates=["日期"])
log("对方指数代码：%s  行数 %d  %s ~ %s" % (ti["Indexcd"].unique(), len(ti), ti["Trddt"].min().date(), ti["Trddt"].max().date()))
log("我的指数行数 %d  %s ~ %s" % (len(mi), mi["日期"].min().date(), mi["日期"].max().date()))
ii = mi.set_index("日期")["收盘"].rename("mine").to_frame().join(ti.set_index("Trddt")["Clsindex"].rename("theirs"), how="inner")
log("可比交易日 %d 天" % len(ii))
if len(ii):
    diff = (ii["mine"] - ii["theirs"]).abs()
    log("收盘点位绝对差：均值 %.4f  最大 %.4f" % (diff.mean(), diff.max()))
    log("点位比值 我/对方 均值 %.6f  标准差 %.3e" % ((ii["mine"] / ii["theirs"]).mean(), (ii["mine"] / ii["theirs"]).std()))
    rr = pd.DataFrame({"rm": ii["mine"].pct_change(), "rt": ii["theirs"].pct_change()}).dropna()
    log("日收益率相关系数 %.8f  平均绝对差 %.3e" % (rr.corr().iloc[0, 1], (rr["rm"] - rr["rt"]).abs().mean()))

# ---------------- E. 财务报表同源核对 ----------------
log("")
log("=" * 78)
log("E. 财务报表 / 公告日期：我自己从 CSMAR 下的 vs 对方从 CSMAR 下的")
log("=" * 78)
pairs = [("fs_combas.csv", "FS_Combas.csv", ["Stkcd", "Accper", "Typrep"]),
         ("fs_comins.csv", "FS_Comins.csv", ["Stkcd", "Accper", "Typrep"]),
         ("fs_comscfd.csv", "FS_Comscfd.csv", ["Stkcd", "Accper", "Typrep"]),
         ("iar_rept.csv", "IAR_Rept.csv", ["Stkcd", "Accper"])]
rows = []
for mf, tf, keys in pairs:
    m = pd.read_csv(os.path.join(MINE, mf))
    t = pd.read_csv(os.path.join(THEIRS, tf))
    common = [c for c in t.columns if c in m.columns and c not in keys]
    mm = m.merge(t, on=keys, how="inner", suffixes=("_mine", "_theirs"))
    mism = {}
    for c in common:
        x = pd.to_numeric(mm[c + "_mine"], errors="coerce")
        y = pd.to_numeric(mm[c + "_theirs"], errors="coerce")
        both_na = x.isna() & y.isna()
        ne = (~both_na) & (~np.isclose(x, y, rtol=1e-9, atol=1e-6, equal_nan=True))
        mism[c] = int(ne.sum())
    rows.append({"文件": tf, "对方行数": len(t), "我的行数": len(m),
                 "可比公共字段数": len(common), "可匹配报告期数": len(mm),
                 "有差异的字段数": sum(1 for v in mism.values() if v > 0),
                 "差异单元格合计": sum(mism.values())})
    log("%-16s 对方 %d 行 / 我 %d 行，公共字段 %d 个，匹配报告期 %d 个，差异单元格 %d 个 %s"
        % (tf, len(t), len(m), len(common), len(mm), sum(mism.values()),
           {k: v for k, v in mism.items() if v > 0}))
pd.DataFrame(rows).to_csv(OUT + r"\compare_financial_statements.csv", index=False, encoding="utf-8-sig")

# ---------------- 汇总 ----------------
summary = pd.DataFrame([
    ["项目", "我的数据", "对方数据", "比对结论"],
    ["日线行数", len(mine_hfq), len(merge_q), ""],
    ["后复权收益率相关系数", round(j[["r_mine", "r_theirs"]].corr().iloc[0, 1], 8), "", ""],
])
summary.to_csv(OUT + r"\compare_data_sources.csv", index=False, encoding="utf-8-sig")

with open(r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\log\step10_数据比对结果.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(REPORT))
log("")
log("比对报告已保存")
