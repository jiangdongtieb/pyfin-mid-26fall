# -*- coding: utf-8 -*-
"""
step01 摸清 CSMAR 有什么可用：已购数据库 -> 相关库的表 -> 候选表的字段
只做探索，不下载数据，避免浪费查询次数（同条件 30 分钟冷却）
"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from csmarapi.CsmarService import CsmarService

CRED_FILE = r"C:\Users\35632\Desktop\python期中大作业\CSMAR账号密码.txt"
OUT = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\log\step01_库表字段.json"


def read_cred(path):
    with open(path, encoding="utf-8") as f:
        lines = [x.strip() for x in f if x.strip()]
    return lines[0], lines[1]


acct, pwd = read_cred(CRED_FILE)
csmar = CsmarService()
csmar.login(acct, pwd, "0")
print("登录成功")

dbs = csmar.getListDbs()
print("已购数据库 %d 个" % len(dbs))
for i, db in enumerate(dbs, 1):
    print("%3d. %s | %s ~ %s" % (i, db.get("databaseName", ""), db.get("startTime", ""), db.get("endTime", "")))

result = {"dbs": dbs}

# 关注的库：行情、财务报表、财务指标、指数、股权结构
keywords = ["交易", "财务报表", "财务指标", "指数", "股权", "公告", "收益率"]
tables_of_interest = {}
for db in dbs:
    name = db.get("databaseName", "")
    if any(k in name for k in keywords):
        ts = csmar.getListTables(name)
        tables_of_interest[name] = ts
        print("\n[%s] 共 %d 张表" % (name, len(ts)))
        for t in ts:
            print("    ", t)
result["tables"] = tables_of_interest

# 候选表字段
cand = ["TRD_Dalyr", "TRD_Co", "TRD_Index", "TRD_Cidx", "IAR_Rept",
        "FS_Combas", "FS_Comins", "FS_Comscfd", "FS_Combas0", "TRD_ShangHaiShenZhen"]
fields = {}
for t in cand:
    try:
        fl = csmar.getListFields(t)
        fields[t] = fl
        print("\n字段表 [%s] %d 个: %s" % (t, len(fl), ", ".join([str(x)[:28] for x in fl[:60]])))
    except Exception as e:
        print("取字段失败 %s: %s" % (t, e))
result["fields"] = fields

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1, default=str)
print("\n已保存 ->", OUT)
