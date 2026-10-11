# -*- coding: utf-8 -*-
"""
step02 把要用的表的字段名（field + 中文名）写成一个可读文本，方便挑字段
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from csmarapi.CsmarService import CsmarService

CRED = r"C:\Users\35632\Desktop\python期中大作业\CSMAR账号密码.txt"
OUT = r"C:\Users\35632\Desktop\python期中大作业\B_我的重做版本\log\step02_字段清单.txt"

lines = [x.strip() for x in open(CRED, encoding="utf-8") if x.strip()]
csmar = CsmarService()
csmar.login(lines[0], lines[1], "0")
print("登录成功")

tables = ["TRD_Dalyr", "TRD_Co", "TRD_Index", "TRD_BwardQuotation",
          "TRD_FwardQuotation", "TRD_AdjustFactor", "IAR_Rept",
          "FS_Combas", "FS_Comins", "FS_Comscfd",
          "FI_T1", "FI_T4", "FI_T5", "FI_T6", "FI_T8", "FI_T10", "FI_T11"]

buf = []
for t in tables:
    buf.append("=" * 78)
    buf.append("TABLE %s" % t)
    buf.append("=" * 78)
    for attempt in range(3):
        try:
            fl = csmar.getListFields(t)
            break
        except Exception as e:
            print("  重试", t, attempt, type(e).__name__)
            fl = None
    if not fl:
        buf.append("  <取字段失败>")
        continue
    for f in fl:
        buf.append("  %-16s %s" % (f.get("field", ""), f.get("fieldName", "")))
    print("%s: %d 字段" % (t, len(fl)))

with open(OUT, "w", encoding="utf-8") as fp:
    fp.write("\n".join(buf))
print("saved ->", OUT)
