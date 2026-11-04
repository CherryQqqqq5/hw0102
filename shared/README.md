# 共用评测代码与复现

[冻结清单](frozen-tasks.json)记录 30 道诊断题和 15 道留出题，三套基准各占 10 道和 5 道。[候选范围](candidate-tasks.json)、[题目排除依据](preflight-exclusions.json)和[仓库排除依据](preflight-exclude-strata.json)记录筛选过程。清单中的 `preflight_paths` 从本目录解析，指向[作业一的评分对照](../作业一/evidence/preflights/)。

## 准备数据和依赖

在 `shared/` 执行下列命令。原始 SWE-bench 评分数据和 Terminal-Bench 验收文件用于独立评分，评测程序只向模型传递题面、可见代码与工具结果。

```sh
mkdir -p work/datasets work/parquet work/process-tmp work/vmshare/aider work/terminal-runtime/deps
uv venv --python 3.13 work/.venv
UV_CACHE_DIR="$PWD/work/uv-cache" TMPDIR="$PWD/work/process-tmp" \
  uv pip install --python work/.venv/bin/python \
  'mini-swe-agent==2.4.6' 'swebench==5.0.2' 'harbor==0.25.0' 'docker==7.1.0'

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
export COURSE_RUN_LIMITS='{"model_calls":24,"wall_seconds":600}'
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
