import hashlib
import json
from pathlib import Path

from render_course_phase_reports import paragraph, subheading, table, width


LABELS = {"base": "原始C0", "dsh": "原生DSH", "environment": "环境提示C0",
    "digest": "长输出精简C0", "dsh-aider-env-swe": "Aider使用DSH、SWE使用环境提示C0的方案",
    "dsh-aider-digest-swe": "Aider使用DSH、SWE使用精简C0的方案"}


def read(path):
    return json.loads(path.read_text())


def load(directory):
    directory = Path(directory)
    study, repeat = read(directory / "study-results.json"), read(directory / "repeat-results.json")
    review = read(directory / "final-study-review.json")
    index = directory / "index.json"
    exported = {entry["path"]: entry for entry in read(index)["files"]} if index.exists() else {}
    if exported:
        for name in ("study-results.json", "repeat-results.json", "final-study-review.json"):
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != exported[name]["export_sha256"]:
                raise ValueError("A portable result or review changed after export")
    for name, key in (("study-results.json", "source_summary_sha256"),
            ("repeat-results.json", "source_repeat_sha256")):
        source_hash = exported[name]["source_sha256"] if exported else hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if source_hash != review[key]:
            raise ValueError("The reviewed efficiency result changed")
    if (review["blocking_findings_remaining"] != 0 or study["stage"] != "complete"
            or repeat["stage"] not in {"complete", "not_started"}):
        raise ValueError("Complete and independently review the registered efficiency study first")
    return {"study": study, "repeat": repeat}


def method(base_data):
    comparison = base_data["comparisons"]["all75"]
    left, right = comparison["left"], comparison["right"]
    total = left["input_tokens"] + left["output_tokens"]
    reference = right["input_tokens"] + right["output_tokens"]
    extra = 100 * (total / reference - 1)
    input_share = 100 * (left["input_tokens"] - right["input_tokens"]) / (total - reference)
    return [subheading("2.3 减少额外输入"),
        paragraph(f"75题性能方案比DSH多用{extra:.1f}%词元，增加部分的{input_share:.1f}%来自输入。"
            "据此比较两种输入调整：给出实际工作目录、解释器和可见测试入口，减少环境寻找；"
            "对后续命令产生的长输出归档并按需读取。"),
        paragraph("两组均归档超过6000字符的命令输出。精简组仅对退出码为0的长输出呈现首尾与关键行，"
            "同时给出完整日志路径，供模型按需读取。既往对话、检查与提交规则保持。")]


def setting():
    return [subheading("3.3 新增任务的效率对照"),
        paragraph("先在3道已定位开销问题的题上比较原始C0、环境提示C0、长输出精简C0。"
            "再在事前固定的6道新增题上比较这三组及原生DSH，Aider和SWE-bench各3题；这些题在本轮开始前未参与本项目配置选择。"
            "软件题各组均要求根据可见题面编写复现与断言，任务结果由原题评分器独立验收。"
            "环境提示给出实际工作目录、解释器及测试入口；精简组与环境组仅改变后续长输出的呈现。"
            "另按事前规则组合Aider的DSH记录与软件题的两种C0记录，参与同一配置选择。"),
        paragraph("新增实验在ModelArts的4核、8 GiB Linux虚拟机上逐题独占执行，模型仍为hy4flash-free。"
            "每题最多500次实际调用、1800秒求解、单命令120秒、单次64000输出词元，原题评分另计。"
            "事前规则要求6题原评分全部通过、C0最终检查合格，较环境组每道通过题的词元至少减少10%，"
            "用时中位数和最大值均不超过其110%；"
            "从符合条件的配置中选择总词元最低者，再用新容器、新会话独立重复6题。"
            "每道通过题的词元以整组总词元除以原题通过数计算。")]


def results(data):
    study, repeat = data["study"], data["repeat"]
    groups = study["by_configuration"]
    diagnostic = {arm: sum(row["total_tokens"] for row in study["rows"]
        if row["stage"] == "diagnostic" and row["arm"] == arm)
        for arm in ("base", "environment", "digest")}
    reduced = 100 * (1 - diagnostic["digest"] / diagnostic["environment"])
    increased = 100 * (diagnostic["digest"] / diagnostic["base"] - 1)
    rows = [["配置", "原题通过", "模型调用", "总词元", "中位秒", "最长秒"]]
    names = [name for name in ("base", "dsh", "environment", "digest") if name in groups]
    chosen = study["chosen_configuration"]
    if chosen is not None and chosen not in names:
        names.append(chosen)
    for name in names:
        group = groups[name]
        label = LABELS[name] if name in {"base", "dsh", "environment", "digest"} else "所选组合"
        rows.append([label, f"{group['passed']}/6", group["actual_requests"],
            f"{group['tokens']:,}", f"{group['median_agent_seconds']:.1f}", f"{group['max_agent_seconds']:.1f}"])
    if repeat["stage"] == "complete":
        group = repeat["summary"]
        rows.append(["所选配置重复", f"{group['passed']}/6", group["actual_requests"],
            f"{group['tokens']:,}", f"{group['median_agent_seconds']:.1f}", f"{group['max_agent_seconds']:.1f}"])
    calls = sum(row["actual_requests"] for row in study["rows"] + repeat.get("rows", []))
    return [subheading("5.4 新题通过率与效率"),
        paragraph(f"三题诊断的三组均通过3/3；精简组累计词元较环境组减少{reduced:.1f}%，"
            f"较原始C0增加{increased:.1f}%。以下用六道固定新题比较配置。"),
        table(rows, [100, 58, 54, 105, 80, width - 397]),
        paragraph(f"输入效率对照完成{len(study['rows']) + len(repeat.get('rows', []))}次任务运行、{calls}次实际模型调用，逐笔积分均为0。"
            "总词元为输入与输出之和，缓存输入已计入输入。本表用时为模型和工具的实际求解时间，独立原评分用时另存记录。"
            "本表各组在同一服务器比较，前述75题表保留原运行环境及其实际耗时。")]


def decision(data):
    study, repeat = data["study"], data["repeat"]
    chosen = study["chosen_configuration"]
    if chosen is None:
        return "新增六题的比较完成后，各候选均未同时达到事前固定的通过率、词元和时间门槛，保留原配置。"
    group = study["by_configuration"][chosen]
    reference = study["by_configuration"]["environment"]
    saving = 100 * (1 - group["tokens_per_passed_task"] / reference["tokens_per_passed_task"])
    text = f"首轮按预定规则选出{LABELS[chosen]}，每道通过题的词元较环境组减少{saving:.1f}%。"
    if repeat["stage"] == "complete":
        repeated = repeat["summary"]
        text += f"独立重复通过{repeated['passed']}/6。"
        if repeated["tokens_per_passed_task"] is not None:
            saving = 100 * (1 - repeated["tokens_per_passed_task"] / reference["tokens_per_passed_task"])
            direction = "减少" if saving >= 0 else "增加"
            text += f"每道通过题的词元较首轮环境组{direction}{abs(saving):.1f}%。"
        text += "该配置满足重复验证的采用条件。" if repeat["adopt"] else "重复结果未同时满足全部采用条件，保留原配置。"
    return text


def conclusion(data):
    study, repeat = data["study"], data["repeat"]
    chosen = study["chosen_configuration"]
    if chosen is None:
        return "新增六题对照完成了通过率、词元与时间的共同比较，按事前标准保留原配置。"
    if repeat["stage"] != "complete":
        raise ValueError("A selected configuration requires its independent repeat")
    group, baseline = repeat["summary"], study["by_configuration"]["environment"]
    if repeat["adopt"]:
        saving = 100 * (1 - group["tokens_per_passed_task"] / baseline["tokens_per_passed_task"])
        return (f"新增六题选出的{LABELS[chosen]}在独立重复中通过6/6，"
            f"每道通过题的词元较环境组减少{saving:.1f}%，并达到预定时间条件，采用该配置。")
    return (f"新增六题选出的配置独立重复通过{group['passed']}/6；"
        "依据预定通过率、词元与时间标准，保留原配置。")


def discussion(data):
    aider = {arm: [row for row in data["study"]["rows"] if row["stage"] == "confirmation"
        and row["benchmark"] == "aider" and row["arm"] == arm] for arm in ("dsh", "environment")}
    dsh_tokens = sum(row["total_tokens"] for row in aider["dsh"])
    environment_tokens = sum(row["total_tokens"] for row in aider["environment"])
    saving = 100 * (1 - dsh_tokens / environment_tokens)
    sklearn = {row["arm"]: row for row in data["study"]["rows"]
        if row["task"] == "scikit-learn__scikit-learn-14710"}
    compact, full = sklearn["digest"], sklearn["environment"]
    sklearn_saving = 100 * (1 - compact["total_tokens"] / full["total_tokens"])
    return [subheading("6.6 输入开销与配置选择"), paragraph(decision(data)),
        paragraph(f"新增Aider三题中，两组均通过3/3，DSH累计使用{dsh_tokens:,}词元，"
            f"较环境提示C0的{environment_tokens:,}词元减少{saving:.1f}%；"
            f"实际调用由{sum(row['actual_requests'] for row in aider['environment'])}次降至"
            f"{sum(row['actual_requests'] for row in aider['dsh'])}次。"
            "这为按任务类型复用成熟执行流程提供了直接对照。"),
        paragraph(f"新增scikit-learn题中，环境提示与精简组均通过原评分。精简组使用{compact['total_tokens']:,}词元、"
            f"{compact['agent_seconds']:.1f}秒，环境组为{full['total_tokens']:,}词元、{full['agent_seconds']:.1f}秒，"
            f"词元减少{sklearn_saving:.1f}%。该组实际精简6段长输出，原文共59,625字符，精简文本为16,413字符，"
            "各段完整日志仍可读取。"),
        paragraph("同题基础C0用了59次调用、3,473,538词元。模型修改原测试后，自写检查虽然通过，文件保护仍持续报错；"
            "从首次保护失败到最终提交用了33次调用、2,465,016词元，约占整题71%，第56次调用才还原原测试。"
            "基础组与环境组的工具原始输出分别约10.8万、8.3万字符；差异更集中在反复定位、核验和由此增长的对话。"
            "因此，减少长输出还需配合清楚的错误定位与恢复步骤。"),
        paragraph("新增Django跨年查询题中，四组都修正了跨年返回值，却移除了既有范围查询优化，原题评分均未通过。"
            "其中原始C0的自写检查还把移除优化当作成功条件。这个案例说明，复现已消失之后，还要检查修复是否保留既有功能和性能。"),
        paragraph("Xarray题中，原始C0通过原评分，其余三组未通过。精简组已覆盖标量分支的数值选择，却未核对该分支的属性归属；"
            "补丁因而可能借用其他参数的属性。检查需要同时覆盖计算值和属性归属。"),
        paragraph("诊断阶段的Django题中，精简组用492,908词元、491.3秒，环境组用886,365词元、1039.9秒。"
            "三次长输出由26,188字符缩为9,395字符，完整日志仍可读取。原始C0为573,710词元、524.4秒，"
            "说明环境提示的效果随执行路径变化。book-store精简组没有触发长输出精简，其用量差异来自求解路径；"
            "因此结合实际呈现次数和逐步轨迹解释总用量变化。"),
        paragraph("pytest精简组将长输出从53,590字符缩为15,517字符，整题用时较原始C0增加586.0秒；"
            "其中扩大测试范围多耗404.6秒。该组还修改了原测试文件，保护检查识别后，模型还原文件并通过最终检查与原评分。"
            "这说明减少工具输出需要配合相关测试选择，文件保护也需要及时反馈，才能同时控制求解开销。")]
