# -*- coding: utf-8 -*-
"""
step14  CSMAR 配额恢复后补下的行情数据，与我们的自建序列做最终交叉验证。
       （对应题目 Alternative method 加分点：用 CSMAR 官方行情与免费接口数据比对）
对比项（按文件可用性自动跳过）：
  1) TRD_Dalyr.Dretwd     含红利再投资日收益率  vs 我们的 ret
  2) TRD_Dalyr.Adjprcwd   官方后复权可比价      vs 我们的 close_adj（比值应为常数）
  3) TRD_Dalyr.Dsmvtll    官方日总市值          vs 我们的 mkt_cap
  4) TRD_Dalyr.LimitStatus vs 我们重建的封板标记（命中率）
  5) TRD_AdjustFactor.BwardFactor vs 我们的 adj_factor
  6) FI_T10 官方 PE/PB vs 我们季度指标里的 PE_TTM / PB
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout

import numpy as np
import pandas as pd

BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"
RAW = os.path.join(BASE, "data_raw")
OUT = os.path.join(BASE, "output")
LOG = os.path.join(BASE, "log", "step14_CSMAR交叉验证.txt")

rows = []
loglines = []


def log(m):
    print(m, flush=True)
    loglines.append(str(m))


def have(name):
    return os.path.exists(os.path.join(RAW, name + ".csv"))


def load_panel():
    p = pd.read_csv(os.path.join(OUT, "panel_full_with_scores.csv"), parse_dates=["trade_date"])
    p = p.set_index("trade_date").sort_index()
    return p


def cmp_series(mine, theirs, tag):
    d = pd.concat([mine.rename("mine"), theirs.rename("theirs")], axis=1).dropna()
    if len(d) < 50:
        log("  %s 可比样本不足 %d" % (tag, len(d)))
        return None
    corr = float(d["mine"].corr(d["theirs"]))
    mad = float((d["mine"] - d["theirs"]).abs().mean())
    bad = int((((d["mine"] - d["theirs"]).abs() > 5e-4)).sum())
    ratio = float((d["mine"] / d["theirs"].replace(0, np.nan)).median())
    log("  %-34s 样本=%4d 相关系数=%.8f 平均绝对差=%.3e 差>0.05%%天数=%d 中位比值=%.6f"
        % (tag, len(d), corr, mad, bad, ratio))
    return {"项目": tag, "可比样本": len(d), "相关系数": round(corr, 8),
            "平均绝对差": round(mad, 8), "差>0.05%%天数": bad, "中位比值": round(ratio, 6)}


panel = load_panel()
log("面板 %d 行（%s ~ %s）" % (len(panel), panel.index.min().date(), panel.index.max().date()))

# ---------- 1) 日收益率 ----------
if have("dalyr_price"):
    d = pd.read_csv(os.path.join(RAW, "dalyr_price.csv"), parse_dates=["Trddt"])
    d = d.set_index("Trddt").sort_index()
    if "Dretwd" in d.columns:
        res = cmp_series(panel["ret"] * 100, pd.to_numeric(d["Dretwd"], errors="coerce") * 100,
                         "日收益率 Dretwd(CSMAR) vs 自建 ret(不含除权日应一致)")
        if res:
            rows.append(res)
    if "Adjprcwd" in d.columns:
        mine = panel["close_adj"]
        theirs = pd.to_numeric(d["Adjprcwd"], errors="coerce")
        dd = pd.concat([mine.rename("mine"), theirs.rename("theirs")], axis=1).dropna()
        ratio = dd["mine"] / dd["theirs"]
        log("  %-34s 中位比值=%.6f 比值标准差=%.3e（应≈常数）" % ("后复权价 Adjprcwd vs close_adj", ratio.median(), ratio.std()))
        rows.append({"项目": "后复权价 Adjprcwd(CSMAR) vs 自建 close_adj",
                     "可比样本": len(dd), "相关系数": round(float(dd["mine"].corr(dd["theirs"])), 8),
                     "平均绝对差": round(float((dd["mine"] - dd["theirs"]).abs().mean()), 8),
                     "差>0.05%%天数": int((((dd["mine"] - dd["theirs"]).abs() > 5e-4)).sum()),
                     "中位比值": round(float(ratio.median()), 6)})
    if "Dsmvtll" in d.columns:
        res = cmp_series(panel["mkt_cap"], pd.to_numeric(d["Dsmvtll"], errors="coerce"),
                         "日总市值 Dsmvtll(CSMAR) vs 自建 mkt_cap")
        if res:
            rows.append(res)

# ---------- 2) 涨跌停状态 ----------
if have("dalyr_limit"):
    d = pd.read_csv(os.path.join(RAW, "dalyr_limit.csv"), parse_dates=["Trddt"])
    d = d.set_index("Trddt").sort_index()
    if "LimitStatus" in d.columns:
        ls = pd.to_numeric(d["LimitStatus"], errors="coerce").dropna()
        if len(ls):
            # CSMAR LimitStatus 约定：0=正常 1=涨停 2=跌停（按常见编码试探，多数资料为 0/1/2）
            up_hit = (ls >= 1).astype(int).reindex(panel.index).fillna(0)
            dn_hit = (ls == 2).astype(int).reindex(panel.index).fillna(0)
            log("  LimitStatus 编码取值分布：%s" % dict(ls.value_counts().head(6)))
            log("  CSMAR 标记涨停 %d 天、跌停 %d 天；我们标记封板涨停 %d 天、封死跌停 %d 天"
                % (int((ls >= 1).sum()), int((ls == 2).sum()),
                   int(panel["seal_limit_up"].sum()), int(panel["seal_limit_down"].sum())))

# ---------- 3) 复权因子 ----------
if have("adjustfactor"):
    d = pd.read_csv(os.path.join(RAW, "adjustfactor.csv"), parse_dates=["TradingDate"])
    d = d.set_index("TradingDate").sort_index()
    if "BwardFactor" in d.columns:
        bf = pd.to_numeric(d["BwardFactor"], errors="coerce")
        dd = pd.concat([panel["adj_factor"].rename("mine"), bf.rename("theirs")], axis=1).dropna()
        ratio = dd["mine"] / dd["theirs"]
        log("  %-34s 中位比值=%.6f 标准差=%.3e（基准不同，比值应≈常数）" % ("复权因子 BwardFactor vs 自建 adj_factor", ratio.median(), ratio.std()))
        rows.append({"项目": "复权因子 BwardFactor(CSMAR) vs 自建 adj_factor", "可比样本": len(dd),
                     "相关系数": round(float(dd["mine"].corr(dd["theirs"])), 8),
                     "平均绝对差": round(float((dd["mine"] - dd["theirs"]).abs().mean()), 8),
                     "差>0.05%%天数": int((((dd["mine"] - dd["theirs"]).abs() > 5e-4)).sum()),
                     "中位比值": round(float(ratio.median()), 6)})

# ---------- 4) FI_T10 官方估值 vs 自算 ----------
if have("fi_t10_valuation"):
    v = pd.read_csv(os.path.join(RAW, "fi_t10_valuation.csv"))
    v["Accper"] = pd.to_datetime(v["Accper"])
    mine_q = pd.read_csv(os.path.join(OUT, "task2_quarterly_indicators.csv"))
    mine_q["报告期"] = pd.to_datetime(mine_q["报告期"], format="%Y-%m-%d")
    for col, refcol in [("F100103C", "PE_TTM"), ("F100401A", "PB")]:
        if col not in v.columns:
            continue
        vv = v.set_index("Accper")[col].dropna()
        mm = mine_q.set_index("报告期")[refcol].dropna()
        d = pd.concat([mm.rename("mine"), vv.rename("theirs")], axis=1).dropna()
        if len(d) > 5:
            corr = float(d["mine"].corr(d["theirs"]))
            log("  %-34s 可比期=%d 相关系数=%.6f 中位比=%.4f" % ("官方" + refcol + " vs 自算", len(d), corr,
                                                              float((d["mine"] / d["theirs"]).median())))
            rows.append({"项目": "官方估值" + refcol + "(FI_T10) vs 自算", "可比样本": len(d),
                         "相关系数": round(corr, 8), "平均绝对差": np.nan,
                         "差>0.05%%天数": np.nan, "中位比值": round(float((d["mine"] / d["theirs"]).median()), 4)})

# ---------- 5) 落盘 + 更新 run_summary ----------
cc = pd.DataFrame(rows)
cc.to_csv(os.path.join(OUT, "compare_csmar_daily.csv"), index=False, encoding="utf-8-sig")
log("\n结果已保存 output/compare_csmar_daily.csv（%d 项）" % len(cc))

try:
    with open(os.path.join(OUT, "run_summary.json"), encoding="utf-8") as f:
        sm = json.load(f)
    sm["CSMAR补下交叉验证"] = cc.to_dict("records")
    with open(os.path.join(OUT, "run_summary.json"), "w", encoding="utf-8") as f:
        json.dump(sm, f, ensure_ascii=False, indent=1)
    log("已把交叉验证结果写进 run_summary.json")
except Exception as e:
    log("更新 run_summary 失败：%s" % str(e)[:100])

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(loglines))
log("step14 完成")
