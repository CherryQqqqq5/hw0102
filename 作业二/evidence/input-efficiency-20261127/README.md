# 新题输入效率实验

本实验在ModelArts上比较原始主动检查方案、环境提示、长输出精简和原生DeepSeek Harness（DSH）。三题用于诊断输入开销，另外六题在首次模型调用前固定，用于配置比较；符合预定条件的配置再独立重复六题。最终结果以`study-results.json`、`repeat-results.json`及独立复核为准。

`candidate-tasks.json`保存题单、预算、排除条件与选择规则；`study-plan.json`保存实际执行源码及原镜像摘要。`inputs/`保存各题输入和评分资格，`preflight/`记录初始实现与官方参考解的原评分。`trials/`与`repeat/`保存真实交互、工具返回、候选、原评分和逐次免费回执。三份修订归档保留评分等待时限、基线补充和参考文件映射的调整及其原记录。

## 离线复核

解压同名证据ZIP后，在解压目录使用Python 3.13和`requirements.txt`中的依赖运行：

```sh
PYTHONPATH=runtime:support:. python export_study.py --verify .
```

该命令逐文件核对摘要，从实际运行记录重算原题成绩、模型用量和每笔零积分回执。它不会发送模型请求或启动容器。`index.json`对应导出前后文件，`verification.json`记录导出复核结果，`final-study-review.json`绑定完整统计与独立复核。

## 代码与执行条件

`runtime/course_eval/tool_output.py`实现完整日志归档和成功长输出精简；相关环境入口由运行时按实际容器生成。`run_study.py`设置比较条件，`run_registered.py`依次执行已登记任务，`analyze_study.py`按固定规则选配置并计算重复结果。`build_images.sh`、`build_cpp_image.sh`及`cpp-image/`提供语言环境的构建入口，`support/work/vmshare/aider/`保存所用小型构建文件。Python测试依赖版本另见`aider-python-requirements.txt`。

`support/server/`保存本次ModelArts环境的搭建程序和实际资格记录。环境说明见该目录`ENVIRONMENT.md`；发布副本中的`[server-project]`代表部署时的项目根目录。

重新执行模型实验需要准备官方任务数据、指定摘要的原镜像及相同资源配置，并重新核验执行环境和免费通道。保存的`execution.json`记录本次实际环境；其中的路径、Docker身份和客户端摘要对应原运行设备。任务容器禁止联网，模型接入与评分分别执行。每笔模型请求核验实际Hy4免费身份及自身零积分回执，费用未知或非零即停止。

原始方案、环境提示和长输出精简均保留相同最终检查。精简只改变新命令长输出的呈现，完整日志仍可读取，原有对话历史不压缩。DSH使用自身执行接口；C0的主动检查、保存和提交规则由课程控制器提供。比较指标同时包含原题通过率、实际词元、请求数及求解时间。
