import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--repository", type=Path, default=Path.cwd())
ROOT = parser.parse_args().repository
EVIDENCE = ROOT / "作业一/evidence"
TASK_GOALS = {
    "django__django-13346": "修复JSON字段键转换后的in查询",
    "django__django-15987": "检测Path形式的重复fixture目录",
    "django__django-16082": "推导不同数值类型取模后的字段类型",
    "pydata__xarray-2905": "赋值时正确处理具有values属性的对象",
    "pydata__xarray-3305": "分位数计算遵守keep_attrs设置",
    "pydata__xarray-6599": "正确计算时间差坐标上的多项式",
    "pytest-dev__pytest-7205": "展示bytes参数时避免BytesWarning",
    "pytest-dev__pytest-8399": "恢复unittest类级fixture的私有性",
    "scikit-learn__scikit-learn-13496": "为IsolationForest暴露warm_start参数",
    "scikit-learn__scikit-learn-14496": "正确处理OPTICS的浮点min_samples",
    "extract-elf": "输出正确内存地址和值，参考覆盖至少75%",
    "fix-git": "找回遗失修改并合入master",
    "llm-inference-batching-scheduler": "交付两桶调度计划并满足性能与形状限制",
    "mailman": "完成本地邮件投递、入组、公告及退出",
    "openssl-selfsigned-cert": "生成符合题面参数与权限的证书文件",
    "query-optimize": "保持数据库及结果不变，交付高效sol.sql",
    "regex-log": "匹配含合法IPv4日志行中的最后一个日期",
    "sparql-university": "查询满足公开组织及授课条件的教授",
    "sqlite-db-truncate": "从截断数据库恢复记录至recover.json",
    "video-processing": "生成起跳及落地帧，满足原题精度验收",
    "cpp/linked-list": "实现双向链表及规定操作",
    "cpp/parallel-letter-frequency": "并行统计文本中的字母频次",
    "go/trinary": "三进制转十进制，非法输入返回零",
    "go/variable-length-quantity": "实现变长整数编码解码及异常检查",
    "java/phone-number": "规范化并校验北美电话号码",
    "javascript/food-chain": "按规则生成累积式歌词",
    "javascript/triangle": "判定合法三角形及边长类别",
    "python/proverb": "按输入顺序生成对应谚语",
    "python/tree-building": "重构记录建树并校验非法关系",
    "rust/doubly-linked-list": "实现双向链表、迭代器及游标",
}
FAILURES = {
    "video-processing": ("语义精度", "脚本能导入，起跳帧66/322超出50–54/219–223；实现较晚压缩验证时间，提前实现能否修复未验证。"),
    "query-optimize": ("产物交付", "临时候选可执行，最终sol.sql缺失；临时索引副本上的等价输出不足以证明原库正确性与性能。"),
    "llm-inference-batching-scheduler": ("产物交付", "plan_b1.jsonl缺失且本地八组设置均未达指标；提供方超时为伴随因素，提前落盘不保证性能达标。"),
    "extract-elf": ("验证范围不足", "原评分参考地址覆盖0%，本地698项自查沿用相同地址假设；映射不一致为原因假设，未完成独立因果验证。"),
}


def build():
    observations = {row["task"]: row for row in json.loads((EVIDENCE / "task-observations.json").read_text())["records"]}
    with (EVIDENCE / "formal-trials.csv").open() as stream:
        rows = [row for row in csv.DictReader(stream) if row["split"] == "D" and row["arm"] == "B0"]
    assert len(rows) == 30
    assert Counter(row["benchmark"] for row in rows) == {"swe": 10, "terminal": 10, "aider": 10}
    assert {row["task"] for row in rows} == TASK_GOALS.keys()
    records = []
    for row in rows:
        directory = EVIDENCE / "formal" / row["run_id"]
        trial = json.loads((directory / "trial.json").read_text())
        result = json.loads((directory / "result.json").read_text())
        assert result["scoreable"] and result["passed"] is (row["passed"] == "True")
        assert trial["task"]["id"] == row["task"]
        instructions = list(directory.rglob("instruction.txt"))
        tools = list(directory.rglob("tools.jsonl"))
        models = list(directory.rglob("model.jsonl"))
        assert len(instructions) == len(tools) == len(models) == 1
        passed = result["passed"]
        category, analysis = FAILURES[row["task"]] if not passed else (
            "原题通过", "原题验收通过；成功仅覆盖其验收范围，终止状态与产物评分分别记录，不额外推断失败机制。")
        observed = observations[row["task"]]
        assert observed["run_id"] == row["run_id"] and observed["passed"] is passed
        for source in observed["sources"].values():
            assert hashlib.sha256((EVIDENCE / source["path"]).read_bytes()).hexdigest() == source["sha256"]
        evidence_paths = [str(path.relative_to(EVIDENCE)) for path in (instructions[0], tools[0], models[0], directory / "result.json")]
        scoring = [str(path.relative_to(EVIDENCE)) for path in directory.rglob("*")
                   if path.is_file() and path.name in ("report.json", "test_output.txt", "test-stdout.txt", "reward.txt", "grader.json")]
        if not scoring:
            raise ValueError("Missing original scoring output: " + row["run_id"])
        records.append({"run_id": row["run_id"], "benchmark": row["benchmark"], "task": row["task"],
            "task_description": TASK_GOALS[row["task"]], "complete_task_input": instructions[0].read_text(),
            "expected_result": observed["expected_result"], "actual_result": observed["actual_result"],
            "passed": passed, "exit_status": row["exit_status"], "model_requests": int(row["model_calls"]),
            "tool_calls": int(row["tool_calls"]), "wall_seconds": float(row["wall_seconds"]),
            "preliminary_category": category, "preliminary_analysis": analysis,
            "execution_and_final_output_sources": evidence_paths, "original_scoring_sources": scoring,
            "artifact_sources": [str(path.relative_to(EVIDENCE)) for path in directory.rglob("*")
                                 if path.is_file() and path.name in ("artifact.json", "candidate.patch", "agent.json")]})
    assert sum(record["passed"] for record in records) == 26
    output = EVIDENCE / "task-records.json"
    output.write_text(json.dumps({"scope": "30 original diagnostic baseline tasks; local reorganization only",
        "new_model_or_grader_calls": 0, "records": records}, ensure_ascii=False, indent=2) + "\n")
    fields = [key for key in records[0] if key != "complete_task_input"]
    with (EVIDENCE / "task-records.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                         for key, value in record.items() if key in fields} for record in records)
    print(json.dumps({"tasks": len(records), "passed": 26, "failed": 4,
        "full_inputs_and_trace_paths_verified": True, "new_model_or_grader_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    build()
