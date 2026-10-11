# -*- coding: utf-8 -*-
"""step04 排查 TRD_Dalyr / TRD_AdjustFactor / TRD_Index / FI_T10 为什么返回空，找到能用的查询写法"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
from csmarapi.CsmarService import CsmarService

CRED = r"C:\Users\35632\Desktop\python期中大作业\0_题目与数据接入\CSMAR账号密码.txt"
BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"

lines = [x.strip() for x in open(CRED, encoding="utf-8") if x.strip()]
csmar = CsmarService()
csmar.login(lines[0], lines[1], "0")
print("登录成功")

log = []


def probe(tag, cols, cond, table, st, et):
    try:
        df = csmar.query_df(cols, cond, table, st, et)
        n = 0 if df is None else len(df)
        print("%-42s -> %d 行" % (tag, n))
        log.append("%s -> %d" % (tag, n))
        if df is not None and len(df) > 0:
            print(df.head(3).to_string()[:400])
            return df
    except Exception as e:
        print("%-42s -> 异常 %s" % (tag, str(e)[:160]))
        log.append("%s -> EXC %s" % (tag, str(e)[:160]))
    return None


base_cols = ["Stkcd", "Trddt", "Clsprc", "Dretwd"]

ok = probe("A dalyr 最小列+短区间", base_cols, "Stkcd='002714'", "TRD_Dalyr", "2024-01-01", "2024-02-01")
if ok is None:
    probe("B dalyr 代码不带引号", base_cols, "Stkcd=2714", "TRD_Dalyr", "2024-01-01", "2024-02-01")
    probe("C dalyr 3位代码带引号", base_cols, "Stkcd='2714'", "TRD_Dalyr", "2024-01-01", "2024-02-01")
    probe("D TRDNEW_Dalyr", base_cols, "Stkcd='002714'", "TRDNEW_Dalyr", "2024-01-01", "2024-02-01")
    probe("E dalyr 无日期区间", base_cols, "Stkcd='002714'", "TRD_Dalyr", "", "")
    probe("F dalyr like条件", base_cols, "Stkcd like '002714%'", "TRD_Dalyr", "2024-01-01", "2024-02-01")
    probe("G BwardQuotation 后复权",
          ["Stkcd", "TradingDate", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice", "Volume", "Amount", "MarketValue"],
          "Stkcd='002714'", "TRD_BwardQuotation", "2024-01-01", "2024-02-01")

probe("H TRD_AdjustFactor", ["Stkcd", "TradingDate", "BwardFactor", "FwardFactor"],
      "Stkcd='002714'", "TRD_AdjustFactor", "2024-01-01", "2024-02-01")
probe("I TRD_Index 沪深300", ["Indexcd", "Trddt", "Clsindex", "Retindex"],
      "Indexcd='000300'", "TRD_Index", "2024-01-01", "2024-02-01")
probe("J TRD_Index 申万农林牧渔", ["Indexcd", "Trddt", "Clsindex", "Retindex"],
      "Indexcd='801010'", "TRD_Index", "2024-01-01", "2024-02-01")
probe("K FI_T10 估值", ["Stkcd", "Accper", "F100103C", "F100401A"],
      "Stkcd='002714'", "FI_T10", "2011-01-01", "2026-06-30")
probe("L FI_T10 含Typrep", ["Stkcd", "Accper", "Typrep", "F100401A"],
      "Stkcd='002714'", "FI_T10", "", "")

with open(BASE + r"\log\step04_probe.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(log))
