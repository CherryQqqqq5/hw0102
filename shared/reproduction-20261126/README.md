# 评测实现与复现入口

本目录保存2026年11月26日评测的完整源码快照：941项选定源码和配置，加1份可迁移的Harbor启动程序，共942项来源文件，涵盖九个冻结运行版本。代码、任务局部修订、模型接入、费用核验、统计、报告与提交包程序均保留对应版本。逐题评分、交互和工程执行记录见[作业二证据目录](../../作业二/evidence/)；本目录的源码验证结果与模型成绩分别记录。

## 核对源码与版本

`SOURCE_MANIFEST.json`列出原实验文件和交付文件各自的摘要、字节数与转换说明。代码保持其记录的原字节；配置记录按既有导出规则处理机器路径等字段。`byte_identical`、`source_sha256`与`export_sha256`用于区分这两类情况。`source_versions`另列24项历史版本及其准确位置，旧[601项源码快照](../reproduction-20261125/)继续保留。

在已安装评测依赖的Python 3.13环境中，从本目录执行：

```sh
PYTHONPATH="$PWD" python -B sync_sources.py verify
```

该命令核对本目录、历史源码、公共依赖与客户端补丁的摘要，不请求模型、不启动容器或原题评分器。运行产生的`__pycache__/*.pyc`按原有规则忽略，其他额外文件会被拒绝。

`SELECTION.json`和`SYNC_PLAN.json`保存本快照的允许清单及原始复制计划。复制计划的摘要为`c815cc1e2483601263e7c606b6af9c613321b69acf9ce922736a3681aa301859`。发布说明单独维护在本文件，当前摘要登记在清单的`generated_files`中；原准备模板和复制计划保持原版本。

## 运行版本与适用任务

| 运行版本 | 对应范围 |
|---|---|
| `frozen-performance-dsh-parallel-guard-20261124` | 原生DeepSeek Harness（DSH，DeepSeek智能体执行框架）对照 |
| Hy4 `sql-layout-v18`及其`guidance-off`版本 | 原固定75题批次和原指导消融 |
| Hy4 `feal-linear-v19` | FEAL（Fast Data Encipherment Algorithm，快速数据加密算法）通用线性攻击支持的局部修订 |
| Hy4 `submit-boundary-v20` | ReLU（Rectified Linear Unit，修正线性单元）与xarray4695的固定修订会话 |
| NVIDIA `free-v27`、`v28`、`v30`、`v31` | 各自传输和提示版本的辅助记录 |

八处任务局部修订对应67个未改变任务定义的两份原记录和16个固定新会话。运行来源逐位置登记，v20行为不回填到其他历史任务。工程参考和零模型资格检查有各自的记录，模型成绩以实际原题评分为准。

## 分析、导出与报告

依赖准备方法见[共用评测说明](../README.md#准备数据和依赖)。在同一环境中，可先检查三个入口：

```sh
PYTHONPATH="$PWD" python -B work/parallel-free-evaluation-20261124/prepare_report_data.py --help
PYTHONPATH="$PWD" python -B work/parallel-free-evaluation-20261124/export_nvidia_history.py --help
PYTHONPATH="$PWD" python -B launchers/harbor_entry.py --help
```

实际源码验证和上述三个入口均已在此目录执行通过，见[执行记录](../../作业二/evidence/reproduction-source-validation-20261126.json)。入口帮助验证其加载与参数解析；统计和报告生成还需传入对应的完整评分、轨迹和审查记录。

`analyze_hy4.py`复算原固定批次，`join_scoped_revisions.py`核对继承位置与固定修订位置，`prepare_report_data.py`生成报告数据。报告程序要求完整预定评分、指导消融和最终独立审查，并核对原题评分与适用的终局验证。`export_joined_evidence.py`按物理运行去重导出证据；`export_nvidia_history.py`单独保存其他模型的历史用量、真实结果及费用缺口。

源码中固定的旧费用状态和本机日志路径用于核对历史记录。原生会话内容、账户数据和登录凭据不在本目录；两个当前项目日志位置的源码引用按精确文件摘要核验，见[发布前扫描记录](../../作业二/evidence/reproduction-source-sensitive-scan-20261126.json)。后续发布扫描器保存在[独立版本](../scripts/scan_staged_delivery_20261126.py)，快照内原扫描器保持其原摘要。

## 准备新的模型实验

新运行需要另行准备固定版本的公开任务数据、镜像、外部依赖与模型登录，并重新核验本机执行条件和免费资格。历史配置描述曾经使用的条件，不能代替新环境的费用回执或准入检查。Hy4每笔请求须有自身新身份与实际零积分回执；新费用不明或非零时停止派发。

[CodeBuddy 2.179.3补丁](../client-patches/codebuddy-2.179.3-free-safety-v8/)提供原始客户端、补丁和目标客户端的摘要。DSH 0.2.2rc2、Python 3.13.12及其9840项文件或链接的来源保存在`work/nvidia75-v27-20261125/dsh-runtime-files.json`。公共sqlparse wheel按清单引用相邻已发布副本。客户端安装树、完整软件环境、容器镜像和可重建缓存均由目标环境自行准备。

