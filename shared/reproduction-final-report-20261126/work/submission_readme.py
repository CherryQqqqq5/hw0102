from datetime import datetime, timedelta, timezone


def build_submission_readme(commit, data, pdfs, *, focused=False):
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("The submission note requires the exact Git commit")
    if len(pdfs) != 2 or not all(row["github_byte_equal"] is True for row in pdfs):
        raise ValueError("The submission note requires both actually matched remote PDFs")
    date = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    groups = data["groups"]
    lines = ["# 作业一、二完整提交包", "",
        f"GitHub来源：CherryQqqqq5/hw0102，main固定提交`{commit}`。打包日期：{date}（北京时间）。", "",
        "两份PDF均已逐字节核对该固定提交及本地正式报告，完整路径如下：", ""]
    lines.extend(f"- `{row['file']}`，{row['bytes']:,}字节，SHA-256：`{row['sha256']}`。" for row in pdfs)
    contents = ("本包包含两份报告、完整共用代码与配置、原30题诊断记录、最终75题对照与重复、指导消融，"
        "以及报告使用的270条控制实验；未收录备用服务排错与无关旧批次。" if focused else "本包包含该提交全部已跟踪文件，保留代码、配置、原题评分、脱敏交互、采集产物、工程验证与独立审查。")
    lines.extend(["", contents +
        "虚拟环境、容器镜像、SDK大树、登录凭据与API密钥不随包分发。", "",
        "| 本轮实际组别 | 已评分/计划 | 原题通过 |", "|---|---:|---:|"])
    for arm, label in (("main", "最终方法"), ("dsh", "原生DSH对照"), ("repeat", "独立重复")):
        row = groups[arm]
        lines.append(f"| {label} | {row['completed']}/75 | {row['passed']}/{row['completed']} |")
    lines.extend(["", f"最终方法与独立重复各{groups['main']['qualified_passed']}题通过原题评分、公开检查及适用的测试文件保护。"])
    acceptance = data.get("incremental_acceptance")
    if acceptance is not None:
        lines.extend(["", f"局部修订计划含{acceptance['required_inherited_positions']}份输入与运行来源等价的原记录，"
            f"以及{acceptance['required_new_positions']}份固定新会话记录；原225份评分与指导消融分别保存。"])
    lines.extend(["", "阅读顺序：两份PDF、各作业README、shared复现入口，再按逐题索引核对评分和工具轨迹。"
        "离线复算无需模型或容器。", "",
        "打包程序已核对固定Git提交、两份PDF字节、全部所选成员和ZIP完整性。", ""])
    return "\n".join(lines)
