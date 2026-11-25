# 2026年11月26日八处修订源码快照准备

本目录保存当前八处任务局部修订对应的显式源码允许清单和同步入口。只准备来源摘要和字节预算，尚未复制完整源码树、修改发布克隆或生成正式提交包。它不表示原225、16个固定修订位置、三题消融、两份正式PDF或最终提交包已经完成。

旧 `work/current-source-preparation-20261126/SYNC_PLAN.json` 的925来源草案及SHA `993cc78b1d5ba9a09c3c2452e24361b12f8bc179583bce604de08bc289a8e8fb` 原样保留。新计划独立新建，不把已变化的当前源码冒充旧审查版本。

## 准备、核验与实际同步

从原项目根使用已有Python环境：

```sh
work/.venv/bin/python -B work/current-source-preparation-eight-20261126/sync_sources.py plan
work/.venv/bin/python -B work/current-source-preparation-eight-20261126/sync_sources.py verify-plan
```

`SELECTION.json`是明确允许的代码、公开配置、动态加载关系与历史版本清单；`SYNC_PLAN.json`记录各文件的原source SHA-256、脱敏export SHA-256和字节数。代码保持原字节，配置沿用已发布同步器的既有scrub。不会递归跟随任一实验plan的all_files_sha256，也不打开在途run、模型或原生会话。任何来源漂移均拒绝，应在新路径重新审查。

父线程审核准确plan SHA后，才可执行一次实际同步：

```sh
work/.venv/bin/python -B work/current-source-preparation-eight-20261126/sync_sources.py sync \
  --approved-plan-sha256 <已审核SYNC_PLAN.json完整SHA> \
  --output work/hw0102-publish/shared/reproduction-20261126
```

目标必须尚不存在；旧`shared/reproduction-20261125`及其601来源清单保留。单次代码快照连同清单、同步器、说明上限32MiB。当前尚未执行此同步。

## 代码与配置范围

沿用旧601来源的明确代码/公开配置集合及前一925来源草案的当前入口，覆盖原R35续接、light版本探针、proxy-CDN镜像准备与预取、已有七处局部修订、typed NVIDIA关闭费用补充、报告与最终提交包说明。新增xarray4695的原pin保护资格、固定两会话冻结器、八scope消费者检查、报告局部版式与真实loader检查，以及实际plan、原命令不变的inputs/tasks/checks和capture policy。

八scope计划只允许67个未改变任务定义各两份原记录加16个固定新会话，真实未完成位置仍pending。ReLU与新增xarray4695两scope使用同一已审v20；NaN等原v18合同和其他实际运行时各保留来源，不把v20行为回填到67个历史继承任务。源码复制不改变模型、单次尝试预算、评分、派发、费用守卫或已有原分。工程资格与参考实现不算模型成绩。

九个冻结运行时仍各保留原相对路径；公开sqlparse wheel引用现有`shared/runtime-snapshots/hy4-v18/course_eval/sqlparse.whl`精确字节。新增小型v20 runtime-manifest是原资源摘要描述，不是新运行准入。

## 历史版本与外部依赖

`source_versions`保留旧601中不同版本的既有发布位置、原925草案选中的authoring前像，以及新增join/consumer/renderer七scope前像和loader P1修复前像。归档版本保持精确原字节；独立资格脚本可据此重现旧loader错误。原审查不回写为新SHA。

CodeBuddy 2.179.3安全补丁继续精确引用`shared/client-patches/codebuddy-2.179.3-free-safety-v8`，不复制5MB补丁、npm树、凭据或登录状态。DeepSeek Harness（DSH）0.2.2rc2/Python3.13.12使用现有小型9840文件/链接来源描述，不复制SDK大树。镜像只保留原pin与下载/导入代码，镜像和公开任务数据须在目标环境另行准备。准备阶段不安装或执行这些依赖。

原模型请求/返回、工具、控制、候选、原评分、实际资格process、缺失费用和接受事件由既有`export_joined_evidence.py`、`export_nvidia_v28.py`、`export_nvidia_history.py`另行脱敏导出。本代码快照不包含这些实际执行数据；依赖它们的审查/资格checker需要相应真实便携证据，不能用缺失记录伪造通过。配置中旧的机器路径和费用状态只作为来源描述，不可直接重放成新准入。

## 最小验证与交付边界

准备阶段只编译允许清单内代码、核来源/导出SHA和预算，并测试来源漂移、超32MiB、路径逃逸/链接和raw模型轨迹拒绝。不会复制完整树或访问任何模型服务。

实际同步经父审核后，再运行新目录的`python -B sync_sources.py verify`，以及现有report-data、typed关闭费用出口和portable Harbor launcher的三项`--help`。需要时核NVIDIA entry的`--import-proof`。可重建的`__pycache__/*.pyc`沿用旧同步器的精确忽略规则，其他额外文件继续拒绝。实际源码大小、便携入口、敏感扫描、完整原评分/费用/轨迹、两PDF字节与最终ZIP仍须分别验收；准备或loader资格均不替代最终交付。

