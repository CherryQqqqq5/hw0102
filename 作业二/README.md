# 作业二 · 智能体改造与验证

[阅读实验报告](231880296_邱昱宁_作业二.pdf)

改造用公开题面、检查命令和依赖文件建立验证记录。A 和 F 在第六个已执行命令后检查题面明确指定的交付文件，缺失时提示保存草稿。智能体声明完成时，程序检查验证记录。完整配置还会核对相关文件内容，发现变化后要求重新验证。最终产物由原题评分器判分。

| 配置 | 行为 |
|---|---|
| B0 原生基线 | 使用默认决策循环和提交处理 |
| BP 文字提示 | 提供同样的公开检查、交付路径与第六步说明 |
| A 时效消融 | 在第六步检查交付文件，执行公开检查并记录结果，提交时沿用已有通过记录 |
| F 完整改造 | 在 A 的基础上核对依赖内容，使过期检查失效 |

## 证据与对照

- 30 道诊断配对中，B0 通过 26 道，F 通过 24 道，下降 6.7 个百分点。四对涉及提供方请求超时，单列后余下 26 道的通过率下降 7.7 个百分点。
- 15 道留出题的四种配置各重复三次，180 次均取得评分。B0、BP、A 和 F 分别通过 38、40、43 和 37 次，分母各为 45 次。以题为单位计算，F 分别低于 B0、BP 和 A 2.2、6.7 和 13.3 个百分点，三个配对区间均包含零。
- `javascript/book-store` 的 F 三轮均检测到测试脚本改变依赖，重测后继续提交。A 和 F 的三轮原题评分均通过。留出 A/F 每轮的通过数依次为 14/12、14/13、15/12，每轮 15 道题。
- [配对案例](evidence/improvement-cases.md)记录较早交付、语义或性能持续失败、补丁缺失，以及提交检查对等效命令的处理。诊断集未出现 0 分转为 1 分。
- [改造代码](../shared/course_eval/verification.py)和[智能体运行入口](../shared/course_eval/agent.py)实现验证记录、过期判定和提交处理。
- [验证时效对照](evidence/verification-proverb/)使用真实 Aider 容器，验证了源文件修改后旧检查失效、无关日志变化无需重测，以及恢复源文件并重新验证后接受提交。
- [请求上限验证](evidence/pilot-aider-budget-deepseek/)和[容器命令超时验证](evidence/terminal-command-timeout-regression/)记录预算终止后的产物保存和命令恢复行为。
- [嵌套命令回归](evidence/terminal-nested-timeout-regression-v2/)验证超时清理进程树及原题评分，[补跑前的未评分尝试](evidence/formal-nested-timeout-recovery-v1/)保留原始错误。模型请求重试的正式触发记录见 [Rust 配对轨迹](evidence/formal/D-aider-rust__doubly-linked-list-F-r1/)。
- [冻结的公开检查](configs/public-checks.json)列出各题可见要求、依赖与命令。[正式对照汇总](evidence/formal-coverage.json)和[逐题成绩](evidence/formal-trials.csv)记录 30 次同题改造对照和 180 次留出评测。[作业一基线](../作业一/)

评测依赖、冻结题目清单及运行命令见[共用代码与复现](../shared/)。
