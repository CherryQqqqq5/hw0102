import argparse
import importlib.util
import json
from pathlib import Path

from render_course_phase_reports import build, heading, subheading, link, paragraph, table, width
import report_input_efficiency as input_efficiency


ROOT = Path.cwd()
FOLDER = ROOT / "work/parallel-free-evaluation-20261124"
LABELS = {"swe": "SWE-bench Verified", "terminal": "Terminal-Bench 2.1", "aider": "Aider Polyglot"}
ARMS = {"main": "最终方法", "dsh": "原生DSH", "repeat": "独立重复"}
AUTHOR = "邱昱宁 · 231880296"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_nvidia_closed_source(data):
    closed = data.get("closed_cost_supplement")
    if closed is None:
        return
    expected_owner = "work/parallel-free-evaluation-20261124/export_nvidia_history.py"
    expected_sha = "c297543da00d7c89883c975159c355ffb3ab1f08a628786b65ed994280cea352"
    if (closed["verifier"] != {"path": expected_owner, "sha256": expected_sha}
            or digest(ROOT / expected_owner) != expected_sha
            or closed["review_source_sha256"] != "88b8da257972410d40c665a9f10fcd5d7f2688c6a5a8eb179554a6c9762b3ca6"):
        raise ValueError("The qualified closed-cost report source changed")
    index_path = ROOT / closed["package_index"]
    if not index_path.resolve().is_relative_to(ROOT) or digest(index_path) != closed["package_index_sha256"]:
        raise ValueError("The closed-cost inventory changed after actual report consumption")
    for member in read(index_path)["files"]:
        relative = Path(member["path"])
        path = index_path.parent / relative
        if (relative.is_absolute() or ".." in relative.parts or any(p.is_symlink() for p in (path, *path.parents))
                or not path.resolve().is_relative_to(index_path.parent.resolve())
                or digest(path) != member["export_sha256"] or path.stat().st_size != member["export_bytes"]):
            raise ValueError("A consumed portable closed-cost member changed")


def rate(group):
    return f"{group['passed']}/{group['completed']}" if group["completed"] else "尚无原评分"


def number(value):
    return "尚无记录" if value is None else f"{value:,.1f}"


def environment_note(data, include_image=False):
    source = data["supplementary"]["execution-environment-20261126.json"]
    path = ROOT / source["path"]
    if digest(path) != source["sha256"]:
        raise ValueError("The measured execution environment changed")
    record = read(path)
    if record["format"] != "readonly_local_execution_environment_v1" or record["new_model_calls"] != 0:
        raise ValueError("The environment note requires its actual read-only receipt")
    host, vm = record["host"], record["linux_vm"]
    text = (f"11月26日本地环境实测：主机内存{host['memory_bytes'] / 2 ** 30:.0f} GiB，"
        f"Linux虚拟机为{vm['architecture']}架构、{vm['logical_processors']}个逻辑处理器、"
        f"约{vm['memory_bytes'] / 2 ** 30:.2f} GiB内存。")
    if include_image:
        image = record["checked_original_task_image"]
        text += (f"单独核验的{image['task']}原镜像为{image['architecture']}架构，与虚拟机架构不同；"
            "该差异对速度的独立影响尚未测定。")
    return text + "75题对照的耗时为该本机环境实测值。"


def load(args):
    data = read(args.data)
    source = ROOT / data["summary"]
    if digest(source) != data["summary_sha256"] or digest(FOLDER / "prepare_report_data.py") != data["producer_sha256"]:
        raise ValueError("The report input differs from its independently recomputed source")
    summary = read(source)
    manifest = ROOT / data["tasks_path"]
    tasks = {row["id"]: row for row in read(manifest)["selected"]}
    if digest(manifest) != data["tasks_sha256"]:
        raise ValueError("The exact75 task union changed")
    for name, evidence in data["supplementary"].items():
        if evidence.get("status") == "pending":
            if (not args.preview or name != "sklearn_completed_review"
                    or evidence.get("review_consumed") is not False
                    or evidence.get("required") != 2 or evidence.get("completed") not in (0, 1, 2)):
                raise ValueError("Only an explicit layout preview may contain a pending NaN-session review")
            continue
        if digest(ROOT / evidence["path"]) != evidence["sha256"]:
            raise ValueError("A cited supplementary source changed")
    for name, evidence in data["case_sources"].items():
        if "files_sha256" in evidence:
            if name not in {"scikit-learn__scikit-learn-25232", "pydata__xarray-4695", "tune-mjcf"} or not evidence["files_sha256"]:
                raise ValueError("The multi-source public case has an unexpected evidence contract")
            for relative, expected in evidence["files_sha256"].items():
                path = ROOT / relative
                if (path.is_symlink() or not path.resolve().is_relative_to(ROOT)
                        or digest(path) != expected):
                    raise ValueError("A source of the real public case changed: " + relative)
        elif digest(ROOT / evidence["path"]) != evidence["sha256"]:
            raise ValueError("A cited case source changed")
    for evidence in data["sources"].values():
        for key in ("score", "protocol", "trace"):
            if digest(ROOT / evidence[key]) != evidence[key + "_sha256"]:
                raise ValueError("An original report position changed: " + evidence[key])
    nvidia = data["nvidia_auxiliary"]
    if (digest(ROOT / nvidia["source"]) != nvidia["source_sha256"]
            or digest(ROOT / nvidia["trials_path"]) != nvidia["trials_sha256"]):
        raise ValueError("The separate NVIDIA report source changed")
    verify_nvidia_closed_source(nvidia)
    if args.preview:
        if not args.out_dir.resolve().is_relative_to(ROOT / "work") or "preview" not in args.out_dir.name:
            raise ValueError("An incomplete layout preview must stay in an explicitly named work preview folder")
    else:
        if not data["complete_required_experiments"] or any(data["groups"][arm]["completed"] != 75 for arm in ARMS):
            raise ValueError("Final PDFs require all225 actual original scores and the3 declared ablations")
        if not data["main_and_repeat_all75_qualified_pass"]:
            raise ValueError("The requested final performance requires all75 main and all75 independent repeats to qualify")
        if args.final_review is None:
            raise ValueError("Final PDFs require the completed independent source and trace review")
        review = read(args.final_review)
        if (review["source_summary_sha256"] != data["summary_sha256"] or review["blocking_findings_remaining"] != 0
                or review["positions_reviewed"] != {"main": 75, "dsh": 75, "repeat": 75}):
            raise ValueError("The completed source review does not cover this exact final result")
    indexed = {arm: {r["task"]: r for r in summary["rows"] if r["arm"] == arm} for arm in ARMS}
    return data, tasks, indexed


def outcome(rows, task):
    row = rows.get(task)
    return "待评分" if row is None else "通过" if row["passed"] else "未通过"




def work1_validation(data, indexed):
    study = data["comparisons"]["D30"]
    repeat = data["independent_repeats"]["D30"]
    records = [["原诊断任务", "改进后", "同题DSH", "独立重复"]]
    for task in ("extract-elf", "llm-inference-batching-scheduler", "query-optimize", "video-processing"):
        records.append([task, *[outcome(indexed[arm], task) for arm in ARMS]])
    return [
        subheading("6.3 改进验证"),
        paragraph("后续使用hy4flash-free，以原生DeepSeek Harness（DSH，DeepSeek智能体执行框架）作同模型对照。"
                  "每题单次最多500次模型调用、3600秒交互、最大64000输出词元。"
                  f"原D30诊断集改进后为{rate(study['left'])}，同题DSH为{rate(study['right'])}；"
                  f"新容器、新会话的独立重复为{rate(repeat['right'])}。"),
        table(records, [220, 85, 85, width - 390]),
        paragraph("二进制提取增加实际装载段的独立检查，视频采用固定机位事件分析并检查邻帧，"
                  "查询与调度先保存指定路径产物，再由原题检验功能与性能。"
                  "原诊断和后续验证的模型、预算不同；同题DSH比较的是执行流程、检查及算法支持的完整方案。")]




def work2_items(data, tasks, indexed, preview, efficiency=None):
    groups = data["groups"]
    comparison = data["comparisons"]["all75"]
    acceptance = data["incremental_acceptance"]
    facts = data["case_observations"]
    query = facts["query-optimize"]
    elf = facts["extract-elf"]["public_result"]
    nan = facts["scikit-learn__scikit-learn-25232"]
    history = data["historical_control_comparison"]["matched_protocol"]
    development = (acceptance["original_core_rows"] + acceptance["new_revision_rows"]
                   + acceptance["previous_json_development_rows"])
    interrupted = data["mechanical_interruption_costs"]
    known_seconds = sum(row["wall_seconds"] for row in interrupted if row["wall_seconds"] is not None)
    missing_seconds = sum(row["wall_seconds"] is None for row in interrupted)
    items = [
        heading("一、实验目的"),
        paragraph("作业一发现，智能体有时已经得到可运行的方案，却没有交付到指定路径；有时自查通过，实际结果仍不正确。"
                  "本实验围绕这两类问题改造执行与验证流程，与原生DeepSeek Harness（DSH，DeepSeek智能体执行框架）比较任务通过率、模型调用和执行时间，"
                  "并通过重复实验与消融分析其作用。"
                  "在提高通过率后，进一步比较成熟框架和输入精简，降低额外求解开销。"),
        heading("二、实验原理与改进方法"),
        subheading("2.1 将执行、检查和候选保存连接起来"),
        paragraph("原生智能体主要依靠命令执行和模型判断推进任务。本方案以mini-SWE-agent为基础，采用模型主动检查模式（C0），"
                  "让模型使用下表五种动作，并由程序记录文件版本及对应的检查结果。"
                  "相关文件改变后，旧检查失效；保存候选时一并保存其检查状态。需要保护既有测试的任务还在提交前核对文件变化。"),
        table([["动作", "作用"],
            ["执行命令（bash）", "修改文件、运行程序或查看实际输出。"],
            ["公开检查（verify）", "执行题面或仓库可见的检查，返回实际结果。"],
            ["保存候选（save）", "保存指定文件及其当前检查状态。"],
            ["恢复候选（restore）", "恢复此前保存的文件版本。"],
            ["提交（submit）", "结束当前求解，将实际产物交给原题评分器。"]], [140, width - 140]),
        paragraph("CodeBuddy持久会话保留助手消息和工具返回，减少续接时的状态丢失。"
                  "controller.py处理动作与状态，verification.py跟踪检查依赖，candidate_io.py处理文件保存和恢复。"
                  "程序记录的检查状态与原题评分分别保存。"),
        subheading("2.2 复用成熟方法，补足检查内容"),
        paragraph("本方案同时提供适用任务的公开方法：例如使用pyelftools独立读取二进制装载段，"
                  "使用公开线性攻击求解FEAL（Fast Data Encipherment Algorithm，快速数据加密算法）任务，"
                  "并针对软件题的输入边界补充公开检查。模型仍需调用方法、生成产物并接受原题验收。"
                  "这些算法支持与执行流程共同构成本次比较的完整方案。"),
        heading("三、实验环境与设置"),
        subheading("3.1 任务、模型与对照"),
        paragraph("任务集合由原诊断D30、后续C30和早期H15组成，共75个不同任务："
                  "SWE-bench Verified、Terminal-Bench 2.1、Aider Polyglot各25题。三个集合互不重合，均已参与开发。"
                  "Aider题目由mini-SWE-agent执行。对照采用原生DSH。"),
        paragraph("两组使用相同hy4flash-free模型、题目、初始镜像、原题评分和单次执行预算："
                  "最多500次模型调用、3600秒交互、单条命令120秒、单次最大64000输出词元，额外超时重试0次。"
                  "机械中断恢复可形成多次尝试，累计开销另计。"
                  "最终方案73题使用C0主动检查接口，fix-git和mailman使用B0原生循环；C1自动检查仅用于历史消融分析。"),
        paragraph(environment_note(data)),
        subheading("3.2 版本、重复与评价指标"),
        paragraph(f"本方案与重复组沿用67题的{acceptance['required_inherited_positions']}份原记录，并为8题各固定首轮、重复两次新会话，"
                  f"共{acceptance['required_new_positions']}份。DSH使用原75份对照。"
                  "独立重复使用重新创建的原容器与会话，各自生成候选和输出。软件修复与性能验收独占虚拟机，轻任务按固定资源限制并行。"),
        paragraph("主要指标为原题评分通过率，同时报告实际模型调用、输入与输出词元、每题耗时中位数及累计耗时。"
                  "耗时包含求解与原题验收，累计时间为逐题之和。公开检查和测试文件保护另行判断。"),
        heading("四、实验步骤"),
        paragraph("（1）读取固定题单和配置，按原镜像创建容器，准备题面、可见材料及对应检查。"),
        paragraph("（2）分别执行本方案、原生DSH及独立重复。模型根据工具返回继续修改、检查或保存文件，"
                  "每次实际模型调用计入预算；题目结束后由独立原题评分器验收。"),
        paragraph("（3）按同一任务配对汇总三组成绩、成本和重复结果。开发阶段的旧尝试、专项复测和无分中断分别统计。"),
        paragraph("（4）按事前固定计划，对网络权重恢复、二进制提取和视频处理撤去明确的复用指导句；"
                  "算法文件、题目、检查、模型和预算保持，使用新容器与新会话，与原v18有指导记录比较。"),
        heading("五、实验结果"),
        subheading("5.1 通过率与独立重复")]
    scores = [["基准", "本方案", "原生DSH", "独立重复"]]
    for benchmark, label in LABELS.items():
        scores.append([label, *[rate(groups[arm]["by_benchmark"][benchmark]) for arm in ARMS]])
    scores.append(["合计", *[rate(groups[arm]) for arm in ARMS]])
    items += [
        table(scores, [155, 110, 110, width - 375]),
        paragraph(f"本方案和独立重复均为75/75，DSH为69/75。双方共同通过{comparison['both_pass']}题，"
                  f"本方案额外通过{comparison['left_only_pass']}题，DSH单独通过0题。"
                  "通过率由92.0%升至100%，绝对提高8.0个百分点，相对DSH提高8.7%。独立重复的75题通过状态均与首轮一致。"),
        subheading("5.2 模型调用与耗时"),
        scored_cost_table(data),
        paragraph("本方案比DSH多70次模型调用，增加5.8%；每题耗时中位数增加约14.6秒，累计用时减少11.9%。"
                  "词元包含实际内部续接和缓存输入。"),
        paragraph(f"75题性能方案的开发记录包括三组原始运行225次、专项复测16次及早期开发5次，合计{sum(row['actual_requests'] for row in development)}次模型调用；"
                  "对应原题评分为213/225、16/16和5/5。最终比较使用其中的相应记录，开发成本按实际调用统计一次。"
                  f"无分中断已记录{known_seconds:.1f}秒，另{missing_seconds}次耗时未记录。"),
        subheading("5.3 复用指导消融")]
    ablation = [["任务", "原题评分：有/无指导", "模型调用：有/无"]]
    for row in data["ablation"]["rows"]:
        left, right = row["full_guidance_reference"], row["without_guidance"]
        ablation.append([row["task"], "/".join("通过" if item["passed"] else "未通过" for item in (left, right)),
                         f"{left['actual_requests']}/{right['actual_requests']}"])
    items += [
        table(ablation, [235, 140, width - 375]),
        paragraph("3题消融两组均为3/3，模型在两组都实际调用了现成方法。"
                  "网络权重恢复题的有指导参考为原计划绑定的v18记录，其原题评分通过、提交检查不合格。"),
        heading("六、结果分析与讨论"),
        subheading("6.1 交付完整性：查询优化"),
        paragraph("query-optimize原诊断已运行临时候选，却未写入/app/sol.sql。改进流程先形成指定路径的实际文件，"
                  "再分别检查结果等价性和执行速度，避免把临时输出当作完成交付。"
                  f"最终原题6项验收通过；{query['iterations']}次测量中位数为候选{query['solution']['median_s']:.3f}秒、"
                  f"参考{query['golden']['median_s']:.3f}秒，参考耗时与候选耗时之比为{query['speedup_solution_vs_golden']:.3f}。"),
        subheading("6.2 检查独立性：二进制地址提取"),
        paragraph("extract-elf原诊断的698项自查均通过，原题地址覆盖率却为0%。实现和自查共用了固定基址的地址映射假设，"
                  "因而相互一致仍会共同出错。改进复用pyelftools按实际装载段和虚拟地址读取无符号32位字，"
                  f"独立检查匹配{elf['matched_loadable_words']}/{elf['total_loadable_words']}个装载字，随后原题2项验收通过。"
                  "这个案例说明，检查依据要独立于待检查实现中的关键假设。")]
    feal = feal_result_items(data, indexed)
    feal[0] = subheading("6.3 成熟算法复用：线性攻击")
    items += feal
    items += [
        subheading("6.4 反馈后修正：缺失值迭代"),
        paragraph("scikit-learn-25232的旧候选把NaN初值误当作训练列没有观测值，提前返回而跳过应有迭代。"
                  "原首轮与重复候选的原题评分均通过，补充检查分别为8/12、9/12。"
                  "修订从训练数据识别空列，并让拟合与后续转换使用一致的特征范围，两个固定新会话均通过原题评分及12/12公开检查。"),
        paragraph("独立重复第24步仍为11/12；模型据反馈修正后续转换的列排序，第28步同一检查达到12/12，"
                  "第33步再次通过。这提供了反馈、代码修改与复测成功的连续记录。"
                  "该题原评分此前已通过，收益体现在补全迭代与转换行为；12例均使用每列有观测值的训练数据。"),
        subheading("6.5 机制使用与对照分析"),
        paragraph("两轮各73题使用C0。首轮实际请求101次公开检查、保存125个候选，其中53个合格；"
                  "重复为96次检查、128个候选、60个合格，两轮恢复操作均为0次。"),
        paragraph("历史消融使用同一mini-SWE-agent：B0保留原生循环，C0增加模型主动调用的检查与保存，"
                  "C1进一步由程序自动安排检查。事后按同协议匹配的"
                  f"{history['tasks']}题为"
                  + "、".join(f"{arm} {history['arms'][arm]['passed']}/{history['tasks']}" for arm in ("B0", "C0", "C1"))
                  + "；模型调用依次为"
                  + "/".join(str(history['arms'][arm]['model_calls']) for arm in ("B0", "C0", "C1"))
                  + "次，执行时间中位数为"
                  + "/".join(f"{history['arms'][arm]['median_execution_seconds']:.1f}" for arm in ("B0", "C0", "C1"))
                  + "秒。C0比C1多通过2题，中位用时少17.7秒。当前方案采用主动检查，优先补足检查内容。"),
        paragraph("本次比较以执行流程、任务检查和公开算法支持组成的完整方案为对象，结合逐题原评分、独立重复和案例轨迹评价整体效果。"),
        heading("七、实验结论"),
        paragraph("本实验完成了有状态动作接口、文件版本检查和公开方法支持的改造。本方案在75道开发题上两轮均通过75/75，"
                  "同模型同题DSH为69/75，通过率提高8.0个百分点；模型调用增加5.8%。"),
        paragraph("案例显示，指定路径交付、独立检查依据和成熟算法复用分别解决了产物缺失、共同错误假设及低效求解问题。"
                  "三题消融中，有无指导均通过3/3。"
                  + (input_efficiency.conclusion(efficiency) if efficiency is not None else "")),
        link("代码仓库：github.com/CherryQqqqq5/hw0102", "https://github.com/CherryQqqqq5/hw0102")]
    if efficiency is not None:
        sections = [("三、实验环境与设置", input_efficiency.method(data)),
            ("四、实验步骤", input_efficiency.setting()),
            ("六、结果分析与讨论", input_efficiency.results(efficiency)),
            ("七、实验结论", input_efficiency.discussion(efficiency))]
        for title, content in sections:
            index = next(index for index, item in enumerate(items) if hasattr(item, "getPlainText")
                and item.getPlainText() == title)
            items[index:index] = content
    return items




def feal_result_items(data, indexed):
    if "feal_completed_review" not in data["supplementary"]:
        return []
    main = indexed["main"].get("feal-linear-cryptanalysis")
    repeat = indexed["repeat"].get("feal-linear-cryptanalysis")
    if main is None or repeat is None:
        return []
    previous = [row for row in data["incremental_acceptance"]["displaced_original_rows"]
        if row["task"] == "feal-linear-cryptanalysis"]
    if len(previous) != 2:
        raise ValueError("The FEAL case requires both retained original cohort attempts")
    final = [main, repeat]
    old_requests = sum(row["actual_requests"] for row in previous)
    new_requests = sum(row["actual_requests"] for row in final)
    old_wall = sum(row["wall_seconds"] for row in previous)
    new_wall = sum(row["wall_seconds"] for row in final)
    return [heading("案例五：复用线性攻击减少计算开销"),
        paragraph("该题要求根据公开的已知明文与密文对，求解四轮FEAL的解密结果。原检查只接受100行数字，无法判断内容。"
                  "修订复用公开线性攻击，并用原程序核对输出；检查另以正确、错误和遗漏项产物验证。"),
        paragraph("两次独立新会话都实际编译并调用公开C算法，先用原程序回验32个已知对，再对100条目标输出逐条再加密核对。"
                  f"两份原题评分分别为{outcome(indexed['main'], 'feal-linear-cryptanalysis')}与{outcome(indexed['repeat'], 'feal-linear-cryptanalysis')}，"
                  f"实际生成分别{main['actual_requests']}与{repeat['actual_requests']}次，"
                  f"完整执行耗时{main['wall_seconds']:.1f}与{repeat['wall_seconds']:.1f}秒。"),
        table([["同一题的实际记录", "原题通过", "两次合计生成", "两次合计执行秒数"],
            ["修订前固定批次", f"{sum(row['passed'] for row in previous)}/2", old_requests, f"{old_wall:.1f}"],
            ["修订后固定新会话", f"{sum(row['passed'] for row in final)}/2", new_requests, f"{new_wall:.1f}"]],
            [180, 85, 100, width - 365]),
        paragraph(f"这道开发任务的请求合计减少{100 * (old_requests - new_requests) / old_requests:.1f}%，"
                  f"执行时间合计减少{100 * (old_wall - new_wall) / old_wall:.1f}%。"
                  "变化来自该题算法支持与语义检查的组合修订，两阶段各观测两次。")]


def scored_cost_table(data):
    comparison = data["comparisons"]["all75"]
    rows = [["评测组", "模型调用", "输入词元", "输出词元", "中位秒", "累计秒"]]
    for label, group in (("最终方法匹配组", comparison["left"]), ("原生DSH匹配组", comparison["right"]),
            ("独立重复匹配组", data["independent_repeats"]["all75"]["right"])):
        rows.append([f"{label}（{group['completed']}题）", group["requests"], f"{group['input_tokens']:,}",
            f"{group['output_tokens']:,}", number(group["median_wall_seconds"]), number(group["summed_wall_seconds"])])
    return table(rows, [115, 55, 85, 85, 75, width - 415])




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=FOLDER / "report-data.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--final-review", type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--efficiency", type=Path)
    args = parser.parse_args()
    data, tasks, indexed = load(args)
    efficiency = input_efficiency.load(args.efficiency) if args.efficiency else None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "preview_" if args.preview else ""
    subtitle = AUTHOR + (" · 内部预览，实验未齐" if args.preview else " · 智能推理与规划")
    footer = "智能推理与规划 · " + ("内部预览，实验未齐" if args.preview else "邱昱宁")
    baseline_path = ROOT / "work/hw0102-publish/shared/scripts/render_hw0102_final.py"
    spec = importlib.util.spec_from_file_location("course_baseline_final", baseline_path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    paths = [args.out_dir.resolve() / (prefix + "231880296_邱昱宁_作业" + numeral + ".pdf") for numeral in ("一", "二")]
    baseline.baseline_report(validation_items=work1_validation(data, indexed), output_filename=str(paths[0]),
        report_subtitle=subtitle, report_footer=footer)
    build(str(paths[1]), "作业二：编程智能体改造实验报告", work2_items(data, tasks, indexed, args.preview, efficiency),
        subtitle=subtitle, footer=footer)
    print(json.dumps({"preview": args.preview, "pdfs": [{"path": str(p), "sha256": digest(p)} for p in paths],
        "new_model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
