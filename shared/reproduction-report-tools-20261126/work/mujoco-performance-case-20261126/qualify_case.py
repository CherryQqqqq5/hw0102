import ast
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


def main():
    root, folder = Path.cwd(), Path(__file__).parent
    path = root / "work/parallel-free-evaluation-20261124/prepare_report_data.py"
    spec = importlib.util.spec_from_file_location("actual_physics_case_reader", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    state = reader.read(root / "work/vmshare/performance75-hy4-sql-layout-v18-repeat-20261125/state.json")
    row = dict(next(r for r in state["policy_results"] if r["task"] == "tune-mjcf"), arm="repeat")
    source = Path(row["run_dir"])
    row["original_score_sha256"] = reader.digest(source / "result.json")
    facts, bindings = reader.mujoco_repeat_case(root, row)
    assert facts["printed_final_difference"] == "0.0000" and isinstance(facts["printed_final_difference"], str)
    assert facts["self_check"]["explicit_finite_rechecks"] == 5 < facts["self_check"]["samples"] == 50
    assert facts["original_physical_tree_unchanged"] is True
    original_hashes = {name: reader.digest(root / name) for name in bindings["files_sha256"]}
    rejected = []

    def deny(name, value):
        try:
            reader.mujoco_repeat_case(root, value)
        except ValueError as error:
            rejected.append({"name": name, "rejected": True, "error_type": type(error).__name__})
        else:
            raise AssertionError("An invalid numerical case was accepted: " + name)

    deny("wrong_arm", row | {"arm": "main"})
    deny("false_original_score", row | {"passed": False})
    deny("wrong_original_result_sha", row | {"original_score_sha256": "0" * 64})
    for kind in ("changed_original_grade", "zero_observed_time", "changed_captured_xml", "changed_reference_tree"):
        fixture = folder / "private-fixtures" / kind
        fixture.mkdir(parents=True, exist_ok=False)
        for name in bindings["files_sha256"]:
            original = root / name
            destination = fixture / original.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
        value = row | {"run_dir": str(fixture.relative_to(root))}
        if kind in {"changed_original_grade", "zero_observed_time"}:
            grade, = fixture.rglob("test-stdout.txt")
            text = grade.read_text()
            if kind == "changed_original_grade":
                text = text.replace("PASSED ../tests/test_outputs.py::test_model_speed", "FAILED ../tests/test_outputs.py::test_model_speed")
            else:
                text = text.replace("Avg simulation time: 0.4276 secs", "Avg simulation time: 0.0000 secs")
            grade.write_text(text)
        elif kind == "changed_captured_xml":
            xml_path = reader.native_output(fixture, "/app/model.xml")
            xml_path.write_text(xml_path.read_text().replace('iterations="100"', 'iterations="99"'))
        else:
            tools_path, = fixture.rglob("tools.jsonl")
            tools = [json.loads(line) for line in tools_path.read_text().splitlines()]
            original, = reader.re.findall(r"<mujoco\b.*?</mujoco>", tools[0]["stdout"], reader.re.DOTALL)
            tree = ET.fromstring(original)
            geom = tree.find(".//geom")
            geom.set("friction", "0.9 0.01 0.001")
            tools[0]["stdout"] = tools[0]["stdout"].replace(original, ET.tostring(tree, encoding="unicode"))
            tools_path.write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in tools))
        deny(kind, value)
    assert original_hashes == {name: reader.digest(root / name) for name in original_hashes}
    before = ast.parse((folder / "consumer-before-physics-case.py.txt").read_text())
    current = ast.parse(path.read_text())
    previous_functions = {n.name: ast.dump(n) for n in before.body if isinstance(n, ast.FunctionDef)}
    current_functions = {n.name: ast.dump(n) for n in current.body if isinstance(n, ast.FunctionDef)}
    changed = {name for name in previous_functions if previous_functions[name] != current_functions[name]}
    assert changed == {"case_observations"}
    assert current_functions.keys() - previous_functions.keys() == {"mujoco_repeat_case"}
    old_renderer = ast.parse((folder / "renderer-before-physics-case.py.txt").read_text())
    new_renderer = ast.parse((root / "work/render_hy4_final_reports.py").read_text())
    old_load = next(n for n in old_renderer.body if isinstance(n, ast.FunctionDef) and n.name == "load")
    new_load = copy.deepcopy(next(n for n in new_renderer.body if isinstance(n, ast.FunctionDef) and n.name == "load"))
    sets = [n for n in ast.walk(new_load) if isinstance(n, ast.Set) and any(isinstance(e, ast.Constant) and e.value == "tune-mjcf" for e in n.elts)]
    assert len(sets) == 1
    sets[0].elts = [e for e in sets[0].elts if not isinstance(e, ast.Constant) or e.value != "tune-mjcf"]
    assert ast.dump(old_load) == ast.dump(new_load)
    proof = {"actual_facts": facts, "actual_case_sources": bindings, "original_sources_unchanged": True,
        "negative_controls": rejected, "consumer_previous_functions_changed": sorted(changed),
        "renderer_load_only_added_exact_case_whitelist": True,
        "source_sha256": {str(path.relative_to(root)): reader.digest(path),
            "work/render_hy4_final_reports.py": reader.digest(root / "work/render_hy4_final_reports.py")},
        "scope": "One actual archived repeat and seven explicit local mutated-copy/data negatives. No model, grader or VM. Private fixture copies are not new experimental outcomes and must not enter delivered run inventories.",
        "new_model_calls": 0, "formal_PDFs_generated": False}
    (folder / "qualification.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"actual_case_sources": len(bindings["files_sha256"]), "negative_controls": len(rejected),
        "all_passed": True, "new_model_calls": 0, "qualification_sha256": reader.digest(folder / "qualification.json")}))


if __name__ == "__main__":
    main()
