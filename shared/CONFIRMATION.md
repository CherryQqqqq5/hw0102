# 免费模型独立确认与历史记录复算

当前正式评测仅使用CodeBuddy 2.179.3的hy4flash-free，实际身份与每个messageId的rawUsage.credit=0逐条核验；新增费用未知、非零或型号不符立即停止。当前源码与精确计划对应[免费v7协议](../作业二/configs/CONFIRMATION_HY4FLASH_PROTOCOL_V7.md)和[冻结计划](../作业二/configs/confirmation-plan-hy4flash-free-v7.json)，包含7条旧来源有效原评分及六次独立前序。复算已上传原评分及费用无需模型请求；正式新调用须遵循当前协议和授权。

以下创智命令和版本说明属于已停止的历史批次，仅用于解释其记录与原执行方式；当前没有创智调用授权。

本轮为30题×3条件×3轮，采用[创智v5协议](../作业二/configs/confirmation-protocol-boyue-v5.md)，270位置使用同一创智服务执行。v5修复科学计算公开探针的命令行与正常退出记录，以及Harbor外层时限与内部预算的竞争；首轮该题三条件整组替换，33条未受影响记录全部复用，237条新运行。原3次尝试保留和计费，详见[探针与时限修复](../作业二/configs/confirmation-probe-repair-v5.md)。原CodeBuddy v3因429停止，保存265评分、1次未评分和4个未启动位置；其成绩和费用单独保留。下列命令从`shared/`执行。

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
  --runs '../作业二/evidence/confirmation-boyue-v5' \
  --plan '../作业二/configs/confirmation-plan-boyue-v5.json' \
  --previous-runs '../作业二/evidence/confirmation-boyue-v5-previous' \
  --out work/recomputed-confirmation
python3 -m course_eval.verify_scores --runs '../作业二/evidence/confirmation-boyue-v5'
python3 -m course_eval.verify_scores --allow-unscored \
  --runs '../作业二/evidence/confirmation-boyue-v5-previous'
```

统计保留同题三轮结构，按基准分层、以任务为单位进行10000次配对自助重采样。创智主比较为33条原协议复用及237条新运行，`all_attempt_usage`包含归档机械恢复及3条前序。完整v4与v5存在33条来源复用，不能重复加总；合成接口准备另列。返回词元无法覆盖超时后未返回的用量，费用字段不等同于账单。

CodeBuddy旧成本读取`confirmation-v3/`、`confirmation-v1/`和`confirmation-v3-previous/`，共281次尝试、279评分。`confirmation-v2/`保留全部86条历史评分，`confirmation-v2-attempts/`保留中断尝试；两者与v3及previous存在复用，不能再次相加。旧v3未完成270位置，完整矩阵统计器会按规则拒绝计算主配对结论。

## 原运行续跑与全新复跑

创智原运行续跑核对既有位置的协议提交、模型及预算；已评分位置不再次执行。将PROTOCOL_COMMIT设置为v5新增正式记录中的提交号后执行：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v2.json' \
  --plan '../作业二/configs/confirmation-plan-boyue-v5.json' \
  --published-repo .. --published-plan '作业二/configs/confirmation-plan-boyue-v5.json' \
  --protocol-commit "$PROTOCOL_COMMIT" --runs work/vmshare/confirmation-boyue-v5
```

创智累计上限300次正式尝试，含270主位置、3次前序及最多27次额外机械恢复；v5队列上限297。内部600秒、24次决策保持；Terminal的Harbor外层630秒覆盖环境识别及日志收尾。正常失败保留。只有原评分缺失的机械故障可使用`--recover <run_id> --recovery-reason <具体原因>`，原件归档相邻的`confirmation-boyue-v5-attempts/`；每位置最多两次额外恢复。429额度耗尽不作超时重试。

全新复跑不复用旧采样，重新执行环境验收后生成无来源复用的新计划：

```sh
work/.venv/bin/python -m course_eval.confirmation \
  --manifest '../作业二/configs/confirmation-tasks-v1.json' \
  --checks '../作业二/configs/confirmation-public-checks-v2.json' \
  --preflights work/vmshare/confirmation-preflights --plan work/confirmation-fresh-plan.json
```

在首次模型请求前将新计划和代码提交，再使用对应发布路径运行；独立命名新结果。不要修改旧计划中的版本或摘要来适配新机器。创智实际传递32768输出词元上限和max推理设置；服务端采样种子和内部更新无法独立保证。

`controller.jsonl`、`candidates/`与`final-verification.json`记录干预、文件字节和最终版本证据。新接口完整保留请求、响应、`reasoning_content`、工具动作、结束原因及返回用量。候选导出前对解码内容进行敏感标记检查；工程控制不计入任务成功率。
