# 创智复测与历史记录复算

本轮为30题×3条件×3轮，采用[创智v4协议](../作业二/configs/confirmation-protocol-boyue-v4.md)，全部270位置使用同一新服务执行。原CodeBuddy v3在265条评分后因429额度耗尽停止，另有1次未评分和4个未启动位置；旧记录及前序尝试均保留，不复用为创智成绩。环境修复范围见[运行时记录](../作业二/configs/confirmation-runtime-repair-v3.md)。下列命令从`shared/`执行。

## 环境准备

数据修订、容器、语言工具和离线评分依赖见[共用说明](README.md)。本地使用Python 3.13.12、mini-SWE-agent 2.4.6、SWE-bench 5.0.2、Harbor 0.25.0、Pydantic 2.14.2。创智客户端在课程独立远端虚拟环境中运行，实际Python 3.10.6、OpenAI Software Development Kit（SDK，软件开发工具包）3.45.0、Pydantic 2.14.3、httpx2 2.14.0。模型`deepseek-v4-pro-0813`、`reasoning_effort=max`、每请求32768输出词元；完整版本与镜像标识在计划和题单中。

```sh
export COURSE_MODEL_BACKEND=course
export COURSE_MODEL_ID=deepseek-v4-pro-0813
export COURSE_RUN_LIMITS='{"model_calls":24,"wall_seconds":600,"command_seconds":60,"max_output_tokens":32768,"timeout_retries":2,"strict_wall":true}'
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

在已授权的远端工作目录建立独立虚拟环境，经HTTPS软件源安装`openai==3.45.0`，将`course_eval/boyue_rpc.py`复制到该目录。用可信配置设置`COURSE_REMOTE_HOST`、`COURSE_REMOTE_ROOT`和现有私有密钥文件路径`COURSE_REMOTE_KEY`，再设置：

```sh
export COURSE_BOYUE_RPC_COMMAND="ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes $COURSE_REMOTE_HOST $COURSE_REMOTE_ROOT/.venv/bin/python $COURSE_REMOTE_ROOT/boyue_rpc.py --credential-file $COURSE_REMOTE_KEY --output $COURSE_REMOTE_ROOT/requests"
work/.venv/bin/python -c 'from course_eval.boyue_transport import BoyueTransport; print(BoyueTransport().metadata())'
```

Secure Shell（SSH，安全外壳协议）入口只传送模型请求和响应，密钥留在远端私有文件，不能把密钥值写入配置或命令。软件开发工具包的自动重试和重定向均关闭；请求限时覆盖SSH等待。原始准备证据中保留六次连续工具调用、三条件完整入口及一次实际短期限超时，共18次请求、17响应。此为合成任务工程验证。

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
  --runs '../作业二/evidence/confirmation-boyue-v4' \
  --plan '../作业二/configs/confirmation-plan-boyue-v4.json' \
  --out work/recomputed-confirmation
python3 -m course_eval.verify_scores --runs '../作业二/evidence/confirmation-boyue-v4'
```

统计保留同题三轮结构，按基准分层、以任务为单位进行10000次配对自助重采样。创智主比较全部为新运行，`all_attempt_usage`包含其归档机械恢复，合成接口准备另列。返回词元无法覆盖超时后未返回的用量，费用字段不等同于账单。

CodeBuddy旧成本读取`confirmation-v3/`、`confirmation-v1/`和`confirmation-v3-previous/`，共281次尝试、279评分。`confirmation-v2/`保留全部86条历史评分，`confirmation-v2-attempts/`保留中断尝试；两者与v3及previous存在复用，不能再次相加。旧v3未完成270位置，完整矩阵统计器会按规则拒绝计算主配对结论。

## 原运行续跑与全新复跑

创智原运行续跑核对既有位置的协议提交、模型及预算；已评分位置不再次执行。将PROTOCOL_COMMIT设置为v4正式记录中的提交号后执行：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v1.json' \
  --plan '../作业二/configs/confirmation-plan-boyue-v4.json' \
  --published-repo .. --published-plan '作业二/configs/confirmation-plan-boyue-v4.json' \
  --protocol-commit "$PROTOCOL_COMMIT" --runs work/vmshare/confirmation-boyue-v4
```

创智批次上限300次正式尝试，含270主位置及最多30次机械恢复；正常失败保留。只有原评分缺失的机械故障可使用`--recover <run_id> --recovery-reason <具体原因>`，原件归档相邻的`confirmation-boyue-v4-attempts/`；每位置最多两次额外恢复。429额度耗尽不作超时重试。

全新复跑不复用旧采样，重新执行环境验收后生成无来源复用的新计划：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v1.json' \
  --preflights work/vmshare/confirmation-preflights --plan work/confirmation-fresh-plan.json
```

在首次模型请求前将新计划和代码提交，再使用对应发布路径运行；独立命名新结果。不要修改旧计划中的版本或摘要来适配新机器。创智实际传递32768输出词元上限和max推理设置；服务端采样种子和内部更新无法独立保证。

`controller.jsonl`、`candidates/`与`final-verification.json`记录干预、文件字节和最终版本证据。新接口完整保留请求、响应、`reasoning_content`、工具动作、结束原因及返回用量。候选导出前对解码内容进行敏感标记检查；工程控制不计入任务成功率。
