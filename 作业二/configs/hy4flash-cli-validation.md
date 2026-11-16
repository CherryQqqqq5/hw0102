# Hy4 flash 命令行免费调用检查

2026-11-16，项目现有CodeBuddy 2.179.3已实际通过Hy4 flash免费调用及两种课程结构化动作接口，三次请求均由服务返回零积分。无需升级客户端。

正确路由为`hy4flash-free`，服务实际模型为`hy4-flash-free`，目录倍率为`x0.00 credits`。输入“Reply with exactly OK.”后实际输出OK，输入3115、输出49 tokens，`providerData.rawUsage.credit=0`。同型号的`hy4flash`是收费路由，不能用作备用模型。

普通命令与控制动作两个真实请求均通过现有课程适配器，实际生成`printf ready`命令及`submit`结构化动作；均未执行基准工具，累计输入6995、输出390 tokens，两次积分均为0。正式批次前的本地回放还验证了收费响应、缺失证明、同序列其他回复缺少证明及费用未知超时的停止规则。

首次网络检查遇到证书链错误，命令行因此返回过时模型目录。当前进程设置`NODE_OPTIONS=--use-bundled-ca`后，保留TLS校验并取得16个当前模型，包含正确免费路由。旧`hy4free`现已作为收费`hy4std`的别名；一次基于过时目录的误调用返回了`rawUsage.credit=0.55`，已单独保留，不能计作免费成功。该响应顶层`total_cost_usd=0`，证明这一顶层字段不能用于判断实际积分。

证据：

- `work/codebuddy-quota-probe/cloud-model-metadata-before-ca.json`：网络修复前的过时目录。
- `work/codebuddy-quota-probe/cloud-model-metadata.json`：修复后当前目录。
- `work/codebuddy-quota-probe/hy4free-smoke-bundledca.stdout.json`：0.55积分误调用原件。
- `work/codebuddy-quota-probe/hy4flash-free-smoke-exactroute-verified.json`：正确免费路由最小调用。
- `work/vmshare/hy4flash-interface-v1/result.json`：两种真实零积分结构化接口。
- `work/check_hy4flash_billing.py`：真实响应回放及本地实际进程超时回归。
- `work/check_codebuddy_free_models.py`：可重复的只读查询入口。

免费适配器在返回任何基准动作前，验证每个模型回复的请求型号、实际型号及独立零积分证明。免费路线遇到请求超时立即停止，禁止费用未知时自动重试；子进程直接固定免费模型、关闭重试开关并移除备用模型变量。免费额度耗尽、型号变化或计费证据异常均停止调度。当前没有账号总额度或活动每日上限的直接证明。
