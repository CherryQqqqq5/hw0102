import json
import os
from pathlib import Path

from reportlab.platypus import PageBreak, Spacer

from render_course_phase_reports import body_style, build, heading, link, paragraph, table, width


ROOT = Path.cwd()
WORK = ROOT / "work"
LABELS = {"swe": "SWE-bench Verified", "terminal": "Terminal-Bench 2.1", "aider": "Aider Polyglot"}
ARMS = ("B0", "C0", "C1")
BATCH = os.environ.get("COURSE_REPORT_BATCH", "confirmation-hy4flash-free-v13")
PROTOCOL = os.environ.get("COURSE_REPORT_PROTOCOL", "abad82197a3b7833478261a0360f2eae873efdaa")


def require_complete_rows(rows):
    if len(rows) != 270 or any(not row["scoreable"] for row in rows):
        raise ValueError("Final report requires all 270 frozen positions")


def load():
    plan = json.loads((WORK / BATCH.replace("confirmation-", "confirmation-plan-", 1)).with_suffix(".json").read_text())
    summary = json.loads((WORK / f"{BATCH}-summary/summary.json").read_text())
    rows = json.loads((WORK / f"{BATCH}-summary/trials.json").read_text())
    require_complete_rows(rows)
    narrative = json.loads((WORK / f"{BATCH}-analysis.json").read_text())
    if summary["previous_attempt_count"] != len(plan["preserved_previous_attempts"]) or summary["previous_scored_count"] != 0:
        raise ValueError("All frozen previous unscored attempts must remain separate")
    if narrative["batch"] != BATCH or narrative["protocol_commit"] != PROTOCOL:
        raise ValueError("Case analysis belongs to another provider or protocol")
    index = {row["run_id"]: row for row in rows}
    slots = {slot["run_id"]: slot for slot in plan["slots"]}
    if len(narrative["cases"]) < 3:
        raise ValueError("Three directly supported case studies are required")
    for case in narrative["cases"]:
        if BATCH + "/" not in case["evidence"]:
            raise ValueError("A main case must cite the current free source batch")
        for evidence in case["scores"]:
            if index[evidence["run_id"]]["passed"] is not evidence["passed"]:
                raise ValueError("Case score differs from the original grading: " + evidence["run_id"])
            if index[evidence["run_id"]]["protocol_commit"] != slots[evidence["run_id"]].get("source_protocol_commit", PROTOCOL):
                raise ValueError("A case must belong to the frozen free protocol")
    audit = json.loads((WORK / f"{BATCH}-source-audit.json").read_text())
    if audit["batch"] != BATCH or audit["protocol_commit"] != PROTOCOL or audit["primary_positions"] != 270:
        raise ValueError("Original-score and source audit is incomplete")
    billing = audit["free_billing"]
    if billing["missing_responses"] or billing["reported_credit_for_returned_responses"] != 0:
        raise ValueError("Free-model billing evidence is incomplete or nonzero")
    return summary, rows, narrative


def rate(record):
    return f"{record['success']}/{record['trials']}（{record['success_rate']:.1%}）"


def interval(comparison):
    low, high = comparison["bootstrap_95_interval_percentage_points"]
    return f"[{low:+.1f}, {high:+.1f}]"


def task_success_tables(rows):
    items = [heading("逐题三轮成功率"),
             paragraph("每格为同一任务三次原题评分的通过次数及平均成功率；完整270次运行的逐条结果见trials.csv。")]
    for benchmark, label in LABELS.items():
        data = [["任务", *ARMS]]
        for task in sorted({row["task"] for row in rows if row["benchmark"] == benchmark}):
            values = []
            for arm in ARMS:
                selected = [row for row in rows if row["benchmark"] == benchmark and row["task"] == task and row["arm"] == arm]
                if len(selected) != 3:
                    raise ValueError("Task table requires three scored repeats: " + task + "/" + arm)
                passed = sum(row["passed"] for row in selected)
                values.append(f"{passed}/3（{passed / 3:.1%}）")
            data.append([task, *values])
        items.extend([heading(label), table(data, [240, 84, 84, width - 408])])
    return items


def render():
    summary, rows, narrative = load()
    execution = json.loads((WORK / "course-execution-failure-analysis-20261118.json").read_text())
    matched = next(item for item in execution["same_protocol_complete_triples"]
                   if item["protocol_commit"].startswith("081a796c") and item["repeat"] == 3)
    by_group = {(item["benchmark"], item["arm"]): item for item in summary["coverage"]}
    total = {arm: by_group["all", arm] for arm in ARMS}
    main, control, information = summary["comparisons"]
    usage = summary["all_attempt_usage"]
    stopped = json.loads((WORK / "codebuddy-v3-stopped-summary.json").read_text())
    audit = json.loads((WORK / f"{BATCH}-source-audit.json").read_text())
    billing = audit["free_billing"]
    preparation = audit["free_preparation"]["usage"]
    plan = json.loads((WORK / BATCH.replace("confirmation-", "confirmation-plan-", 1)).with_suffix(".json").read_text())
    request_window = plan.get("request_window_min_seconds", 60)
    prior_missing = audit["mechanical_free_billing"]["missing_responses"] + sum(
        item["missing_responses"] for item in audit["previous_free_billing"])
    prior_returned_unknown = sum(item.get("returned_unknown_responses", item.get("returned_unverified_responses", 0))
                                 for item in audit["previous_free_billing"])
    prior_known_local = sum(item.get("returned_known_zero_local_metadata_rejections", 0)
                            for item in audit["previous_free_billing"])
    body_style.leading = 16.8
    body_style.spaceAfter = 6
    items = [
        paragraph(narrative["main_conclusion"]),
        heading("一、研究问题与失败依据"),
        paragraph("本作业研究：在固定执行预算内，公开语义检查、候选版本管理和截止前交付，能否减少智能体最终产物不满足任务要求的情况。"
                  "作业一已在三套基准各完成10题，原生基线通过26/30。此前的错误轨迹形成了三个具体改造目标。"),
        table([["真实失败", "可观察事实", "本轮处理"],
               ["产物缺失", "查询已在临时路径运行，时限结束时未生成指定的sol.sql", "提示提前保存；程序在截止前进入交付阶段"],
               ["语义条件遗漏", "调度方案使用13种全局形状，超过公开上限8；格式检查仍通过", "按题面构造可执行条件，返回实测值和失败条件"],
               ["最终版本未验证", "xarray中途公开测试通过，随后继续修改，以时限终止且原题失败", "验证证据绑定候选版本；保存并恢复已验证产物"]],
              [79, 207, width - 286]),
        paragraph("30道任务最初选定时排除了此前45道开发任务及重复家族，旧产物用于工程验收。"
                  "这些任务随后在CodeBuddy及创智服务执行并形成错误分析；本轮使用相同方法、检查和题单，"
                  f"以Hy4 flash免费模型完成270个位置。主比较保留此前同免费型号{plan['reused_positions']}条有效原评分，"
                  f"其余{plan['new_positions']}位置在本次客户端修复后新运行。全部真实失败及其原评分保留。"
                  "方法形成阶段的正向、负向与未复现结果在后文保留。"),
        heading("二、控制器与信息条件一致的消融"),
        table([["配置", "决策与交付行为"],
               ["B0 原生基线", "原生mini-SWE-agent的Bash决策与提交机制，共用模型适配器及硬执行时限"],
               ["C0 关闭控制", "公开检查说明、验证入口、候选保存/恢复和预算反馈；模型决定何时验证、保存与结束"],
               ["C1 完整控制", "与C0共用相同提示和工具；程序安排检查、保存满足公开条件的版本并在截止前交付"]],
              [93, width - 93]),
        paragraph("verify(check_id)由程序执行登记命令，保存退出状态、检查输出、依赖内容与产物版本。save保存候选，"
                  "restore(candidate_id)按字节恢复文件。产物修改使旧证据失效；既有测试、输入或未允许的配置变化会使验证依据失效。"
                  "候选内容以Secure Hash Algorithm 256-bit（SHA-256，256位安全散列）关联验证记录。"),
        paragraph("C1从第6次决策后开始，在候选变化且存在待验证条件时安排检查，两次自动触发至少相隔2次决策。"
                  "每次决策开始时根据已有的检查耗时估计t，预留min(180,max(30,2.5t+20))秒；首次检查前t为60秒，"
                  "初始预留170秒，后续根据实测更新。剩余时间不超过max(180,2×预留时间)，"
                  "或已用20次决策时进入最终验证阶段；剩余时间不超过预留时间加25秒，或已用23次决策时结束探索。"
                  "当前候选没有有效通过证据、且受保护依据未改变时，恢复最近保存的公开可行候选。"),
        paragraph("模型请求、重试、命令、检查、候选摘要及保存恢复共用600秒执行预算。C1会为恢复保留30秒（已有可行候选）"
                  "或15秒（尚无可行候选）。无法完成验证时记录unknown状态；没有可行候选时保留当前真实产物，由原题评分。"
                  "公开通过的含义严格受检查覆盖范围限制。"),
        table([["代码位置", "实质改造与消融开关"],
               ["controller.py：ControlledEnvironment.verify", "执行公开条件，登记真实输出及对应候选；C0/C1共同使用"],
               ["controller.py：before_decision、finish", "C1安排检查与截止前交付；C0关闭程序安排，保留相同提示和工具"],
               ["controller.py：CandidateStore；candidate_io.py", "保存与按字节恢复候选，核对受保护文件；两组使用同一接口"],
               ["verification.py：VerificationState", "维护公开条件与依赖版本，相关文件改变时旧验证失效"],
               ["agent.py：run_baseline、CodeBuddyModel", "B0保持原生决策；三组共用模型适配及预算修复，后者不作算法贡献"]],
              [218, width - 218]),
        paragraph("实现沿用mini-swe-agent的决策、工具执行与格式反馈循环，并参考Harbor的Terminus 2截断处理。"
                  "免费模型回复先通过实际身份与逐条费用验证。最后一个原生输出段达到4096词元上限时，适配器拒绝执行并反馈截断错误。"
                  "此前输出段截断、后续输出段未达上限时，继续验证成功状态及结构化动作。"
                  "命令行客户端（Command-Line Interface，CLI）本地错误与服务回复分列；每个已识别本地错误须关联独立前置模型用量，"
                  "恢复动作与最终结构化输出一致后才接受。该共同适配器用于三个条件，工程恢复不计为C1算法收益。"),
        heading("三、公开检查与真实工程验收"),
        paragraph("检查依据完整公开题面、初始可见测试和输入编制。软件修复任务使用公开问题的行为复现，例如布尔数组的勾选状态、"
                  "自定义管理站点链接、数组类型保持与动态xfail行为。Aider使用原可见测试；Java公开检查保留原Disabled标记，"
                  "独立评分启用原完整测试。Terminal按题面验证数据聚合、概率分布、数据库恢复、Coq证明或跨语言编译等条件。"),
        paragraph("部分任务只能提供局部检查：密码分析任务检查整数载荷容量，完整密钥和明文正确性由原题评分判断；漏洞利用检查交付文件和格式；"
                  "数据库恢复检查11条输出与修复后数据库的一致性，日志更新真值由原题评分判断；"
                  "Bottle检查报告格式及可见回归，隐藏漏洞条件继续由原评分器判定。检查器使用上游参考产物作工程控制，"
                  "参考解不会进入模型提示或正式任务可读目录。30题原评分控制全部为初始失败、上游参考通过；"
                  "软件修复和终端基准共20题的最终公开检查也正确区分初始与参考产物。"),
        table([["真实材料或控制", "实测行为"],
               ["历史调度命令重建", "B0的13种全局形状被拒绝，RP的7种形状满足公开约束；重建保留原日志来源"],
               ["历史scikit-learn补丁", "40项公开测试通过；恢复后产物摘要一致，后来新建和暂存文件被正确清除"],
               ["历史xarray与pytest补丁", "检查后修改使证据失效；修改既有测试使验证依据失效"],
               ["实际检查超时", "最终阶段和主动验证超时后，分别约33.55/32.53秒恢复可行候选，均在62秒工程预算内"],
               ["公开探针与Harbor截止", "隔离候选命令行、记录正常退出；非零退出保留失败；5秒真实容器时限停止后正常评分"],
               ["实际候选初始化错误", "明确记录操作错误，独立Aider评分仍返回有效失败"]], [130, width - 130]),
        paragraph("上述工程控制的模型请求数为0。真实查询优化的公开原查询在120秒内未完成，等价性和速度检查记为unknown；"
                  "合成SQLite数据仅用于验证检查程序，不作为真实任务的性能证据。"),
        heading("四、免费模型固定任务复测协议"),
        paragraph("SWE-bench Verified、Terminal-Bench 2.1和Aider Polyglot各10道任务。"
                  "按仓库、终端类别和语言分层，使用固定种子nju-course-independent-confirmation-20261105-v1排序。"
                  "环境资格检查在模型运行前完成；缺少离线必要资源或输入含凭据形式数据的候选按预定边界排除，理由完整保存。"),
        paragraph("三组每题各重复三次，共270个预定位置。每题三轮轮换配置顺序，使三个条件在第一、第二、第三位置各出现一次。"
                  f"本次修复协议{PROTOCOL[:7]}在首次新增正式请求前提交并核验远端一致，"
                  f"{plan['reused_positions']}条原评分按逐位置来源保留，{plan['new_positions']}位置新执行。"
                  f"{len(plan['preserved_previous_attempts'])}条前序未评分独立保留，费用不明仍为未知；"
                  f"当前主目录最多{plan['max_total_attempts']}次尝试，加前序保持累计300上限，每个未评分位置最多两次机械恢复；"
                  "有效失败按原评分计入，未评分故障保留原件及恢复原因。"),
        paragraph("科学计算公开探针原先将元数据路径传入候选命令行，正常sys.exit(0)又会跳过记录。修复隔离候选命令行并始终保存观测，"
                  "非零退出仍判失败。真实原空解、上游参考、两种正常退出和非零退出已验收。Harbor外层由600秒改为630秒，"
                  "用于环境识别与日志收尾；内部600秒硬预算、模型、控制方法和原评分保持。5秒缩尺真实Harbor回归复现旧异常，"
                  "修复后内部5.00127秒停止且无截止后动作，原评分正常产生失败。该修复属于工程边界，不能作为控制算法收益。"),
        paragraph("CodeBuddy v3因明确429额度耗尽停止，取得265条评分，另1条未评分、4条未启动；"
                  "与前序15次合计281次尝试、279条评分，完整保留。该批次经历的文件名编码、JavaScript运行时和原npm准备顺序修复，"
                  "均已在本轮启动前完成真实回归。创智服务另保留178条主位置评分和修复前2条评分，因余额不足停止；"
                  "不同服务分别记录成绩和费用，控制效果由本轮免费模型内部的同题三条件比较判断。"),
        table([["条件", "实际设置"],
               ["模型与客户端", "CodeBuddy 2.179.3；请求hy4flash-free，实际hy4-flash-free；原生结构化动作；服务端推理设置未独立固定"],
               ["每次执行预算", f"24次决策、600秒内部硬时限、60秒单命令；无额外请求重试；本次新增位置请求至少留{request_window}秒；Harbor外层630秒含识别与收尾"],
               ["资源与网络", "本地Docker虚拟机4核/约5GB；任务容器离线；一次仅执行一项生成与评分"],
               ["环境一致性", "Django与pytest所需公开依赖只读挂载；polyglot统一补充Python运行时，准备耗时单列"],
               ["评分与统计", "原题独立评分；30道题为统计单位，按基准分层进行10000次配对重采样，固定种子20261104"]],
              [100, width - 100]),
        paragraph("适配器固定主、轻、强模型均为hy4flash-free，清除备用模型并关闭客户端重试、钩子和外部工具。"
                  "CODEBUDDY_CODE_MAX_OUTPUT_TOKENS实际设置4096；每段服务输出上限为4096词元，"
                  "一次CLI调用可包含多个服务回复，因此其总输出可能超过4096。每个实际messageId都须有自身型号和rawUsage.credit=0证明；"
                  "费用缺失、非零、未知错误或已发出请求超时均停止整队列。已知格式错误计入24次决策，连续三次则结束并保留原题评分。"
                  f"本次新增位置三条件的新请求窗口均为{request_window}秒，C1原收尾预留继续计入；不足窗口时结束生成并评价当前真实产物。"
                  "服务端采样种子和内部更新无法独立固定。容器准备与原题评分另计，总用时包含实际清理时间。"),
        paragraph("网络修复使新进程继承已有代理并固定环境来源。密码分析及xarray首轮三条件均为同一旧来源；"
                  "Django11999首轮包含旧C1和新B0/C0。来源版本逐条列出，预先增加排除该整题的29题辅助比较，"
                  "用于检查混合网络策略对结论的影响，主要结果仍覆盖完整30题。"),
        paragraph("后续续跑还修复了超时诊断、4096截断恢复、已识别轮数异常的响应序列化及大响应输出接收。"
                  "各位置的来源版本、失败原件、实际用量和恢复请求分别保留，修复不改变原题评分，也不结清历史未知费用。"
                  "29题辅助分析针对此前声明的网络来源差异，不覆盖后续全部客户端版本变化；"
                  "这些工程变化及服务端不可固定因素仍构成控制效果解释的限制。"),
        paragraph(audit.get("comparison_limitations", "各来源客户端版本及预算处理按冻结协议保留。")),
        heading("执行协议变化与无动作终止"),
        paragraph("完整270条保留所有原评分，汇总比较同时包含客户端恢复方式变化。第一轮90条使用的客户端可在一次外层决策内续接截断输出；"
                  "v10/v12协议复用首轮后，将截断恢复交给外层FormatError，关闭原内置截断续接和结构化追加路径。"
                  "原生每段4096上限相同，单次决策内可获得的续接次数、历史状态和实际用量口径仍不同。"
                  "后两轮还存在已定位工具错误的内部处理，不能简单将一次CLI请求等同于一个原生模型回复。"),
        table([["轮次", "条件", "原题通过", "格式终止", "CLI请求", "原生用量", "输出词元"],
               *[[item["repeat"], item["arm"], f"{item['passed']}/30", item["format_exits"], item["model_calls"],
                  item["native_usage_records"], f"{item['output_tokens']:,}"] for item in execution["rounds"]]],
              [38, 38, 73, 70, 70, 83, width - 372]),
        paragraph("首轮B0/C0/C1分别29/28/25次通过，后两轮合计39/43/43次通过；格式终止由首轮1次增至后两轮28/23次。"
                  "该并行变化支持把恢复方式作为重要混杂检查，不能单凭跨轮差值断言恢复改动导致全部失分。"
                  "相同协议提交的配对位置可作来源检查；它仍未统一任务组成、模型内部采样和全部客户端条件。"
                  "以下整体配对区间描述已保存的混合来源记录，不能解释成严格同一执行策略下的因果效应。"),
        heading("同协议、同轮次的23题三条件比较"),
        paragraph("事后按任务及轮次配对，仅保留B0、C0、C1齐全且protocol_commit完全相同的位置，再按协议与轮次分组，"
                  "保留全部符合条件的任务，不按成绩筛选。081a796c第三轮为最大完整分组，包含23题69次运行，"
                  "覆盖Aider 10题、SWE-bench 6题、Terminal-Bench 7题。全部九个分组及组成见附录。"),
        table([["指标", *ARMS],
               ["原题通过", *[f"{matched['arms'][arm]['passed']}/23（{matched['arms'][arm]['passed']/23:.1%}）" for arm in ARMS]],
               ["CLI请求", *[matched["arms"][arm]["model_calls"] for arm in ARMS]],
               ["输出词元", *[f"{matched['arms'][arm]['output_tokens']:,}" for arm in ARMS]],
               ["执行中位数/秒", *[f"{matched['arms'][arm]['median_execution_seconds']:.1f}" for arm in ARMS]],
               ["连续格式错误终止", *[matched["arms"][arm]["format_exits"] for arm in ARMS]]],
              [145, 115, 115, width - 375]),
        paragraph("该共同协议分组中，C1比B0少通过1题、比C0少2题，输出词元与执行时间中位数较高，未观察到程序安排验证的净收益。"
                  "该分组提供相同已记录协议下的描述性对照；样本是执行完成后分组，提供方内部状态和采样仍不可固定，"
                  "不能把23题作为预先注册的独立确认或将其他分组隐藏。"),
        table([["同原协议提交的事后子集", "位置对数", "对照通过", "改造通过"],
               *[[f"{item['treatment']} / {item['reference']}", item["task_repeat_pairs"], item["reference_passed"], item["treatment_passed"]]
                 for item in execution["protocol_matched_descriptive_pairs"]]], [220, 90, 90, width - 400]),
        paragraph("这里的一个位置对是一题某轮的两条件，子集按既有protocol_commit匹配，各比较排除位置不同；"
                  "不是预先固定的新测试集，也未统一提供方内部状态。不以该子集替代全部原记录或推断显著性。"),
        paragraph(f"52次RepeatedFormatError中48次原题失败、4次仍通过，分别保留。{execution['last_native_reasoning_only_4096_tail_and_original_failed']}条失败的最后三次CLI响应，"
                  "其最后一段原生输出均为4096个推理词元、无工具动作，占63条失败的58.7%。"
                  "若严格要求三次CLI响应各仅一段原生输出，则为36条；另1条xarray请求含2003+4096词元，不能把整次响应记成4096。"
                  "这些记录定位了动作产生之前的执行瓶颈，尚未证明修复后能够挽救多少原题。"),
        paragraph("polyglot-rust-c/B0第二轮仅三次请求，各输出4096个推理词元，累计12288且无动作。后续请求历史依次只有1、2、3条user消息，"
                  "没有失败原生assistant消息或reasoning_content，实际增加的是短动作错误提示。第一轮同题第2个CLI请求含4096、4096、3650三段，"
                  "保存truncation_recovered并最终通过原题。该同题跨版本对照说明状态续接与决策预算发生变化，不能当作预算一致的恢复收益。"
                  "应优先研究同总预算下的原生历史保留与受限续接；本轮未运行该新方案，未放宽截断动作或真实费用校验。"),
        heading("五、任务成功率与机制消融"),
        table([["基准", "B0", "C0", "C1"],
               *[[label, *[rate(by_group[key, arm]) for arm in ARMS]] for key, label in LABELS.items()],
               ["合计", *[rate(total[arm]) for arm in ARMS]]], [145, 115, 115, width - 375]),
    ]
    comparisons = [["比较", "差值/百分点", "95%区间", "改善/持平/退化题数"]]
    for comparison in (main, control, information):
        changes = comparison["changes"]
        gain, loss = changes.get("gain", 0), changes.get("loss", 0)
        comparisons.append([f"{comparison['treatment']} − {comparison['reference']}",
                            f"{comparison['delta_percentage_points']:+.1f}", interval(comparison),
                            f"{gain}/{30-gain-loss}/{loss}"])
    items.append(table(comparisons, [80, 96, 125, width - 301]))
    items.append(paragraph("每条件成功率为通过次数/90；每题先对三轮0/1成绩求均值，再对30题的条件差值求均值，乘100得到百分点差。"
                           "相对百分比为通过数差/对照通过数×100%。C1/B0为0次、0.0个百分点、相对0.0%；"
                           "C1/C0为−3次、−3.3个百分点、相对−4.2%；C0/B0为+3次、+3.3个百分点、相对+4.4%。"
                           "配对重采样以任务为单位，保留同题三轮，不能将270次执行当作270道独立题目。"))
    sensitivity = summary["transport_sensitivity"]
    items.extend([paragraph("预先声明的网络版本辅助分析排除Django11999整题，保留29题、261条有效评分；"
                            "它用于检查混合网络来源是否改变结论，不替代上面的30题主要结果。"),
                  table([["29题辅助比较", "差值/百分点", "95%区间"],
                         *[[f"{item['treatment']} − {item['reference']}",
                            f"{item['delta_percentage_points']:+.1f}", interval(item)]
                           for item in sensitivity["comparisons"]]], [170, 125, width - 295])])
    items.extend([paragraph(narrative["comparison_interpretation"]),
                  paragraph("C1/B0、C1/C0、C0/B0分别对应完整改造、程序控制和新增信息接口的设计比较目标。"
                            "整体汇总报告观察到的配对差异，并结合分版本结果解释。检查反馈、候选修改和复测通过的先后顺序提供过程证据。"
                            "三轮重复保留在每道题内部，不能解释为每配置90道独立任务。"),
                  table([["超时敏感性（辅助）", "无超时配对题数", "差值/百分点"],
                         *[[f"{item['treatment']} − {item['reference']}", item["pairs_without_provider_timeout"],
                            f"{item['delta_without_provider_timeout_percentage_points']:+.1f}"
                            if item["delta_without_provider_timeout_percentage_points"] is not None else "无可用配对"]
                           for item in (main, control, information)]], [195, 140, width - 335]),
                  paragraph("辅助分析保留该比较中两个条件三轮均没有请求超时的整道任务，样本组成因比较而异。"
                            "主要结果覆盖全部30题；服务等待和失败产物按冻结规则保留，辅助口径不替代主比较。"),
                  table([["稳定性与过程", "B0", "C0", "C1"],
                         ["三轮全部通过的题数", *[str(total[arm]["all_three_successful_tasks"]) + "/30" for arm in ARMS]],
                         ["有效最终验证记录", "不适用", *[str(total[arm]["valid_final_verification_trials"]) + "/90" for arm in ("C0", "C1")]],
                         ["自动检查次数", *[total[arm]["automatic_checks"] for arm in ARMS]],
                         ["没有取得模型响应的运行数", *[sum(row["model_responses"] == 0 for row in rows if row["arm"] == arm) for arm in ARMS]],
                         ["因连续格式错误结束的运行数", *[sum(row["exit_status"] == "RepeatedFormatError" for row in rows if row["arm"] == arm) for arm in ARMS]],
                         ["失败后改版复测通过，且原题通过", *[total[arm]["repair_chain_and_original_pass_trials"] for arm in ARMS]],
                         ["最终阶段自动恢复的运行数", *[total[arm]["restored_final_candidate"] for arm in ARMS]]],
                        [240, 84, 84, width - 408]),
                  paragraph("失败反馈、候选改变、复测通过的先后顺序属于过程证据；成功率的因果解释以同题匹配消融为依据。"
                            "连续格式错误按RepeatedFormatError退出状态统计，与无模型响应分别列出，最终成绩均取原题判定。"
                            "退出后的检查计入实际检查开销，模型是否收到反馈由后续请求原文核对。"
                            "公开通过而原题失败的记录仍保留，可以揭示检查覆盖的局限。"),
                  *task_success_tables(rows),
                  heading("六、成本与时限"),
                  table([["配置", "请求", "输入词元", "输出词元", "执行中位秒", "总用时中位秒"],
                         *[[arm, total[arm]["model_calls"], f"{total[arm]['input_tokens']:,}", f"{total[arm]['output_tokens']:,}",
                            f"{total[arm]['median_execution_seconds']:.1f}", f"{total[arm]['median_wall_seconds']:.1f}"] for arm in ARMS]],
                        [40, 60, 110, 100, 90, width - 400]),
                  table([["时限与验证开销", *ARMS],
                         ["请求超时次数", *[total[arm]["model_request_timeouts"] for arm in ARMS]],
                         ["额外请求重试次数", *[total[arm]["model_request_retries"] for arm in ARMS]],
                         ["未返回响应的请求数", *[total[arm]["usage_unreturned_requests"] for arm in ARMS]],
                         ["响应缺失输入/输出用量", *[f"{total[arm]['usage_missing_input_responses']}/{total[arm]['usage_missing_output_responses']}" for arm in ARMS]],
                         ["公开检查累计秒数", *[f"{total[arm]['public_check_seconds']:.1f}" for arm in ARMS]],
                         ["候选操作累计秒数", *[f"{total[arm]['candidate_operation_seconds']:.1f}" for arm in ARMS]]],
                        [240, 84, 84, width - 408]),
                  paragraph(narrative["cost_interpretation"]),
                  paragraph("请求次数按适配器发起的请求尝试计算，包含超时重试。每次模型查询消耗一次决策额度，格式错误也计入；"
                            "同一查询的超时重试按请求尝试另计。输入、输出和缓存词元仅合计服务已返回字段，"
                            "输出包括返回用量中的推理输出。无响应与缺失用量均单独计数，不能据数值合计推断未知部分为零。"),
                  paragraph("24次额度计算外层决策，4096上限针对每次原生模型输出。同一命令行响应仍可能包含客户端对未知工具名恢复时的多笔原生回执；"
                            "每笔须有自身免费身份与零积分，后一笔不结清前一笔。已复核的双回执实例中，命令行输入与输出用量为两笔实际用量之和。"
                            "客户端num_turns属于轮数记录，不直接当作原生模型调用次数。"),
                  paragraph("预算门限拒绝的一次决策没有实际模型请求，也没有模型费用。scikit-learn25232第三轮基线记录18次外层决策，"
                            "其中最后一次在剩137.75秒时被150秒门限拒绝，实际17请求、17响应和19条原生用量；"
                            "C0对应22次外层决策、21请求、21响应和24条原生用量。本文请求与费用均依据实际事件及自身回执，"
                            "不直接使用外层api_calls充当实际调用次数。两组在截止前保留现有补丁，原评分均通过。"),
                  paragraph(f"免费模型正式比较共{270 + summary['mechanical_attempt_count'] + summary['previous_attempt_count']}次尝试，主比较270次取得有效原题评分，"
                            f"另保留{summary['previous_attempt_count']}次前序未评分尝试及{summary['mechanical_attempt_count']}次未评分机械尝试。累计{usage['model_calls']:,}次请求、"
                            f"{usage['model_responses']:,}次响应、{usage['model_request_timeouts']}次请求超时和{usage['model_request_retries']}次额外重试；"
                            f"输入{usage['input_tokens']:,}、输出{usage['output_tokens']:,}词元。上表只统计进入主要比较的正式位置，"
                            "全部正式尝试用量另列于summary.json。词元统计来自服务返回记录；超时且未返回用量的请求，"
                            "词元无法独立核算，其请求次数和等待时间仍保留。服务费用字段无法代替实际账户账单。"),
                  paragraph(f"本轮主比较{billing['responses']}次CLI响应中的{billing['actual_model_usage_records']}条实际模型用量均通过逐条免费身份及零积分核验，"
                            f"恢复{billing['recovered_actions']}次完整动作。前序正式尝试保留{prior_missing}次缺失回执及{prior_returned_unknown}次已返回但原生费用不全，"
                            f"准备记录另保留{audit['free_preparation']['missing_responses']}次缺失回执，真实费用继续未知，不能计为零。"
                            "免费接口准备包括最小连通、4096上限、轮数异常、短动作恢复及完整大响应接收验证；"
                            "旧别名hy4free误调用产生0.55积分，单独披露。CLI的total_cost_usd不能替代实际模型积分证明。"),
                  paragraph(f"前序另有{prior_known_local}次本地工具结果的model元数据拒绝：其配置别名与父调用实际型号不一致，"
                            "原生请求各自具有正确免费型号及零积分回执。诊断核对同一callId、messageId和conversationRequestId，"
                            "客户端修复只沿用该父调用的实际身份；不添加别名白名单，也不变更原生事件或费用。"
                            "原始整次拒绝和未评分状态保持，与上述真实费用未知分列。"),
                  paragraph(f"按不重复的初始及恢复准备来源，合计{preparation['model_calls']}次请求、{preparation['model_responses']}次响应，"
                            f"输入{preparation['input_tokens']:,}、输出{preparation['output_tokens']:,}、缓存输入{preparation['cached_input_tokens']:,}词元；"
                            f"其{audit['free_preparation']['actual_model_usage_records']}条实际模型用量均明确零积分。"
                            "准备数据单列，未加入正式三组的通过率或费用合计。"),
                  paragraph(f"旧CodeBuddy独立批次保留{stopped['all_attempts']}次尝试、{stopped['all_scored']}条评分，"
                            f"{stopped['all_attempt_usage']['model_calls']:,}次请求、{stopped['all_attempt_usage']['model_responses']:,}次响应；"
                            f"已返回输入{stopped['all_attempt_usage']['input_tokens']:,}、输出{stopped['all_attempt_usage']['output_tokens']:,}词元。"
                            "创智主位置178条及前序2条评分、服务中断与额度不足请求也单独保留。各服务成本分别列于来源审计，未加入免费三组通过率。"),
                  PageBreak(), heading("七、代表性轨迹")])
    for case in narrative["cases"]:
        items.extend([heading(case["title"]), paragraph(case["observations"]), paragraph(case["interpretation"]),
                      paragraph("证据：" + case["evidence"] )])
    items.extend([
        heading("八、方法形成与历史结果"),
        table([["批次", "结果", "解释范围"],
               ["原诊断30题", "B0 26/30，F 24/30", "依赖时效检查未产生总体改善"],
               ["原15题三轮", "B0/BP/A/F为38/40/43/37次通过，各45次", "A的早期优势用于配置探索"],
               ["同题新重复确认", "A 41/45，B0 42/45", "A的早期优势未复现"],
               ["修订15题三臂", "B0/RP/R为13/15、15/15、14/15", "已见任务探索；RP差值+13.3百分点，区间[0,26.7]"],
               ["CodeBuddy固定30题，未完成", "B0/C0/C1为82/89、84/88、82/88", "265评分、1未评分、4未启动；分母不同，结果仅作描述"]],
              [107, 195, width - 302]),
        paragraph("原15题三臂成绩为14/15、15/15、14/15。调度公开检查修复后按预先记录规则对三配置成组补跑，"
                  "保留42条原记录并替换3条。正向差值扩大全部来自B0新采样由通过变失败，RP/R通过数未增加。"
                  "RP在读取首轮结果后选作主要正向配置，因此该比较属于探索；本轮承担固定30题的新服务复测。"),
        paragraph("scikit-learn-14496的B0/RP/R补丁逐字节相同，均通过原题，分别使用9/15/8次请求、"
                  "187.8/349.2/160.5秒。自动执行相对RP减少7次请求，相对原生B0减少1次，主要减少了命令字符串登记造成的重复提交。"
                  "本轮verify(check_id)直接登记执行证据，C0/C1均使用该入口。"),
        paragraph("原384条评分包含重复运行、开发实验和被替换的记录，对应45道独立旧题；本轮主比较270条对应固定30道复测任务。"
                  f"旧CodeBuddy后续{stopped['all_scored']}条评分、创智主位置{audit['boyue_main_scored_preserved']}条及修复前2条评分分别保留，"
                  "同一来源复用记录不重复计数。历史与本轮合计覆盖75道不同任务。"
                  "历史失败、工程控制和机械未评分尝试分别保留。"),
        heading("九、结论与适用范围"), paragraph(narrative["conclusion"]),
        paragraph("原C0/C1接口中，71份submit返回符合发送的JavaScript Object Notation（JSON，JavaScript对象表示法）Schema，"
                  "却与本地操作约束冲突，涉及60次运行。"
                  "其中68份在紧接下一请求的新增消息中出现对应的实际校验拒绝；3份处于运行最后一次请求，没有下一请求可供核对。"
                  "71份响应的最后一个原生输出段均未达到4096。C1另有24条轨迹中的37次请求包含空自动检查反馈；"
                  "37按实际消息计数，不直接等于净新增请求或失分。"),
        heading("接口修复与工程验证范围"),
        paragraph("2026年11月18日的修复版本保留本地动作接受规则，以同一操作—字段定义生成发送端分支约束。"
                  "bash必须有非空command，verify必须有非空check_id，restore必须有非空candidate_id；save和submit不接受其他操作的非空参数。"
                  "归档全部1757个控制动作中，旧发送约束与本地判定冲突150个：submit 71、save 35、bash 25、verify 19；"
                  "修复后1607个合法动作两端接受、150个非法动作两端拒绝，另150个字段边界组合判定一致。"),
        paragraph("自动反馈改为仅在产生新检查报告时追加消息；按实际候选、受保护依据和检查依赖版本识别已经反馈的结果。"
                  "模型主动验证与程序安排验证共用该记录，相同候选及依赖不重复检查已报告的稳定失败，候选或依赖改变后仍重新检查。"
                  "用归档候选字节和本地真实子进程复现旧空反馈，并验证主动检查、候选变化、失败去重、依赖失效、精确恢复及五种操作的返回和终止。"
                  "该工程检查使用文件比较，不是原题成功率实验；历史冻结代码、270条原评分及真实费用校验保持。"
                  "修复后模型行为和任务成功率仍无新增实测证据。"),
        paragraph("检查器按每道公开任务编制，包含人工规则设计，尚未验证自动生成检查器的能力。软件修复任务集中于四个仓库的较短修复，"
                  "Terminal限于可离线、单容器和当前资源能承载的任务，Aider覆盖六种语言。"
                  "除已披露的接口修复外，公开条件与方法在旧提供方运行前固定；免费复测前已读取旧服务结果，模型训练暴露情况未知。"
                  "检查范围、固定时限、客户端服务波动和样本规模共同限制结论外推。"),
        heading("材料与复现"),
        paragraph("frozen-runtime/v16/course_eval/保存历史冻结执行实现，计划逐位置注明复用来源协议；"
                  "shared/course_eval/controller.py为当前接口修复版本，candidate_io.py保持。作业二/configs/保存冻结协议、"
                  f"题单、公开检查与顺序；evidence/{BATCH}/保存主比较的可审计模型交互、真实计费回执、工具、候选版本和原评分；"
                  f"{BATCH}-summary/保存统计，{BATCH}-previous/保留{len(plan['preserved_previous_attempts'])}次前序未评分，"
                  "复用来源由计划逐位置列出。旧服务停止批次及前序记录单独保留，"
                  "codebuddy-v3-stopped-summary.json保存其未完成范围和去重费用，v2中的80条复用不能重复相加。"
                  "完整命令见shared/CONFIRMATION.md。"
                  "辅助实现、检查编制、执行与报告整理使用Codex；模型行为与原题成绩由保存的实际运行记录支持。"),
        paragraph("shared/README.md提供独立分析环境，shared/CONFIRMATION.md两条只读命令统一使用work/.venv/bin/python。"
                  "干净环境执行完整原记录复核与分组/接口分析，具体版本、输出和工程验收见evidence/control-interface-repair-20261118.md。"
                  "课程逐项要求与材料对应关系见evidence/course-rubric-audit-20261118.md。"
                  "完整输入、配置、代码、模型交互和独立原评分可由上述目录逐项核对。"),
        link("课程作业仓库", "https://github.com/CherryQqqqq5/hw0102"),
        link("免费模型执行协议提交", f"https://github.com/CherryQqqqq5/hw0102/commit/{PROTOCOL}"),
        link("mini-swe-agent维护者实现说明", "https://mini-swe-agent.com/latest/advanced/cookbook/"),
        link("Harbor Terminus 2源代码", "https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/terminus_2/terminus_2.py"),
        link("Terminal-Bench版本目录", "https://www.tbench.ai/benchmarks"),
    ])
    items.extend([PageBreak(), heading("附录：全部同协议、同轮次三条件分组"),
        paragraph("采用正文相同事后规则，保留所有满足三条件齐全且protocol_commit一致的任务—轮次。下表A/S/T依次为Aider、SWE-bench、Terminal-Bench题数；"
                  "通过数、请求、输出和中位数均按B0/C0/C1顺序。各组任务及运行编号完整保存在course-execution-failure-analysis-20261118.json。"
                  "不同轮次可含相同题，不把分组题数相加作为独立任务数。"),
        table([["协议/轮次", "题数", "A/S/T", "B0通过", "C0通过", "C1通过"],
            *[[f"{item['protocol_commit'][:8]}/r{item['repeat']}", item["tasks"],
               "/".join(str(item["benchmarks"][name]) for name in ("aider", "swe", "terminal")),
               *[f"{item['arms'][arm]['passed']}/{item['tasks']}" for arm in ARMS]]
              for item in execution["same_protocol_complete_triples"]]], [123, 45, 70, 84, 84, width - 406]),
        Spacer(1, 9),
        table([["协议/轮次", "CLI请求", "输出词元", "执行中位数/秒"],
            *[[f"{item['protocol_commit'][:8]}/r{item['repeat']}",
               "/".join(str(item["arms"][arm]["model_calls"]) for arm in ARMS),
               "/".join(str(item["arms"][arm]["output_tokens"]) for arm in ARMS),
               "/".join(f"{item['arms'][arm]['median_execution_seconds']:.1f}" for arm in ARMS)]
              for item in execution["same_protocol_complete_triples"]]], [123, 95, 170, width - 388]),
        paragraph("该附录与完整270条矩阵、按轮汇总及87/86对两条件匹配分析共用同一原评分。"
                  "分组没有引入模型请求、替换有效失败或重新运行评分器；各子集保留原执行差异与负结果。")])
    build("231880296_邱昱宁_作业二.pdf", "作业二 · 公开验证与候选交付控制", items,
          subtitle="邱昱宁 · 231880296", footer="智能推理与规划 · 邱昱宁")


if __name__ == "__main__":
    render()
