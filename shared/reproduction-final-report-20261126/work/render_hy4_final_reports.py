import argparse
import importlib.util
import json
from pathlib import Path

from reportlab.platypus import Spacer, TableStyle

from render_course_phase_reports import build, heading, link, paragraph, table, width


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
    return text + "下文耗时均为该本机环境的实测值。"


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


def revision_accounting(data):
    acceptance = data.get("incremental_acceptance")
    if acceptance is None:
        return []
    original, revised, previous = (acceptance[key] for key in
        ("original_core_rows", "new_revision_rows", "previous_json_development_rows"))
    inherited_positions = acceptance["required_inherited_positions"]
    revision_positions = acceptance["required_new_positions"]
    if inherited_positions + revision_positions != 150 or inherited_positions % 2 or revision_positions % 2:
        raise ValueError("The local-revision accounting must cover exactly75 main and75 repeat positions")
    inherited_tasks, revised_tasks = inherited_positions // 2, revision_positions // 2
    loc_revision = "loc_preservation" in acceptance["revision_plans"]
    runtime_description = "ReLU与xarray4695的固定新会话使用各自声明的v20运行时" if loc_revision else "ReLU单独使用声明的修订运行时"
    records = [["记录范围", "已评分位置", "原题通过", "模型调用", "输入/输出词元", "累计计分秒"]]
    for label, rows in (("原固定批次（计划225）", original), (f"{revised_tasks}处修订新会话（计划{revision_positions}）", revised),
            ("JSON开发记录", previous)):
        records.append([label, len(rows), sum(row["passed"] for row in rows),
            sum(row["actual_requests"] for row in rows),
            f"{sum(row['input_tokens'] for row in rows):,} / {sum(row['output_tokens'] for row in rows):,}",
            number(sum(row["wall_seconds"] for row in rows))])
    return [heading("局部修订的验收与开发开销"),
        paragraph(f"最终150个方法位置由{inherited_tasks}题的{inherited_positions}份原记录与{revised_tasks}题的{revision_positions}份固定新会话组成，"
                  "并非最终冻结后全量重跑。八处更新涉及JSON（JavaScript Object Notation，JavaScript对象表示法）查询、线性攻击、共享对象转换、参数安全显示、数值恢复、缺失值迭代及两题的测试保护。"
                  f"继承记录的任务输入、提示、检查和运行时已逐项核对；{runtime_description}。同题DSH保留原75份评分。"),
        table(records, [135, 50, 50, 60, 135, width - 430]),
        paragraph("上表列出互不重复的开发记录；前表的最终位置取自这些记录，不能再次累加。指导消融和早期查询布局验证单列。")]


def work1_validation(data, indexed):
    study = data["comparisons"]["D30"]
    repeat = data["independent_repeats"]["D30"]
    original_failures = ("extract-elf", "llm-inference-batching-scheduler", "query-optimize", "video-processing")
    repaired = sum(indexed["main"].get(task, {}).get("passed", False) for task in original_failures)
    items = [heading("改进结果与原诊断对照"),
        paragraph(f"原诊断中的二进制提取、批处理调度、查询优化与视频定位四题，本次最终方法首轮已通过{repaired}/4题原评分。"
                  "下表列出同题DSH对照和新会话独立重复。"),
        paragraph("原30题诊断结果为26/30。后续以hy4flash-free重新运行原题，"
                  "并在同模型、同题目、同声明预算下执行DeepSeek Harness（DSH，DeepSeek智能体执行框架）对照；"
                  "独立重复使用新容器和新会话。原诊断与复测的模型、预算不同，方法收益以同题DSH比较为准。"),
        table([["比较对象", "匹配/原计划", "最终方法通过", "对照或重复通过"],
            ["同题DSH对照", f"{study['matched']}/30", rate(study["left"]), rate(study["right"])],
            ["新会话独立重复", f"{repeat['matched']}/30", rate(repeat["left"]), rate(repeat["right"])]],
            [130, 100, 125, width - 355]),
        heading("四道原失败题的对应结果")]
    records = [["原诊断任务", "最终方法", "同题DSH", "独立重复"]]
    for task in ("extract-elf", "llm-inference-batching-scheduler", "query-optimize", "video-processing"):
        records.append([task, *[outcome(indexed[arm], task) for arm in ARMS]])
    items.extend([table(records, [220, 85, 85, width - 390]),
        paragraph("二进制提取使用基于程序装载段的独立内存检查，减少实现与自查共享错误地址假设的风险；"
                  "视频提供只接收可见像素的固定机位方法，并要求观察实际事件附近画面；"
                  "查询与调度要求按题面路径交付可执行候选，正确性与性能交给原题验收。"
                  "这些策略与持久会话、结构化动作及共同的单次执行预算组成最终配置。"),
        paragraph("通过由原题评分器判定。同题DSH比较包括提示、动作接口和公开算法支持的完整方案。"
                  "作业二进一步报告75题比较、重复与消融；这些题均已参与开发。"),
        link("75题配置、逐题评分与复现入口", "https://github.com/CherryQqqqq5/hw0102/tree/main/%E4%BD%9C%E4%B8%9A%E4%BA%8C")])
    return items




def work2_items(data, tasks, indexed, preview):
    groups, comparison = data["groups"], data["comparisons"]["all75"]
    repeat = data["independent_repeats"]["all75"]
    facts = data["case_observations"]
    query = facts["query-optimize"]
    elf = facts["extract-elf"]["public_result"]
    relu = facts["model-extraction-relu-logits"]["public_result"]
    video = facts["video-processing"]
    history = data["historical_control_comparison"]
    old_match = history["matched_protocol"]
    interrupted_attempts = data["mechanical_interruption_costs"]
    recorded_interruption_walls = [row["wall_seconds"] for row in interrupted_attempts if row["wall_seconds"] is not None]
    missing_interruption_walls = len(interrupted_attempts) - len(recorded_interruption_walls)
    items = []
    if preview:
        items.append(paragraph("内部排版预览。实验仍在执行；待评分位置不计作通过或失败，本文不作为完整实验的最终结论。"))
    items.extend([heading("结果概览"),
        paragraph(f"最终方法通过{comparison['left']['passed']}/75题，新容器、新会话的独立重复通过{groups['repeat']['passed']}/75题；"
                  f"同模型同题的原生DSH通过{comparison['right']['passed']}/75题，方法提高{comparison['percentage_point_difference']:.1f}个百分点。"
                  "原诊断中的四道失败题现均在两次运行中通过原题验收。"),
        heading("问题与实质改造"),
        paragraph("作业一的四道失败集中于交付缺失、语义精度和检查覆盖不足。较早270条实验还出现推理耗尽而没有动作、"
                  "上下文续接异常与反复自查的额外开销。最终方案以可靠的连续执行为共同基础，加入结构化动作、"
                  "面向实际产物的公开验证和候选版本接口，并复用适用问题的公开算法方法。"
                  "方法以mini-SWE-agent为执行基础，以DeepSeek Harness（DSH，DeepSeek智能体执行框架）为对照。"),
        table([["环节", "实际设计与代码", "验收证据"],
            ["模型与连续状态", "CodeBuddy持久会话；仅接受完整动作；每笔实际身份和零积分。codebuddy_free.py", "model.jsonl内独立请求、响应、真实用量与回执"],
            ["动作与候选", "controller.py处理五种动作；candidate_io.py保存和恢复指定文件，并检查受保护文件是否改变", "动作记录、候选文件与提交检查"],
            ["公开检查", "verification.py在相关文件变化后要求重测；复用公开测试与独立检查方法", "检查命令、文件摘要与原题评分"],
            ["成熟方法复用", "mini-SWE-agent与原生DSH；二进制/数值恢复/视频方法在限定任务范围提供", "源代码、适用边界、实际调用与指导消融"]],
            [90, 235, width - 325]),
        paragraph("B0为原生执行循环；C0增加模型主动选择的检查、保存和恢复接口；C1另启用程序自动控制。"
                  "最终文件或仓库任务采用C0，fix-git与mailman采用B0。自动控制与复用指导的作用分别由后文消融检验。"),
        paragraph("方法来源与适配：二进制检查直接使用pyelftools的装载段解析，避免重写格式解析器。"
                  "ReLU（Rectified Linear Unit，修正线性单元）精度修订依据Carlini、Jagielski与Mironov的CRYPTO2020论文第5.1、5.3节，"
                  "重新定位临界见证并拟合超平面；作者代码的示例传入完整网络架构，本题适配只接受公开可调用函数与输入维数，"
                  "隐藏宽度由查询估计。视频使用OpenCV的背景差分、形态学处理与连通分量，并针对固定机位单跑者设计接触规则。"),
        paragraph("结构化查询语言（Structured Query Language，SQL）的交付复用sqlparse0.6.1去除注释及重复布局空白，保持非布局词元、字面量与顺序；"
                  "只接收一条SELECT。替换前使用公开数据库只读连接比较列名与有序结果，再执行公开检查和独立原验收。"
                  "其中结果比较用于检查SQLite隐式列名等受布局影响的行为。"),
        heading("任务、对照与执行预算"),
        paragraph("完整并集为原诊断D30、后续C30及早期H15，共75个不同任务，SWE-bench Verified、Terminal-Bench 2.1、"
                  "Aider Polyglot各25题。三个集合互不重合，均已参与开发；Aider题目由mini-SWE-agent执行。"),
        paragraph("原生DSH与最终方法使用相同75题、初始镜像摘要、原题验收及声明上限：hy4flash-free、"
                  "每次实际尝试最多500次生成、3600秒交互时限、单命令120秒、最大64000输出词元，额外超时重试0次。"
                  "同一逻辑题目的机械恢复可产生多次尝试，各次分别使用该上限，累计恢复开销另列。"
                  "每题保持助手与工具消息的连续状态。比较对象为完整方案，包括框架提示、工具接口、公开算法支持与检查。"),
        paragraph("独立重复每题重新创建原镜像容器及原生会话，不复制首轮模型输出或候选。下载与镜像导入不使用模型；"
                  "软件修复与性能验收独占虚拟机，两个轻任务可并行；全部75题按计划执行。"),
        paragraph(environment_note(data, include_image=True)),
        heading("原题通过率与同题比较")])
    score_table = [["基准", "最终方法", "原生DSH", "独立重复"]]
    for bench, label in LABELS.items():
        score_table.append([label, *[f"{groups[a]['by_benchmark'][bench]['passed']}/{groups[a]['by_benchmark'][bench]['completed']}" for a in ARMS]])
    score_table.append(["合计", *[f"{groups[a]['passed']}/{groups[a]['completed']}" for a in ARMS]])
    items.extend([table(score_table, [155, 113, 113, width - 381]),
        paragraph("通过由各基准原评分器判定。方法与重复组还核对公开检查和既有测试保护；DSH不使用课程控制接口。"),
        paragraph(f"已形成{comparison['matched']}/75个同题配对：双方均过{comparison['both_pass']}，"
                  f"仅最终方法过{comparison['left_only_pass']}，仅DSH过{comparison['right_only_pass']}，双方均未过{comparison['both_fail']}。"
                  f"合计增加{comparison['absolute_pass_difference']}题，通过率提高{number(comparison['percentage_point_difference'])}个百分点。"),
        heading("计算开销与效率")])
    items.extend([scored_cost_table(data),
        paragraph(f"同题计分尝试耗时差的中位数为{number(comparison['median_paired_left_minus_right']['wall_seconds'])}秒；"
                  f"每题请求差的均值为{number(comparison['mean_paired_left_minus_right']['actual_requests'])}。"
                  "词元包含内部续接及缓存输入。累计秒数为执行与原验收的逐题用时之和；同题差值与各组中位数之差分别计算。"
                  "请求和时间统计包含相应组的所有已评分位置。"),
        paragraph(f"无分中断另有{sum(recorded_interruption_walls):.1f}秒已知耗时及{missing_interruption_walls}次耗时缺失，故总恢复成本只知下界。"
                  "计分调用均核对实际零积分；历史费用缺口在附件账目中保留。"),
        *revision_accounting(data),
        heading("独立重复与分集合稳定性")])
    repeated_table = [["任务来源", "配对/计划", "首轮通过", "重复通过", "两次均通过"]]
    for name in ("D30", "C30", "H15", "all75"):
        item = data["independent_repeats"][name]
        repeated_table.append(["全部75题" if name == "all75" else name,
            f"{item['matched']}/{item['planned']}", rate(item["left"]), rate(item["right"]), item["both_pass"]])
    items.extend([table(repeated_table, [85, 95, 100, 100, width - 380]),
        paragraph(f"{repeat['both_pass']}/{repeat['matched']}题两次均通过，说明本开发题集结果可重复；新任务表现仍待独立测试。"),
        heading("检查与候选接口的实际使用"),
        table([["组别", "C0位置", "主动检查", "保存候选", "其中合格", "实际恢复"],
            *[[ARMS[arm], *[data["mechanism_use"][arm][key] for key in
                ("controlled_positions", "requested_checks", "candidates_saved", "eligible_candidates_saved", "actual_restores")]]
                for arm in ("main", "repeat")]], [80, 70, 90, 90, 85, width - 415]),
        paragraph("合格候选须通过对应检查并保持受保护文件。两组检查均由模型主动请求，未实际执行恢复操作。"),
        heading("案例一：先交付，再验证结果与速度"),
        paragraph("query-optimize的原诊断已找到可运行临时候选，却没有交付/app/sol.sql。最终策略要求先形成题面路径的实际产物，"
                  "再依照原题验收同时判断等价性与速度。SQL语法或EXPLAIN检查"
                  "只覆盖可解析性，不能替代结果逐行比较和性能测量。"
                  f"新原验收6项全过；{query['iterations']}次测量中位数为候选{query['solution']['median_s']:.3f}秒、"
                  f"参考{query['golden']['median_s']:.3f}秒，参考耗时/候选耗时为{query['speedup_solution_vs_golden']:.3f}。"
                  "这说明指定路径的可运行交付与结果、速度的联合验收补足了原诊断缺口。"),
        heading("案例二：用独立检查发现地址映射错误"),
        paragraph("extract-elf的原诊断自查698项零不一致，原评分地址覆盖率却为0%。自查与实现共用地址映射假设，"
                  "不能排除共同错误。新配置复用pyelftools解析PT_LOAD装载段，按虚拟地址比较无符号32位字，"
                  "独立对照公开二进制中的内存内容。"
                  f"本次公开诊断匹配{elf['matched_loadable_words']}/{elf['total_loadable_words']}个装载字，"
                  "二进制摘要保持，随后原题2项验收通过。检查范围为本题ELF装载段。"),
        heading("案例三：提高网络权重恢复精度"),
        paragraph("ReLU任务要求从函数查询恢复未知宽度单隐层网络的输入权重方向。参考公开数值提取方法，"
                  "恢复器定位分段线性折点，再用临界见证修正精度；输入只有可调用函数和输入维数。"
                  f"本次保存矩阵与新查询推得的尺寸均为{relu['actual_shape']}；{relu['fresh_oracle_queries']:,}次本地函数查询"
                  f"所得最大方向误差为{relu['max_direction_error']:.2e}，阈值{relu['direction_tolerance']:.0e}，原题矩阵验收通过。"
                  "这是保存产物的数值检查，本地函数查询与模型调用分别计数；有限网格仍可能漏掉弱折点。"),
        paragraph("最终ReLU方案将恢复程序导出为独立脚本，C0提交时检查当前候选是否通过公开检查、受保护文件是否保持。"
                  "两个新会话实际调用通用导出命令、生成相同字节的独立脚本并通过原题验收；"
                  f"分别产生{indexed['main']['model-extraction-relu-logits']['actual_requests']}与"
                  f"{indexed['repeat']['model-extraction-relu-logits']['actual_requests']}次模型调用。"
                  "两次完整工具轨迹均只见函数查询；首轮还在另一工作目录运行独立脚本。重复先保存待检查候选，"
                  "再主动验证、保存合格版本并提交。访问拒绝与提交检查另经零模型回放验证，本例两次成功未触发拒绝。"),
        heading("案例四：按实际画面定位起跳与落地"),
        paragraph("video-processing的原失败是定位精度，脚本可导入仍输出错误事件帧。新方法复用固定机位单跑者的时间背景、"
                  "脚接触和连续腾空区间，输入只有可见像素；要求在预测位置及邻帧检查实际画面。最终脚本自包含，"
                  "场景假设为固定机位、单跑者。"
                  f"保存的示例结果为起跳{video['jump_takeoff_frame_number']}帧、落地{video['jump_land_frame_number']}帧；"
                  "原题5项验收通过示例、另一段视频和脚本导入。事件精度由原题验收判定，语法检查只检验可运行性。"),
        table([["案例原题评分", "最终方法", "同题DSH", "独立重复"],
            *[[task, *[outcome(indexed[arm], task) for arm in ARMS]] for task in
                ("query-optimize", "extract-elf", "model-extraction-relu-logits", "video-processing")]],
            [220, 85, 85, width - 390]),
        *feal_result_items(data, indexed),
        *mujoco_result_items(data),
        heading("其他软件缺陷的检查设计"),
        table([["任务", "复用方法与检查重点", "两次真实验收"],
            ["Django13346", "保留父表达式处理；逐参数区分JSON标量、列表及编码语义",
             "公开69/69，原题与保护均通过"],
            ["xarray2905", "在共享函数中显式识别受支持容器，同时覆盖构造与赋值",
             "公开26/26，原题365项均通过"],
            ["pytest7205", "统一安全显示bytes、str、int及显式或函数生成的参数标识",
             "6类参数×3种setup场景，共18例；原题26项通过"]], [90, 225, width - 315]),
        paragraph("Django的Oracle部分只检查编译，实际数据库验收为SQLite。xarray更广套件另有6项基线已有失败。"
                  "pytest按题面的新显示要求排除3个旧格式检查函数中的9条断言，保留16条其他检查；原测试文件和独立原评分保持。"),
        *nan_contract_items(data, indexed),
        *loc_preservation_items(data, indexed),
        paragraph("批处理调度的注册检查只检验文件和JSON格式。对实际保存候选另用题目CostModel离线重放，22个语义条件均满足；"
                  "这项回放定位了检查覆盖差距，其作用尚未通过新增模型对照测量。"),
        paragraph("pytest5631也使用相同保护原则：自写检查放入临时文件，既有测试保持；生产修复按pytest6.0.0的哨兵身份语义处理NumPy对象。"
                  "固定的首轮与重复均通过原题、公开检查和测试保护，分别使用14与16次生成。"),
        heading("消融：明确复用指导的实际作用"),
        paragraph("事前冻结3题消融，在ReLU、二进制提取和视频上只撤去优先观察并复用现有方法的指导句。"
                  "算法文件、可用性、原输入、公开检查、保护范围、模型和预算保持。每题使用新会话与新容器，"
                  "与原v18有指导首轮逐题比较。ReLU后续v20改变了交付机制，故此处仍使用v18参考；所检验变量为指导句。")])
    ablation_table = [["任务", "原题评分：有/无指导", "检查合格：有/无", "模型调用：有/无"]]
    for row in data["ablation"]["rows"]:
        left, right = row["full_guidance_reference"], row["without_guidance"]
        scores = "/".join("通过" if record["passed"] else "未通过" for record in (left, right))
        qualified = "/".join("合格" if record["qualified_passed"] else "不合格" for record in (left, right))
        ablation_table.append([row["task"], scores, qualified, f"{left['actual_requests']}/{right['actual_requests']}"])
    if len(ablation_table) == 1:
        ablation_table.append(["3个事前指定位置", "已有参考", "尚未执行", "待实际用量"])
    items.extend([table(ablation_table, [210, 90, 90, width - 390]),
        paragraph("3题消融两组均通过，未观察到指导带来的通过率提升，模型在两组都实际调用了现成方法。旧270条记录中，"
                  f"严格同协议{old_match['tasks']}题比较为"
                  + "、".join(f"{arm} {old_match['arms'][arm]['passed']}/{old_match['tasks']}" for arm in ("B0", "C0", "C1"))
                  + f"；全部{history['all270']['C1']['trials']}次C1与C0通过题次之差为"
                  f"{history['all270']['C1']['passed']-history['all270']['C0']['passed']:+d}。"
                  "该23题分组为事后同协议分析。现有消融支持最终方案采用模型主动检查；自动检查未显示稳定通过率收益。"),
        heading("贡献范围与公开强方案"),
        paragraph("DeepSeek官方在Terminal-Bench 2.1公布DSH Minimal 90.6%、mini-SWE 90.3%，使用DeepSeek V4.1 Flash、"
                  "最高推理强度、100万词元上下文和每题3次采样。本实验使用Hy4及三基准各25道开发题，"
                  "性能结论为本题集上75/75对DSH 69/75；完整公开榜单的最优水平尚未验证。"),
        heading("代码与复现"),
        paragraph("仓库提供代码、配置、逐题评分及工具轨迹，按任务索引可复算本文表格。代码与原评分分别固定版本；"
                  "记录中的源摘要与过滤后导出摘要分列，部分早期DSH只保存命令和验收轨迹。第三方来源及许可证随代码登记。"),
        link("完整代码、原始证据与复现命令", "https://github.com/CherryQqqqq5/hw0102"),
        link("课程原文及3.4、4.3评分要求", "https://nju-link-lab.feishu.cn/wiki/QLwBwXov6iHjsJkeBPLck9AUncc"),
        link("mini-SWE-agent作者代码", "https://github.com/SWE-agent/mini-swe-agent"),
        link("DeepSeek公开DSH与mini-SWE配置说明", "https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/README.md"),
        link("腾讯CodeBuddy原生Harbor接入", "https://github.com/Tencent/workbuddy-bench/blob/main/src/workbuddy_bench/agents/cbc_agent.py"),
        link("Carlini等：Cryptanalytic Extraction of Neural Network Models，CRYPTO2020，第5.1、5.3节", "https://arxiv.org/pdf/2003.04884"),
        link("上述论文的作者开源实现", "https://github.com/google-research/cryptanalytic-model-extraction"),
        link("pyelftools作者使用说明与装载段接口", "https://github.com/eliben/pyelftools/blob/main/doc/user-guide.md"),
        link("OpenCV官方背景差分说明", "https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html"),
        link("sqlparse官方格式化接口与非验证解析器说明", "https://sqlparse.readthedocs.io/en/stable/api.html"),
        link("Oracle JSON_VALUE官方说明", "https://docs.oracle.com/en/database/oracle/oracle-database/19/adjsn/function-JSON_VALUE.html"),
        link("Django官方逐参数JSON查询实现", "https://github.com/django/django/blob/stable/5.2.x/django/db/models/fields/json.py"),
        link("xarray官方显式容器转换实现", "https://github.com/pydata/xarray/blob/v2024.11.0/xarray/core/variable.py"),
        link("pytest官方安全参数显示实现", "https://github.com/pytest-dev/pytest/blob/6.0.0/src/_pytest/setuponly.py"),
        link("scikit-learn官方训练缺失掩码与后续转换实现", "https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/impute/_iterative.py"),
        link("Mark Stamp：FEAL线性攻击教学材料，第21—27页", "https://www.cs.sjsu.edu/~stamp/crypto/PowerPoint_PDF/13_FEAL.pdf"),
        heading("附录：全部75题原评分与独立重复")])
    for bench, label in LABELS.items():
        items.append(heading(label))
        records = [["任务 / 原集合", "最终方法", "原生DSH", "独立重复"]]
        for task in sorted(tasks):
            if tasks[task]["benchmark"] == bench:
                records.append([task + " / " + tasks[task]["split"], *[outcome(indexed[arm], task) for arm in ARMS]])
        scores = table(records, [235, 80, 80, width - 395])
        scores.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        items.extend([scores, Spacer(1, 7)])
    return items


def loc_preservation_items(data, indexed):
    task = "pydata__xarray-4695"
    facts = data["case_observations"].get(task)
    if facts is None:
        return []
    labels = {"base": "原始实现", "recorded_bad_repeat": "原重复完整候选",
        "recorded_good_main": "原首轮完整候选", "recorded_repeat_tests_restored": "重复候选仅恢复测试"}
    records = [["原镜像本地验证", "原题示例", "公开检查", "测试文件保护", "允许提交"]]
    for row in facts["engineering_variants"]:
        records.append([labels[row["variant"]], "通过" if row["original_issue_example_passed"] else "未通过",
            "通过" if row["controller_state"] == "passed" else "保护失效",
            "保持" if row["final_protected_unchanged"] else "改变", "是" if row["submit_accepted"] else "否"])
    sessions = [["固定新模型会话", "原题评分", "提交检查 / 测试保护", "模型调用 / 秒"]]
    for slot in facts["fixed_model_sessions"]:
        if slot["status"] != "original_scored":
            sessions.append([ARMS[slot["arm"]], "待评分", "待验证", "尚未形成完整记录"])
            continue
        row = indexed[slot["arm"]][task]
        sessions.append([ARMS[slot["arm"]], "通过" if row["passed"] else "未通过",
            ("通过" if slot["final_valid_verification"] else "未通过") + " / "
            + ("保持" if slot["final_protected_unchanged"] else "改变"),
            f"{row['actual_requests']} / {row['wall_seconds']:.1f}"])
    return [heading("提交时核对测试保护与当前证据"),
        paragraph("xarray4695的旧重复修复了.loc索引，却向既有测试追加15行自测。第14步已报告保护失效，"
                  "模型仍依据9条测试通过继续保存、提交。这揭示了测试退出码与交付约束的差别。"
                  "C0在提交时核对当前检查与保护摘要，失败时要求恢复测试、重新检查。下表以原镜像回放验证："
                  "相同生产修复仅恢复测试文件，就由拒绝提交变为允许。功能仍由原题评分器独立验收。"),
        table(records, [145, 60, 85, 75, width - 365]),
        paragraph("固定新会话仅增加三条测试保护指导并复用提交检查；任务、镜像、公开命令、评分及预算保持。两次均完成合格交付："),
        table(sessions, [115, 85, 130, width - 330])]


def nan_contract_items(data, indexed):
    task = "scikit-learn__scikit-learn-25232"
    facts = data["case_observations"].get(task)
    if facts is None:
        return []
    labels = {"base": "原始实现", "actual_main": "原首轮候选", "actual_repeat": "原重复候选",
        "public_reference": "独立工程参考"}
    reference = facts["separate_engineering_original_grade"]
    variants = [["检查对象", "公开检查", "提交检查", "测试文件保护"]]
    for row in facts["engineering_variants"]:
        variants.append([labels[row["variant"]], f"{row['public_passed']}/{row['public_total']}",
            "通过" if row["final_valid_verification"] else "未通过",
            "保持" if row["final_protected_unchanged"] else "改变"])
    sessions = [["新模型会话", "原题评分", "公开检查", "提交检查 / 测试保护", "模型调用 / 秒"]]
    for slot in facts["fixed_model_sessions"]:
        row = indexed[slot["arm"]].get(task)
        if slot["status"] != "original_scored":
            sessions.append([ARMS[slot["arm"]], "待评分", "待验证", "待验证", "尚未形成完整记录"])
            continue
        if row is None or row["run_dir"] != slot["run_dir"]:
            raise ValueError("The NaN case must use its exact fixed session,not an old passing candidate")
        probe = slot["public_probe"]
        public = f"{sum(case['passed'] for case in probe['cases'])}/{probe['total']}" if probe else "无完整输出"
        sessions.append([ARMS[slot["arm"]], "通过" if row["passed"] else "未通过", public,
            ("通过" if row["final_valid_verification"] else "未通过") + " / "
                + ("保持" if row["final_protected_unchanged"] else "改变"),
            f"{row['actual_requests']} / {row['wall_seconds']:.1f}"])
    feedback_items = []
    reviewed = data.get("supplementary", {}).get("sklearn_completed_review")
    if reviewed is not None and reviewed.get("status") != "pending":
        if digest(ROOT / reviewed["path"]) != reviewed["sha256"]:
            raise ValueError("The reviewed NaN feedback trajectory changed before rendering")
        adoption = read(ROOT / reviewed["path"])["feedback_adoption"]
        first, following = adoption["repeat"]["first_check"], adoption["repeat"]["second_check"]
        fix, final = adoption["repeat"]["production_fix"], adoption["repeat"]["final_recheck"]
        feedback_items.append(paragraph(
            f"实际反馈链：独立重复第{first['step']}步公开检查为{first['passed']}/{first['total']}，"
            "遗漏发生在拟合时完整、后续转换时缺失的列。"
            f"模型第{fix['model_step']}步修正特征排序，保留可用于后续转换的训练列，仅过滤训练时真正全空的列；"
            f"第{following['step']}步同一检查达到{following['passed']}/{following['total']}，随后保存合格候选。"
            f"第{final['step']}步对同一最终产物再次通过。首轮的一次注册检查直接通过。"
            "这条轨迹显示模型根据实际反馈补全了转换逻辑。"))
    return [heading("缺失值处理：区分初值统计与训练缺失状态"),
        paragraph("IterativeImputer须支持NaN（Not a Number，非数值）常量初值，以配合树估计器。"
                  "旧候选虽通过原评分，NaN初值仍将有效特征误判为空，提前返回并跳过迭代。"
                  "原因是把初值统计当作训练列是否有观测值的依据，训练后转换也沿用了错误列掩码。"),
        paragraph("修订借鉴官方实现，从原训练数据的缺失掩码识别空列，在fit时缓存并供transform复用；"
                  "初值统计与是否存在训练观测值分别处理。新增公开检查覆盖常量与默认初值、两种缺失哨兵、两种空列保留设置、"
                  "树估计器实际迭代，以及训练后新缺失列的转换。给定小样本与平方损失单叶树的预测应为目标观察均值，"
                  "另用四个零填充或一填充负控核对数值判据能拒绝错误实现。"),
        table(variants, [170, 90, 100, width - 360]),
        paragraph(f"独立工程参考通过{reference['fail_to_pass_passed']}个修复目标及{reference['pass_to_pass_passed']}个回归目标，"
                  "仅用于检验检查规则。随后固定两个新模型会话，模型获得公开检查和方法指导："),
        table(sessions, [85, 70, 75, 110, width - 340]),
        *feedback_items,
        paragraph("收益是补足原题评分遗漏的迭代与转换行为；该题原题评分此前已通过。12例均使用每列有观测值的训练数据，全空训练列覆盖仍有限。")]


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
        paragraph("FEAL（Fast Data Encipherment Algorithm，快速数据加密算法）本题采用四轮结构与20位种子扩展。原形态检查接受100条数字，内容需要另行验证。"
                  "新增支持复用公开线性攻击的概率1关系，仅从题面已知明密文对筛选外轮种子、反解中间轮；"
                  "公开语义检查再比较原程序解密产物的十进制词元与重数。通用算法的输入只有公开已知对。"
                  "检查经正确产物与错误、遗漏项回放验证。"),
        paragraph("两次独立新会话都实际编译并调用公开C算法，先用原程序回验32个已知对，再对100条目标输出逐条再加密核对。"
                  f"两份原题评分分别为{outcome(indexed['main'], 'feal-linear-cryptanalysis')}与{outcome(indexed['repeat'], 'feal-linear-cryptanalysis')}，"
                  f"实际生成分别{main['actual_requests']}与{repeat['actual_requests']}次，"
                  f"完整执行耗时{main['wall_seconds']:.1f}与{repeat['wall_seconds']:.1f}秒。"
                  "两份最终产物各100行、2047字节，与保存候选一致。"),
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


def mujoco_result_items(data):
    case = data["case_observations"].get("tune-mjcf")
    if case is None:
        if data["complete_required_experiments"]:
            raise ValueError("The final report lacks its completed original numerical-performance case")
        return []
    configuration = case["configuration"]
    options = "; ".join(f"{key}={value}" for key, value in configuration["options"].items())
    flags = "; ".join(f"{key}={value}" for key, value in configuration["flags"].items())
    check = case["self_check"]
    return [heading("速度目标与动态状态精度的联合验收"),
        paragraph("tune-mjcf要求同一场景模拟两秒，耗时不超过原来的60%，完整物理状态误差不超过1e-5，"
                  "且不能出现NaN（Not a Number，非数值）或无穷值。这同时考察速度和数值正确性。"
                  "下表来自独立重复会话；其四项原题验收均通过，公开检查仅确认文件存在且"
                  "可扩展标记语言（Extensible Markup Language，XML）文件可解析。"),
        table([["原题评分器观测", "记录值"],
            ["参考模型平均耗时", f"{case['reference_seconds']:.4f} 秒"],
            ["交付模型平均耗时", f"{case['tuned_seconds']:.4f} 秒"],
            ["报告的耗时比例／加速倍数", f"{case['printed_time_fraction']:.2f} / {case['printed_speedup']:.2f}x"],
            ["状态差异的原打印值", case["printed_final_difference"] + "（按输出精度）"],
            ["最终求解配置", options + "; " + flags]], [155, width - 155]),
        paragraph("本表测量仿真程序速度；前文用时表测量模型执行与原题验收的总时间。"
                  "从真实工具输出的原XML与采集的最终XML核对，修改仅涉及求解器选项，原物理属性树保持。"
                  "配置采用PGS（Projected Gauss–Seidel，投影高斯–赛德尔）求解器与稠密约束雅可比矩阵。"
                  "速度比来自这次本机联合调参验收；参考与候选的采样种子未配对，多个参数同时变化。"),
        paragraph(f"最终写出该配置后的真实脚本还报告{check['samples']}个扰动初态的自测，"
                  f"最大误差{check['reported_maximum_error']:.2e}，{check['reported_above_threshold']}项超过1e-5。"
                  f"另对前{check['explicit_finite_rechecks']}个初态显式复查有限性；原题四项验收独立通过。"),
        link("MuJoCo 3.3.5：Performance tuning（性能调优）",
            "https://mujoco.readthedocs.io/en/3.3.5/modeling.html#performance-tuning")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=FOLDER / "report-data.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--final-review", type=Path)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    data, tasks, indexed = load(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "preview_" if args.preview else ""
    subtitle = AUTHOR + (" · 内部预览，实验未齐" if args.preview else " · 同题比较与独立重复")
    footer = "智能推理与规划 · " + ("内部预览，实验未齐" if args.preview else "邱昱宁")
    baseline_path = ROOT / "work/hw0102-publish/shared/scripts/render_hw0102_final.py"
    spec = importlib.util.spec_from_file_location("course_baseline_final", baseline_path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    paths = [args.out_dir.resolve() / (prefix + "231880296_邱昱宁_作业" + numeral + ".pdf") for numeral in ("一", "二")]
    baseline.baseline_report(validation_items=work1_validation(data, indexed), output_filename=str(paths[0]),
        report_subtitle=subtitle, report_footer=footer, validation_first=True)
    build(str(paths[1]), "作业二 · 连续执行、公开验证与同题评测", work2_items(data, tasks, indexed, args.preview),
        subtitle=subtitle, footer=footer)
    print(json.dumps({"preview": args.preview, "pdfs": [{"path": str(p), "sha256": digest(p)} for p in paths],
        "new_model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
