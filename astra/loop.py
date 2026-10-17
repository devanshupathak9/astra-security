"""Teacher -> student loop: ties all steps together.

  1. teacher scan                         -> teacher findings (or reuse a saved file)
  2. teacher findings -> lessons          (single pass, leak-filtered; shared by all students)
  3. for each student in config `loop.students`:
       student scan x N  (no lessons)     -> recall BEFORE
       student scan x N  (with lessons)   -> recall AFTER
  4. report: before vs after per student, mean +- std over N runs, per-bug hit counts

Labels are the ground truth when one is configured. Without it (e.g. a new app),
the teacher's findings are the labels, so we measure how close each student gets to the teacher.
Everything is saved to the run folder.
"""
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from astra.lessons import make_lessons, split_leaky
from astra.llm import get_llm
from astra.match import score
from astra.scan import scan
from astra.schemas import App, Finding, GroundTruth


def run_loop(app: App, config: dict, labels: list[GroundTruth] | None, strategy: str, depth: int,
             out: Path, teacher_findings: list[Finding] | None = None) -> str:
    teacher = get_llm(config, "teacher")
    runs = config["loop"]["student_runs"]

    def run_scan(llm, lessons=None):
        return scan(app, llm, config["categories"], strategy, depth, lessons,
                    config["scan"]["drop_unverified"])

    print(f"\n[1/3] Teacher scan ({teacher.model})")
    if teacher_findings is None:
        teacher_findings = run_scan(teacher)
    else:
        print(f"  reusing {len(teacher_findings)} saved findings")
    _save(out / "teacher_findings.json", [asdict(f) for f in teacher_findings])

    if labels is None:
        labels = labels_from_findings(teacher_findings)
        print(f"  no ground truth: using {len(labels)} teacher findings as labels")

    print("\n[2/3] Teacher writes lessons (single pass)")
    lessons = make_lessons(teacher_findings, teacher, config["loop"]["max_lessons"])
    lessons, rejected = split_leaky(lessons, app)
    _save(out / "lessons.json", {"lessons": lessons, "rejected_as_app_specific": rejected})
    for l in lessons:
        print(f"  - {l}")
    if rejected:
        print(f"  ({len(rejected)} rejected for naming app-specific things)")

    results = {}
    for role in config["loop"]["students"]:
        student = get_llm(config, role)
        print(f"\n[3/3] Student '{role}' ({student.model})")
        before, after = [], []
        for name, lessons_used, store in [("before", None, before), ("after", lessons, after)]:
            for i in range(runs):
                print(f" {name} lessons, run {i + 1}/{runs}")
                store.append(run_scan(student, lessons_used))
                _save(out / f"{role}_{name}_{i + 1}.json", [asdict(f) for f in store[-1]])
        results[role] = {"model": student.model, "before": before, "after": after}

    text = loop_report(labels, teacher_findings, teacher.model, results, lessons)
    (out / "report.md").write_text(text)
    _save(out / "results.json", {
        "teacher": teacher.model, "strategy": strategy, "runs": runs, "lessons": lessons,
        "teacher_score": score(teacher_findings, labels),
        "students": {role: {"model": r["model"],
                            "before": [score(f, labels) for f in r["before"]],
                            "after": [score(f, labels) for f in r["after"]]}
                     for role, r in results.items()},
    })
    return text


def labels_from_findings(findings: list[Finding]) -> list[GroundTruth]:
    unique = {(f.category, f.file): f for f in findings}
    return [GroundTruth(id=i + 1, title=f.title, categories=[f.category], files=[f.file])
            for i, f in enumerate(unique.values())]


def loop_report(labels, teacher_findings, teacher_model, results, lessons) -> str:
    def recall(runs, strict):
        values = [score(r, labels, strict)["recall"] * 100 for r in runs]
        return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)

    def cell(runs, strict):
        mean, sd = recall(runs, strict)
        return f"{mean:.0f}% ± {sd:.0f}"

    def lift(r, strict):
        return recall(r["after"], strict)[0] - recall(r["before"], strict)[0]

    t_strict = score(teacher_findings, labels, True)["recall"] * 100
    t_lenient = score(teacher_findings, labels, False)["recall"] * 100
    runs = len(next(iter(results.values()))["before"])
    lines = [
        "# Teacher -> student results",
        f"Teacher: {teacher_model} (strict {t_strict:.0f}%, lenient {t_lenient:.0f}%)   "
        f"Labels: {len(labels)}   Runs per student: {runs}   Lessons: {len(lessons)}",
        "",
        "| student | strict before | strict after | strict lift | lenient before | lenient after | lenient lift |",
        "|---|---|---|---|---|---|---|",
    ]
    for role, r in results.items():
        lines.append(f"| {r['model']} | {cell(r['before'], True)} | {cell(r['after'], True)} | "
                     f"**{lift(r, True):+.0f} pts** | {cell(r['before'], False)} | "
                     f"{cell(r['after'], False)} | {lift(r, False):+.0f} pts |")

    lines += ["", "Per bug: runs where each student found it (strict), before -> after. [T] = teacher found it.", ""]
    header = "".join(f" {r['model'][-18:]:>18}" for r in results.values())
    lines.append(f"  {'':4}{'bug':52}{header}")
    teacher_hits = score(teacher_findings, labels)["matched"]
    for lab in labels:
        t = "[T]" if lab.id in teacher_hits else "   "
        cols = ""
        for r in results.values():
            b = sum(lab.id in score(f, labels)["matched"] for f in r["before"])
            a = sum(lab.id in score(f, labels)["matched"] for f in r["after"])
            hits = f"{b}/{len(r['before'])} -> {a}/{len(r['after'])}"
            cols += f" {hits:>18}"
        lines.append(f"  {t} {lab.id:2}. {lab.title[:48]:48}{cols}")

    precision = []
    for r in results.values():
        p_b = statistics.mean(score(f, labels)["precision"] * 100 for f in r["before"])
        p_a = statistics.mean(score(f, labels)["precision"] * 100 for f in r["after"])
        n_b = statistics.mean(len(f) for f in r["before"])
        n_a = statistics.mean(len(f) for f in r["after"])
        precision.append(f"  {r['model']}: precision {p_b:.0f}% -> {p_a:.0f}%, findings {n_b:.1f} -> {n_a:.1f}")
    lines += ["", "Precision (unlisted real bugs count as wrong) and finding counts:", *precision]
    return "\n".join(lines)


def _save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2))
