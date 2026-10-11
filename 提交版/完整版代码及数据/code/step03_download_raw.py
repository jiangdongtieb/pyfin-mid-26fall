# -*- coding: utf-8 -*-
"""
step03 从 CSMAR 下载牧原股份(002714)期中大作业所需的全部原始数据
- 日行情（含涨跌停状态、总市值、后复权价）
- 复权因子（用于前复权/后复权对比）
- 公司基本情况（上市日、行业）
- 三张财务报表（资产负债 / 利润 / 现金流量，均为累计值）
- 财务报告公告日期（做 Point-in-Time 对齐）
- 财务指标数据库的比率（作为自算指标的交叉验证）
- 基准指数日行情（沪深300 或 申万农林牧渔）
每份原始数据存到 data_raw/，不加工，加工在后面的脚本里做
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
LOG = BASE + r"\log\step03_下载日志.txt"

STK = "002714"
ST, ET = "2014-01-01", "2026-10-07"     # 行情时间区间
FST, FET = "2011-01-01", "2026-06-30"   # 财报时间区间（多取几年做预热）

log_lines = []


def log(msg):
    print(msg)
    log_lines.append(str(msg))


def read_cred(path):
    lines = [x.strip() for x in open(path, encoding="utf-8") if x.strip()]
    return lines[0], lines[1]


def save(df, name):
    if df is None or len(df) == 0:
        log("  !! %s 无数据" % name)
        return None
    path = RAW + "\\" + name + ".csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log("  -> %s.csv  %d 行 x %d 列" % (name, len(df), df.shape[1]))
    return path


def q(csmar, cols, cond, table, st, et, name):
    """一次查询 + 保存，命中冷却就等一等再试一次"""
    log("查询 %s | %s | %s ~ %s" % (name, table, st, et))
    for attempt in range(2):
        try:
            df = csmar.query_df(cols, cond, table, st, et)
            return save(df, name)
        except Exception as e:
            msg = str(e)
            log("  第%d次失败: %s" % (attempt + 1, msg[:200]))
            if "30" in msg and ("分钟" in msg or "minute" in msg.lower()):
                log("  命中冷却，等待 60 秒重试")
                time.sleep(60)
            else:
                time.sleep(3)
    log("  !! %s 下载失败" % name)
    return None


acct, pwd = read_cred(CRED)
csmar = CsmarService()
csmar.login(acct, pwd, "0")
log("登录成功，开始下载 %s" % STK)

# ---------- 1. 日行情 ----------
q(csmar,
  ["Stkcd", "Trddt", "Opnprc", "Hiprc", "Loprc", "Clsprc",
   "Dnshrtrd", "Dnvaltrd", "Dsmvosd", "Dsmvtll",
   "Dretwd", "Dretnd", "Adjprcwd", "Adjprcnd",
   "PreClosePrice", "ChangeRatio", "LimitUp", "LimitDown", "LimitStatus",
   "Trdsta", "Markettype", "Capchgdt"],
  "Stkcd='%s'" % STK, "TRD_Dalyr", ST, ET, "dalyr")

# ---------- 2. 复权因子 ----------
q(csmar,
  ["Stkcd", "TradingDate", "FwardFactor", "BwardFactor",
   "CumulateFwardFactor", "CumulateBwardFactor"],
  "Stkcd='%s'" % STK, "TRD_AdjustFactor", ST, ET, "adjustfactor")

# ---------- 3. 公司基本情况 ----------
q(csmar,
  ["Stkcd", "Stknme", "Conme", "Indnme", "Nindnme", "Nnindnme",
   "Listdt", "Ipodt", "Ipoprc", "Nshripo", "Markettype"],
  "Stkcd='%s'" % STK, "TRD_Co", "", "", "co_info")

# ---------- 4/5/6. 三张财务报表 ----------
q(csmar,
  ["Stkcd", "Accper", "Typrep", "IfCorrect",
   "A001000000", "A001100000", "A001101000", "A001123000",
   "A001200000", "A001204000", "A001212000", "A001216000",
   "A002000000", "A002100000", "A002101000", "A002200000",
   "A002201000", "A002203000", "A003000000", "A003100000", "A003105000",
   "A004000000"],
  "Stkcd='%s'" % STK, "FS_Combas", FST, FET, "fs_combas")

q(csmar,
  ["Stkcd", "Accper", "Typrep", "IfCorrect",
   "B001100000", "B001101000", "B001200000", "B001201000",
   "B001209000", "B001210000", "B001211000", "B001216000",
   "B001300000", "B001000000", "B002100000",
   "B002000000", "B002000101", "B003000000"],
  "Stkcd='%s'" % STK, "FS_Comins", FST, FET, "fs_comins")

q(csmar,
  ["Stkcd", "Accper", "Typrep", "IfCorrect",
   "C001001000", "C001000000", "C002000000", "C002006000",
   "C003000000", "C003006000", "C005000000", "C006000000"],
  "Stkcd='%s'" % STK, "FS_Comscfd", FST, FET, "fs_comscfd")

# ---------- 7. 公告日期（PIT 对齐） ----------
q(csmar,
  ["Stkcd", "Accper", "Reptyp", "Annodt", "Annowk", "Profita", "Profitb"],
  "Stkcd='%s'" % STK, "IAR_Rept", FST, ET, "iar_rept")

# ---------- 8. 财务指标（交叉验证用） ----------
q(csmar, ["Stkcd", "Accper", "Typrep", "F010101A", "F010201A", "F011201A"],
  "Stkcd='%s'" % STK, "FI_T1", FST, FET, "fi_t1_solvency")
q(csmar, ["Stkcd", "Accper", "Typrep", "F041705C", "F040505C", "F040604C", "F041205C"],
  "Stkcd='%s'" % STK, "FI_T4", FST, FET, "fi_t4_efficiency")
q(csmar, ["Stkcd", "Accper", "Typrep", "F050504C", "F053004C", "F050204C", "F053301C"],
  "Stkcd='%s'" % STK, "FI_T5", FST, FET, "fi_t5_profitability")
q(csmar, ["Stkcd", "Accper", "Typrep", "F060101C", "F060101B"],
  "Stkcd='%s'" % STK, "FI_T6", FST, FET, "fi_t6_cashflow")
q(csmar, ["Stkcd", "Accper", "Typrep", "F100103C", "F100401A", "F100203C", "F100901A"],
  "Stkcd='%s'" % STK, "FI_T10", FST, FET, "fi_t10_valuation")
q(csmar, ["Stkcd", "Accper", "Typrep", "F081601B", "F081001B", "F080601A"],
  "Stkcd='%s'" % STK, "FI_T8", FST, FET, "fi_t8_growth")

# ---------- 9. 基准指数：先查指数代码，再下日线 ----------
idx_fields = csmar.getListFields("IDX_Idxinfo")
log("IDX_Idxinfo 字段: %s" % ", ".join([f.get("field", "") for f in idx_fields]))
name_field = None
for f in idx_fields:
    fn = f.get("fieldName", "") or ""
    if "名称" in fn or "简称" in fn:
        name_field = f.get("field")
        break
log("指数名称字段: %s" % name_field)

col_names = [f.get("field") for f in idx_fields]
probe = None
for kw in ["沪深300", "农林牧渔", "农牧"]:
    if name_field is None:
        break
    try:
        probe = csmar.query_df(col_names[:6], "%s like '%%%s%%'" % (name_field, kw),
                               "IDX_Idxinfo", "", "")
        log("指数关键词 %s -> %d 条" % (kw, len(probe)))
        if probe is not None and len(probe) > 0:
            log(probe.head(12).to_string())
            save(probe, "idx_info_%s" % kw)
    except Exception as e:
        log("指数探查失败 %s: %s" % (kw, str(e)[:150]))

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines))
log("全部完成")
