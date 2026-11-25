# IterativeImputer的NaN常量初值合同

阶段：ANALYZE / RUN预注册。现有75题主队列继续；本修订原pin零模型资格已完成，固定两会话计划待独立准入，尚无新模型成绩。

目标是实现题面明确要求的 `fill_value=np.nan` 与可接收缺失预测变量的树估计器兼容，同时保留旧原评分和既有测试文件。重复会话虽通过原评分和原注册检查，真实工具16已显示 `keep_empty_features=False` 时直接返回含NaN的初值。此为新增语义修订，不能登记为机械重试或覆盖原true/qualifiedtrue。

原证据：`work/vmshare/performance75-hy4-sql-layout-v18-repeat-20261125/scikit-learn__scikit-learn-25232-C0-r2/{instruction.txt,tools.jsonl,candidate.patch}`。工具16原命令及返回显示，在各列均有观察值的4×2矩阵、缺失哨兵−1、HistGradientBoostingRegressor和一轮迭代下，False分支仍含NaN，True分支补为4.3333及4.6667。原重复patch SHA为c70ee0015006574c0b20ccd0df584a9e0cf6d3f91a6f9801a214da0a597fe938；只供独立诊断，不给新模型复制。主补丁已有NaN统计掩码修复，仍需验证训练与transform特征掩码的一致性。

拟复用当前官方实现从原始缺失掩码确定空列、在fit缓存相应特征状态的责任层，按原版本API适配。只采用通用实现原则和官方文档，不向模型提供该基准的参考修复补丁、隐藏评分输入或前一会话候选。

1. 从题面建立公开检查：有限常量/默认初值正常；NaN常量与树估计器在两种keep设置下实际迭代并补齐有观察值的目标；训练和transform采用一致的特征范围。明确全空训练特征的适用边界。
2. 在原镜像、原C0实现下离线验证原base、两份旧候选和独立工程参考，保留实际失败；至少一个已知错误与正常邻例经过真实Controller检查，不改原grader或测试。
3. 只更新此题公开合同及必要通用方法资料，冻结同样500请求/3600秒单次预算/64000输出/无额外超时重试/严格实际Hy4零积分守卫。预定首轮和独立重复各一个新会话，重新原容器，不复制模型候选。
4. 独立审查准入后运行两会话及原评分。原true与真实成本继续保留；新增收益区分语义覆盖、实际反馈采用及原分，不虚构原评分增益。
5. 将最终联合方法的六个任务修订扩为七个：68个任务定义可继承，两组14个固定修订位置。先前六scope join字节已存`prior-six-scope-join.py.txt`供旧审查绑定；新消费修改前后保持两个版本来源。尚未执行时不把14或68写成新成绩。

已有原225→3指导消融→2保护续接顺序保持；本题两会话需要独立新准入后追加。新费用未知或非零仍立即停调，既有35笔未知不填零，不使用收费fallback。

原始公开需求见[scikit-learn issue25052](https://github.com/scikit-learn/scikit-learn/issues/25052)，通用责任层参照[官方IterativeImputer当前实现](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/impute/_iterative.py)。后者不是原版本API的逐字可用补丁，需要以固定版本的真实行为验证。

数值合同补充：给定公开4×2数据与HistGradientBoostingRegressor默认min_samples_leaf=20，各目标仅3个观察样本，平方损失下单叶预测应为各目标观察均值13/3、14/3。训练完整的4×2邻例在transform首列缺失时应预测训练首列均值4。这些解析约束用于拒绝简单零/一填充，并非隐藏验收答案。独立资格另对实际同一公开验证函数输入零/一填充，记录4个拒绝负控，仍保持12个公开案例。

该补充发生在资格仅有路径argv且等待EX租约、尚无admitted_at/子进程/程序或SHA快照时。原probe、driver与等待记录字节保存在before-numeric-contract；未停止或重启任何原模型/评分，也未把未执行前像计成失败尝试。实际执行会记录首次读取的修订probe与driver SHA。

实际资格：原pin下base1/12、旧main8/12、旧repeat9/12，三者真实C0拒绝；独立工程参考12/12、真实C0终局与保护均通过，4个零/一填充数值负控全拒。一次独立原评分通过，96.6129477秒，原报告1个FAIL_TO_PASS及214个PASS_TO_PASS通过，完整stdout217 passed、210 warnings、exit0。0新模型调用，工程参考不算模型成绩；未修改任何旧评分。

复现入口：qualify_public_contract.py必须由原work/parallel-free-evaluation-20261124/resource_trial.py以该SWE任务和精确pin取得独占租约后运行；现有qualification目录拒绝覆盖。prepare_repair.py只在实际资格最终phase和来源SHA相符后冻结frozen/plan.json。真实模型入口仍为原run_fixed_free_trials.py --plan本计划；执行由父线程独立审查后负责，本实施不调用模型。
