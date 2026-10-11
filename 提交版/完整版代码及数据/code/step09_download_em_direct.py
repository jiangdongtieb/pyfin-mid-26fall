# -*- coding: utf-8 -*-
"""
step09 直连东方财富 kline 接口下行情（akshare 1.19.1 的内部接口被断连，requests 直连可用）
这正是课上 Class03 Part A「3. Interacting with Web APIs」教的用法：requests + JSON -> DataFrame
下载：
  em_002714_bfq / qfq / hfq  牧原股份日线三种复权
  em_index_000300 / 000001   沪深300、上证指数
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import requests

BASE = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本"
RAW = BASE + r"\data_raw"
PROG = BASE + r"\log\step09_进度.txt"

URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quote.eastmoney.com/"}
FIELDS1 = "f1,f2,f3,f4,f5,f6"
FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
COLS = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额",
        "振幅", "涨跌幅", "涨跌额", "换手率"]

BEG = "20140101"
END = time.strftime("%Y%m%d")


def log(m):
    line = time.strftime("%H:%M:%S  ") + str(m)
    print(line, flush=True)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch(secid, fqt, name, tries=4):
    params = {"secid": secid, "fields1": FIELDS1, "fields2": FIELDS2,
              "klt": "101", "fqt": fqt, "beg": BEG, "end": END}
    for i in range(tries):
        try:
            r = requests.get(URL, params=params, headers=HEAD, timeout=30)
            r.raise_for_status()
            data = r.json().get("data")
            if not data or not data.get("klines"):
                log("  %s 空（第%d次）" % (name, i + 1))
                time.sleep(6)
                continue
            rows = [k.split(",") for k in data["klines"]]
            df = pd.DataFrame(rows, columns=COLS)
            df["名称"] = data.get("name")
            df["代码"] = data.get("code")
            df["复权方式"] = {"0": "不复权", "1": "前复权", "2": "后复权"}.get(str(fqt), str(fqt))
            for c in COLS[1:10]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df.to_csv(RAW + "\\" + name + ".csv", index=False, encoding="utf-8-sig")
            log("  保存 %s.csv  %d 行  %s ~ %s" % (name, len(df), df["日期"].iloc[0], df["日期"].iloc[-1]))
            return df
        except Exception as e:
            log("  %s 异常 %s（第%d次）" % (name, str(e)[:100], i + 1))
            time.sleep(8)
    log("  !! %s 失败" % name)
    return None


log("开始直连下载")
fetch("0.002714", "0", "em_002714_bfq"); time.sleep(2)
fetch("0.002714", "1", "em_002714_qfq"); time.sleep(2)
fetch("0.002714", "2", "em_002714_hfq"); time.sleep(2)
fetch("1.000300", "1", "em_index_000300"); time.sleep(2)
fetch("1.000001", "1", "em_index_000001")
log("step09 结束")
