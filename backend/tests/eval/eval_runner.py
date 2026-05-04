"""Extraction quality evaluation harness.

Runs all fixture files through the extraction pipeline and scores results
against ground truth in baseline/expected.json.

Usage:
    docker compose exec -e GEMINI_API_KEY=$GEMINI_API_KEY api python tests/eval/eval_runner.py
    PROMPT_VERSION=v1 docker compose exec -e GEMINI_API_KEY=$GEMINI_API_KEY api python tests/eval/eval_runner.py

Requires: GEMINI_API_KEY environment variable (real Gemini API access).
This is NOT a pytest test — run directly as a Python script.
"""
import json
import os
import sys
from pathlib import Path

from app.ai.prompts import get_system_prompt
from app.ai.gemini_client import call_gemini
from app.ai.postprocessor import deduplicate, validate_tasks
from tests.eval.scorer import completeness_score, precision_score, priority_accuracy, dedup_rate

FIXTURE_DIR = Path(__file__).parent / "fixtures"
BASELINE_FILE = Path(__file__).parent / "baseline" / "expected.json"


def run_fixture(name: str, content: str, ground_truth: dict, system_prompt: str) -> dict:
    """Run a single fixture through extraction and score it."""
    user_prompt = f"<content>\n{content}\n</content>"
    result = call_gemini(user_prompt, system_prompt)
    before_dedup = result.tasks
    after_dedup = validate_tasks(deduplicate(before_dedup))
    extracted_titles = [t.title for t in after_dedup]
    expected_titles = ground_truth.get("expected_titles", [])
    expected_prio = ground_truth.get("expected_priorities", {})
    return {
        "name": name,
        "extracted": len(after_dedup),
        "min_tasks": ground_truth.get("min_tasks", 0),
        "max_tasks": ground_truth.get("max_tasks", 99),
        "completeness": completeness_score(extracted_titles, expected_titles),
        "precision": precision_score(extracted_titles, expected_titles),
        "priority_acc": priority_accuracy(after_dedup, expected_prio),
        "dedup_rate": dedup_rate(before_dedup, after_dedup),
    }


def main() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set. Export it before running:", file=sys.stderr)
        print("  export GEMINI_API_KEY=your-key", file=sys.stderr)
        print("  docker compose exec -e GEMINI_API_KEY=$GEMINI_API_KEY api python tests/eval/eval_runner.py", file=sys.stderr)
        sys.exit(1)

    ground_truth = json.loads(BASELINE_FILE.read_text())
    prompt_version = os.environ.get("PROMPT_VERSION", "v2")
    system_prompt = get_system_prompt()

    print(f"\n{'='*65}")
    print(f"  Extraction Eval Report  |  PROMPT_VERSION={prompt_version}")
    print(f"{'='*65}")
    print(f"{'Fixture':<20} {'Tasks':>6} {'Compl':>7} {'Prec':>7} {'Prio':>7} {'Dedup':>7}")
    print(f"{'-'*65}")

    results = []
    errors = []
    for fixture_path in sorted(FIXTURE_DIR.glob("*.txt")):
        name = fixture_path.stem
        content = fixture_path.read_text()
        truth = ground_truth.get(name, {})
        try:
            r = run_fixture(name, content, truth, system_prompt)
            results.append(r)
            count_flag = ""
            if r["extracted"] < r["min_tasks"] or r["extracted"] > r["max_tasks"]:
                count_flag = " !"
            print(
                f"{name:<20} {r['extracted']:>5}{count_flag:>1}  "
                f"{r['completeness']:>6.2f}  {r['precision']:>6.2f}  "
                f"{r['priority_acc']:>6.2f}  {r['dedup_rate']:>6.2f}"
            )
        except Exception as e:
            errors.append(name)
            print(f"{name:<20} ERROR: {e}")

    if results:
        avg_completeness = sum(r["completeness"] for r in results) / len(results)
        avg_precision = sum(r["precision"] for r in results) / len(results)
        avg_priority = sum(r["priority_acc"] for r in results) / len(results)
        print(f"{'-'*65}")
        print(f"{'AVERAGE':<20} {'':>6}  {avg_completeness:>6.2f}  {avg_precision:>6.2f}  {avg_priority:>6.2f}")

    print(f"{'='*65}")
    if errors:
        print(f"\nFailed fixtures: {errors}")
        sys.exit(1)


if __name__ == "__main__":
    main()
