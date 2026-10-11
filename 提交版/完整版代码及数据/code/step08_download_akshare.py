# -*- coding: utf-8 -*-
"""
step08 用 akshare（东方财富/乐咕乐股接口）补下行情数据
背景：CSMAR 官方 API 今天返回「Downloads has reached the limit today」，
     行情类当天拉不出来；而财务报表类（资产负债表/利润表/现金流量表/公告日/财务比率）
     今天已经在 CSMAR 全部下好。题目明确允许用 akshare 作为替代来源并与 CSMAR 交叉核对，
     所以今天先用 akshare 把行情拿全，等 CSMAR 配额恢复后再跑 step07 补一份 CSMAR 行情，
     两者做交叉验证（正好对应题目 Task1 的 Alternative method 加分项）。
下载内容：
  em_002714_bfq   牧原股份 日线（不复权）
  em_002714_qfq   牧原股份 日线（前复权）
  em_002714_hfq   牧原股份 日线（后复权）
  em_index_000300 沪深300 日线
  lg_indicator    牧原股份 每日 PE(TTM) / PB / 总市值 / 股息率（乐咕乐股）
"""
import io
import sys
import time
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"
RAW = BASE + r"\data_raw"
PROG = BASE + r"\log\step08_进度.txt"

SYMBOL = "002714"
BEG, END = "20140101", time.strftime("%Y%m%d")


def log(m):
    line = time.strftime("%H:%M:%S  ") + str(m)
    print(line, flush=True)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save(df, name):
    p = RAW + "\\" + name + ".csv"
    df.to_csv(p, index=False, encoding="utf-8-sig")
    log("  保存 %s.csv  %d 行 x %d 列" % (name, len(df), df.shape[1]))


import akshare as ak
log("akshare 版本 %s，开始下载" % ak.__version__)

# ---------- 1. 个股日线：不复权 / 前复权 / 后复权 ----------
for adj, name in [("", "em_002714_bfq"), ("qfq", "em_002714_qfq"), ("hfq", "em_002714_hfq")]:
    try:
        df = ak.stock_zh_a_hist(symbol=SYMBOL, period="daily", start_date=BEG, end_date=END, adjust=adj)
        if df is not None and len(df) > 0:
            save(df, name)
        else:
            log("  %s 空" % name)
    except Exception as e:
        log("  %s 失败 %s" % (name, str(e)[:150]))
    time.sleep(3)

# ---------- 2. 沪深300 指数日线 ----------
for sym, name in [("000300", "em_index_000300"), ("000001", "em_index_000001")]:
    try:
        df = ak.index_zh_a_hist(symbol=sym, period="daily", start_date=BEG, end_date=END)
        if df is not None and len(df) > 0:
            save(df, name)
    except Exception as e:
        log("  指数 %s 失败 %s" % (name, str(e)[:150]))
    time.sleep(3)

# ---------- 3. 每日估值指标（PE TTM / PB / 总市值 / 股息率） ----------
try:
    df = ak.stock_a_indicator_lg(symbol=SYMBOL)
    if df is not None and len(df) > 0:
        df = df[(df["trade_date"] >= "2014-01-01")]
        save(df, "lg_indicator")
except Exception as e:
    log("  估值指标失败 %s" % str(e)[:150])
    traceback.print_exc()

# ---------- 4. 总股本变动（用于自己算市值，防止估值接口缺数据） ----------
try:
    df = ak.stock_zh_a_gbjg_em(symbol=SYMBOL)
    if df is not None and len(df) > 0:
        save(df, "em_share_change")
except Exception as e:
    log("  股本变动失败 %s（可忽略）" % str(e)[:120])

log("step08 结束")
