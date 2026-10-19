"""Teacher -> student loop: ties all steps together.

  1. teacher scan                          -> teacher findings (or reuse a saved file)
  2. teacher findings -> lessons           (single pass, leak-filtered; shared by all students)
  3. for each student in config `loop.students`, N runs each of:
       before   - no extra advice                         -> recall BEFORE
       placebo  - generic advice, same length as lessons   -> control (optional)
       after    - the teacher's lessons                    -> recall AFTER
  4. report: recall per condition (mean +- std), lift, per-bug hit counts

The three conditions differ ONLY in the extra text added to the scan prompt.
Labels are the ground truth when one is configured. Without it (e.g. a new app),
the teacher's findings are the labels, so we measure how close each student gets to the teacher.
Everything is saved to the run folder.
"""
import json
import statistics
from dataclasses import asdict
from pathlib import Path

from astra.lessons import make_lessons, make_placebo, split_leaky
from astra.llm import get_llm
from astra.match import score
from astra.scan import scan
from astra.schemas import App, Finding, GroundTruth


def run_loop(app: App, config: dict, labels: list[GroundTruth] | None, strategy: str, depth: int,
             out: Path, teacher_findings: list[Finding] | None = None) -> str:
    teacher = get_llm(config, "teacher")
    runs = int(config["loop"]["student_runs"])

    def run_scan(llm, advice=None):
        return scan(app, llm, config["categories"], strategy, depth, advice,
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
    placebo = make_placebo(lessons)
    _save(out / "lessons.json", {"lessons": lessons, "rejected_as_app_specific": rejected,
                                 "placebo": placebo})
    for l in lessons:
        print(f"  - {l}")
    if rejected:
        print(f"  ({len(rejected)} rejected for naming app-specific things)")

    # condition name -> extra text added to the student's prompt
    conditions = {"before": None, "after": lessons}
    if config["loop"].get("placebo"):
        conditions = {"before": None, "placebo": placebo, "after": lessons}

    results = {}
    for role in config["loop"]["students"]:
        student = get_llm(config, role)
        print(f"\n[3/3] Student '{role}' ({student.model})")
        results[role] = {"model": student.model}
        for name, advice in conditions.items():
            results[role][name] = []
            for i in range(runs):
                print(f" {name}, run {i + 1}/{runs}")
                findings = run_scan(student, advice)
                results[role][name].append(findings)
                _save(out / f"{role}_{name}_{i + 1}.json", [asdict(f) for f in findings])

    text = loop_report(labels, teacher_findings, teacher.model, results, list(conditions), len(lessons))
    (out / "report.md").write_text(text)
    _save(out / "results.json", {
        "teacher": teacher.model, "strategy": strategy, "runs": runs, "lessons": lessons,
        "teacher_score": score(teacher_findings, labels),
        "students": {role: {"model": r["model"],
                            **{c: [score(f, labels) for f in r[c]] for c in conditions}}
                     for role, r in results.items()},
    })
    return text


def labels_from_findings(findings: list[Finding]) -> list[GroundTruth]:
    unique = {(f.category, f.file): f for f in findings}
    return [GroundTruth(id=i + 1, title=f.title, categories=[f.category], files=[f.file])
            for i, f in enumerate(unique.values())]


def loop_report(labels, teacher_findings, teacher_model, results, conditions, n_lessons) -> str:
    def recall(runs, strict):
        """Mean and std (in %) of recall over the runs."""
        values = [score(r, labels, strict)["recall"] * 100 for r in runs]
        return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)

    def recall_table(strict):
        cols = " | ".join(conditions)
        lift_cols = "lift vs before" + (" | lift vs placebo" if "placebo" in conditions else "")
        rows = [f"| student | {cols} | {lift_cols} |",
                "|---" * (len(conditions) + 2 + ("placebo" in conditions)) + "|"]
        for r in results.values():
            cells = []
            for c in conditions:
                mean, sd = recall(r[c], strict)
                cells.append(f"{mean:.0f}% ± {sd:.0f}")
            after = recall(r["after"], strict)[0]
            lifts = [f"**{after - recall(r['before'], strict)[0]:+.0f} pts**"]
            if "placebo" in conditions:
                lifts.append(f"{after - recall(r['placebo'], strict)[0]:+.0f} pts")
            rows.append(f"| {r['model']} | {' | '.join(cells)} | {' | '.join(lifts)} |")
        return rows

    t_strict = score(teacher_findings, labels, True)["recall"] * 100
    t_lenient = score(teacher_findings, labels, False)["recall"] * 100
    runs = len(next(iter(results.values()))["before"])
    lines = [
        "# Teacher -> student results",
        "",
        f"Teacher: {teacher_model} (strict recall {t_strict:.0f}%, lenient {t_lenient:.0f}%)  ",
        f"Labels: {len(labels)}   Runs per condition: {runs}   Lessons: {n_lessons}",
        "",
        "## Strict recall (right file and right category)",
        *recall_table(True),
        "",
        "## Lenient recall (right file, any category)",
        *recall_table(False),
        "",
        "## Per bug: runs where the student found it (strict), " + " -> ".join(conditions),
        "[T] = the teacher found it",
        "",
    ]
    teacher_hits = score(teacher_findings, labels)["matched"]
    for lab in labels:
        t = "[T]" if lab.id in teacher_hits else "   "
        cols = ""
        for r in results.values():
            hits = " -> ".join(f"{sum(lab.id in score(f, labels)['matched'] for f in r[c])}/{len(r[c])}"
                               for c in conditions)
            cols += f"  {r['model'][-14:]:>14}: {hits}"
        lines.append(f"    {t} {lab.id:2}. {lab.title[:46]:46}{cols}")

    lines += ["", "## Precision and finding counts (unlisted real bugs count as wrong)"]
    for r in results.values():
        parts = []
        for c in conditions:
            p = statistics.mean(score(f, labels)["precision"] * 100 for f in r[c])
            n = statistics.mean(len(f) for f in r[c])
            parts.append(f"{c} {p:.0f}% ({n:.1f} findings)")
        lines.append(f"- {r['model']}: " + ", ".join(parts))
    return "\n".join(lines)


def _save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2))
