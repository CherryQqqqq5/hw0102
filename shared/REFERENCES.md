# 方法与数据来源

## 智能体与评测任务

- [mini-SWE-agent作者代码](https://github.com/SWE-agent/mini-swe-agent)：原生执行循环及本项目的改造基础。
- [SWE-bench官方评分器](https://www.swebench.com/SWE-bench/reference/harness/)：软件修复的原题验收。
- [Terminal-Bench 2.1任务版本](https://github.com/harbor-framework/terminal-bench-2-1/tree/7131e4375048a0e408a8fb404b5f499d726b695b)：终端任务及原验收程序。
- [Aider Polyglot任务版本](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f)：跨语言编程任务及原测试。
- [DeepSeek DSH与公开实验说明](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)：原生对照框架及其公开设置。本作业的成绩来自实际同题运行。

## 复用的检查与算法

- [pyelftools装载段解析说明](https://github.com/eliben/pyelftools/blob/main/doc/user-guide.md)：二进制装载段与地址读取。
- [Mark Stamp：FEAL线性攻击，第21—27页](https://www.cs.sjsu.edu/~stamp/crypto/PowerPoint_PDF/13_FEAL.pdf)：线性攻击的公开算法依据。
- [scikit-learn缺失值迭代实现](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/impute/_iterative.py)：缺失值迭代与转换行为的实现依据。

采用的实际文件与版本由源码快照和逐题运行记录登记，公开说明的后续更新不改变本项目的冻结版本。
