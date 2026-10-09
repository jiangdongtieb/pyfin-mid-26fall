# 成员 2：Task 1 技术面择时指标

## 我的任务
负责 Task 1：在 1 号同学的面板上实现 MA / 动量 / 量价三类信号 + RSI/MACD/布林等进阶指标，并按题目要求做 0/1 信号与 expanding 百分位两种打分，合成技术面得分。你的输出交给 4 号做检验。

## 我交付什么（本文件夹）
- 我的代码/：**我的代码.ipynb**（一个文件讲完，Restart & Run All 可独立跑通）+ **数据/**（输入文件已贴好）+ **输出/**（运行结果）
- 我的报告章节.md：我负责的章节正文（摘自完整报告）
- 我的写作思路.md：我负责部分的逐行讲解（摘自代码指导书）
- 我的PPT.pptx：我讲解的页面（从完整 14 页 PPT 中抽出）
- 我的讲稿.md：每页讲什么、关键数字是什么

## 交接（任务干一半交给下一位）
交给 3 号：技术面得分列（panel 的 tech_score / tech_score_full / 13 个 sig_* 信号列），并说明三类信号为何等权。

## 我的 PPT 讲解安排
第 5、6、8 页：数据与清洗（你引用 1 号的成果讲复权与涨跌停）→ Task1 技术面（图 1 + 描述统计）→ Task3 技术信号两分组（你算的信号的检验结果）。约 3 分钟。

## 我负责的代码位置
在 muyuan_core.py 中负责 TechnicalFramework 类：rolling 均线、shift 动量、VWMA 两步除法、ewm 实现的 Wilder RSI、expanding().rank(pct=True) 百分位打分、三类等权合成 tech_score。重点能讲：为什么 RSI 用 ewm(alpha=1/14)、为什么 expanding 不是全样本 rank（防前视）。

完整代码：B_我的重做版本/code/muyuan_core.py（只读，勿改）；完整报告/PPT 在 B_我的重做版本/。
