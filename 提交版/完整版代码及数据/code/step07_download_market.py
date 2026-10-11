# -*- coding: utf-8 -*-
"""
step07 只补下载「行情类」数据，慢速 + 断点续传，可重复运行
要补的：
  quote_bward   后复权日行情（含总股本/换手率/总市值/交易状态）
  dalyr_price   日行情核心字段（价格、量额、市值、日收益率、复权价）
  dalyr_limit   涨跌停相关字段（昨收、涨跌幅、涨停价、跌停价、状态）
  adjustfactor  复权因子（前复权/后复权对比用）
  index_csi300  沪深300
  index_sw      申万农林牧渔 801010
  fi_t10        估值比率（PE TTM / PB）
"""
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
from csmarapi.CsmarService import CsmarService

BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"
CRED = r"C:\Users\35632\Desktop\python期中大作业\0_题目与数据接入\CSMAR账号密码.txt"
RAW = BASE + r"\data_raw"
PROG = BASE + r"\log\step07_进度.txt"

STK = "002714"
ST, ET = "2014-01-01", "2026-10-07"
FST, FET = "2011-01-01", "2026-06-30"
GAP = 6


def log(m):
    txt = time.strftime("%H:%M:%S  ") + str(m)
    print(txt, flush=True)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(txt + "\n")


class Downloader(object):
    """封装登录、限速、重试（对应课上 Class04 的 OOP 写法）"""

    def __init__(self, cred_path, gap=GAP):
        lines = [x.strip() for x in open(cred_path, encoding="utf-8") if x.strip()]
        self.account, self.pwd = lines[0], lines[1]
        self.gap = gap
        self.client = None
        self.n_query = 0

    def connect(self):
        self.client = CsmarService()
        self.client.login(self.account, self.pwd, "0")
        log("登录成功")

    def query(self, cols, cond, table, st, et, tag, tries=3):
        if self.client is None:
            self.connect()
        for i in range(tries):
            try:
                df = self.client.query_df(cols, cond, table, st, et)
                self.n_query += 1
                time.sleep(self.gap)
                if df is None or len(df) == 0:
                    log("    [%s] 空，等 %ds 再试(%d/%d)" % (tag, self.gap * 4, i + 1, tries))
                    time.sleep(self.gap * 4)
                    continue
                return df
            except Exception as e:
                log("    [%s] 异常 %s" % (tag, str(e)[:100]))
                time.sleep(self.gap * 3)
                self.connect()
        return None


def done(name, min_rows=500):
    p = os.path.join(RAW, name + ".csv")
    if not os.path.exists(p):
        return False
    try:
        return len(pd.read_csv(p)) >= min_rows
    except Exception:
        return False


def save(df, name):
    df.to_csv(os.path.join(RAW, name + ".csv"), index=False, encoding="utf-8-sig")
    log("  保存 %s.csv  %d 行 x %d 列" % (name, len(df), df.shape[1]))


def by_year(dl, cols, table, cond_fmt, name, st_year=2014, min_rows=2500):
    if done(name, min_rows):
        log("跳过（已存在）%s" % name)
        return
    parts = []
    for yy in range(st_year, 2027):
        a, b = "%d-01-01" % yy, min("%d-12-31" % yy, ET)
        d = dl.query(cols, cond_fmt, table, a, b, "%s %d" % (name, yy))
        if d is not None:
            parts.append(d)
    if parts:
        full = pd.concat(parts, ignore_index=True)
        key = "Trddt" if "Trddt" in full.columns else "TradingDate"
        full = full.drop_duplicates(subset=[key]).sort_values(key)
        save(full, name)
    else:
        log("  !! %s 一段都没下到" % name)


dl = Downloader(CRED)
dl.connect()

# 1) 后复权日行情（最全：含总股本、换手率、总市值、交易状态）
q_cols = ["Symbol", "TradingDate", "ShortName", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice",
          "Volume", "Amount", "AvgPrice", "ChangeRatio", "TotalShare", "CirculatedShare",
          "TurnoverRate1", "MarketValue", "CirculatedMarketValue", "StateCode"]
by_year(dl, q_cols, "TRD_BwardQuotation", "Symbol='%s'" % STK, "quote_bward")

# 2) 日行情核心字段（含考虑现金红利的可比价格 Adjprcwd 与日收益率 Dretwd）
core = ["Stkcd", "Trddt", "Opnprc", "Hiprc", "Loprc", "Clsprc", "Dnshrtrd", "Dnvaltrd",
        "Dsmvosd", "Dsmvtll", "Dretwd", "Dretnd", "Adjprcwd", "Adjprcnd"]
by_year(dl, core, "TRD_Dalyr", "Stkcd='%s'" % STK, "dalyr_price")

# 3) 涨跌停字段（若整组查不动就逐个试）
lim = ["Stkcd", "Trddt", "PreClosePrice", "ChangeRatio", "LimitUp", "LimitDown", "LimitStatus", "Trdsta"]
if not done("dalyr_limit"):
    d = dl.query(lim, "Stkcd='%s'" % STK, "TRD_Dalyr", ST, ET, "dalyr_limit 全区间")
    if d is None:
        keep = ["Stkcd", "Trddt"]
        for f in lim[2:]:
            d2 = dl.query(keep + [f], "Stkcd='%s'" % STK, "TRD_Dalyr", ST, ET, "limit字段 " + f)
            if d2 is not None:
                keep.append(f)
        if len(keep) > 2:
            d = dl.query(keep, "Stkcd='%s'" % STK, "TRD_Dalyr", ST, ET, "dalyr_limit 精简")
    if d is not None:
        save(d, "dalyr_limit")

# 4) 复权因子
if not done("adjustfactor"):
    d = dl.query(["Symbol", "TradingDate", "FwardFactor", "BwardFactor",
                  "CumulateFwardFactor", "CumulateBwardFactor"],
                 "Symbol='%s'" % STK, "TRD_AdjustFactor", ST, ET, "adjustfactor")
    if d is not None:
        save(d, "adjustfactor")

# 5) 指数
idx = ["Indexcd", "Trddt", "Opnindex", "Hiindex", "Loindex", "Clsindex", "Retindex"]
for code, nm in [("000300", "index_csi300"), ("801010", "index_sw_nlfsh"), ("399110", "index_399110")]:
    if done(nm):
        log("跳过（已存在）%s" % nm)
        continue
    d = dl.query(idx, "Indexcd='%s'" % code, "TRD_Index", ST, ET, nm)
    if d is None:
        d = dl.query(idx, "Indexcd='%s'" % code, "IDX_Idxtrd", ST, ET, nm + " IDX_Idxtrd")
    if d is not None:
        save(d, nm)

# 6) 估值比率
if not done("fi_t10_valuation", 40):
    d = dl.query(["Stkcd", "Accper", "F100103C", "F100101B", "F100203C", "F100401A", "F100901A"],
                 "Stkcd='%s'" % STK, "FI_T10", FST, FET, "fi_t10")
    if d is not None:
        save(d, "fi_t10_valuation")

log("全部结束，共查询 %d 次" % dl.n_query)
