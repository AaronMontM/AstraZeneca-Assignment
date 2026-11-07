import argparse
import csv
import json
import logging
import re

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


METRICS_ORDER = [
    "route_accuracy",
    "data_retrieval_accuracy",
    "policy_answer_accuracy",
    "both_answer_accuracy",
    "clarification_accuracy",
    "factual_correctness",
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "average_latency_seconds",
]

JUDGE_METRICS = [
    "policy_answer_accuracy",
    "both_answer_accuracy",
    "factual_correctness",
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save a JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def get_model_name(benchmark_stem: str) -> str:
    """Extract a readable model name from a benchmark filename."""

    name = benchmark_stem

    if name.startswith("benchmark_"):
        name = name[len("benchmark_"):]

    return name


def find_judge_file(
    benchmark_stem: str,
    judged_dir: Path,
    judge_model: Optional[str] = None,
) -> Optional[Path]:
    """Find the Judge report associated with a benchmark."""

    prefix = f"judged_{benchmark_stem}_"

    candidates = [
        path
        for path in judged_dir.glob("judged_*.json")
        if path.name.startswith(prefix)
    ]

    if judge_model:
        judge_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", judge_model)

        candidates = [
            path
            for path in candidates
            if path.stem.endswith(judge_slug)
        ]

    if not candidates:
        return None

    # If several Judge reports exist, use the most recently modified one.
    return max(candidates, key=lambda path: path.stat().st_mtime)


def extract_accuracy(
    report: dict[str, Any],
    metric_path: tuple[str, ...],
) -> Optional[float]:
    """Extract an accuracy value from a nested report."""

    current: Any = report

    for key in metric_path:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    if isinstance(current, (int, float)):
        return float(current)

    return None


def extract_deterministic_metrics(
    report: dict[str, Any],
) -> dict[str, Optional[float]]:
    """Extract deterministic metrics from a metrics report."""

    functional = report.get("functional_metrics", {})
    performance = report.get("performance_metrics", {})

    route_accuracy = extract_accuracy(
        functional,
        ("route_accuracy", "overall", "accuracy"),
    )

    data_retrieval_accuracy = extract_accuracy(
        functional,
        ("data_retrieval_accuracy", "accuracy"),
    )

    clarification = functional.get("clarification_accuracy", {})

    # Prefer the combined value if semantic clarification evaluation
    # has been implemented. Otherwise, use deterministic accuracy.
    clarification_accuracy = clarification.get("combined_accuracy")

    if clarification_accuracy is None:
        clarification_accuracy = clarification.get("deterministic_accuracy")

    if clarification_accuracy is None:
        clarification_accuracy = clarification.get("accuracy")

    if clarification_accuracy is not None:
        clarification_accuracy = float(clarification_accuracy)

    average_latency = performance.get("average_latency_seconds")

    if average_latency is not None:
        average_latency = float(average_latency)

    return {
        "route_accuracy": route_accuracy,
        "data_retrieval_accuracy": data_retrieval_accuracy,
        "clarification_accuracy": clarification_accuracy,
        "average_latency_seconds": average_latency,
    }


def extract_judge_metrics(
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Aggregate Judge scores across completed evaluations."""

    results = report.get("results", [])

    metrics = {
        metric: {
            "score": None,
            "evaluated": 0,
        }
        for metric in JUDGE_METRICS
    }

    score_totals = {
        metric: 0.0
        for metric in JUDGE_METRICS
    }

    for result in results:
        if result.get("status") != "completed":
            continue

        evaluation = result.get("evaluation")

        if not isinstance(evaluation, dict):
            continue

        applicable_metrics = result.get("applicable_metrics", [])

        for metric in JUDGE_METRICS:
            if applicable_metrics and metric not in applicable_metrics:
                continue

            metric_result = evaluation.get(metric)

            if not isinstance(metric_result, dict):
                continue

            score = metric_result.get("score")

            if not isinstance(score, (int, float)):
                continue

            score_totals[metric] += float(score)
            metrics[metric]["evaluated"] += 1

    for metric in JUDGE_METRICS:
        evaluated = metrics[metric]["evaluated"]

        if evaluated > 0:
            metrics[metric]["score"] = (
                score_totals[metric] / evaluated
            )

    return metrics


def build_model_report(
    deterministic_path: Path,
    judged_dir: Path,
    judge_model: Optional[str] = None,
) -> dict[str, Any]:
    """Build the global metrics report for one model."""

    deterministic_report = load_json(deterministic_path)

    benchmark_stem = deterministic_path.stem.removeprefix("metrics_")
    model_name = get_model_name(benchmark_stem)

    deterministic_metrics = extract_deterministic_metrics(
        deterministic_report
    )

    judge_path = find_judge_file(
        benchmark_stem=benchmark_stem,
        judged_dir=judged_dir,
        judge_model=judge_model,
    )

    judge_metrics = {
        metric: {
            "score": None,
            "evaluated": 0,
        }
        for metric in JUDGE_METRICS
    }

    judge_model_name = None

    if judge_path:
        judge_report = load_json(judge_path)
        judge_metadata = judge_report.get("metadata", {})

        judge_model_name = judge_metadata.get("judge_model")
        judge_metrics = extract_judge_metrics(judge_report)

    else:
        logger.warning(
            "No Judge report found for benchmark '%s'.",
            benchmark_stem,
        )

    metrics = {}

    for metric in METRICS_ORDER:
        if metric in deterministic_metrics:
            metrics[metric] = {
                "score": deterministic_metrics[metric],
                "evaluated": None,
            }

        elif metric in judge_metrics:
            metrics[metric] = judge_metrics[metric]

    clarification = (
        deterministic_report
        .get("functional_metrics", {})
        .get("clarification_accuracy", {})
    )

    semantic_accuracy = clarification.get("semantic_accuracy")
    combined_accuracy = clarification.get("combined_accuracy")

    return {
        "model": model_name,
        "benchmark_file": deterministic_path.name,
        "judge_file": judge_path.name if judge_path else None,
        "judge_model": judge_model_name,
        "clarification_evaluation": {
            "deterministic_accuracy": deterministic_metrics[
                "clarification_accuracy"
            ],
            "semantic_accuracy": semantic_accuracy,
            "combined_accuracy": combined_accuracy,
        },
        "metrics": metrics,
    }


def build_global_report(
    reports_dir: Path,
    judged_dir: Path,
    judge_model: Optional[str] = None,
) -> dict[str, Any]:
    """Build a comparison report for all available models."""

    deterministic_files = sorted(
        reports_dir.glob("metrics_*.json")
    )

    if not deterministic_files:
        raise FileNotFoundError(
            f"No deterministic metrics files found in {reports_dir}"
        )

    models = []

    for path in deterministic_files:
        logger.info("Processing %s", path.name)

        try:
            model_report = build_model_report(
                deterministic_path=path,
                judged_dir=judged_dir,
                judge_model=judge_model,
            )

            models.append(model_report)

        except (OSError, ValueError, KeyError, TypeError) as error:
            logger.exception(
                "Could not process %s: %s",
                path.name,
                error,
            )

    models.sort(key=lambda item: item["model"].lower())

    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "models_compared": len(models),
            "judge_model_filter": judge_model,
            "metrics_order": METRICS_ORDER,
            "clarification_note": (
                "Clarification accuracy uses deterministic routing "
                "accuracy when semantic and combined scores are unavailable."
            ),
        },
        "models": models,
    }


def export_csv(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    """Export the comparison report as CSV."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["model"] + METRICS_ORDER

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for model in report["models"]:
            row = {
                "model": model["model"],
            }

            for metric in METRICS_ORDER:
                metric_data = model["metrics"].get(metric, {})
                row[metric] = metric_data.get("score")

            writer.writerow(row)


def print_comparison(report: dict[str, Any]) -> None:
    """Print a compact comparison table."""

    models = report["models"]

    if not models:
        print("No models available for comparison.")
        return

    headers = ["Model"] + METRICS_ORDER

    rows = []

    for model in models:
        row = [model["model"]]

        for metric in METRICS_ORDER:
            value = model["metrics"].get(metric, {}).get("score")

            if value is None:
                row.append("-")
            elif metric == "average_latency_seconds":
                row.append(f"{value:.2f}s")
            else:
                row.append(f"{value * 100:.2f}%")

        rows.append(row)

    widths = [
        max(
            len(headers[index]),
            *(len(row[index]) for row in rows),
        )
        for index in range(len(headers))
    ]

    header_line = " | ".join(
        headers[index].ljust(widths[index])
        for index in range(len(headers))
    )

    separator = "-+-".join(
        "-" * width
        for width in widths
    )

    print()
    print(header_line)
    print(separator)

    for row in rows:
        print(
            " | ".join(
                row[index].ljust(widths[index])
                for index in range(len(row))
            )
        )

    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare deterministic and LLM Judge metrics "
            "across Finance Spend Intelligence Assistant models."
        )
    )

    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("evaluation/results/reports"),
        help="Directory containing deterministic metrics JSON files.",
    )

    parser.add_argument(
        "--judged-dir",
        type=Path,
        default=Path("evaluation/results/judged"),
        help="Directory containing LLM Judge JSON files.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/results/reports"),
        help="Directory where global reports will be saved.",
    )

    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help=(
            "Optional Judge model filter, e.g. gpt-oss:20b. "
            "If omitted, the most recently modified Judge report "
            "is selected for each benchmark."
        ),
    )

    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    args = parse_args()

    report = build_global_report(
        reports_dir=args.reports_dir,
        judged_dir=args.judged_dir,
        judge_model=args.judge_model,
    )

    output_json = args.output_dir / "global_metrics.json"
    output_csv = args.output_dir / "global_metrics.csv"

    save_json(report, output_json)
    export_csv(report, output_csv)

    print_comparison(report)

    logger.info("JSON report saved to: %s", output_json)
    logger.info("CSV report saved to: %s", output_csv)


if __name__ == "__main__":
    main()