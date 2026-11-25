# 共用评测代码与复现

截至2026年11月25日，新75题比较仍在执行。原批次代码见[Hy4 v18源码快照](runtime-snapshots/hy4-v18/README.md)与[NVIDIA v31源码快照](runtime-snapshots/nvidia-v31/README.md)，新增[ReLU专用v20源码与真实验证](runtime-snapshots/hy4-v20/README.md)。此前的[NVIDIA v30源码快照](runtime-snapshots/nvidia-v30/README.md)继续对应其实际记录；每份快照以逐文件摘要对应实际运行版本。[当前164份真实评分证据](../作业二/evidence/performance75-current-20261125.md)包含通过和未通过记录，属于部分完成快照。正式报告和完整证据包按完成后的原评分及独立审查更新，源码同步本身不表示75题已全部完成。

本轮使用的[CodeBuddy 2.179.3实际客户端补丁](client-patches/codebuddy-2.179.3-free-safety-v8/README.md)提供原始文件、补丁后客户端及补丁本身的准确摘要，与评测计划的 `client_sha256` 对应。旧客户端补丁继续用于核查各自历史记录；复现本轮接入时应使用此处对应版本。同步这些依赖未新增模型请求。

历史免费复测v16已完成270/270，207通过、63失败；B0/C0/C1为68/90、71/90、68/90，完整统计未支持程序控制稳定提升。新增109实际响应、119原生用量均零费用，旧13笔真实未知及1笔原生费用已知零的本地元数据拒绝分列保留。150秒请求准入修复经过真实任务验证，该批600秒执行预算与计费校验保持。[该批完整结果](../作业二/evidence/hy4flash-v16-results-20261118.md) · [原评分、费用与配对统计复算](CONFIRMATION.md)

新增30道独立题目的B0/C0/C1确认实验使用单独的[冻结协议与复现入口](CONFIRMATION.md)。下文保留原45题实验的参数与复算方法。

[冻结清单](frozen-tasks.json)记录 30 道诊断题和 15 道留出题，三套基准各占 10 道和 5 道。[候选范围](candidate-tasks.json)、[题目排除依据](preflight-exclusions.json)和[仓库排除依据](preflight-exclude-strata.json)记录筛选过程。清单中的 `preflight_paths` 从本目录解析，指向[作业一的评分对照](../作业一/evidence/preflights/)。

## 准备数据和依赖

只复算已发布记录时，在`shared/`建立以下独立环境即可，不需要模型登录、容器或原评分依赖。`requirements-analysis.txt`固定已验证的直接及间接依赖版本，后续只读命令均使用该环境的解释器。

```sh
mkdir -p work/process-tmp
TMPDIR="$PWD/work/process-tmp" python3.13 -m venv work/.venv
TMPDIR="$PWD/work/process-tmp" work/.venv/bin/python -m pip install \
  --index-url https://pypi.org/simple --cache-dir work/pip-cache -r requirements-analysis.txt
```

若已备齐与本机Python版本及平台匹配的标准wheel安装包，可将安装命令改为`work/.venv/bin/python -m pip install --no-index --find-links work/wheels -r requirements-analysis.txt`。本次独立环境使用71个核对PyPI发布方摘要的发行包，以及11个通过标准`wheel pack`从已保存发行内容重建的安装包，统一离线安装。普通包索引访问和部分完整下载曾超时，未记为安装通过。实际环境、安装方式与复算验收见作业二的`control-clean-environment-validation-20261118.json`。

在 `shared/` 执行下列命令。原始 SWE-bench 评分数据和 Terminal-Bench 验收文件用于独立评分，评测程序只向模型传递题面、可见代码与工具结果。

```sh
mkdir -p work/datasets work/parquet work/process-tmp work/vmshare/aider work/terminal-runtime/deps
uv venv --python 3.13 work/.venv
UV_CACHE_DIR="$PWD/work/uv-cache" TMPDIR="$PWD/work/process-tmp" \
  uv pip install --python work/.venv/bin/python \
  'mini-swe-agent==2.4.6' 'swebench==5.0.2' 'harbor==0.25.0' 'docker==7.1.0' 'jsonschema==4.26.0'

curl -fL -o work/datasets/swe-verified.parquet \
  https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/resolve/78f471bf655a3137b2e8a75af1501690ec009ec3/data/test-00000-of-00001.parquet
curl -fL -o work/datasets/terminal.tar.gz \
  https://codeload.github.com/harbor-framework/terminal-bench-2-1/tar.gz/7131e4375048a0e408a8fb404b5f499d726b695b
curl -fL -o work/datasets/aider.tar.gz \
  https://codeload.github.com/Aider-AI/polyglot-benchmark/tar.gz/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f
tar -xzf work/datasets/terminal.tar.gz -C work/datasets
tar -xzf work/datasets/aider.tar.gz -C work/datasets
npm install --registry=https://registry.npmjs.org --prefix work/parquet --ignore-scripts \
  hyparquet@1.32.0 hyparquet-compressors@1.1.3
node course_eval/swe_rows.mjs "$PWD/work/parquet/package.json" \
  work/datasets/swe-verified.parquet inventory > work/datasets/swe-inventory.json
node course_eval/swe_rows.mjs "$PWD/work/parquet/package.json" \
  work/datasets/swe-verified.parquet grader > work/datasets/swe-grader.json
```

## 配置评分环境

原实验使用 Lima 2.2.1 和 Docker 29.9.3，虚拟机配置为 4 个虚拟中央处理器、5 GiB 内存和 80 GiB 磁盘。SWE-bench 和 Terminal-Bench 镜像为 `linux/amd64`，Aider 的运行配置使用 `linux/arm64`。Docker 通过显式 Unix 套接字连接，`DOCKER_HOST` 需指向当前机器的套接字。`work/vmshare` 需能被虚拟机和 Harbor 访问。

```sh
export PYTHONPATH="$PWD"
export COURSE_DOCKER_BIN="$(command -v docker)"
export COURSE_HARBOR_BIN="$PWD/work/.venv/bin/harbor"
export COURSE_TERMINAL_DEPS="$PWD/work/terminal-runtime/deps"
export COURSE_TERMINAL_PYTHON="$PWD/work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz"
export COURSE_TERMINAL_PYTHON_312="$PWD/work/terminal-runtime/python-3.12.13-linux-x86_64.tar.gz"

jq -r '.selected[] | .image // empty' frozen-tasks.json | sort -u | xargs -n 1 docker pull --platform linux/amd64
cp scripts/aider/* course_eval/aider.Dockerfile course_eval/JavaEnvironmentCheck.java work/vmshare/aider/
UV_CACHE_DIR="$PWD/work/uv-cache" uv pip install --target work/vmshare/aider/python-test-packages 'pytest==8.4.1'
for language in python go rust cpp javascript java; do
  docker build --platform linux/arm64 --target "$language" -t "nju-course-aider:$language" \
    -f work/vmshare/aider/aider.Dockerfile work/vmshare/aider
done

curl -fL -o "$COURSE_TERMINAL_PYTHON" \
  'https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.13.12%2B20260325-x86_64-unknown-linux-gnu-install_only.tar.gz'
curl -fL -o "$COURSE_TERMINAL_PYTHON_312" \
  'https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.12.13%2B20260325-x86_64-unknown-linux-gnu-install_only.tar.gz'
mkdir -p work/vmshare/terminal-dep-builder
cp scripts/install-mailman.sh "$COURSE_TERMINAL_PYTHON_312" work/vmshare/terminal-dep-builder/
docker run --rm --platform linux/amd64 --memory 1536m --cpus 1 --pids-limit 256 \
  --security-opt no-new-privileges -v "$PWD/work/vmshare/terminal-dep-builder:/benchmark-setup" \
  --entrypoint /bin/bash alexgshaw/mailman:20251031 /benchmark-setup/install-mailman.sh
cp work/vmshare/terminal-dep-builder/mailman-deps.tar.gz \
  "$COURSE_TERMINAL_DEPS/python3.12+mailman==3.3.8+pytest-json-ctrf==0.3.5+pytest==8.4.1.tar.gz"
work/.venv/bin/python scripts/install-terminal-deps.py frozen-tasks.json
```

智能体容器关闭外部网络。Terminal-Bench 的评分依赖在宿主机准备，保留原题测试文件、测试参数与奖励条件。SWE-bench 容器以空的只读挂载屏蔽软件包缓存，以免智能体读取较新版本的源码。

## 查看排程或运行基线

`--list` 只输出运行编号。作业一、二对应的 `diagnose`、`compare` 和 `holdout` 分别有 30、30 和 180 个运行位置。

```sh
work/.venv/bin/python -m course_eval.matrix --manifest frozen-tasks.json \
  --sources work/datasets --runs work/vmshare/formal --phase diagnose --list
```

正式基线使用 CodeBuddy 2.179.3。通过命令行登录后设置以下变量，从空运行目录开始复跑。每题最多 24 次模型请求，智能体在相邻请求之间检查 600 秒交互时限。

```sh
export COURSE_MODEL_BACKEND=codebuddy
export COURSE_MODEL_ID=deepseek-v4.1-flash
export COURSE_CODEBUDDY_BIN="$(command -v codebuddy)"
export COURSE_RUN_LIMITS='{"model_calls":24,"wall_seconds":600,"timeout_retries":0}'
work/.venv/bin/python -m course_eval.matrix --manifest frozen-tasks.json \
  --sources work/datasets --runs work/vmshare/formal --phase diagnose --workers 2
work/.venv/bin/python -m course_eval.summarize --manifest frozen-tasks.json \
  --runs work/vmshare/formal --out work/formal-summary
```

在原始运行工作区续跑时，程序会跳过同一模型已取得有效评分的位置。重试前应将未评分的原尝试另行归档。`compare` 和 `holdout` 使用[冻结的公开检查清单](../作业二/configs/public-checks.json)。每项包括 `check_id`、`source_quote`、`command` 和 `dependencies`，存在明确指定交付路径时可附加 `deliverables`。Aider 的公开检查来自题目可见的原测试套件。

```sh
work/.venv/bin/python -m course_eval.matrix --manifest frozen-tasks.json \
  --sources work/datasets --runs work/vmshare/formal --phase compare --workers 3 \
  --checks '../作业二/configs/public-checks.json'
work/.venv/bin/python -m course_eval.matrix --manifest frozen-tasks.json \
  --sources work/datasets --runs work/vmshare/formal --phase holdout --workers 3 \
  --checks '../作业二/configs/public-checks.json'
```

`--task` 可重复传入以重跑指定题目，`--repeat` 可选定留出集的某一轮。模型请求超时仍会由原题验收程序检查现有产物，汇总中的 `provider_timeouts` 和配对敏感性统计单列此类运行。

首次运行的重试额度为 0。追加阶段新派发的运行将 `timeout_retries` 显式设为 2，仅在模型请求超时时重发同一请求，每题合计最多两个额外尝试。缺失 `timeout_retries` 字段统一表示 0，执行程序和统计程序采用相同约定。复跑单题时使用该题 `trial.json` 中的 `limits`，不套用当前环境的另一组额度。原 240 份配置应恢复为 109 份零重试、131 份两次重试。逐题表中 `model_calls` 是实际发送次数，`model_request_timeouts` 与 `model_request_retries` 分别计数。超时尝试可能没有服务报告的词元用量。

| 原实验集合与配置 | 零重试 | 两次重试 |
|---|---:|---:|
| D/B0 | 30 | 0 |
| D/F | 29 | 1 |
| H/B0 | 12 | 33 |
| H/BP | 12 | 33 |
| H/A | 13 | 32 |
| H/F | 13 | 32 |

H 的 A/F 45 对额度均匹配。其余比较各有一对额度不同：D/B0–F 的 `rust/doubly-linked-list`、H/B0–F 首轮的 `scikit-learn__scikit-learn-10908`、H/BP–F 第二轮的 `tune-mjcf`。这三对双方均通过，只有 Rust 的 F 实际使用了一次重试。

## 抽样范围与公开检查

候选清单包含 SWE-bench 的 500 题、Terminal-Bench 的 89 题和 Aider 的 225 题。元数据及环境预检排除后，清单中未标记排除的候选分别为 447、53、222 题。正式抽样使用固定顺序、分层覆盖及任务组去重，分数来自被选中的 45 题。

- SWE-bench 只保留 `<15 min fix`、`15 min - 1 hour` 两个修复时间标签，并要求官方镜像与 `pass_and_fail` 评分。Requests 仓库因参考补丁也出现证书相关回归而被排除。正式样本来自 Django、xarray、scikit-learn、pytest 四个仓库，偏向较短修复任务。
- Terminal-Bench 限制为无图形处理器、每题不超过 2 个中央处理器核心和 3072 MB 内存、有预构建镜像、单容器、可离线评分。需运行时下载数据或模型、多容器、依赖无法离线准备、原参考解未通过评分的任务不纳入。
- Aider 覆盖 C++、Go、Java、JavaScript、Python、Rust 六种语言。排除缺原始文件、不支持的语言、参考解离线编译失败及原始空白实现已经通过的题。D 各语言数量为 2、2、1、2、2、1；H 为前五种语言各一题。

公开检查在正式 F/H 运行前固定。编制者为辅助实验开发的 Codex：依据公开题面、初始仓库可见测试和构建文件，逐题选定命令及依赖；脚本验证题面引用和路径后输出 JavaScript Object Notation（JSON，JavaScript 对象表示法）清单。SWE-bench 使用相关的既有公开回归测试，Terminal 使用交付路径和可执行/格式检查，Aider 使用原题可见测试。规则没有根据隐藏评分答案补入目标输出。该过程包含任务级人工指定式的规则设计，并非通用自动生成检查器；用户提供执行目标与审查意见，逐项测试及运行由程序完成。检查清单覆盖有限，语法或存在性通过不能保证任务语义正确。

检查生成脚本保留逐题命令与依赖选择，可从相同原始材料重建清单。

```sh
work/.venv/bin/python scripts/build-public-checks.py --sources work/datasets \
  --manifest frozen-tasks.json --out work/rebuilt-public-checks.json
cmp work/rebuilt-public-checks.json '../作业二/configs/public-checks.json'
```

Harbor 的命令时限回归可独立复跑。普通和嵌套超时都应返回 124，后续命令检查超时的子进程未继续写文件。

```sh
work/.venv/bin/python -m scripts.harbor_timeout_probe --manifest frozen-tasks.json \
  --out work/vmshare/terminal-nested-timeout-regression
```

```sh
work/.venv/bin/python -m course_eval.check_verification \
  --sources work/datasets --out work/vmshare/verification-proverb
```

该命令验证检查记录的时效和提交处理，使用真实 Aider 容器，无需模型请求。[作业二工程证据](../作业二/evidence/)

仅从仓库复算作业一逐题成绩与用量时，使用已上传的脱敏记录，无需登录模型服务或启动容器。

```sh
python3 -m course_eval.summarize --manifest frozen-tasks.json \
  --runs '../作业一/evidence/formal' --out work/recomputed-hw1
```

复算作业二时，在本地工作目录汇合两份作业的正式运行，包含作业一的 B0 轨迹。下列软链接仅用于本地统计。

```sh
mkdir -p work/combined-formal
for trial in "$PWD"/../作业{一,二}/evidence/formal/*/trial.json; do
  run=${trial%/trial.json}
  ln -s "$run" "work/combined-formal/${run##*/}"
done
python3 -m course_eval.summarize --manifest frozen-tasks.json \
  --runs work/combined-formal --out work/recomputed-hw2
```

原 240 份重试配置、三对不匹配位置和超时敏感性删除范围可独立检查。

```sh
work/.venv/bin/python -m course_eval.audit_repro --runs work/combined-formal \
  --out work/reproduction-audit.json
```

## 新配置与重复确认

R 与 RP 使用相同的公开检查、阶段性提示、预算反馈、依赖时效和提交控制。R 额外在第八个模型命令或过半交互时限后的首个命令结束时检查一次，并在提交时自动执行尚未通过或过期的公开检查。检查由程序真实执行，避免依赖模型精确复述命令。所有同步检查时间计入原来的软时限及总耗时。`tool_calls` 表示模型选择的命令数，`automatic_checks` 表示程序自动执行的公开检查数；依赖快照等内部操作不计入这两个字段。

A 重复确认使用原 H 的全部十五题、每配置三次。其任务已参与配置选择，结果只用于已见任务的重复确认。B0/A 共90次，全部显式两次超时重试。

```sh
export COURSE_RUN_LIMITS='{"model_calls":24,"wall_seconds":600,"timeout_retries":2}'
work/.venv/bin/python -m course_eval.revision --manifest frozen-tasks.json \
  --sources work/datasets --checks '../作业二/configs/public-checks.json' \
  --runs work/vmshare/revision-confirm-A-v1 --split H --arms B0 A --repeats 3 --workers 2
work/.venv/bin/python -m course_eval.revision_summary --runs work/vmshare/revision-confirm-A-v1 \
  --out work/revision-confirm-A-summary --reference B0 --treatment A
```

R 的开发比较选取六道既有诊断题：地址提取、查询优化、视频处理、批处理调度、pytest-7205 和 xarray-6599。该批次只有新 R，旧 B0/F 作为开发参考；其 `summary.json` 没有同期配对。开发结果按原题评分净增加一道通过后，执行后续三臂比较。十五题按 D 中各基准的 `order("revision/" + task_id)` 排序取前五题，使用相同预算，任务清单独立保存，原题评分保持不变。

```sh
work/.venv/bin/python -m course_eval.revision --manifest frozen-tasks.json \
  --sources work/datasets --checks '../作业二/configs/public-checks.json' \
  --runs work/vmshare/revision-matched-R-v1 --selection '../作业二/configs/revision-matched-tasks.json' \
  --split D --arms B0 RP R --workers 2
work/.venv/bin/python -m course_eval.revision_summary --runs work/vmshare/revision-matched-R-v1 \
  --out work/revision-R-vs-B0 --reference B0 --treatment R
work/.venv/bin/python -m course_eval.revision_summary --runs work/vmshare/revision-matched-R-v1 \
  --out work/revision-R-vs-RP --reference RP --treatment R
work/.venv/bin/python -m course_eval.revision_summary --runs work/vmshare/revision-matched-R-v1 \
  --out work/revision-RP-vs-B0 --reference B0 --treatment RP
```

工程回归不消耗模型请求，在真实 Aider 容器中检查旧配置恢复和自动验证的0/1/0退出码。

```sh
work/.venv/bin/python -m course_eval.check_revision --runs work/combined-formal \
  --sources work/datasets --out work/vmshare/revision-engineering
```

新增记录独立放在各批次目录，批次内的 `run-plan.json` 固定完整位置。用 `revision_summary` 对仓库中的相应批次目录复算，无需访问模型或容器。开发记录、选择配置后的确认和原始留出实验分别统计，不合并为一个独立未见样本分母。

## JSON Lines 检查修复与成组恢复

首版三臂实验的原题成绩有效，完整保存在 `revision-matched-R-v1/`。日志复核发现调度镜像的 Python 3.13.7 对合法文件执行 `python3 -m json.tool --json-lines <file>` 时返回 `I/O operation on closed file`。独立真实容器回归用合成合法记录和非法记录验证了修复，见[回归证据](../作业二/evidence/jsonlines-engineering-v2/)。该回归没有模型调用，不计入正式题目数量。

修复使用标准库 `json.loads` 逐行解析；[第二版检查清单](../作业二/configs/public-checks-v2.json)仅改变调度题的命令，其余44项与首版相同。生成脚本默认重建历史首版，添加以下开关重建第二版。

```sh
work/.venv/bin/python scripts/build-public-checks.py --sources work/datasets \
  --manifest frozen-tasks.json --out work/public-checks-v2.json --repair-json-lines
cmp work/public-checks-v2.json '../作业二/configs/public-checks-v2.json'
work/.venv/bin/python -m course_eval.check_jsonlines --out work/vmshare/jsonlines-engineering
```

恢复在读取新结果之前固定为调度题 B0、RP、R 三配置成组运行，消耗预留机械恢复额度3次。新增有效评分记录为144条，另两条未评分网络失败见下文。模型、预算、Agent实现和原题评分不变。修订后的十五题统计统一用新三条替换旧三条，其他14题复用检查命令未变化的原记录；原45次结果完整单列。没有按新旧得分挑选版本。

```sh
work/.venv/bin/python -m course_eval.revision --manifest frozen-tasks.json \
  --sources work/datasets --checks '../作业二/configs/public-checks-v2.json' \
  --runs work/vmshare/revision-jsonlines-recovery-v2 --split D \
  --task llm-inference-batching-scheduler --arms B0 RP R --workers 2
work/.venv/bin/python -m course_eval.revision_summary \
  --runs '../作业二/evidence/revision-matched-R-v1' \
  --replace-runs '../作业二/evidence/revision-jsonlines-recovery-v2' \
  --out work/recomputed-matched-v2 --reference B0 --treatment RP
```

本次旧批45条完整，`--replace-runs` 要求新记录与受影响任务的全部旧运行编号严格一致、全部已评分，且后端、模型与预算一致；否则终止统计。将 `--reference/--treatment` 换成 `B0/R` 或 `RP/R` 可复算另外两组比较。修订表的 `source_batch` 与 `run_id` 共同定位真实记录，[修订汇总](../作业二/evidence/revision-matched-R-v2/)只保存统计，不重复复制原始轨迹。确认和检查恢复队列重叠时各使用两路；检查恢复结束后，最后一批确认使用四路。全局最多四个任务。

RP 的主要正向结果是在读取首轮三臂评分后选定的探索分析。修订比较沿用十四题，不是该选择的独立确认。调度题补跑包含新的模型采样和不同的请求超时情况，不能把新旧成绩差单独归因为解析命令修复。

以下命令逐条核对保存的原题评分与汇总成绩，并检查新增批次是否覆盖完整计划；它读取评分证据，不重新执行模型或评分器。

```sh
python3 -m course_eval.verify_scores --runs work/combined-formal \
  '../作业二/evidence/revision-pilot-v1' \
  '../作业二/evidence/revision-confirm-A-v1' \
  '../作业二/evidence/revision-matched-R-v1' \
  '../作业二/evidence/revision-jsonlines-recovery-v2'
```

累计新增用量包含开发6次、确认90次、首轮三臂45次和检查恢复3次，共144条已评分运行。另有确认第三轮 tune-mjcf 的 A/B0 因同一时段的服务域名解析失败而未评分，归档后按相同条件补跑。因此总计146次尝试，保留被替换的旧三条及两条网络失败成本；修订比较表只包含选入比较的45条。下列命令从可见模型日志复算累计请求、响应、词元、超时和自动检查次数。

```sh
python3 -m course_eval.revision_usage --runs \
  '../作业二/evidence/revision-pilot-v1' \
  '../作业二/evidence/revision-confirm-A-v1' \
  '../作业二/evidence/revision-matched-R-v1' \
  '../作业二/evidence/revision-jsonlines-recovery-v2' \
  '../作业二/evidence/revision-confirm-provider-recovery-v1' \
  --out work/recomputed-revision-usage.json
cmp work/recomputed-revision-usage.json '../作业二/evidence/revision-usage.json'
```
