# 分批确认实验复现

本轮为30题×3条件×3轮，共270个主要位置。当前采用[v3协议](../作业二/configs/confirmation-protocol-v3.md)，80条完整非JavaScript记录来自v2，其余190条按修复后的环境执行。全部旧失败与被替换记录保留，详见[运行时修复范围](../作业二/configs/confirmation-runtime-repair-v3.md)。下列命令从`shared/`执行。

## 环境准备

数据修订、容器、语言工具、离线评分依赖和CodeBuddy登录方式见[共用说明](README.md)。本轮使用Python 3.13.12、mini-SWE-agent 2.4.6、SWE-bench 5.0.2、Harbor 0.25.0、Pydantic 2.14.2及CodeBuddy 2.179.3，模型为deepseek-v4.1-flash。完整环境版本与镜像标识在计划和题单中。

```sh
export COURSE_MODEL_BACKEND=codebuddy
export COURSE_MODEL_ID=deepseek-v4.1-flash
export COURSE_CODEBUDDY_BIN="$(command -v codebuddy)"
export COURSE_PUBLIC_DEPS_ROOT="$PWD/work/vmshare/confirmation-public-deps"
export COURSE_AIDER_PUBLIC_PYTHON="$PWD/work/terminal-runtime/python-3.13.12-linux-aarch64.tar.gz"
export TMPDIR="$PWD/work/process-tmp"
mkdir -p "$TMPDIR" "$COURSE_PUBLIC_DEPS_ROOT/django-12193" work/terminal-runtime
UV_CACHE_DIR="$PWD/work/uv-cache" uv pip install --target "$COURSE_PUBLIC_DEPS_ROOT/django-12193" \
  --python-version 3.6 --python-platform x86_64-manylinux2014 --only-binary :all: 'psycopg2-binary==2.8.6'
UV_CACHE_DIR="$PWD/work/uv-cache" uv pip install --target "$COURSE_PUBLIC_DEPS_ROOT/pytest-5631-py39" \
  --python-version 3.9 --python-platform x86_64-manylinux2014 --only-binary :all: 'numpy==1.23.5'
curl -fL -o "$COURSE_AIDER_PUBLIC_PYTHON" \
  'https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.13.12%2B20260325-aarch64-unknown-linux-gnu-install_only.tar.gz'
work/.venv/bin/python scripts/install-terminal-deps.py '../作业二/configs/confirmation-tasks-v1.json'
```

JavaScript运行时采用[固定上游发布](https://github.com/astral-sh/python-build-standalone/releases/tag/20260325)，程序校验下载摘要。三个条件均在执行预算前提供该运行时，并执行原npm脚本以启用xtest和建立依赖链接，再捕获受保护测试。准备耗时单列；原评分器不变。Django与pytest公开依赖对三个条件只读挂载；Terminal的polyglot-rust-c统一使用共用说明中的x86 Python运行时。生成和评分逐项顺序执行。

## 无模型环境验收

```sh
work/.venv/bin/python -m course_eval.confirmation_preflight \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' --out work/vmshare/confirmation-preflights
work/.venv/bin/python -m course_eval.check_confirmation_public \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' --out work/vmshare/confirmation-swe-public
work/.venv/bin/python -m course_eval.check_confirmation_terminal \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' --out work/vmshare/confirmation-terminal-public
work/.venv/bin/python -m course_eval.check_aider_runtime \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' --out work/vmshare/aider-runtime-recheck
```

原评分控制为初始失败、上游参考通过。上游参考只用于工程控制，不进入模型提示或正式任务可读范围。FEAL仅验证整数载荷容量，漏洞利用仅验证文件及格式，Bottle仅验证报告格式和可见测试；完整正确性继续由原评分判断。

## 已发布记录复算

以下操作只读取可见交互和原评分，无需模型或Docker。主要统计必须等待全部270位置取得有效评分。

```sh
python3 -m course_eval.confirmation_summary \
  --runs '../作业二/evidence/confirmation-v3' \
  --plan '../作业二/configs/confirmation-plan-v3.json' \
  --previous-runs '../作业二/evidence/confirmation-v1' '../作业二/evidence/confirmation-v3-previous' \
  --out work/recomputed-confirmation
python3 -m course_eval.verify_scores --runs '../作业二/evidence/confirmation-v3'
```

统计保留同题三轮结构，按基准分层、以任务为单位进行10000次配对自助重采样。逐题表的source_batch与protocol_commit定位实际来源。主目录包含80条v2复用，不得再将整个v2目录加入累计用量。主比较外为v1的8次，加previous目录中的6条整组替换记录和1条未评分中断记录，共15次。`all_attempt_usage`包含这些尝试；返回词元无法覆盖超时后未返回的用量，费用字段不等同于账单。

`confirmation-v2/`保留全部86条历史评分，`confirmation-v2-attempts/`保留中断尝试。它们与主目录、previous目录之间存在明确复用关系，目录数不能直接相加为独立运行数。

## 原运行续跑与全新复跑

原运行续跑必须先将计划中声明的80条旧记录放在运行目录相同位置。调度器核对原提交和预算，缺少声明复用记录时立即失败；不能用新采样伪装旧记录。将PROTOCOL_COMMIT设置为v3正式记录中的提交号后执行：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v1.json' \
  --plan '../作业二/configs/confirmation-plan-v3.json' \
  --published-repo .. --published-plan '作业二/configs/confirmation-plan-v3.json' \
  --protocol-commit "$PROTOCOL_COMMIT" --runs work/vmshare/confirmation-v3
```

v3新队列计数上限285（包含80条复用），加主比较外15次，累计上限仍为300。正常失败保留。只有原评分缺失的机械故障可使用`--recover <run_id> --recovery-reason <具体原因>`，原件归档相邻的`confirmation-v3-attempts/`；每位置最多两次额外恢复。

全新复跑不复用旧采样，重新执行环境验收后生成无来源复用的新计划：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v1.json' \
  --preflights work/vmshare/confirmation-preflights --plan work/confirmation-fresh-plan.json
```

在首次模型请求前将新计划和代码提交，再使用对应发布路径运行；独立命名新结果。不要修改旧计划中的版本或摘要来适配新机器。CodeBuddy没有实际采用通用字段max_output_tokens=4096，采样种子、内部推理预算及模型别名更新也无法固定。

`controller.jsonl`、`candidates/`与`final-verification.json`记录干预、文件字节和最终版本证据。可见模型交互保留请求、动作、响应和返回用量，服务内部账户元数据剔除。候选导出前对解码内容进行敏感标记检查；工程控制不计入任务成功率。
