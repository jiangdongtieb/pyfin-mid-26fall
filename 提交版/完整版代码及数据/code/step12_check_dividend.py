# -*- coding: utf-8 -*-
"""
step12 查清除权除息：
1) 打印东财不复权文件里 2026-06-24~07-03 的原始行（含涨跌幅/涨跌额）
2) 找出「hfq 收益 != 不复权收盘收益」的所有日子（这些就是除权除息日）
3) 从东方财富数据中心抓 002714 的分红送转明细，看看这些日子对应什么事件
4) 保存分红明细，后面自己构造复权因子用
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import requests

MINE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\data_raw"
R = []


def log(m=""):
    print(m, flush=True)
    R.append(str(m))


bfq = pd.read_csv(MINE + r"\em_002714_bfq.csv", parse_dates=["日期"]).set_index("日期")
hfq = pd.read_csv(MINE + r"\em_002714_hfq.csv", parse_dates=["日期"]).set_index("日期")
qfq = pd.read_csv(MINE + r"\em_002714_qfq.csv", parse_dates=["日期"]).set_index("日期")

log("1) 东财【不复权】文件 2026-06-24 ~ 2026-07-03 原始行")
log(bfq.loc["2026-06-24":"2026-07-03", ["开盘", "收盘", "最高", "最低", "涨跌幅", "涨跌额", "成交额"]].to_string())

log("")
log("2) 三种复权口径的收益差异")
r_bfq_close = bfq["收盘"].pct_change()
r_hfq_close = hfq["收盘"].pct_change()
r_bfq_field = bfq["涨跌幅"] / 100.0
r_hfq_field = hfq["涨跌幅"] / 100.0
cmp = pd.DataFrame({"bfq收盘收益": r_bfq_close, "bfq涨跌幅字段": r_bfq_field,
                    "hfq收盘收益": r_hfq_close, "hfq涨跌幅字段": r_hfq_field})
cmp["hfq-bfq收盘收益差"] = cmp["hfq收盘收益"] - cmp["bfq收盘收益"]
bad = cmp[cmp["hfq-bfq收盘收益差"].abs() > 5e-4]
log("hfq 收盘收益 与 bfq 收盘收益 差值超 0.05%% 的日子共 %d 天：" % len(bad))
log(bad.round(5).to_string())
gap = (cmp["bfq收盘收益"] - cmp["bfq涨跌幅字段"]).abs()
log("\nbfq 收盘收益 与交易所口径涨跌幅 差值超 0.05%% 的天数：%d" % int((gap > 5e-4).sum()))
log(cmp.loc[gap[gap > 5e-4].index].round(5).to_string())

log("")
log("3) 东方财富分红送转明细")
url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
       "reportName=RPT_SHAREBONUS_DET&columns=ALL&pageSize=200&pageNumber=1&"
       "sortColumns=EX_DIVIDEND_DATE&sortTypes=-1&filter=(SECURITY_CODE%3D%22002714%22)")
try:
    r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0",
                                               "Referer": "https://data.eastmoney.com/"})
    j = r.json()
    rows = (j.get("result") or {}).get("data") or []
    log("抓到 %d 条分红记录" % len(rows))
    if rows:
        cols = ["EX_DIVIDEND_DATE", "REPORT_DATE", "IMPL_PLAN_PROFILE", "PRETAX_BONUS_RMB",
                "ASSIGN_PROGRESS", "BONUS_IT_RATIO", "TRANSFER_IT_RATIO", "EQUITY_RECORD_DATE"]
        df = pd.DataFrame(rows)
        have = [c for c in cols if c in df.columns]
        df = df[have]
        log(df.to_string()[:3000])
        df.to_csv(MINE + r"\fhps_002714.csv", index=False, encoding="utf-8-sig")
        log("已保存分红明细 -> fhps_002714.csv")
except Exception as e:
    log("抓取失败 %s: %s" % (type(e).__name__, str(e)[:200]))

with open(r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\log\step12_复权诊断.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(R))
