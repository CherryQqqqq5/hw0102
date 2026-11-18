# 控制接口修复与同协议记录分析

日期：2026年11月18日。历史270条评分保持207通过、63失败，旧13笔未知费用保留。本轮只执行归档记录复算和本地工程检查，新增模型请求、原评分器执行及模型费用均为0。

## 实现与成绩的版本关系

历史运行由`frozen-runtime/v16/course_eval/`及冻结计划逐位置的`source_protocol_commit`定位。当前`shared/course_eval/controller.py`含动作Schema与自动反馈修复，版本以本次Git提交记录；原冻结目录和保存评分不更新。`agent.py`、`codebuddy_free.py`、`candidate_io.py`与v16冻结文件逐字节相同，4096保护、实际身份与逐条费用校验保持。

当前控制器SHA-256为`9a8a1a28d14228fc339887e0e056e1e58175c0cffe323e5856a3c7c55ce863ef`。独立环境中完成原计划15份冻结文件的摘要核对，原始270条仍由对应旧版本解释。

## 动作定义

原ControlAction的Pydantic运行时校验包含操作与字段的关联规则，默认生成的JSON Schema未包含该规则。Pydantic官方支持通过`__get_pydantic_json_schema__`定制发送约束；本次由同一`required_fields`定义生成五种操作分支，保留原本地接受规则。[官方用法](https://docs.pydantic.dev/latest/concepts/json_schema/#implementing-__get_pydantic_json_schema__)

| 操作 | 必需参数 | 其余动作参数 | 返回或结束 |
|---|---|---|---|
| bash | 非空command，最多65536字符 | check_id、candidate_id仅缺省或null | 命令观察；成功输出提交标记时结束 |
| verify | 非空check_id | command、candidate_id仅缺省或null | 实际检查报告 |
| save | 无 | command、check_id、candidate_id仅缺省或null | 保存候选信息 |
| restore | 非空candidate_id | command、check_id仅缺省或null | 恢复信息；未知编号返回明确错误 |
| submit | 无 | command、check_id、candidate_id仅缺省或null | 完成最终验证并抛出Submitted结束 |

note为可选字符串，未知字段继续拒绝。归档1757个控制动作中，1607个满足本地约束，150个不满足；原发送Schema与本地判定冲突150个，分为submit 71、save 35、bash 25、verify 19。修复后全部1757个两端判定一致，非法动作继续拒绝，另150个字段类型、空值及多余参数边界组合通过。动作回放不执行归档命令。

其中71个submit冲突涉及60次运行。逐条比较紧邻下一请求与当前请求的历史前缀，仅核对新增消息：68个有对应实际拒绝，3个没有下一请求。71个响应末段输出均小于4096。原动作、发送Schema、追加消息和末段词元数见`course-execution-failure-analysis-20261118.json`，不把其他动作混入71的统计。

## 自动反馈

旧代码仅以最后一次自动检查的产物摘要抑制触发；主动检查全部通过后，自动分支仍可能得到空结果并追加消息。37条实际空反馈分布于24条轨迹。修复后只有新执行的检查报告才进入消息。主动和自动检查共用候选、受保护依据及依赖快照记录；稳定的失败结果在候选与依赖不变时不自动重复，未知或不稳定结果不冒充有效证据。候选改变、依赖变化或验证依据失效后仍可重新检查。最终交付检查与候选恢复保持。

`check_control_feedback`读取归档all-your-base候选字节，使用本地实际文件、cmp、sha256sum和Python子进程执行工程检查；仅将容器的固定传输路径映射到工作区。相同检查在原冻结控制器上实际失败于空反馈断言，修复后通过主动验证无空消息、候选变更后失败反馈、相同失败去重、按字节恢复、依赖变化后检查、最终阶段无空消息、非法动作无执行副作用及五种操作的结束/返回检查。工程文件比较不等同于原题语义评分。

## 同协议、同轮次分组

按任务与轮次组成B0/C0/C1三元组，保留三个条件齐全且protocol_commit完全相同的所有位置，再按协议及轮次分组；不按评分筛选，共九组。最大组081a796c第三轮含23道题69次运行，Aider/SWE-bench/Terminal-Bench为10/6/7题。

| 指标 | B0 | C0 | C1 |
|---|---:|---:|---:|
| 通过 | 18/23 | 19/23 | 17/23 |
| 实际CLI请求 | 193 | 226 | 219 |
| 输出词元 | 313258 | 328118 | 350067 |
| 执行时间中位数/秒 | 107.0 | 127.0 | 144.7 |
| 连续格式错误终止 | 5 | 3 | 5 |

该组未显示C1正向收益。全部九组在报告附录列出，任务与运行编号及未四舍五入的数值保存在分析JSON。完整270条、九组和两条件87/86对匹配分析共用原评分，不累计为独立任务数。该事后分组改善已记录协议的一致性，不控制提供方内部状态，也不建立新的随机化因果结论。

## 复现入口与证据

`shared/requirements-analysis.txt`固定mini-swe-agent、Pydantic及jsonschema版本。`shared/README.md`提供独立虚拟环境；`shared/CONFIRMATION.md`两条当前只读复算命令统一使用`work/.venv/bin/python`，分别复核完整保存评分/费用/来源和失败/分组/接口证据。另提供两个当前工程检查入口。

验证结果由`control-contracts-after-20261118.json`、`control-feedback-after-20261118.json`及`control-clean-environment-validation-20261118.json`记录。新实现尚未发起模型请求，不能把工程判定通过解释为模型成功率提升；正式270条仍对应原冻结实现。

独立Python 3.13.12虚拟环境已安装82项固定依赖，`pip check`通过；核心版本为mini-swe-agent 2.4.6、Pydantic 2.14.2及jsonschema 4.26.0。普通索引访问与部分完整下载曾超时；实际安装使用71个核对发布方摘要的官方发行包，以及11个由标准`wheel pack`从既有发行内容重建的包，统一离线安装。未把失败的联网安装写成通过。干净环境成功执行完整评分/费用/来源复核、失败与九组分析、动作回放及反馈工程检查；新分析结果与发布JSON逐字节一致，270评分、63失败、13未知和原配对统计复算通过，新增模型及原评分执行0。
