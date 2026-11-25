from datetime import datetime, timedelta, timezone


def build_submission_readme(commit, data, pdfs):
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
    lines.extend(["", "本包包含该提交全部已跟踪文件，保留代码、配置、原题评分、脱敏交互、采集产物、工程验证与独立审查。"
        "虚拟环境、容器镜像、SDK大树、登录凭据与API密钥不随包分发。", "",
        "| 本轮实际组别 | 已评分/计划 | 原题通过 |", "|---|---:|---:|"])
    for arm, label in (("main", "最终方法"), ("dsh", "原生DSH对照"), ("repeat", "独立重复")):
        row = groups[arm]
        lines.append(f"| {label} | {row['completed']}/75 | {row['passed']}/{row['completed']} |")
    lines.extend(["", f"最终方法与独立重复分别有{groups['main']['qualified_passed']}和"
        f"{groups['repeat']['qualified_passed']}个位置同时满足已登记的原评分与适用的终局验证要求。"
        "原始固定批次和任务局部修订分别留证，没有把旧失败覆盖成修订后成功。"])
    acceptance = data.get("incremental_acceptance")
    if acceptance is not None:
        lines.extend(["", f"局部修订计划含{acceptance['required_inherited_positions']}份输入与运行来源等价的原记录，"
            f"以及{acceptance['required_new_positions']}份固定新会话记录。完整原225个预定评分位置、被替代的原始结果、"
            "早期JSON开发、指导消融和机械中断开销分别保存，不重复累计为新增成功。"])
    lines.extend(["", f"费用记录保留{data['historical_unknown_calls_preserved']}笔历史未知，缺失金额和用量未填零。"
        "Hy4按每笔自身新身份与真实零积分核验；NVIDIA辅助记录按已授权的官方免费范围及实际身份、用量核验，"
        "缺少逐笔金额仍为null，并与Hy4同模型比较分开。", "",
        "原作业一诊断、早期270条控制配置实验及其他版本的真实通过、未通过和无分中断均保留。"
        "报告中的原题通过、公开功能检查、候选或文件保护和方法作用具有各自范围，以两份报告及对应来源记录为准。", "",
        "阅读顺序：两份PDF、各作业README、shared中的执行与复现说明，再按逐题索引检查原评分和交互。"
        "离线核查使用保存记录及明确不发模型请求的命令；重新运行模型需要另行准备原题数据、固定容器、依赖和免费模型权限。", "",
        "打包程序已核对固定Git提交、两PDF字节、成员完整性与ZIP校验。此次打包不发模型请求，不重跑原题评分器。", ""])
    return "\n".join(lines)
