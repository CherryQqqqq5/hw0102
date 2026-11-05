# 公开条件检查器

检查器只使用原任务的完整 `instruction.md` 与公开环境文件。任务根目录是 `work/datasets/terminal-bench-2-1-7131e4375048a0e408a8fb404b5f499d726b695b/tasks/`。实现期间没有读取任务的隐藏测试、参考解答或官方评分阈值。

两个实现文件是 `course_eval/public_semantics.py` 和 `course_eval/check_public_semantics.py`，依赖 Python 3.11 及以上版本的标准库。检查器不会导入或运行候选环境中的 Python 代码。输出为 JavaScript Object Notation（JSON，结构化数据表示）对象：

```json
{
  "conditions": [
    {"id": "scheduler.global_shape_cap", "passed": false, "status": "fail",
     "actual": 13, "required": {"operator": "<=", "value": 8, "scope": "both buckets"}}
  ],
  "metrics": {},
  "passed": false
}
```

所有硬条件通过时顶层 `passed=true`，退出码为 `0`；存在明确失败时 `passed=false`，退出码为 `1`。参考查询未完成、查询超时或计时未完成时，对应条件为 `passed=null,status=unknown`；没有其他明确失败时顶层同为 `passed=null`，退出码为 `2`。每条条件保留实际值与要求。公开检查通过只说明本检查器覆盖的公开条件通过，正式评分仍由独立评价流程产生。

## 调度任务

来源为 `llm-inference-batching-scheduler/instruction.md`、`environment/task_file/scripts/cost_model.py` 以及两个公开请求文件。

| 条件 | 检查方式 |
| --- | --- |
| 输入保持不变 | 对比候选执行前保存的整个 `input_data` 文件集合及文件内容摘要 |
| 输出结构 | 每行一个 JSON 对象；请求及批次标识为字符串，三个形状维度为整数，布尔值不作为整数接受 |
| 请求覆盖 | 每个桶的输入请求恰好出现一次；报告缺失、重复和额外标识 |
| 形状尺寸 | `heads_align=32`、`hidden_align=4096` |
| 对齐与容量 | `seq_align` 是 64 的倍数，且至少为 `ceil(prompt_len/64)*64` |
| 批次一致性 | 每个输出文件内，同一个 `batch_id` 的形状完全一致 |
| 全局形状数 | 两个桶的形状三元组并集最多 8 个 |
| 性能 | 两个桶分别满足下表的全部严格小于条件 |

| 桶 | `cost` | `pad_ratio` | `p95_latency_ms` | `sequential_timecost` |
| --- | ---: | ---: | ---: | ---: |
| 1 | `<3.0e11` | `<0.055` | `<2.1e6` | `<2.7e8` |
| 2 | `<4.8e10` | `<0.15` | `<2.1e5` | `<3.2e7` |

公开基线给两个桶重复使用批次编号，因此批次编号在各自文件内解释；形状数量严格按两份文件的并集计算。性能公式逐项根据公开 `cost_model.py` 实现，并通过独立数值对比验证。该公开模型在批次计算中使用真实请求的最大对齐提示长度，声明形状影响编译成本；检查器保留此公开定义。

## 查询任务

来源为 `query-optimize/instruction.md`、`environment/task-deps/my-sql-query.sql` 与 `environment/Dockerfile` 所指定的 Open English Wordnet（OEWN，开放英语词网）数据库。Structured Query Language（SQL，结构化查询语言）由 SQLite 自身解析。

- 数据库文件必须与候选执行前的原文件逐字节一致。原查询文本从执行前基线读取，候选对 `/app/my-sql-query.sql` 的改写不会改变比较对象。
- `/app/sol.sql` 必须无注释、以分号结束，并由 SQLite 接受为一个产生结果的查询。字符串或带引号标识中的注释分隔符不视为注释。
- 每次查询创建只读数据库连接，启用 `query_only`，只允许查询相关授权动作，并把临时计算存储放在内存中。写入、附加数据库、修改设置等语句会被拒绝。
- 原查询与候选先各预热一次，再进行偶数轮交错计时。默认 4 轮，顺序依次为原查询先、候选先；连接在每次执行后关闭。每次执行均核对列名、行顺序、重复次数及全部值与公开原查询一致。
- 每次查询有 120 秒默认运行上限，超时保留 `unknown` 条件及具体阶段。原参考查询未完成时，不能判定候选是否等价。此上限是检查器的资源保护参数，不是任务的评分阈值。
- 原说明要求提高效率，没有提供数值耗时阈值。检查器报告每轮实际耗时，以“原查询时间减候选时间的配对中位数大于 0”作为公开优化目标的本地操作性判定；该条件不来自隐藏评分标准，也不声称统计显著。短查询、并发负载和缓存状态会影响该判定。
- 查询前后再次核对数据库内容。计时结果包含 `public_numeric_runtime_threshold: null`，避免将本地操作规则当作官方阈值。

## 控制器集成

控制器必须在候选首次修改前采集基线，保留在候选不能更改的控制器状态中。候选检查时使用受信的两份检查器源码和原基线；候选可写目录中的同名检查器或基线不能作为依据。摘要的用途仅为落实原说明中“输入或数据库不得改动”的要求。

```sh
python3 check_public_semantics.py capture scheduler --root /app/task_file
python3 check_public_semantics.py scheduler --root /app/task_file --baseline /opt/public-checker/baseline.json

python3 check_public_semantics.py capture query --root /app
python3 check_public_semantics.py query --root /app --baseline /opt/public-checker/baseline.json --repeats 4 --timeout-seconds 120
```

`capture` 输出基线对象，由控制器保存；两个检查子命令输出上面的条件报告。直接调用接口如下：

```python
baseline = capture_baseline("scheduler", Path("/app/task_file"))
report = check_scheduler(Path("/app/task_file"), baseline)

baseline = capture_baseline("query", Path("/app"))
report = check_query(Path("/app"), baseline, repeats=4, timeout_seconds=120)
```

控制器可将失败条件交还候选进行修正，再以同一基线重新检查。原始报告及退出码应保留，最终候选的检查结果应关联最终交付文件。检查器不自行恢复文件、修改候选、调用模型或触发官方评分。

## 工程验证

已保存的调度重建输出可用 `scripts/recheck_public_semantics.py` 重新进行离线检查。从本目录执行，使用 Python 3.11 或以上版本；该命令不启动容器或查询真实数据库，并核对已发布历史日志中的原命令：

```sh
PYTHONPATH=. python3 scripts/recheck_public_semantics.py
```

历史调度输出文件未保存。验证根据 `work/vmshare/revision-jsonlines-recovery-v2/` 下 B0 与 RP 的 `agent/tools.jsonl` 中 `codebuddy-7` 完整命令，在新的断网任务容器中重建候选。每次重建保留原命令、日志位置、事件编号、历史标准输出、当前标准输出及新检查报告。该材料是有来源的重建结果，不是原运行当时保存的交付文件。

| 重建候选 | 两桶各自形状数 | 跨桶形状数 | 公开性能条件 | 检查结论 |
| --- | --- | ---: | --- | --- |
| B0 | 7 / 7 | 13 | 八项均通过 | 全局形状上限失败 |
| RP | 4 / 4 | 7 | 八项均通过 | 全部公开条件通过 |

两个候选、两个桶的成本、填充量、实际词元数、填充率、95 分位延迟和顺序执行时间均与原公开成本模型在 `1e-12` 相对容差内一致。重复请求、漏请求、错误固定维度、未对齐形状、容量不足、布尔形状值及输入字节变更均有实际拒绝验证。

第一次 B0 重建在 `sh` 中执行历史命令时，命令使用的 `time` 不可用，未生成候选。该失败保留在 `work/public-semantics-validation/B0-failed-shell/`；按历史工具类型改用 `bash` 后完成重建。没有修改历史候选算法。

查询的真实 OEWN 数据库验证遇到参考查询未完成：宿主执行达到 120 秒上限；随后在新的断网任务容器内仅执行一次原查询，SQLite 3.50.4 在约 120.27 秒返回 `interrupted`。两次检查均保留原数据库字节内容。真实任务的查询等价性与速度改善均未验证，不再重复原查询。

SQLite 合成工程样例包含 150 个词与 900 条词义记录，使用原公开查询和人工编写的公共表达式聚合候选。14 项样例检查验证了精确有序输出比较、交错计时、只读执行、注释和多语句拒绝、不同结果拒绝、数据库改动拒绝，以及参考超时返回 `unknown` 和退出码 `2`。这些结果验证检查器行为，不作为真实 OEWN 任务或模型方法成功的证据。调度离线验证 17 项通过，加上真实查询容器的数据库未改动检查，共计 32 项工程断言通过，模型调用数为 0。

完整证据位于 [`作业二/evidence/public-semantics-v1`](../作业二/evidence/public-semantics-v1/README.md)。上文 `work/` 路径描述原执行环境；原工程脚本按执行时内容保存。发布目录中的结果位置：

- `scheduler-validation.json`：17 项调度检查。
- `B0/public-check-current.json` 与 `RP/public-check-current.json`：最终检查器对重建候选的报告。
- `query/public-check.json`：首次宿主参考查询超时的原始报告，保留首次实现的失败编码。
- `query/container-reference-once.json`：真实容器单次参考查询超时及数据库摘要。
- `query-validation.json`：真实容器 1 项与合成样例 14 项工程检查。
- `query-synthetic/public-check.json`、`timeout-check.json`：合成样例及三态超时报告。
