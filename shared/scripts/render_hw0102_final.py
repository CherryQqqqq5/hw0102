import argparse
import csv
import json
from pathlib import Path
from statistics import median

from reportlab.platypus import PageBreak, Spacer

from render_course_phase_reports import build, heading, subheading, link, paragraph, table, width


work = Path("work")
stats = work / "coverage-check"
summary = json.loads((stats / "summary.json").read_text())
with (stats / "trials.csv").open() as stream:
    rows = list(csv.DictReader(stream))

labels = {"swe": "SWE-bench Verified", "terminal": "Terminal-Bench 2.1", "aider": "Aider Polyglot"}
identifier = "231880296_邱昱宁"
author = "邱昱宁  ·  231880296"
footer = "智能推理与规划 · 邱昱宁"


def baseline_report(confirmation_batch: str | None = None, *, validation_items: list | None = None,
                    output_filename: str | None = None, report_subtitle: str | None = None,
                    report_footer: str | None = None, validation_first: bool = False) -> None:
    coverage = {row["benchmark"]: row for row in summary["coverage"] if row["split"] == "D" and row["arm"] == "B0"}
    baseline = [row for row in rows if row["split"] == "D" and row["arm"] == "B0"]
    if len(baseline) != 30 or any(coverage[key]["scoreable"] != 10 for key in labels):
        raise ValueError("The final baseline report requires30valid original scores")
    overview = [["基准", "已评分", "通过", "未通过", "通过率"]]
    for key, label in labels.items():
        item = coverage[key]
        overview.append([label, 10, item["success"], 10 - item["success"], f"{item['success'] / 10:.0%}"])
    successes = sum(item["success"] for item in coverage.values())
    overview.append(["合计", 30, successes, 30 - successes, f"{successes / 30:.1%}"])
    calls, responses, input_tokens, output_tokens = (
        sum(int(row[key]) for row in baseline)
        for key in ("model_calls", "model_responses", "input_tokens", "output_tokens"))
    items = [
        heading("一、实验目的"),
        paragraph("本实验评测编程智能体在软件缺陷修复、终端多步任务和跨语言编程中的表现，"
                  "通过实际运行与原题评分定位影响完成任务的关键问题，提出对应改进，并检验改进后的结果。"),
        heading("二、实验原理与方法"),
        paragraph("使用mini-SWE-agent的原生执行循环：模型读取题面和可见代码，选择命令，"
                  "根据真实工具返回继续修改，最后交付文件或补丁。任务结束后由独立原题评分器检查实际产物。"
                  "模型声明完成、命令退出和原题评分分别记录。"),
        paragraph("SWE-bench Verified按官方resolved指标判定软件修复；Terminal-Bench 2.1使用Harbor执行原题验收；"
                  "Aider Polyglot以原测试全部通过判定。通过率以实际取得原题评分的任务数为分母。"),
        heading("三、实验环境与设置"),
        subheading("3.1 任务抽样"),
        paragraph("三套基准各选10道诊断题，共30题；另各预留5题用于后续研究。45题均核对起始状态与参考解评分后固定。"
                  "SWE-bench候选500题，样本覆盖Django、xarray、scikit-learn、pytest；Terminal候选89题，"
                  "按任务类型覆盖抽样；Aider候选225题，覆盖C++、Go、Java、JavaScript、Python、Rust六种语言。"),
        paragraph("筛选优先选择可离线评分和较短的软件修复。Terminal任务限制为单容器、至多2个处理器核心及3072 MB内存，"
                  "排除运行时必须联网下载或参考解离线失败的任务。Aider排除离线依赖缺失或初始实现已通过的题。"
                  "这些筛选条件在正式评测前固定。"),
        subheading("3.2 模型与执行预算"),
        paragraph("基线采用mini-SWE-agent 2.4.6、CodeBuddy 2.179.3与deepseek-v4.1-flash。"
                  "每题最多24次模型请求，交互时限600秒，在相邻请求之间检查；单请求上限150秒，单命令60秒。"
                  "已发请求和独立验收可能延长总耗时。智能体与评分证据隔离，Aider题目原测试可见。"),
        heading("四、实验步骤"),
        paragraph("（1）固定题单、初始环境和预算，核对起始状态及参考解的原题评分。"),
        paragraph("（2）为每题创建隔离环境，执行原生智能体，保存模型请求、命令、工具返回和最终产物。"),
        paragraph("（3）正常提交或达到时限后，对实际留下的产物执行原题评分，汇总三套基准成绩。"),
        paragraph("（4）从轨迹中提取错误发生的步骤、产物状态与验收断言，区分直接原因和超时等伴随条件，"
                  "提出改进并用后续原题评分、同题对照和独立重复验证。"),
        heading("五、实验结果"),
        table(overview, [171, 82, 70, 70, width - 393]),
        paragraph(f"30道题中26/30通过，4道未通过均来自Terminal任务。共记录{calls}次模型请求、{responses}次响应，"
                  f"已返回用量为输入{input_tokens:,}词元、输出{output_tokens:,}词元。"),
        heading("六、结果分析与改进验证"),
        subheading("6.1 关键案例分析"),
        paragraph("视频处理：video-processing第3至13步反复探索前景和轮廓，第14步交付的脚本已可导入，"
                  "原题两段视频的起跳帧却为66和322，超出允许区间50–54和219–223。"
                  "直接问题是事件定位精度，格式和导入检查未覆盖这一要求。改进应观察事件邻帧，并以独立定位验收检验算法。"),
        paragraph("查询优化：query-optimize第8步的临时候选在2.425秒返回500行，第9步记录其与原查询输出相同，"
                  "最终却未写入/app/sol.sql，原题四项测试因此失败。问题发生在探索与交付之间，"
                  "应先在指定路径保存可运行草稿，再继续优化和检验等价性。"),
        paragraph("批处理调度：llm-inference-batching-scheduler第8步脚本正常退出，但两个请求桶的八组设置均未达到本地指标。"
                  "第9次模型请求超时后，原题评分器又发现plan_b1.jsonl缺失，五项测试失败。"
                  "性能不足与交付缺失同时存在，改进需先保存计划，再按题面约束检验性能。"),
        paragraph("二进制提取：extract-elf第12步的698项自查零不一致，原题地址覆盖率却为0%，低于75%。"
                  "自查沿用实现中的固定0x400000基址与相同映射，未独立验证地址含义。"
                  "该例暴露了检查与实现共享关键假设的风险，改进应依据二进制实际装载段独立核对。"),
        subheading("6.2 错误机制与对应策略"),
        paragraph("交付没有落实到文件：查询已有临时结果，调度也执行过脚本，但这些局部进展没有形成评分器要求的产物。"
                  "发生中断时，评分器只能读取已保存的文件。策略是先在指定路径交付可运行草稿，再逐步优化，并在结束前核对路径与内容。"),
        paragraph("检查没有覆盖任务要求：视频的导入检查只能证明脚本可加载，无法检验起跳帧的定位精度；调度脚本正常退出也不代表性能达标。"
                  "策略是从题面拆出功能、精度和性能条件，分别检查，防止用命令成功替代任务验收。"),
        paragraph("实现与自查共享错误假设：二进制提取的实现和检查都使用固定基址，698次一致只证明两者相同。"
                  "策略是改用实际装载段建立独立检查依据。调度性能不足和错误自查均在终止前出现，单纯延长时间无法补足这些检查缺口。")]
    if validation_items:
        items.extend(validation_items)
    items += [
        heading("七、实验结论"),
        paragraph("原生基线在30道诊断题上通过26/30。影响结果的关键环节包括产物交付、功能精度和独立验证，"
                  "单纯可运行或自查通过不足以保证原题验收。对应改进在原诊断集首轮和独立重复均为30/30，四道原失败题两轮均通过4/4。"),
        paragraph("本实验样本偏向资源受限、可离线评分的任务，结论适用于该抽样与执行条件。"
                  "后续验证更换了模型和预算，其结果与原诊断分列；同模型方法效果由后续DSH对照判断。"),
        link("代码仓库：github.com/CherryQqqqq5/hw0102", "https://github.com/CherryQqqqq5/hw0102")]
    build(output_filename or f"{identifier}_作业一.pdf", "作业一：编程智能体评测实验报告", items,
          subtitle=report_subtitle or author, footer=report_footer or footer)


def comparison_rates(comparison: dict) -> tuple[str, str, str, str]:
    pairs = comparison["pairs"]
    if not pairs:
        return "未取得", "未取得", "未取得", "未取得"
    rates = [sum(sum(pair[arm]) / len(pair[arm]) for pair in pairs) / len(pairs)
             for arm in ("reference", "treatment")]
    relative = comparison["relative_change_percent"]
    return f"{rates[0]:.1%}", f"{rates[1]:.1%}", f"{comparison['delta_percentage_points']:+.1f}", (
        f"{relative:+.1f}%" if relative is not None else "未定义")


def cost_table(cohort: list[dict], arms: tuple[str, ...]) -> list[list[str]]:
    result = [["配置", "运行", "请求", "输入词元", "输出词元", "总用时中位数", "费用字段"]]
    for arm in arms:
        trials = [row for row in cohort if row["arm"] == arm]
        if not trials:
            continue
        requests, inputs, outputs = (sum(int(row[key]) for row in trials)
                                     for key in ("model_calls", "input_tokens", "output_tokens"))
        wall = median(float(row["wall_seconds"]) for row in trials)
        money = [row["provider_reported_cost_usd"] for row in trials]
        cost = f"{sum(float(value) for value in money):.4f} 美元" if all(money) else "字段缺失"
        result.append([arm, str(len(trials)), str(requests), f"{inputs:,}", f"{outputs:,}", f"{wall:.1f} 秒", cost])
    return result


def improvement_report() -> None:
    from render_course_phase_reports import body_style
    from render_revision_sections import revision_sections

    body_style.leading = 17.0
    body_style.spaceAfter = 6
    revised_headline, revised_items = revision_sections(cost_table)
    diagnostic, *holdout = summary["comparisons"]
    complete_ablation = next(item for item in holdout if item["reference"] == "A")
    first_ablation = next(item for item in summary["holdout_by_repeat"] if item["reference"] == "A" and item["repeat"] == 1)
    if diagnostic["paired_tasks"] < 10 or not first_ablation["paired_tasks"]:
        raise ValueError("Assignment two requires at least ten paired scores and one formal ablation")
    case_path = work / "hw0102-a2-cases.json"
    analysis = json.loads(case_path.read_text())
    cases = analysis["cases"]
    if len(cases) < 3:
        raise ValueError("Assignment two requires at least three traced case analyses")
    diagnostic_scores = {pair["task"]: pair for pair in diagnostic["pairs"]}
    analyzed = []
    for case in cases:
        observed = diagnostic_scores[case["task"]]
        if [observed[arm][0] for arm in ("reference", "treatment")] != case["scores"]:
            raise ValueError(f"Case scores do not match the benchmark: {case['task']}")
        analyzed.extend([heading(case["title"]), paragraph(case["observations"]), paragraph(case["interpretation"])])
    coverage = summary["coverage"]
    h_scoreable = sum(item["scoreable"] for item in coverage if item["split"] == "H")
    ablation = complete_ablation if complete_ablation["paired_tasks"] == 15 else first_ablation
    d_before, d_after, d_delta, d_relative = comparison_rates(diagnostic)
    a_before, a_after, a_delta, _ = comparison_rates(ablation)
    changes = diagnostic["changes"]
    interval = diagnostic["bootstrap_95_interval_percentage_points"]
    uncertainty = (f"按基准分层、以题为单位做 10,000 次配对重采样，95% 区间为 [{interval[0]:+.1f}, {interval[1]:+.1f}] 个百分点。"
                   if interval else "诊断对照尚未覆盖全部 30 道题，表中列出已评分配对。")
    timeout_count = diagnostic["paired_tasks"] - diagnostic["pairs_without_provider_timeout"]
    if timeout_count and diagnostic["pairs_without_provider_timeout"]:
        uncertainty += (f"其中 {timeout_count} 对涉及提供方超时。单列排除这些配对后的差值为 "
                        f"{diagnostic['delta_without_provider_timeout_percentage_points']:+.1f} 个百分点。")
    stage = "三轮完整配对" if ablation is complete_ablation else "首轮配对"
    d_table = [["基准", "配对题", "B0 通过", "F 通过", "改善", "退化"]]
    for key, label in labels.items():
        pairs = [pair for pair in diagnostic["pairs"] if pair["benchmark"] == key]
        d_table.append([label, len(pairs), sum(pair["reference"][0] for pair in pairs),
                        sum(pair["treatment"][0] for pair in pairs), sum(pair["change"] > 0 for pair in pairs),
                        sum(pair["change"] < 0 for pair in pairs)])
    ablation_rows = [["对照", "配对题", "对照成功率", "F 成功率", "差值（百分点）", "相对变化"]]
    for reference in ("B0", "BP", "A"):
        comparison = next(item for item in (holdout if ablation is complete_ablation else summary["holdout_by_repeat"])
                          if item["reference"] == reference and item.get("repeat", 1) == 1)
        before, after, delta, relative = comparison_rates(comparison)
        ablation_rows.append([f"{reference} → F", comparison["paired_tasks"], before, after, delta, relative])
    checks = {arm: sum(int(row["submission_check_opportunities"]) for row in rows if row["split"] == "H" and row["arm"] == arm
                       and row["scoreable"] == "True") for arm in ("A", "F")}
    stale = sum(int(row["stale_at_submission"]) for row in rows if row["split"] == "H" and row["arm"] == "F"
                and row["scoreable"] == "True")
    reminders = sum(int(row["deliverable_reminders"]) for row in rows if row["split"] == "D" and row["arm"] == "F"
                    and row["scoreable"] == "True")
    diagnostic_cohort = [row for row in rows if row["split"] == "D" and row["task"] in diagnostic_scores
                         and row["scoreable"] == "True"]
    cost_widths = [41, 44, 53, 86, 82, 91, width - 397]
    items = [
        heading("主要结果"), paragraph(revised_headline),
        heading("从基线失败到改造"),
        paragraph("查询优化基线能够执行临时候选，但没有写到指定路径。批处理调度既缺交付文件，又观察到本地性能超限。"
                  "视频脚本已写出，但定位仍然偏离原题要求。改造分别干预保存产物的时点和完成声明依据的有效性。"),
        paragraph("对题面明确指定的文件，程序在第六个已执行命令后探测存在性与非空性，必要时提醒保存草稿。公开检查记录实际退出码。"
                  "F 配置在检查前后和完成声明时核对关联文件内容；依赖发生变化后，旧通过记录失效，智能体可重新执行检查或明确提交部分结果。"),
        table([["配置", "相对于原生智能体的变化"], ["B0", "使用默认决策循环和提交处理。"],
               ["BP", "加入相同的可见检查命令和交付时间提示。"], ["A", "增加交付探测、检查记录及提交处理，允许沿用已有通过记录。"],
               ["F", "在 A 的基础上检查依赖内容，使过期记录失效。"],
               ["RP", "加入阶段性验证提示和剩余预算反馈，保持验证时效与提交控制。"],
               ["R", "在 RP 基础上，中途与提交时自动执行待验证或过期的公开检查。"]], [70, width - 70]),
        heading("实验条件"),
        paragraph("同一题的配置使用相同初始环境的独立隔离容器、原题评分器、CodeBuddy 2.179.3 和 deepseek-v4.1-flash，最多 24 个决策请求及"
                  " 600 秒交互时限，在相邻决策之间检查。追加阶段每题允许两次超时重试，按实际请求计数，逐题表标注重试额度。"
                  "诊断集 D 用于设计和对照，留出集 H 在诊断前冻结，15 道题每配置安排三次。"
                  "本实验未固定服务端采样种子。以原题评分通过为成功，模型终止和提交声明另行统计。"),
        paragraph("全局最多四个任务并发，各容器资源上限固定，宿主机负载未严格固定。"
                  "性能题按各次原题参考结果判定，总耗时比较同时受模型响应、容器及评分执行影响。"),
        paragraph("公开检查由辅助实验开发的 Codex 在准备阶段按题面与初始仓库可见材料逐题编制，"
                  "SWE 选择既有相关回归测试，Terminal 选择交付文件与格式检查，Aider 使用原题可见测试。"
                  "脚本核对题面引用与路径后固定结构化清单；用户提供目标和审查意见，检查规则与执行由助手及程序完成。"
                  "这包含任务级规则设计，尚非通用自动生成检查器，检查通过仍受内容覆盖范围限制。"),
        link("代码、公开检查与复现入口", "https://github.com/CherryQqqqq5/hw0102/tree/main/shared"),
        link("逐题结果、脱敏轨迹与案例证据", "https://github.com/CherryQqqqq5/hw0102/tree/main/%E4%BD%9C%E4%B8%9A%E4%BA%8C"),
        *([heading("留出任务中的时效检查"), paragraph(analysis["holdout_observation"])]
          if analysis.get("holdout_observation") else []),
        *revised_items,
        Spacer(1, 12), heading("原始 B0/F 同题比较"), table(d_table, [158, 63, 64, 64, 64, width - 413]), Spacer(1, 7),
        paragraph(f"{diagnostic['paired_tasks']} 道有效配对的成功率为 {d_before} → {d_after}，差值 {d_delta} 个百分点，"
                  f"相对变化 {d_relative}。其中 {changes.get('gain', 0)} 道由未通过变为通过，{changes.get('loss', 0)} 道退化。"
                  f"F 的诊断集运行记录了 {reminders} 次交付缺失提醒。{uncertainty}"),
        heading("诊断集配对运行开销"), table(cost_table(diagnostic_cohort, ("B0", "F")), cost_widths), Spacer(1, 6),
        paragraph("总用时包含容器、模型、工具与原题评分。请求数包含实际重试。词元合计来自服务实际返回的用量字段，未返回的请求可能没有词元记录。"
                  "费用栏为服务返回的美元字段，课程实验未取得可按运行核对的账号积分扣减明细。"),
        heading(f"留出消融 · {stage}"), table(ablation_rows, [71, 58, 89, 83, 111, width - 412]), Spacer(1, 7),
        paragraph(f"A 与 F 的配对成功率为 {a_before} → {a_after}，差值 {a_delta} 个百分点。留出任务已评分 {h_scoreable}/180 次。"
                  f"留出集中，A 和 F 的完成检查分别记录 {checks['A']} 和 {checks['F']} 个检查项次，其中 F 有 {stale} 个过期项次。"
                  "A 和 F 均启用交付探测，这一消融用于观察验证时效处理的影响。"),
    ]
    if h_scoreable == 180:
        holdout_arms = ("B0", "BP", "A", "F")
        stable_table = [["配置", "首轮通过", "第二轮通过", "第三轮通过", "三轮全通过的题数"]]
        holdout_cohort = [row for row in rows if row["split"] == "H" and row["scoreable"] == "True"]
        for arm in holdout_arms:
            per_repeat = [sum(row["passed"] == "True" for row in holdout_cohort
                              if row["arm"] == arm and int(row["repeat"]) == repeat) for repeat in (1, 2, 3)]
            stable = sum(item["all_repeats_successful"] for item in coverage if item["split"] == "H" and item["arm"] == arm)
            stable_table.append([arm, *per_repeat, stable])
        intervals = [["对照", "差值（百分点）", "95% 区间（百分点）", "涉及请求超时", "排除后差值"]]
        for comparison in holdout:
            low, high = comparison["bootstrap_95_interval_percentage_points"]
            without = comparison["delta_without_provider_timeout_percentage_points"]
            intervals.append([f"{comparison['reference']} → F", f"{comparison['delta_percentage_points']:+.1f}",
                              f"[{low:+.1f}, {high:+.1f}]", 15 - comparison["pairs_without_provider_timeout"],
                              f"{without:+.1f}" if without is not None else "未取得"])
        items.extend([
            Spacer(1, 12), heading("留出集的重复与开销"), table(stable_table, [62, 87, 95, 95, width - 339]), Spacer(1, 7),
            paragraph("每轮各含 15 道题。三轮全通过的题数按同一任务计数。估计成功率变化时对同一题的三次结果取平均，"
                      "然后在各基准内按题做配对重采样，保留题内的重复和配置配对。"),
            table(intervals, [70, 104, 127, 92, width - 393]), Spacer(1, 9),
            paragraph("排除后差值以百分点计，剔除任一对照配置曾遇到提供方请求超时的整道题。"
                      "三项比较删除的均为 django-15554 与 model-extraction-relu-logits，因此排除后仅描述其余 13 题。"
                      "被删记录还包括无超时的错误补丁和正常提交后的数值失败，不能把被删除差距全部归因为超时。"
                      "完整结果以全部 15 道配对为主要分母。"),
            table(cost_table(holdout_cohort, holdout_arms), cost_widths),
        ])
    items.extend([
        Spacer(1, 12), heading("重试条件与主要留出退化"),
        table([["集合/配置", "零次重试额度", "两次重试额度"], ["D/B0", 30, 0], ["D/F", 29, 1],
               ["H/B0", 12, 33], ["H/BP", 12, 33], ["H/A", 13, 32], ["H/F", 13, 32]], [150, 170, width - 320]),
        paragraph("旧配置缺失 timeout_retries 时统一解释为 0，240 份配置复现得到 109 份零重试和 131 份两次重试。"
                  "A/F 的 45 对额度全部一致。D/B0–F 的 Rust doubly-linked-list、H/B0–F 首轮 scikit-learn-10908、"
                  "H/BP–F 第二轮 tune-mjcf 各有一对额度不同；三对双方均通过，只有 Rust F 实际重试一次。"),
        heading("Django · 产物缺失与错误补丁"),
        paragraph("django-15554 的 A 三轮通过、F 三轮失败。六次均无提交声明和精确登记的公开检查，时效机制没有介入。"
                  "F 第一轮第 13 步修改后公开回归出现 23 个错误，第 17 步为比较原行为恢复源码，最终补丁为空。"
                  "第二轮将 j.equals(join) 改为 j == join，目标测试与 22 项既有测试失败。第三轮同样改比较逻辑并删除 Join.equals；"
                  "后续修复脚本抛出断言异常，复合命令最终仍返回 0，保留了错误补丁。直接原因分别为产物未保留和修复引入回归。"),
        heading("模型提取 · 精度与跨实例验证"),
        paragraph("model-extraction-relu-logits 的 A 通过两轮、F 全部失败。F 首轮遇到提供方终止；后两轮正常提交，"
                  "官方分别发现 10、22 行矩阵未满足逐元素比例偏差小于 1e-4 的要求。可见实例为 20 个隐层神经元，"
                  "独立评分采用不同网络参数及 30 行目标矩阵；题面明确形状未知。文件存在和语法检查不能验证数值恢复及跨实例完整性。"
                  "F 第二轮因等价检查命令未被登记多耗约 66.5 秒，第三轮约 15.2 秒，均无证据证明该开销造成最终数值失败。"),
        paragraph("A/F 六次通过差距中，Django 占三次、模型提取占两次、tune-mjcf 占一次。前两题合计 83.3%。"
                  "这些轨迹支持提前执行公开回归、保留候选和独立检验语义，不能将所有差距归结为时效检查。"),
    ])
    items.extend([
        Spacer(1, 12), *analyzed,
        heading("原 F 方案的结论"), paragraph(analysis["conclusion"]),
        paragraph("公开检查覆盖可见条件，原题评分耗时可超过交互时限。诊断题参与机制设计，留出题按同一任务聚合。"
                  "verification.jsonl 记录提醒、重测和提交处理，原题评分单独保存。"),
        heading("改造的收益与适用范围"),
        paragraph("本次最明确的正向任务结果来自阶段反馈 RP：修订十五题中通过15题，同预算基线通过13题，"
                  "改善集中于查询性能和调度约束，实际请求增加22.9%。自动检查 R 通过14题，"
                  "相同补丁案例显示它能减少重复提交，但总体消融未提高通过率。"
                  "当前证据支持将交付、语义验证与预算反馈用于这些已见任务的改进分析；"
                  "样本量、事后配置选择、检查覆盖与服务波动限制了更广泛的结论。"),
    ])
    build(f"{identifier}_作业二.pdf", "作业二 · 智能体改造与验证", items, subtitle=author, footer=footer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignment", type=int, choices=(1, 2), default=1)
    parser.add_argument("--confirmation-batch")
    args = parser.parse_args()
    if args.assignment == 1:
        baseline_report(args.confirmation_batch)
    else:
        improvement_report()
