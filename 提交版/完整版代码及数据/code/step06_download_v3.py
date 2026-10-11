# -*- coding: utf-8 -*-
"""
step06 稳健下载（慢速 + 断点续传）
背景：step05 一次性打了几十个查询，CSMAR 服务端开始限流（返回空/非 JSON）
做法：
  1) 每次查询之间 sleep，查询失败自动重连再试
  2) 已下载好的文件跳过，可反复运行直到全部拿全
  3) TRD_Dalyr 先用小窗口分组验证字段，再用可用字段按年分段下载
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

STK = "002714"
ST, ET = "2014-01-01", "2026-10-07"
FST, FET = "2011-01-01", "2026-06-30"
GAP = 7          # 每次查询之间的间隔秒数


def log(m):
    print(m, flush=True)


class Csmar(object):
    """把登录/重连/查询/限速包在一起（OOP：课上 Class04 的写法）"""

    def __init__(self, cred_path):
        self.cred_path = cred_path
        lines = [x.strip() for x in open(cred_path, encoding="utf-8") if x.strip()]
        self.account, self.pwd = lines[0], lines[1]
        self.client = None
        self.query_count = 0

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
                self.query_count += 1
                time.sleep(GAP)
                if df is None or len(df) == 0:
                    log("  [%s] 空结果（第 %d 次）" % (tag, i + 1))
                    time.sleep(GAP * 3)      # 空结果多半是限流，多等一会
                    continue
                return df
            except Exception as e:
                msg = str(e)
                log("  [%s] 异常 %s" % (tag, msg[:110]))
                time.sleep(GAP * 3)
                if "Expecting value" in msg or "30" in msg:
                    self.connect()          # 重连一次
        return None


def have(name, min_rows=1):
    p = RAW + "\\" + name + ".csv"
    if not os.path.exists(p):
        return False
    try:
        return len(pd.read_csv(p)) >= min_rows
    except Exception:
        return False


def save(df, name):
    df.to_csv(RAW + "\\" + name + ".csv", index=False, encoding="utf-8-sig")
    log("  存 -> %s.csv  %d x %d" % (name, len(df), df.shape[1]))


c = Csmar(CRED)
c.connect()

# ================= 1. 验证 TRD_Dalyr 字段分组 =================
if have("field_probe", 1):
    valid_cols = pd.read_csv(RAW + r"\field_probe.csv").iloc[0].to_dict().get("cols")
    valid_cols = eval(valid_cols)
    log("字段验证已缓存：%s" % valid_cols)
else:
    groups = {
        "core": ["Stkcd", "Trddt", "Opnprc", "Hiprc", "Loprc", "Clsprc",
                 "Dnshrtrd", "Dnvaltrd", "Dsmvosd", "Dsmvtll",
                 "Dretwd", "Dretnd", "Adjprcwd", "Adjprcnd"],
        "limit": ["PreClosePrice", "ChangeRatio", "LimitUp", "LimitDown", "LimitStatus", "Trdsta"],
        "extra": ["Markettype", "Capchgdt", "Ahshrtrd_D", "Ahvaltrd_D"],
    }
    base = groups["core"]
    valid = list(base)
    for gname in ["limit", "extra"]:
        cand = base + groups[gname]
        df = c.query(cand, "Stkcd='%s'" % STK, "TRD_Dalyr", "2024-06-03", "2024-06-07",
                     "字段组 " + gname)
        if df is not None:
            valid = [x for x in df.columns]
            log("  %s 组可用，累计 %d 字段" % (gname, len(valid)))
        else:
            # 组内逐个试
            for f in groups[gname]:
                d2 = c.query(base + [f], "Stkcd='%s'" % STK, "TRD_Dalyr",
                             "2024-06-03", "2024-06-07", "单字段 " + f)
                if d2 is not None and f in d2.columns:
                    valid.append(f)
                    log("  %s 可用" % f)
                else:
                    log("  %s 不可用" % f)
    pd.DataFrame({"cols": [str(valid)]}).to_csv(RAW + r"\field_probe.csv", index=False)
    valid_cols = valid
log("TRD_Dalyr 最终字段：%s" % valid_cols)

# ================= 2. 日行情按年下载 =================
if have("dalyr", 2500):
    log("日行情已有，跳过")
else:
    parts = []
    for yy in range(2014, 2027):
        a, b = "%d-01-01" % yy, min("%d-12-31" % yy, ET)
        d = c.query(valid_cols, "Stkcd='%s'" % STK, "TRD_Dalyr", a, b, "dalyr %d" % yy)
        if d is not None:
            parts.append(d)
            log("  %d 年 %d 行" % (yy, len(d)))
        else:
            log("  %d 年缺失，稍后补" % yy)
    if parts:
        full = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["Trddt"]).sort_values("Trddt")
        save(full, "dalyr")

# ================= 3. 后复权 / 前复权 / 复权因子 =================
qc = ["Symbol", "TradingDate", "ShortName", "OpenPrice", "HighPrice", "LowPrice", "ClosePrice",
      "Volume", "Amount", "AvgPrice", "ChangeRatio", "TotalShare", "CirculatedShare",
      "TurnoverRate1", "MarketValue", "CirculatedMarketValue", "StateCode"]
for tbl, nm in [("TRD_BwardQuotation", "quote_bward"), ("TRD_FwardQuotation", "quote_fward")]:
    if have(nm, 2500):
        log("%s 已有，跳过" % nm)
        continue
    got = c.query(qc, "Symbol='%s'" % STK, tbl, ST, ET, tbl)
    if got is None:
        got = c.query(qc, "Symbol=%s" % int(STK), tbl, ST, ET, tbl + " 代码不带前导0")
    if got is not None:
        save(got, nm)

if not have("adjustfactor", 2500):
    got = c.query(["Symbol", "TradingDate", "FwardFactor", "BwardFactor",
                   "CumulateFwardFactor", "CumulateBwardFactor"],
                  "Symbol='%s'" % STK, "TRD_AdjustFactor", ST, ET, "AdjustFactor")
    if got is None:
        got = c.query(["Symbol", "TradingDate", "BwardFactor"], "Symbol=%s" % int(STK),
                      "TRD_AdjustFactor", ST, ET, "AdjustFactor 备选写法")
    if got is not None:
        save(got, "adjustfactor")

# ================= 4. 指数 =================
idx_cols = ["Indexcd", "Trddt", "Opnindex", "Hiindex", "Loindex", "Clsindex", "Retindex"]
for code, tag in [("000300", "csi300"), ("801010", "sw_nlfsh"), ("399110", "nlymy_399110")]:
    nm = "index_" + tag
    if have(nm, 2500):
        log("%s 已有，跳过" % nm)
        continue
    d = c.query(idx_cols, "Indexcd='%s'" % code, "TRD_Index", ST, ET, nm)
    if d is None:
        d = c.query(idx_cols, "Indexcd='%s'" % code, "IDX_Idxtrd", ST, ET, nm + "(IDX_Idxtrd)")
    if d is not None:
        save(d, nm)

# ================= 5. FI_T10 估值 =================
if not have("fi_t10_valuation", 40):
    d = c.query(["Stkcd", "Accper", "F100103C", "F100101B", "F100203C", "F100401A", "F100901A"],
                "Stkcd='%s'" % STK, "FI_T10", FST, FET, "FI_T10")
    if d is not None:
        save(d, "fi_t10_valuation")

log("本轮查询次数 %d，完成" % c.query_count)
