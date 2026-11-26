# 作业一 · 基线评测、错误分析与改进验证

邱昱宁 · 231880296　｜　[阅读实验报告](231880296_邱昱宁_作业一.pdf)

原诊断30题通过26题。报告围绕四题的问题、原因、改法和最终验收展开：2026年11月26日完成的最终方法在同一D30诊断集首轮30/30、独立重复30/30。原诊断与后续复测分别记录。

| 基准 | 原诊断通过 | 最终方法验证 | 独立重复 |
|---|---:|---:|---:|
| SWE-bench Verified任务子集 | 10/10 | 10/10 | 10/10 |
| Terminal-Bench 2.1任务子集 | 6/10 | 10/10 | 10/10 |
| Aider Polyglot任务子集 | 10/10 | 10/10 | 10/10 |
| 合计 | 26/30 | 30/30 | 30/30 |

四个原失败任务为地址提取、推理批处理调度、查询优化和视频处理，最终方法两轮均通过其原题评分。后续方法由模型与预算、产物交付流程、公开检查和算法支持共同组成；原诊断与后续验证按各自配置分别记录。

报告按课程[3.4真实评分表](../作业二/evidence/course-grading-tables-20261118.md)组织评测实施、完整轨迹、深入错误分析、至少两类机制与策略，以及改进验证。任务输入、预期行为、实际结果及判分依据均有对应原件。

## 证据入口

- [原30题任务、预期与实际记录](evidence/task-records.json) · [表格索引](evidence/task-records.csv)
- [原逐题成绩](evidence/formal-trials.csv) · [覆盖统计](evidence/formal-coverage.json) · [诊断笔记](evidence/diagnosis-notes.md)
- [原正式运行轨迹](evidence/formal/) · [原评分预检](evidence/preflights/)
- [完整75题结果与独立重复](../作业二/evidence/performance75-final-20261126/)：D30、C30、H15的来源和逐题成绩分别列明
- [源码快照](../shared/reproduction-20261126/) · [最终报告程序](../shared/reproduction-final-report-20261126/)
- [方法与数据来源](../shared/REFERENCES.md)

附件保留完整逐题输入、工具轨迹和原题评分。历史免费模型的[270条对照记录](../作业二/evidence/confirmation-hy4flash-free-v16-summary/)单独统计，源码与导出记录各有对应摘要。

逐题表将题面要求与实际验收分开记录，包含测试数量、具体失败断言和原评分；`task-observations.json`登记这些摘要的来源。需要重建表格时，从仓库根目录运行 `python3 shared/scripts/build_course_task_records.py`，只读取保存的原件，不调用模型或原评分器。
