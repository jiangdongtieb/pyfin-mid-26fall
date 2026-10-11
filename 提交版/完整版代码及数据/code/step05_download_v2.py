# -*- coding: utf-8 -*-
"""
step05 正式下载 v2
1) 先对 TRD_Dalyr 逐字段验证（有的字段在字段清单里挂着，但实际查不了）
2) 用验证过的字段下行情全区间
3) 后复权/前复权行情、复权因子表用 Symbol 作为代码字段
4) 指数：沪深300(000300) + 申万农林牧渔(801010) 试两个库
5) FI_T10 估值（该表没有 Typrep 字段）
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
from csmarapi.CsmarService import CsmarService

BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"
CRED = r"C:\Users\35632\Desktop\python期中大作业\0_题目与数据接入\CSMAR账号密码.txt"
RAW = BASE + r"\data_raw"
LOG = []

STK = "002714"
ST, ET = "2014-01-01", "2026-10-07"
FST, FET = "2011-01-01", "2026-06-30"

lines = [x.strip() for x in open(CRED, encoding="utf-8") if x.strip()]
csmar = CsmarService()
csmar.login(lines[0], lines[1], "0")


def log(m):
    print(m)
    LOG.append(str(m))


def safe_query(cols, cond, table, st, et, tag, retry=2):
    for i in range(retry):
        try:
            df = csmar.query_df(cols, cond, table, st, et)
            if df is None or len(df) == 0:
                log("  [%s] 空结果" % tag)
                return None
            return df
        except Exception as e:
            msg = str(e)
            if "30" in msg and ("分钟" in msg or "minute" in msg.lower()):
                log("  [%s] 冷却，等 90s" % tag)
                time.sleep(90)
                continue
            log("  [%s] 异常 %s" % (tag, msg[:120]))
            time.sleep(2)
    return None


def save(df, name):
    path = RAW + "\\" + name + ".csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log("  存 -> %s.csv  %d x %d" % (name, len(df), df.shape[1]))


log("登录成功，开始验证字段可用性")

# ---------- 1. TRD_Dalyr 字段逐个验证 ----------
all_cols = ["Stkcd", "Trddt", "Opnprc", "Hiprc", "Loprc", "Clsprc",
            "Dnshrtrd", "Dnvaltrd", "Dsmvosd", "Dsmvtll",
            "Dretwd", "Dretnd", "Adjprcwd", "Adjprcnd",
            "PreClosePrice", "ChangeRatio", "LimitUp", "LimitDown", "LimitStatus",
            "Trdsta", "Markettype", "Capchgdt", "Ahshrtrd_D", "Ahvaltrd_D"]
good = []
bad = []
for c in all_cols:
    df = safe_query(["Stkcd", "Trddt", c] if c not in ("Stkcd", "Trddt") else ["Stkcd", "Trddt"],
                    "Stkcd='%s'" % STK, "TRD_Dalyr", "2024-06-03", "2024-06-07", "字段 " + c)
    if df is None or (c not in ("Stkcd", "Trddt") and c not in df.columns) or len(df) == 0:
        bad.append(c)
    else:
        good.append(c)
log("TRD_Dalyr 可用字段 %d 个: %s" % (len(good), good))
log("TRD_Dalyr 不可用字段: %s" % bad)

# ---------- 2. 日行情全区间 ----------
cols_daily = list(dict.fromkeys(["Stkcd", "Trddt"] + good))
d_full = None
for yy in range(2014, 2027):          # 按年分段下，避免单次太大/超时
    a = "%d-01-01" % yy
    b = min("%d-12-31" % yy, ET)
    d = safe_query(cols_daily, "Stkcd='%s'" % STK, "TRD_Dalyr", a, b, "dalyr %d" % yy)
    if d is not None:
        d_full = d if d_full is None else pd.concat([d_full, d], ignore_index=True)
    log("  %d 年累计 %s 行" % (yy, 0 if d_full is None else len(d_full)))
if d_full is not None:
    d_full = d_full.drop_duplicates(subset=["Trddt"]).sort_values("Trddt")
    save(d_full, "dalyr")

# ---------- 3. 后复权 / 前复权行情（Symbol 作为代码字段） ----------
q_cols = ["Symbol", "TradingDate", "ShortName", "OpenPrice", "HighPrice", "LowPrice",
          "ClosePrice", "Volume", "Amount", "AvgPrice", "ChangeRatio",
          "TotalShare", "CirculatedShare", "TurnoverRate1", "MarketValue",
          "CirculatedMarketValue", "StateCode", "Filling", "Distance"]
for tbl, nm in [("TRD_BwardQuotation", "quote_bward"), ("TRD_FwardQuotation", "quote_fward")]:
    for sym in ("'%s'" % STK, "%s" % int(STK)):
        d = safe_query(q_cols, "Symbol=%s" % sym, tbl, ST, ET, "%s Symbol=%s" % (tbl, sym))
        if d is not None:
            save(d, nm)
            break

# ---------- 4. 复权因子 ----------
d = safe_query(["Symbol", "TradingDate", "FwardFactor", "BwardFactor",
                "CumulateFwardFactor", "CumulateBwardFactor"],
               "Symbol='%s'" % STK, "TRD_AdjustFactor", ST, ET, "AdjustFactor")
if d is not None:
    save(d, "adjustfactor")

# ---------- 5. 指数行情：沪深300 + 申万农林牧渔 ----------
idx_cols = ["Indexcd", "Trddt", "Opnindex", "Hiindex", "Loindex", "Clsindex", "Retindex"]
for code, tag in [("000300", "csi300"), ("399300", "csi300sz"), ("801010", "sw_nlfsh")]:
    d = safe_query(idx_cols, "Indexcd='%s'" % code, "TRD_Index", ST, ET, "TRD_Index %s" % code)
    if d is not None:
        save(d, "index_" + tag)

# ---------- 6. FI_T10 估值（无 Typrep） ----------
d = safe_query(["Stkcd", "Accper", "F100103C", "F100101B", "F100203C",
                "F100401A", "F100901A"],
               "Stkcd='%s'" % STK, "FI_T10", FST, FET, "FI_T10")
if d is not None:
    save(d, "fi_t10_valuation")

with open(BASE + r"\log\step05_下载日志.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(LOG))
log("done")
