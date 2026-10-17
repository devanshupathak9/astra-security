"""Teacher -> student loop: ties all steps together.

  1. teacher scan                         -> teacher findings (or reuse a saved file)
  2. student scan x N  (no lessons)       -> recall BEFORE
  3. teacher findings -> lessons          (single pass, leak-filtered)
  4. student scan x N  (with lessons)     -> recall AFTER
  5. report: before vs after, mean +- std over N runs, per-bug hit counts

Labels are the ground truth when one is configured. Without it (e.g. a new app),
the teacher's findings are the labels, so we measure how close the student gets to the teacher.
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
    teacher, student = get_llm(config, "teacher"), get_llm(config, "student")
    runs = config["loop"]["student_runs"]

    def run_scan(llm, lessons=None):
        return scan(app, llm, config["categories"], strategy, depth, lessons,
                    config["scan"]["drop_unverified"])

    print(f"\n[1/4] Teacher scan ({teacher.model})")
    if teacher_findings is None:
        teacher_findings = run_scan(teacher)
    else:
        print(f"  reusing {len(teacher_findings)} saved findings")
    _save(out / "teacher_findings.json", [asdict(f) for f in teacher_findings])

    if labels is None:
        labels = labels_from_findings(teacher_findings)
        print(f"  no ground truth: using {len(labels)} teacher findings as labels")

    print(f"\n[2/4] Student scan WITHOUT lessons ({student.model}) x{runs}")
    before = []
    for i in range(runs):
        print(f" run {i + 1}/{runs}")
        before.append(run_scan(student))
        _save(out / f"student_before_{i + 1}.json", [asdict(f) for f in before[-1]])

    print("\n[3/4] Teacher writes lessons (single pass)")
    lessons = make_lessons(teacher_findings, teacher, config["loop"]["max_lessons"])
    lessons, rejected = split_leaky(lessons, app)
    _save(out / "lessons.json", {"lessons": lessons, "rejected_as_app_specific": rejected})
    for l in lessons:
        print(f"  - {l}")
    if rejected:
        print(f"  ({len(rejected)} rejected for naming app-specific things)")

    print(f"\n[4/4] Student scan WITH lessons x{runs}")
    after = []
    for i in range(runs):
        print(f" run {i + 1}/{runs}")
        after.append(run_scan(student, lessons))
        _save(out / f"student_after_{i + 1}.json", [asdict(f) for f in after[-1]])

    text = loop_report(labels, teacher_findings, before, after, teacher.model, student.model)
    (out / "report.md").write_text(text)
    _save(out / "results.json", {
        "teacher": teacher.model, "student": student.model, "strategy": strategy, "runs": runs,
        "teacher_score": score(teacher_findings, labels),
        "before": [score(r, labels) for r in before],
        "after": [score(r, labels) for r in after],
        "lessons": lessons,
    })
    return text


def labels_from_findings(findings: list[Finding]) -> list[GroundTruth]:
    unique = {(f.category, f.file): f for f in findings}
    return [GroundTruth(id=i + 1, title=f.title, categories=[f.category], files=[f.file])
            for i, f in enumerate(unique.values())]


def loop_report(labels, teacher_findings, before, after, teacher_model, student_model) -> str:
    def stats(results, strict):
        recalls = [score(r, labels, strict)["recall"] * 100 for r in results]
        sd = statistics.stdev(recalls) if len(recalls) > 1 else 0.0
        return statistics.mean(recalls), sd

    def row(name, results):
        s_mean, s_sd = stats(results, True)
        l_mean, l_sd = stats(results, False)
        prec = statistics.mean(score(r, labels)["precision"] * 100 for r in results)
        n = statistics.mean(len(r) for r in results)
        return f"| {name} | {s_mean:.0f}% ± {s_sd:.0f} | {l_mean:.0f}% ± {l_sd:.0f} | {prec:.0f}% | {n:.1f} |"

    b_strict, a_strict = stats(before, True)[0], stats(after, True)[0]
    b_len, a_len = stats(before, False)[0], stats(after, False)[0]
    lines = [
        f"# Teacher -> student results",
        f"Teacher: {teacher_model}   Student: {student_model}   Labels: {len(labels)}   Runs: {len(before)}",
        "",
        "| | strict recall | lenient recall | precision | findings |",
        "|---|---|---|---|---|",
        row("teacher", [teacher_findings]),
        row("student before", before),
        row("student after", after),
        "",
        f"**Recall lift: strict {a_strict - b_strict:+.0f} pts, lenient {a_len - b_len:+.0f} pts**",
        "",
        "Per bug, runs where the student found it (strict), before -> after:",
    ]
    for lab in labels:
        hits_b = sum(lab.id in score(r, labels)["matched"] for r in before)
        hits_a = sum(lab.id in score(r, labels)["matched"] for r in after)
        t = "T" if lab.id in score(teacher_findings, labels)["matched"] else " "
        lines.append(f"  [{t}] {lab.id:2}. {lab.title[:55]:55} {hits_b}/{len(before)} -> {hits_a}/{len(after)}")
    lines.append("  ([T] = the teacher found it)")
    return "\n".join(lines)


def _save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2))
