import argparse
import csv
import json
from pathlib import Path
from statistics import median

from reportlab.platypus import PageBreak, Spacer

from render_course_phase_reports import build, heading, link, paragraph, table, width


work = Path("work")
stats = work / "coverage-check"
summary = json.loads((stats / "summary.json").read_text())
with (stats / "trials.csv").open() as stream:
    rows = list(csv.DictReader(stream))

labels = {"swe": "SWE-bench Verified", "terminal": "Terminal-Bench 2.1", "aider": "Aider Polyglot"}
identifier = "231880296_邱昱宁"
author = "邱昱宁  ·  231880296"
footer = "智能推理与规划 · 邱昱宁"


def baseline_report(confirmation_batch: str | None = None) -> None:
    task_records = json.loads((work / "hw0102-publish/作业一/evidence/task-records.json").read_text())["records"]
    task_index = {record["task"]: record for record in task_records}
    coverage = {row["benchmark"]: row for row in summary["coverage"] if row["split"] == "D" and row["arm"] == "B0"}
    baseline = [row for row in rows if row["split"] == "D" and row["arm"] == "B0"]
    if len(baseline) != 30 or any(coverage[key]["scoreable"] != 10 for key in labels):
        raise ValueError("The final baseline report requires 30 valid benchmark scores")
    overview = [["基准", "有效评分", "通过", "未通过", "通过率"]]
    for key, label in labels.items():
        item = coverage[key]
        overview.append([label, 10, item["success"], 10 - item["success"], f"{item['success'] / 10:.0%}"])
    successes = sum(item["success"] for item in coverage.values())
    overview.append(["合计", 30, successes, 30 - successes, f"{successes / 30:.1%}"])
    valid_responses = sum(int(row["model_responses"]) for row in baseline)
    calls = sum(int(row["model_calls"]) for row in baseline)
    input_tokens = sum(int(row["input_tokens"]) for row in baseline)
    output_tokens = sum(int(row["output_tokens"]) for row in baseline)
    case_items = [
        heading("代表案例与归因"),
        paragraph("视频处理 · video-processing。第 1 次调用发现缺少 toml 模块，但第 14 次调用写出的脚本已可导入。"
                  "第 3 至 13 次反复探索前景和轮廓，留给示例验证的时间较少。原题验收的两段视频起跳帧为 66 和 322，"
                  "超出允许区间 50–54 和 219–223。直接失败是定位输出不准确。题面没有标准帧标签，"
                  "公开检查可以验证产物结构和可执行性，定位精度仍需独立验收。"),
        paragraph("查询优化 · query-optimize。第 8 步的临时候选在 2.425 秒返回 500 行，第 9 步在临时索引副本上"
                  "记录候选与原查询输出相同。第 4、5、10 步触及命令时限，最后未写入 /app/sol.sql，原题四项测试因此失败。"
                  "先保存可运行草稿后，原题才可分别检查正确性、效率、语句数和长度。"),
        paragraph("本地邮件列表 · mailman。补跑第 14、18 步仍返回 124，第 17 步已看到邮件送达和回复确认后入组。"
                  "智能体以 TimeExceeded 终止，独立评分器验证本地投递、列表存在、入组及公告与退出，三项通过。"
                  "命令时限、智能体终止和服务产物质量分别记录。"),
        paragraph("批处理调度 · llm-inference-batching-scheduler。两次旧尝试都因模型请求超时而无评分。"
                  "补跑第 8 步脚本正常退出，但两个请求桶的八组设置均未达本地指标。第 9 次请求超时后，"
                  "原题评分器发现 plan_b1.jsonl 缺失，五项测试失败。尽早落盘可以检查候选，已观察到的性能超限仍需解决。"),
        paragraph("二进制地址提取 · extract-elf。第 5 步已写脚本，第 12 步完成 698 项本地检查并报告零不一致。"
                  "原题确认程序可执行，但参考地址覆盖率为 0.00%，低于 75%。本地检查沿用实现的固定 0x400000 基址和相同地址映射，"
                  "因此未独立检验地址定义。已确认的失败是地址集合未覆盖参考结果，地址映射或表示不一致是有依据的原因假设。"
                  "终止状态 TimeExceeded 无法单独解释零覆盖率。"),
        paragraph("诊断笔记列出各案例的逐步工具记录、原题评分与归因边界。"),
        paragraph("跨基准对照。Aider 的 go/variable-length-quantity 在第 3 步测试发现两字节序列的解码值错误，"
                  "第 4 步修正后同套测试通过，正式评分也通过。SWE-bench 的 xarray-6599 在第 11 步修改源码，"
                  "虽以 TimeExceeded 终止，官方仍判定补丁解决问题。两例分别体现公开测试覆盖任务语义、先保存候选的价值。"),
        heading("错误机制与改进"),
        paragraph("第一类是验证范围不足。脚本能导入、运行或产出格式正确的文件，仍可能在任务语义或精度上失败。"
                  "将格式、可运行性和任务语义分成独立检查，并标明公开检查的覆盖边界。第二类是探索与交付脱节。"
                  "存在可运行的临时候选时，后续诊断可能耗尽预算，最终路径仍为空。为显式交付路径设置早期检查点，"
                  "将草稿落盘和改进过程连接起来。提供方与容器故障单独记录。"),
        table([["互斥主机制", "实际失败题", "数量", "改进与验证边界"],
               ["产物交付", "query-optimize；批处理调度", "2/4", "先保存指定路径；保存后仍须检验等价性与性能"],
               ["语义精度", "video-processing", "1/4", "增加独立精度验证；提前实现能否修复尚未验证"],
               ["验证范围不足", "extract-elf", "1/4", "独立检验地址含义；避免实现与自查共用未经检验假设"]],
              [90, 135, 40, width - 265]),
        paragraph("以上为对4条真实失败进行的人工主机制编码，每题归入一类，分母为全部4条失败。"
                  "它们均来自Terminal任务；SWE-bench与Aider在当前各10题中未见原评分失败，不能据此推断不存在错误。"
                  "调度题的提供方超时和多题交互截止另记为伴随因素，不替代具体产物或断言归因。"
                  "公开检查改善是否带来净收益，由作业二的同题比较及消融检验。"),
    ]
    items = [
        heading("任务抽样与固定条件"),
        paragraph("SWE-bench Verified 检查真实软件缺陷修复，Terminal-Bench 2.1 检查终端环境中的多步执行，"
                  "Aider Polyglot 检查跨语言编程和可执行测试。三套基准分别按仓库、终端任务类型和编程语言覆盖抽样，"
                  "各冻结 10 道诊断题和 5 道留出题。45 道题均经起始状态和参考解评分对照，完整候选与排除理由见冻结清单。"),
        paragraph("候选数据分别含 SWE-bench 500 题、Terminal-Bench 89 题、Aider 225 题。SWE 仅保留小于 15 分钟或 "
                  "15 分钟至 1 小时修复标签，并要求可用官方评分镜像；正式样本来自 Django、xarray、scikit-learn、pytest 四个仓库，"
                  "偏向短修复。Terminal 限每题不超过 2 个处理器核心、3072 MB 内存、单容器和离线运行；"
                  "运行时需下载模型或数据、参考解离线失败的题被排除。"),
        paragraph("Aider 按 C++、Go、Java、JavaScript、Python、Rust 六语言覆盖抽样，D 数量依次为 2、2、1、2、2、1。"
                  "预检排除参考解缺离线依赖的 Rust alphametics，以及起始实现已经通过的 Go markdown、ledger。"
                  "这些规则先于正式模型评测，限制了样本范围。"),
        paragraph("基线使用 mini-SWE-agent 2.4.6 和 CodeBuddy 2.179.3，模型固定为 deepseek-v4.1-flash。"
                  "每题最多 24 次模型请求，模型调用之间检查 600 秒交互时限，单次模型请求上限 150 秒，"
                  "单条容器命令上限 60 秒。已发出的请求和独立评分会增加实际耗时。智能体容器与评分证据隔离。"),
        paragraph("Aider 部分为“Aider Polyglot 任务子集上的 mini-SWE-agent 评测”，原测试对模型可见，"
                  "使用本实验的交互预算和提交方式；结果仅在上述条件下比较，不直接对应官方 Aider 排行榜。"),
        heading("基准结果"), table(overview, [171, 82, 70, 70, width - 393]), Spacer(1, 7),
        paragraph(f"共记录 {calls} 次模型请求、{valid_responses} 次响应、{input_tokens:,} 个服务报告输入词元和 "
                  f"{output_tokens:,} 个输出词元。未返回响应的调用可能缺少用量。通过率以各基准的 10 道有效评分为分母。"),
        paragraph("SWE-bench 由官方 resolved 指标判定，Terminal-Bench 使用 Harbor 的原题奖励，Aider 以原题测试全通过判定。"
                  "模型超时后由原题评分器检查实际留下的产物，提供方超时单列。评分通过和智能体提交声明分别统计。"),
        PageBreak(), *case_items, heading("逐题结果与证据索引"),
        paragraph("完整记录采用JavaScript Object Notation（JSON，JavaScript对象表示法），表格索引采用"
                  "Comma-Separated Values（CSV，逗号分隔值）。逐题目标与预期行为见下表，具体输入和原验收路径见附件。"),
    ]
    for key, label in labels.items():
        items.append(heading(label))
        details = [["任务", "任务目标与预期行为", "原评分", "终止状态"]]
        for row in baseline:
            if row["benchmark"] == key:
                details.append([row["task"], task_index[row["task"]]["task_description"],
                                "通过" if row["passed"] == "True" else "未通过", row["exit_status"] or "见轨迹"])
        items.extend([table(details, [161, 188, 45, width - 394]), Spacer(1, 5)])
    items.extend([
        heading("局限性"),
        paragraph("每套只有 10 道诊断题，且偏向资源有限、可离线评分与较短修复的任务，结果适用于当前抽样范围和运行条件。"
                  "首轮 xarray 轨迹读取了镜像内缓存的较新版本源码。屏蔽缓存后重新执行，隔离前的尝试另存。"
                  "SWE-bench Verified 公开题目还存在训练暴露与测试覆盖问题，不能从本结果推断一般软件工程能力。"),
        paragraph("仓库作业一目录中的 evidence/formal-trials.csv 可逐题复算，evidence/formal/ 保存命令、"
                  "脱敏可见模型交互、产物及评分日志。原始启动异常和重复提供方超时证据分别保留。"),
        paragraph("evidence/task-records.json逐题收录完整任务输入、预期评分标准、实际原评分、执行与最终产物路径、"
                  "初步归因及原验收日志路径；task-records.csv提供相同索引，完整输入以JSON为准。"
                  "本表的通过表示原题resolved、奖励1或原题测试全通过；失败的具体断言及过程见对应记录，"
                  "未将模型完成声明或工具退出状态直接当作成绩。辅助实现、分析与报告整理使用Codex，实测结果以保存原件为依据。"),
        link("作业一证据目录", "https://github.com/CherryQqqqq5/hw0102/tree/main/%E4%BD%9C%E4%B8%9A%E4%B8%80"),
        link("课程说明", "https://nju-link-lab.feishu.cn/wiki/QLwBwXov6iHjsJkeBPLck9AUncc"),
        link("Aider Polyglot原始任务与固定版本7e0611e7", "https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"),
        link("SWE-bench Verified原始数据与固定版本78f471bf", "https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/tree/78f471bf655a3137b2e8a75af1501690ec009ec3"),
        link("Terminal-Bench 2.1原始任务与固定版本7131e437", "https://github.com/harbor-framework/terminal-bench-2-1/tree/7131e4375048a0e408a8fb404b5f499d726b695b"),
        link("SWE-bench 官方评测程序", "https://www.swebench.com/SWE-bench/reference/harness/"),
        link("SWE-bench Verified 覆盖与训练暴露审查", "https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/"),
    ])
    if confirmation_batch is not None:
        complete = work / (confirmation_batch + "-summary")
        confirmed_rows = json.loads((complete / "trials.json").read_text())
        confirmed = json.loads((complete / "summary.json").read_text())
        audit = json.loads((work / (confirmation_batch + "-source-audit.json")).read_text())
        if len(confirmed_rows) != 270 or any(not row["scoreable"] for row in confirmed_rows):
            raise ValueError("The baseline update requires all 270 original confirmation scores")
        if audit["batch"] != confirmation_batch or audit["primary_positions"] != 270:
            raise ValueError("The baseline update requires the matching complete source audit")
        if audit["free_billing"]["missing_responses"] or audit["free_billing"]["reported_credit_for_returned_responses"] != 0:
            raise ValueError("The new baseline has missing or nonzero actual billing")
        grouped = {row["benchmark"]: row for row in confirmed["coverage"] if row["arm"] == "B0"}
        new_baseline = grouped["all"]
        if new_baseline["trials"] != 90:
            raise ValueError("The free baseline requires three scored repeats for each of 30 tasks")
        items.extend([
            PageBreak(), heading("免费模型重复基线复测"),
            paragraph("在另一份固定30题清单上，以hy4flash-free执行三条件、每题三轮共270个位置，"
                      "其中原生基线B0有90次独立原题评分。该集合曾用于服务复测，属于固定任务重复评测。"
                      "原报告的30道诊断题和本次30道任务分别记录，不将不同模型、题单及预算口径的成绩相加。"),
            table([["基准", "B0原题通过", "三轮均通过题数", "模型请求"],
                *[[label, f"{grouped[key]['success']}/{grouped[key]['trials']}",
                   f"{grouped[key]['all_three_successful_tasks']}/10", grouped[key]["model_calls"]]
                  for key, label in labels.items()],
                ["合计", f"{new_baseline['success']}/90（{new_baseline['success_rate']:.1%}）",
                 f"{new_baseline['all_three_successful_tasks']}/30", new_baseline["model_calls"]]],
                [145, 135, 110, width - 390]),
            paragraph("本次每题24次决策、600秒内部硬时限、60秒命令、4096输出词元上限，无额外请求重试。"
                      "每条实际服务回复均验证免费模型身份及零积分；未评分和历史未知费用单独保留，"
                      "不能作为有效失败或零费用填入成绩。客户端截断、轮数异常及输出传输修复按来源版本记录。"
                      "作业二给出三条件配对比较、成本、失败案例和解释限制。"),
            paragraph(audit.get("comparison_limitations", "各来源执行版本分别保留。")),
            heading("推理耗尽而未形成工具动作"),
            paragraph("免费B0的90次原评分中，20次以RepeatedFormatError退出，其中19次原题失败、1次仍通过。"
                      "polyglot-rust-c第二轮的三次实际请求，各输出4096个推理词元，合计12288，均没有工具动作，原题失败。"
                      "后两次请求只在原题后增加短动作错误提示，保存历史分别为2、3条user消息，没有失败原生assistant状态。"
                      "此处错误发生在工具执行之前，重复提醒仍受相同输出上限约束，后续结果验证没有机会处理未生成的候选。"),
            paragraph("同题第一轮第2个命令行客户端（Command-Line Interface，CLI）请求包含4096、4096、3650三段原生输出，最终形成动作，记录truncation_recovered且原题通过。"
                      "首轮B0为29/30，第二、三轮为19/30和20/30；客户端续接与外层恢复的版本变化同时发生，不能只归因于模型能力或某一控制模块。"
                      "改进假设是在相同总预算内保留原生状态、限制续接并给动作保留额度；本轮只分析原记录，没有运行新恢复方案。"
                      "这组补充案例不并入原30道诊断题的4条失败分类，完整逐段用量及请求历史角色见作业二的course-execution-failure-analysis-20261118.json。"),
            paragraph(f"本次基线已返回输入{new_baseline['input_tokens']:,}、输出{new_baseline['output_tokens']:,}词元，"
                      f"运行总用时中位数{new_baseline['median_wall_seconds']:.1f}秒。"
                      f"完整逐位置成绩及来源见作业二/evidence/{confirmation_batch}-summary/，"
                      "原题评分与实际费用由匹配的source-audit.json核验。"),
            link("免费模型冻结协议", "https://github.com/CherryQqqqq5/hw0102/commit/" + audit["protocol_commit"]),
        ])
    build(f"{identifier}_作业一.pdf", "作业一 · 基线评测与错误分析", items, subtitle=author, footer=footer)


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
