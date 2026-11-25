import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle


root = Path.cwd()
work = root / "work"
output = root / "outputs"
font = "CourseCJK"
pdfmetrics.registerFont(TTFont(font, "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"))
ink = colors.HexColor("#172434")
muted = colors.HexColor("#4F6275")
accent = colors.HexColor("#145E61")
rule = colors.HexColor("#D2DCE1")
page_width, page_height = A4
margin = 52
width = page_width - 2 * margin
title_style = ParagraphStyle("Title", fontName=font, fontSize=23, leading=32, textColor=ink, spaceAfter=12)
subtitle_style = ParagraphStyle("Status", fontName=font, fontSize=10.5, leading=16, textColor=accent, spaceAfter=13)
heading_style = ParagraphStyle("Heading", fontName=font, fontSize=14, leading=22, textColor=accent,
                               spaceBefore=11, spaceAfter=5, keepWithNext=True)
body_style = ParagraphStyle("Body", fontName=font, fontSize=10.7, leading=17.8, alignment=TA_LEFT,
                            textColor=ink, spaceAfter=7, wordWrap="CJK")
cell_style = ParagraphStyle("Cell", parent=body_style, fontSize=9.4, leading=14, spaceAfter=0)
header_style = ParagraphStyle("HeaderCell", parent=cell_style, textColor=accent)


def paragraph(value: str) -> Paragraph:
    return Paragraph(escape(value), body_style)


def heading(value: str) -> Paragraph:
    return Paragraph(escape(value), heading_style)


def link(label: str, address: str) -> Paragraph:
    return Paragraph(f'<link href="{escape(address)}" color="#145E61">{escape(label)}</link>', body_style)


def table(rows: list[list[str]], column_widths: list[float]) -> LongTable:
    data = [[Paragraph(escape(str(value)), header_style if index == 0 else cell_style) for value in row]
            for index, row in enumerate(rows)]
    result = LongTable(data, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F2F1")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, accent),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, rule),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return result


def draw_page(canvas, doc, footer: str) -> None:
    canvas.setStrokeColor(rule)
    canvas.setLineWidth(0.6)
    canvas.line(margin, 40, page_width - margin, 40)
    canvas.setFont(font, 8.6)
    canvas.setFillColor(muted)
    canvas.drawString(margin, 25, footer)
    canvas.drawRightString(page_width - margin, 25, str(doc.page))


def build(filename: str, title: str, items: list, *, subtitle: str = "阶段稿   ·   2026 年 11 月 4 日",
          footer: str = "智能推理与规划 · 课程作业阶段稿") -> None:
    doc = SimpleDocTemplate(str(output / filename), pagesize=A4, title=title,
                            leftMargin=margin, rightMargin=margin, topMargin=50, bottomMargin=53)
    def on_page(canvas, document):
        draw_page(canvas, document, footer)

    doc.build([Paragraph(escape(title), title_style), Paragraph(escape(subtitle), subtitle_style), *items],
              onFirstPage=on_page, onLaterPages=on_page)


if __name__ == "__main__":
    summary = json.loads((work / "coverage-check/summary.json").read_text())
    diagnosis = {row["benchmark"]: row for row in summary["coverage"] if row["split"] == "D" and row["arm"] == "B0"}
    coverage_rows = [["基准", "计划", "已派发", "可评分", "通过", "未通过"]]
    labels = {"swe": "SWE-bench Verified", "terminal": "Terminal-Bench 2.1", "aider": "Aider Polyglot"}
    for key, label in labels.items():
        row = diagnosis[key]
        coverage_rows.append([label, row["planned"], row["started"], row["scoreable"], row["success"],
                              row["scoreable"] - row["success"]])
    fields = ["planned", "started", "scoreable", "success"]
    totals = {field: sum(row[field] for row in diagnosis.values()) for field in fields}
    coverage_rows.append(["合计", *[totals[field] for field in fields], totals["scoreable"] - totals["success"]])
    build("作业一_基线评测与错误分析_阶段稿.pdf", "作业一 · 基线评测与错误分析", [
    heading("评测范围与评分"),
    paragraph("三套基准各选 10 道诊断题和 5 道留出题。45 道题均通过原始状态和上游参考解的评分对照后冻结。"
              "基线采用 mini-SWE-agent 2.4.6 的默认决策循环，连接已登录的 CodeBuddy 2.179.3，固定模型 deepseek-v4.1-flash。"
              "每题最多 24 次模型请求，智能体在相邻请求之间检查 600 秒交互时限。已发出的请求和独立评分可能延长总时间。"),
    paragraph("模型只接收题面、可见代码与实际工具结果。SWE-bench 使用官方评分器，Terminal-Bench 由 Harbor 执行原题验收，"
              "Aider Polyglot 使用原题测试。SWE-bench 的智能体与评分器及其余两套智能体容器均关闭外部网络。"),
    heading("正式基线覆盖"),
    table(coverage_rows, [167, 62, 65, 65, 65, width - 424]), Spacer(1, 8),
    paragraph(f"已取得 {totals['scoreable']} 道有效评分，其中 {totals['success']} 道通过。两道已派发题未取得评分，"
              f"另有 {totals['planned'] - totals['started']} 道尚未派发。SWE-bench 的 10/10 仅描述本次抽样和环境。"),
    paragraph("逐题表、可评分分母、原始轨迹和评分日志见证据包。阶段稿已有两例正式失败分析，仍缺完整的 30 道评测和后续代表案例复核。"),
    link("课程说明", "https://nju-link-lab.feishu.cn/wiki/QLwBwXov6iHjsJkeBPLck9AUncc"),
    link("SWE-bench 官方评测程序", "https://www.swebench.com/SWE-bench/reference/harness/"),
    PageBreak(),
    heading("案例一 · 视频起跳帧定位偏差"),
    paragraph("在 video-processing 上，第 1 次工具调用发现容器缺少 toml 模块。第 3 至 13 次调用反复检查轮廓和帧特征，"
              "第 14 次才写出可导入的脚本。示例视频与另一段验收视频分别得到起跳帧 66 和 322，超出原题区间 50–54 和 219–223。"
              "评分确认脚本可以导入，失败发生在定位输出。智能体到达时限，没有发出完成声明。"),
    paragraph("原题示例能验证脚本是否运行以及输出的字段结构，题面没有给出示例的标准帧号。提前写出脚本会增加验证时间，"
              "现有轨迹无法判断是否足以修复定位偏差。证据见 D-terminal-video-processing-B0-r1 的工具轨迹与验收输出。"),
    heading("案例二 · 查询产物留在临时路径"),
    paragraph("在 query-optimize 上，第 7 次工具调用在约 3.9 秒内执行临时候选查询并输出 500 行。之后继续检查数据分布和索引，"
              "到达时限时仍未写入题面指定的 /app/sol.sql。原数据库完整性检查通过，另有 4 项因缺少最终文件而失败。"),
    paragraph("候选查询的退出码和行数只支持可运行性，无法证明与原查询逐行一致。该例的直接失败是未在指定路径交付产物。"
              "证据见 D-terminal-query-optimize-B0-r1 的工具轨迹与验收输出。"),
    heading("运行中断与证据边界"),
    paragraph("批处理调度题的两次尝试分别在第 7 次和第 6 次 CodeBuddy 请求超过 150 秒，均无评分。并行的 Mailman 题"
              "遇到容器内命令超时，评分未运行。恢复前保留这些记录，继续沿用冻结的任务清单。"),
    paragraph("较早一轮 xarray 轨迹读取了镜像内缓存的新版源码。程序隔离软件包缓存后重新启动基线，"
              "旧环境的四次尝试另行保存。隔离版 xarray 产物通过官方测试，智能体以时限终止。两类状态分别统计。"),
])

if __name__ == "__main__":
    build("作业二_智能体改造与验证_阶段稿.pdf", "作业二 · 智能体改造与验证", [
    heading("待检验的问题"),
    paragraph("智能体执行公开检查之后，继续修改源文件或测试依赖时，早先的成功结果可能失效。改造记录每次检查及其依赖，"
              "在智能体声明完成时判断证据是否仍适用。可测试的目标是减少使用过期检查的完成声明，并测量对独立验收成功率和运行成本的影响。"),
    paragraph("作业一已有两个正式失败案例。一个是视频定位偏差，另一个是查询候选未写入最终路径。两次均在时限处终止，"
              "没有触发提交检查。因此这两条轨迹支持分析交互过程和交付边界，不能用于断言提交验证能够修复这两题。"),
    heading("实现位置与配置"),
    paragraph("course_eval/verification.py 保存检查命令、题面原文和依赖路径。工具适配器记录实际退出码。完整配置在执行检查前后"
              "计算依赖文件的 Secure Hash Algorithm 256-bit（SHA-256，256 位安全散列），并在完成声明时重新比较。"
              "缺少有效证据时返回未完成项。智能体也可以用明确的部分完成声明提交当前产物。"
              "独立评分器始终依据实际产物判分。"),
    table([
        ["配置", "提示与程序行为"],
        ["B0 原生基线", "保持默认决策循环与提交处理。"],
        ["BP 文字提示", "加入与改造一致的公开检查说明，依靠智能体遵循。"],
        ["A 时效消融", "检查实际执行是否通过，完成时沿用已有通过记录。"],
        ["F 完整改造", "执行同一检查和完成控制，比较相关文件内容并使旧检查失效。"],
    ], [112, width - 112]), Spacer(1, 8),
    PageBreak(),
    heading("已验证的程序行为"),
    paragraph("在 Aider 的 python/proverb 容器中，原题测试通过后改变被测源文件。F 把原验证标记为过期并暂停完成声明，"
              "A 仍接受已有的通过记录。独立日志的变化没有使 F 的证据过期，恢复源文件并重测后 F 接受提交。"
              "这一实验使用实际文件与测试程序，模型请求数为 0。"),
    paragraph("另一次 CodeBuddy 试跑将请求上限设为 1。智能体以 LimitsExceeded 终止，产物保存成功，原题评分正常返回未通过。"
              "Harbor 的独立命令超时测试也确认容器能返回 124 并正常执行下一条命令。"),
    heading("正式对照状态"),
    paragraph("诊断集原计划在 30 道题上比较 B0 与 F。留出集冻结了 15 道题，按 B0、BP、A、F 四种配置各重复三次。"
              "当前 F 的 30 次诊断题对照和 180 次留出对照均未启动。没有改造后的任务成功率、相对增益或消融效应。"),
    paragraph("正式统计按同题配对。留出集先对每题的三次结果取平均，同时单列三次均通过的题数。最终报告将区分成功率、"
              "错误完成声明、模型请求、独立评分耗时和服务返回的费用字段。账号实际积分消耗需另行核实。"),
    paragraph("实现和真实控制记录见证据包的 course_eval/、evidence/verification-proverb/ 及 evidence/formal-coverage.json。"),
    link("课程说明", "https://nju-link-lab.feishu.cn/wiki/QLwBwXov6iHjsJkeBPLck9AUncc"),
])
