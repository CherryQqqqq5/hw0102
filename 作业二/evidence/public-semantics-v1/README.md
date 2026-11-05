# 历史公开语义检查

这里保存调度方案重建、真实查询超时及合成数据库工程检查。模型请求数为0，不计入正式任务成功率。检查器见`shared/course_eval/public_semantics.py`。

调度方案根据历史`revision-jsonlines-recovery-v2`中B0/RP的第7步完整命令，在新的断网任务容器重建。原运行未保存最终调度文件，因此这里的文件明确标记为重建产物。`provenance.json`指向原工具日志，`original-command.sh`保留执行命令，`replay.stdout`和`replay.stderr`保留重建输出。

| 候选 | 两桶合计形状数 | 要求 | 公开检查 |
|---|---:|---:|---|
| B0重建 | 13 | ≤8 | 失败，超出全局形状数量 |
| RP重建 | 7 | ≤8 | 通过全部已列公开条件 |

两份候选各自八项性能条件均满足题面阈值。`task_file/scripts/cost_model.py`来自原公开环境；两个桶的六项指标分别与该模型独立复算一致。`B0-failed-shell/`保留第一次使用不支持`time`的Shell而未完成重建的记录。

从仓库`shared/`执行以下命令，读取已发布产物重算条件和指标，并核对历史命令来源；不需要容器或模型额度：

```sh
PYTHONPATH=. python3 scripts/recheck_public_semantics.py
```

`scheduler-validation.json`记录17项工程断言。`query-validation.json`记录真实数据库未改动及14项合成样例断言。原工程脚本`validate.py`、`query_validate.py`和`container_reference_once.py`按执行时内容保存，目录假设见其常量；它们用于解释原记录生成过程，便携复算入口为上面的命令。

真实查询在宿主和任务容器中均达到120秒上限。`query/container-reference-once.json`记录SQLite 3.50.4的`interrupted`、约120.27秒耗时和前后相同的数据库摘要。等价性和速度改善均未得到判定。`query/public-check.json`保留首次实现的失败编码，最终检查器将该情况记为`unknown`。原数据库来自任务镜像，未随证据重复上传。

`query-synthetic/`是150个词、900条词义的合成工程样例，包含查询、基线和检查输出。它验证精确有序输出比较、交错计时、只读执行、错误查询拒绝、数据库修改拒绝及超时三态结果；不提供真实任务成功率或速度改善证据。合成数据库已在最后一项测试中被故意修改，因此保留创建脚本和原记录，未将最终数据库当作初始样例发布。
