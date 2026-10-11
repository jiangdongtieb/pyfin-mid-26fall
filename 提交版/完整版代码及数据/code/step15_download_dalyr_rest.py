# -*- coding: utf-8 -*-
"""
step15  补全 TRD_Dalyr 2021-2026 缺口（2014-2020 已在 dalyr_price.csv），
        并顺带重试 dalyr_limit / adjustfactor / fi_t10。
        慢速 + 断点续传，可重复运行。
"""
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, "buffer") else sys.stdout

import pandas as pd
from csmarapi.CsmarService import CsmarService

BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"
CRED = r"C:\Users\35632\Desktop\python期中大作业\0_题目与数据接入\CSMAR账号密码.txt"
RAW = os.path.join(BASE, "data_raw")
LOG = os.path.join(BASE, "log", "step15_进度.txt")

STK = "002714"
GAP = 6


def log(m):
    line = time.strftime("%H:%M:%S  ") + str(m)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class DL(object):
    def __init__(self):
        ls = [x.strip() for x in open(CRED, encoding="utf-8") if x.strip()]
        self.acct, self.pwd = ls[0], ls[1]
        self.c = None

    def connect(self):
        self.c = CsmarService()
        self.c.login(self.acct, self.pwd, "0")
        log("登录成功")

    def query(self, cols, cond, table, st, et, tag, tries=3):
        if self.c is None:
            self.connect()
        for i in range(tries):
            try:
                df = self.c.query_df(cols, cond, table, st, et)
                time.sleep(GAP)
                if df is None or len(df) == 0:
                    log("  [%s] 空，等 %ds 再试(%d/%d)" % (tag, GAP * 4, i + 1, tries))
                    time.sleep(GAP * 4)
                    continue
                return df
            except Exception as e:
                log("  [%s] 异常 %s" % (tag, str(e)[:110]))
                time.sleep(GAP * 3)
                self.connect()
        return None


def save(df, name):
    df.to_csv(os.path.join(RAW, name + ".csv"), index=False, encoding="utf-8-sig")
    log("  保存 %s.csv  %d 行" % (name, len(df)))


dl = DL()
dl.connect()

# ---------- 1) TRD_Dalyr 2021-2026 补全（每年单独落盘，崩溃不丢、可续传） ----------
core = ["Stkcd", "Trddt", "Opnprc", "Hiprc", "Loprc", "Clsprc", "Dnshrtrd", "Dnvaltrd",
        "Dsmvosd", "Dsmvtll", "Dretwd", "Dretnd", "Adjprcwd", "Adjprcnd"]

# 已有年份 = 主文件年份 ∪ 各年碎片文件年份
have_years = set()
if os.path.exists(os.path.join(RAW, "dalyr_price.csv")):
    old = pd.read_csv(os.path.join(RAW, "dalyr_price.csv"), parse_dates=["Trddt"])
    have_years |= set(pd.to_datetime(old["Trddt"]).dt.year)
for f in os.listdir(RAW):
    if f.startswith("dalyr_") and f.endswith(".csv") and f != "dalyr_price.csv":
        y = pd.read_csv(os.path.join(RAW, f), parse_dates=["Trddt"])
        have_years |= set(pd.to_datetime(y["Trddt"]).dt.year)
log("已有年份: %s，需补: %s" % (sorted(have_years), [y for y in range(2014, 2027) if y not in have_years]))

for yy in range(2021, 2027):
    if yy in have_years:
        continue
    df = dl.query(core, "Stkcd='%s'" % STK, "TRD_Dalyr", "%d-01-01" % yy, "%d-12-31" % yy, "TRD_Dalyr %d" % yy)
    if df is not None:
        df["Trddt"] = pd.to_datetime(df["Trddt"])
        df.to_csv(os.path.join(RAW, "dalyr_%d.csv" % yy), index=False, encoding="utf-8-sig")
        log("  %d 年 +%d 行（已单独落盘 dalyr_%d.csv）" % (yy, len(df), yy))

# ---------- 合并全部年份，覆写 dalyr_price.csv ----------
alls = []
if os.path.exists(os.path.join(RAW, "dalyr_price.csv")):
    alls.append(pd.read_csv(os.path.join(RAW, "dalyr_price.csv"), parse_dates=["Trddt"]))
for yy in range(2014, 2027):
    p = os.path.join(RAW, "dalyr_%d.csv" % yy)
    if os.path.exists(p):
        alls.append(pd.read_csv(p, parse_dates=["Trddt"]))
if alls:
    full = pd.concat(alls, ignore_index=True)
    full["Trddt"] = pd.to_datetime(full["Trddt"])
    full = full.drop_duplicates(subset=["Trddt"]).sort_values("Trddt")
    full.to_csv(os.path.join(RAW, "dalyr_price.csv"), index=False, encoding="utf-8-sig")
    log("TRD_Dalyr 合并完成：%d 行（%s ~ %s）" % (len(full), full["Trddt"].min().date(), full["Trddt"].max().date()))
    for yy in range(2014, 2027):
        p = os.path.join(RAW, "dalyr_%d.csv" % yy)
        if os.path.exists(p):
            os.remove(p)
    log("已清理碎片文件")

# ---------- 2) 顺带重试：涨跌停字段 / 复权因子 / FI_T10 ----------
if not os.path.exists(os.path.join(RAW, "dalyr_limit.csv")):
    lim = ["Stkcd", "Trddt", "PreClosePrice", "ChangeRatio", "LimitUp", "LimitDown", "LimitStatus", "Trdsta"]
    df = dl.query(lim, "Stkcd='%s'" % STK, "TRD_Dalyr", "2014-01-01", "2026-10-07", "dalyr_limit")
    if df is not None:
        save(df, "dalyr_limit")

if not os.path.exists(os.path.join(RAW, "adjustfactor.csv")):
    df = dl.query(["Symbol", "TradingDate", "FwardFactor", "BwardFactor",
                   "CumulateFwardFactor", "CumulateBwardFactor"],
                  "Symbol='%s'" % STK, "TRD_AdjustFactor", "2014-01-01", "2026-10-07", "adjustfactor")
    if df is not None:
        save(df, "adjustfactor")

if not os.path.exists(os.path.join(RAW, "fi_t10_valuation.csv")):
    df = dl.query(["Stkcd", "Accper", "F100103C", "F100101B", "F100203C", "F100401A", "F100901A"],
                  "Stkcd='%s'" % STK, "FI_T10", "2011-01-01", "2026-06-30", "fi_t10")
    if df is not None:
        save(df, "fi_t10_valuation")

log("step15 结束")
