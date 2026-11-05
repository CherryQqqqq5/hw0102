# 独立确认实验复现

本轮使用30道此前未参与解题开发的任务，B0、C0、C1各重复三次，共270个位置。主要比较、选择规则、恢复额度及统计单位见[实验协议](../作业二/configs/confirmation-protocol-v1.md)。本文件中的命令从`shared/`执行；原384条评分及其复现方法见[共用说明](README.md)。

## 环境准备

沿用共用说明中的固定数据修订、Docker镜像、Aider六种语言环境、Terminal离线评分依赖和CodeBuddy登录方式。本轮使用Python 3.13、mini-SWE-agent 2.4.6、SWE-bench 5.0.2、Harbor 0.25.0、Pydantic 2.14.2。完整本机Python版本和镜像内容标识在运行计划及题单中。

```sh
export COURSE_MODEL_BACKEND=codebuddy
export COURSE_MODEL_ID=deepseek-v4.1-flash
export COURSE_CODEBUDDY_BIN="$(command -v codebuddy)"
export COURSE_PUBLIC_DEPS_ROOT="$PWD/work/vmshare/confirmation-public-deps"
export TMPDIR="$PWD/work/process-tmp"
mkdir -p "$TMPDIR" "$COURSE_PUBLIC_DEPS_ROOT/django-12193"
UV_CACHE_DIR="$PWD/work/uv-cache" uv pip install --target "$COURSE_PUBLIC_DEPS_ROOT/django-12193" \
  --python-version 3.6 --python-platform x86_64-manylinux2014 --only-binary :all: \
  'psycopg2-binary==2.8.6'
UV_CACHE_DIR="$PWD/work/uv-cache" uv pip install --target "$COURSE_PUBLIC_DEPS_ROOT/pytest-5631-py39" \
  --python-version 3.9 --python-platform x86_64-manylinux2014 --only-binary :all: \
  'numpy==1.23.5'
work/.venv/bin/python scripts/install-terminal-deps.py '../作业二/configs/confirmation-tasks-v1.json'
```

Django-12193和pytest-5631的依赖对所有条件只读挂载。polyglot-rust-c在原镜像中补充共用说明下载的Python 3.13.12独立运行时，三个条件执行同一准备程序，准备时间单列。任务容器保持离线，原题评分条件不变。正式运行一次只执行一个任务，生成与评分不重叠。

## 环境与公开检查控制

以下命令只执行初始产物和上游参考产物的工程控制，不调用模型。参考补丁及解法仅留在本机控制目录，不能进入正式任务容器的可读范围。

```sh
work/.venv/bin/python -m course_eval.confirmation_preflight \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --out work/vmshare/confirmation-preflights
work/.venv/bin/python -m course_eval.check_confirmation_public \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --out work/vmshare/confirmation-swe-public
work/.venv/bin/python -m course_eval.check_confirmation_terminal \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --out work/vmshare/confirmation-terminal-public
```

原题控制必须为初始产物未通过、上游参考通过。公开检查的输出保存具体约束、实测值、返回状态及覆盖范围。FEAL只检查可读整数载荷容量，漏洞利用只检查指定文件和格式，Bottle只检查报告格式及可见测试；这些任务的完整语义正确性由独立原题评分判断。

## 冻结与运行

已发布的`confirmation-plan-v1.json`保存本轮270个位置、运行顺序、代码与检查摘要。每个正式`trial.json`和可见模型事件记录`protocol_commit`，该提交在首个模型请求前产生。CodeBuddy没有可用的输出词元硬限选项，配置字段`max_output_tokens=4096`不表示服务实际采用该限制。

在原环境继续运行时，将`PROTOCOL_COMMIT`设置为正式记录中的提交号：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v1.json' \
  --plan '../作业二/configs/confirmation-plan-v1.json' \
  --published-repo .. --protocol-commit "$PROTOCOL_COMMIT" \
  --runs work/vmshare/confirmation-v1
```

更换机器或Python微版本时，应重新执行环境控制、生成新计划并在首次请求前提交该计划。新复跑须独立命名，不能改写已发布记录的模型标识、环境版本或代码摘要来通过验证。首次准备计划的命令为：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v1.json' \
  --preflights work/vmshare/confirmation-preflights --plan work/confirmation-plan-v1.json
```

程序跳过同一协议下已有完整评分的位置。正常失败仍是有效成绩。只有原评分缺失的机械故障可以在记录原因后使用`--recover <run_id> --recovery-reason <具体原因>`；原目录会保存在相邻的`confirmation-v1-attempts/`中，成本继续统计。每个位置最多两次额外恢复，总尝试上限300。

## 从发布证据复算

下列操作读取已脱敏的可见交互和原题评分，无需模型额度或Docker：

```sh
python3 -m course_eval.confirmation_summary \
  --runs '../作业二/evidence/confirmation-v1' \
  --plan '../作业二/configs/confirmation-plan-v1.json' \
  --out work/recomputed-confirmation
python3 -m course_eval.verify_scores --runs '../作业二/evidence/confirmation-v1'
```

统计要求全部270个位置取得原题评分，保留每道题三轮结构，按基准分层对任务进行10000次配对重采样。`all_attempt_usage`包含正式与机械失败尝试；`formal_attempt_usage`和`mechanical_attempt_usage`分别给出来源。费用字段为服务返回值，无法独立确认账号账单。

`controller.jsonl`、`candidates/`和`final-verification.json`分别记录干预、候选文件及证据、最终版本。候选文件使用Base64编码保存原始字节；导出前对解码后的内容进行敏感标记检查。可见模型交互保留请求、结构化动作、响应及词元统计，剔除服务内部账户元数据。工程控制不纳入正式成功率。
