# 共用代码与复现说明

报告使用两批独立记录：75题的正式对照与重复，以及33项输入效率实验。下列入口对应各批实际运行版本。

## 75题正式评测

最终方法与独立重复均为75/75，同题原生DeepSeek Harness（DSH，DeepSeek智能体执行框架）为69/75。实现以mini-SWE-agent为基础，使用CodeBuddy连续会话、公开检查和候选管理。

| 阅读内容 | 实际源码 |
|---|---|
| 动作执行、检查和候选管理 | [v18 controller.py](runtime-snapshots/hy4-v18/course_eval/controller.py) |
| 检查依赖与失效状态 | [v18 verification.py](runtime-snapshots/hy4-v18/course_eval/verification.py) |
| 文件保存、恢复和测试文件保护 | [v18 candidate_io.py](runtime-snapshots/hy4-v18/course_eval/candidate_io.py) |
| 连续会话、请求预算与零积分核验 | [v18 agent.py](runtime-snapshots/hy4-v18/course_eval/agent.py) |
| FEAL算法支持 | [v19 terminal_runtime.py](reproduction-20261126/work/frozen-performance-hy4-feal-linear-v19/course_eval/terminal_runtime.py) |
| ReLU与xarray4695的提交检查 | [v20 controller.py](runtime-snapshots/hy4-v20/course_eval/controller.py) |

v18用于每轮72题，v19用于FEAL一题，v20用于其余两题。[完整源码快照](reproduction-20261126/README.md)保留942项来源文件及九个冻结运行版本；[最终结果](../作业二/evidence/performance75-final-20261126/)保存逐题来源、独立审查与三个证据分包。

## 输入效率实验

[完整源码](reproduction-input-efficiency-20261127/)包含123份来源文件及对应SHA-256；[实际记录](../作业二/evidence/input-efficiency-20261127/)包含33项运行、原评分、674笔自身零积分回执和工具输出。原始日志与提供给模型的摘要分别保存，可核对摘要实际保留的内容。

在Python 3.13环境安装该目录固定的依赖后，可从仓库根目录执行离线复算；该命令不调用模型，也不需要Docker：

```sh
cd 作业二/evidence/input-efficiency-20261127
PYTHONPATH=runtime:support:. python export_study.py --verify .
```

实际复算结果为33项运行、26项原评分通过、674笔自身零积分回执、18,438,554词元，883个导出文件通过完整性校验。各配置的实际结果和预先规定的采用条件见同目录说明。

## 报告与费用记录

[本版报告与提交包程序](reproduction-final-report-20261127/)包含报告数据读取、排版、页面检查、打包及依赖。PDF由服务器保留的原始数据生成；包内提供经过凭据过滤的代码与实验记录，来源摘要和导出摘要分列。

[提交复查试验费用记录](../作业二/evidence/input-efficiency-cost-history-20261127/)保留22笔自身零积分回执和第23笔未知费用，35笔历史未知继续保留。该试验中断，尚无原评分，未计入性能结果；新增模型调用保持停止。

早期评测的环境与执行说明保存在[历史说明](history/early-experiments.md)，各批源码与真实记录维持原有版本。
