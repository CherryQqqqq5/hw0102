def build_submission_readme(commit, data, pdfs, *, focused=False, efficiency=None, interruption_cost=None):
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("The submission note requires the exact Git commit")
    if len(pdfs) != 2 or not all(row["github_byte_equal"] is True for row in pdfs):
        raise ValueError("The submission note requires both actually matched remote PDFs")
    groups = data["groups"]
    lines = ["# 作业一、二完整提交包", "",
        f"GitHub来源：CherryQqqqq5/hw0102，固定提交`{commit}`。", "",
        "两份PDF均已逐字节核对该固定提交及正式报告，完整路径如下：", ""]
    lines.extend(f"- `{row['file']}`，{row['bytes']:,}字节，SHA-256：`{row['sha256']}`。" for row in pdfs)
    contents = ("本包包含两份报告、完整共用代码与配置、原30题诊断记录、最终75题对照与重复、指导消融，"
        "以及报告使用的历史控制实验。" if focused else "本包包含该提交全部已跟踪文件，保留代码、配置、原题评分、脱敏交互、采集产物、工程验证与独立审查。")
    lines.extend(["", contents, "",
        "| 75题性能评测 | 已评分/计划 | 原题通过 |", "|---|---:|---:|"])
    for arm, label in (("main", "最终方法"), ("dsh", "原生DSH对照"), ("repeat", "独立重复")):
        row = groups[arm]
        lines.append(f"| {label} | {row['completed']}/75 | {row['passed']}/{row['completed']} |")
    lines.extend(["", f"最终方法与独立重复各{groups['main']['qualified_passed']}题通过原题评分，适用的公开检查和测试文件保护均合格。"])
    acceptance = data.get("incremental_acceptance")
    if acceptance is not None:
        lines.extend(["", f"局部修订计划含{acceptance['required_inherited_positions']}份输入与运行来源等价的原记录，"
            f"以及{acceptance['required_new_positions']}份固定新会话记录；原225份评分与指导消融分别保存。"])
    if efficiency is not None:
        study, repeat = efficiency["study"], efficiency["repeat"]
        labels = {"base": "原始C0", "environment": "环境提示C0", "digest": "长输出精简C0", "dsh": "原生DSH"}
        lines.extend(["", "新增效率实验包含三题诊断和六题配置对照，按预定规则选择后续配置。",
            "", "| 六题效率对照 | 原题通过 | 总词元 |", "|---|---:|---:|"])
        for arm, label in labels.items():
            if arm in study["by_configuration"]:
                group = study["by_configuration"][arm]
                lines.append(f"| {label} | {group['passed']}/6 | {group['tokens']:,} |")
        chosen = study["chosen_configuration"]
        if chosen is not None and chosen not in labels:
            group = study["by_configuration"][chosen]
            lines.append(f"| 所选组合 | {group['passed']}/6 | {group['tokens']:,} |")
        if repeat["stage"] == "complete":
            group = repeat["summary"]
            lines.append(f"| 所选配置独立重复 | {group['passed']}/6 | {group['tokens']:,} |")
        lines.extend(["", "逐题结果、选择记录及完整轨迹见`作业二/evidence/input-efficiency-20261127/`和同名ZIP；"
            "相应源码与依赖说明见`shared/reproduction-input-efficiency-20261127/`。"])
    if interruption_cost is not None:
        lines.extend(["", f"另一次追加复核尝试已停止：{interruption_cost['known_zero']}笔有自身零积分回执，"
            f"{len(interruption_cost['unknown'])}笔费用待核验，未纳入性能成绩。"
            f"{interruption_cost['historical_unknown']}笔历史未知继续保留，费用停止保持有效。"
            "逐笔原生回执与独立核查见`作业二/evidence/input-efficiency-cost-history-20261127/`。"])
    lines.extend(["", "阅读顺序：两份PDF、各作业README、共享源码和运行说明，再按逐题索引核对评分和工具轨迹。"
        "提供离线复核命令，可直接从保存的记录复算成绩和用量。", "",
        "打包程序已核对固定Git提交、两份PDF字节、全部所选成员和ZIP完整性。", ""])
    return "\n".join(lines)
