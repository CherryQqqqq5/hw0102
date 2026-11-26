# 长输出精简与环境提示：实验源码

本目录保存33次真实运行所用的代码及构建文件。原始来源与发布文件的摘要见`SOURCE_MANIFEST.json`。

- `runtime/course_eval/tool_output.py`：保存完整工具输出，按需提供首尾与关键行，并读取实际工作目录和解释器。
- `runtime/course_eval/controller.py`：主动检查、候选保存和提交。
- `run_study.py`、`run_trial.py`、`analyze_study.py`：实验条件、真实执行和事前选择规则。
- `runtime/course_eval/codebuddy_free.py`、`financial_stop.py`、`remote_codebuddy.py`：逐笔实际免费回执校验与停止处理。
- `support/`与`cpp-image/`：实际构建文件、服务器搭建程序和环境资格。

完整题单、原评分、交互与结果见[对应证据目录](../../作业二/evidence/input-efficiency-20261127/)，该目录README提供已实际验证的离线复核命令。运行依赖固定在`requirements.txt`；数据版本、原镜像和预算由证据中的冻结计划及逐题输入记录。
