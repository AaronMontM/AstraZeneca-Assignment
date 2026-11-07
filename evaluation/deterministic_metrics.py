import argparse
import json
import logging
import math

from collections import Counter
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)

NUMERIC_TOLERANCE = 0.01

FIELD_ALIASES = {
    "invoice_number": ["invoice_number"],
    "invoice_date": ["invoice_date"],
    "invoice_month": ["invoice_month"],
    "invoice_quarter": ["invoice_quarter", "quarter"],
    "vendor_id": ["vendor_id"],
    "vendor_name": ["vendor_name"],
    "vendor_status": ["vendor_status"],
    "vendor_country": ["vendor_country"],
    "vendor_category": ["vendor_category"],
    "currency": ["currency"],
    "amount": ["amount"],
    "EUR_amount": ["EUR_amount", "eur_amount"],
    "net_spend_eur": ["net_spend_eur", "total_eur_spend"],
    "total_net_spend_eur": [
        "total_net_spend_eur",
        "total_eur_spend",
    ],
    "average_invoice_eur": [
        "average_invoice_eur",
        "average_invoice_amount",
    ],
    "invoice_count": ["invoice_count"],
    "vendor_count": ["vendor_count"],
    "po_number": ["po_number"],
    "approved_by": ["approved_by"],
    "required_approver": ["required_approver"],
    "maverick_spend": ["maverick_spend"],
    "missing_po": ["missing_po"],
    "missing_approver": ["missing_approver"],
    "requires_PE_escalation": ["requires_PE_escalation"],
    "required_action": ["required_action"],
    "cost_center": ["cost_center", "cost_centre"],
    "credit_note": ["credit_note"],
}


def load_benchmark(path: Path) -> dict[str, Any]:
    """Load a raw benchmark JSON file."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_route(route: Optional[str]) -> Optional[str]:
    """Normalize a route name."""

    if route is None:
        return None

    return route.strip().lower()


def parse_acceptable_routes(value: Optional[str]) -> list[str]:
    """Parse acceptable routes from the ground truth."""

    if not value:
        return []

    return [
        route.strip().lower()
        for route in value.replace(",", ";").split(";")
        if route.strip()
    ]


def get_expected_routes(
    ground_truth: dict[str, Any],
    turn_type: str,
) -> list[str]:
    """Get the acceptable routes for a benchmark turn."""

    if turn_type == "initial":
        acceptable_routes = parse_acceptable_routes(
            ground_truth.get("Acceptable routes")
        )

        if acceptable_routes:
            return acceptable_routes

        expected_route = ground_truth.get("Expected route")

    elif turn_type == "follow_up":
        expected_route = ground_truth.get(
            "Expected route after clarification"
        )

    else:
        raise ValueError(f"Unknown turn type: {turn_type}")

    if not expected_route:
        return []

    return [normalize_route(expected_route)]


def evaluate_route(
    actual_route: Optional[str],
    expected_routes: list[str],
) -> Optional[bool]:
    """Check whether the actual route is acceptable."""

    if not actual_route or not expected_routes:
        return None

    return normalize_route(actual_route) in expected_routes


def calculate_route_metrics(
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate route accuracy globally and by expected route."""

    valid_evaluations = [
        item
        for item in evaluations
        if item["route_correct"] is not None
    ]

    total = len(valid_evaluations)
    correct = sum(
        item["route_correct"]
        for item in valid_evaluations
    )

    by_route = {}

    route_groups = Counter(
        route
        for item in valid_evaluations
        for route in item["expected_routes"]
    )

    for route in sorted(route_groups):
        route_evaluations = [
            item
            for item in valid_evaluations
            if route in item["expected_routes"]
        ]

        route_total = len(route_evaluations)
        route_correct = sum(
            item["route_correct"]
            for item in route_evaluations
        )

        by_route[route] = {
            "correct": route_correct,
            "total": route_total,
            "accuracy": (
                route_correct / route_total
                if route_total
                else None
            ),
        }

    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else None,
        "by_expected_route": by_route,
    }


def get_turn_key(turn_type: str) -> str:
    """Return the benchmark key corresponding to a turn type."""

    if turn_type == "initial":
        return "initial_turn"

    if turn_type == "follow_up":
        return "follow_up_turn"

    raise ValueError(f"Unknown turn type: {turn_type}")


def evaluate_turn(
    case: dict[str, Any],
    turn_type: str,
) -> Optional[dict[str, Any]]:
    """Evaluate the route of one benchmark turn."""

    turn = case.get(get_turn_key(turn_type))

    if not turn:
        return None

    ground_truth = case.get("ground_truth", {})

    expected_routes = get_expected_routes(
        ground_truth,
        turn_type,
    )

    response = turn.get("response") or {}
    actual_route = response.get("route")

    return {
        "case_id": case.get("case_id"),
        "turn_type": turn_type,
        "expected_routes": expected_routes,
        "actual_route": normalize_route(actual_route),
        "route_correct": evaluate_route(
            actual_route,
            expected_routes,
        ),
        "success": turn.get("success"),
        "status_code": turn.get("status_code"),
        "elapsed_seconds": turn.get("elapsed_seconds"),
    }


def calculate_clarification_metrics(
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Evaluate the deterministic component of clarification accuracy.

    The semantic component is evaluated separately by the LLM Judge.
    """

    clarification_cases = [
        item
        for item in evaluations
        if "clarification" in item["expected_routes"]
    ]

    total = len(clarification_cases)

    correct = sum(
        item["actual_route"] == "clarification"
        for item in clarification_cases
    )

    deterministic_accuracy = (
        correct / total
        if total
        else None
    )

    return {
        "correct": correct,
        "total": total,
        "accuracy": deterministic_accuracy,
        "deterministic_accuracy": deterministic_accuracy,
        "semantic_accuracy": None,
        "combined_accuracy": None,
        "note": (
            "The semantic component must be supplied by the LLM Judge. "
            "Combined accuracy is not calculated until that evaluation "
            "is available."
        ),
    }


def parse_expected_table(
    ground_truth: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse the expected table stored in the ground truth."""

    raw_table = ground_truth.get("Expected table (JSON)")

    if not raw_table:
        return []

    try:
        parsed = (
            json.loads(raw_table)
            if isinstance(raw_table, str)
            else raw_table
        )
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Invalid expected table JSON for case %s",
            ground_truth.get("ID"),
        )
        return []

    if not isinstance(parsed, list):
        return []

    return [
        row
        for row in parsed
        if isinstance(row, dict)
    ]


def get_candidate_values(
    row: dict[str, Any],
    expected_field: str,
) -> tuple[bool, Any]:
    """Find a field in an actual result using known aliases."""

    aliases = FIELD_ALIASES.get(
        expected_field,
        [expected_field],
    )

    for alias in aliases:
        if alias in row:
            return True, row[alias]

    return False, None


def values_match(
    expected: Any,
    actual: Any,
) -> bool:
    """Compare expected and actual values."""

    if expected is None or actual is None:
        return expected is None and actual is None

    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual

    if isinstance(expected, (int, float)) and isinstance(
        actual, (int, float)
    ):
        return math.isclose(
            float(expected),
            float(actual),
            rel_tol=0.0,
            abs_tol=NUMERIC_TOLERANCE,
        )

    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().casefold() == actual.strip().casefold()

    return expected == actual


def collect_result_rows(value: Any) -> list[dict[str, Any]]:
    """
    Recursively collect dictionaries from tool evidence.

    This supports invoice lists, aggregation breakdowns and nested
    compliance results.
    """

    rows = []

    if isinstance(value, dict):
        rows.append(value)

        for nested_value in value.values():
            rows.extend(collect_result_rows(nested_value))

    elif isinstance(value, list):
        for item in value:
            rows.extend(collect_result_rows(item))

    return rows


def extract_evidence_rows(
    response: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract structured rows from all tool evidence."""

    evidence = response.get("evidence") or []
    rows = []

    for item in evidence:
        if not isinstance(item, dict):
            continue

        result = item.get("result")

        if isinstance(result, dict):
            rows.extend(collect_result_rows(result))

    return rows


def compare_expected_row(
    expected_row: dict[str, Any],
    actual_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare one expected row against the available evidence.

    Fields not present in tool evidence are ignored. This is useful
    for expected columns that are derived from policy rather than
    directly returned by a data tool.
    """

    best_match_count = 0
    best_total_fields = 0
    best_correct = False

    for actual_row in actual_rows:

        comparable_fields = 0
        matching_fields = 0

        for field, expected_value in expected_row.items():
            exists, actual_value = get_candidate_values(
                actual_row,
                field,
            )

            if not exists:
                continue

            comparable_fields += 1

            if values_match(expected_value, actual_value):
                matching_fields += 1

        if comparable_fields == 0:
            continue

        is_correct = matching_fields == comparable_fields

        if (
            matching_fields > best_match_count
            or (
                matching_fields == best_match_count
                and comparable_fields > best_total_fields
            )
        ):
            best_match_count = matching_fields
            best_total_fields = comparable_fields
            best_correct = is_correct

        if is_correct:
            return {
                "evaluated": True,
                "correct": True,
                "matched_fields": matching_fields,
                "compared_fields": comparable_fields,
            }

    if best_total_fields == 0:
        return {
            "evaluated": False,
            "correct": None,
            "matched_fields": 0,
            "compared_fields": 0,
        }

    return {
        "evaluated": True,
        "correct": best_correct,
        "matched_fields": best_match_count,
        "compared_fields": best_total_fields,
    }


def evaluate_data_retrieval(
    case: dict[str, Any],
    turn_type: str,
) -> dict[str, Any]:
    """Evaluate structured data retrieval for one benchmark turn."""

    ground_truth = case.get("ground_truth", {})
    expected_rows = parse_expected_table(ground_truth)

    if not expected_rows:
        return {
            "case_id": case.get("case_id"),
            "turn_type": turn_type,
            "status": "not_applicable",
            "correct_rows": 0,
            "total_rows": 0,
            "accuracy": None,
            "row_results": [],
        }

    turn = case.get(get_turn_key(turn_type))

    if not turn:
        return {
            "case_id": case.get("case_id"),
            "turn_type": turn_type,
            "status": "not_applicable",
            "correct_rows": 0,
            "total_rows": 0,
            "accuracy": None,
            "row_results": [],
        }

    response = turn.get("response") or {}
    actual_rows = extract_evidence_rows(response)

    row_results = [
        compare_expected_row(expected_row, actual_rows)
        for expected_row in expected_rows
    ]

    evaluated_rows = [
        item
        for item in row_results
        if item["evaluated"]
    ]

    correct_rows = sum(
        item["correct"] is True
        for item in evaluated_rows
    )

    total_rows = len(evaluated_rows)

    return {
        "case_id": case.get("case_id"),
        "turn_type": turn_type,
        "status": (
            "completed"
            if total_rows
            else "not_applicable"
        ),
        "correct_rows": correct_rows,
        "total_rows": total_rows,
        "accuracy": (
            correct_rows / total_rows
            if total_rows
            else None
        ),
        "row_results": row_results,
    }


def calculate_data_retrieval_metrics(
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate data retrieval accuracy across benchmark turns."""

    applicable = [
        item
        for item in evaluations
        if item["status"] == "completed"
    ]

    correct = sum(
        item["correct_rows"]
        for item in applicable
    )

    total = sum(
        item["total_rows"]
        for item in applicable
    )

    return {
        "correct_rows": correct,
        "total_rows": total,
        "accuracy": correct / total if total else None,
        "evaluated_cases": len(applicable),
        "not_applicable_cases": len(evaluations) - len(applicable),
        "case_results": evaluations,
    }


def calculate_performance_metrics(
    evaluations: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Calculate benchmark execution and latency metrics."""

    total = len(evaluations)

    successful = sum(
        item["success"] is True
        for item in evaluations
    )

    latencies = [
        item["elapsed_seconds"]
        for item in evaluations
        if isinstance(item["elapsed_seconds"], (int, float))
    ]

    return {
        "successful_requests": successful,
        "total_requests": total,
        "http_success_rate": (
            successful / total if total else None
        ),
        "average_latency_seconds": (
            sum(latencies) / len(latencies)
            if latencies
            else None
        ),
        "total_benchmark_time_seconds": metadata.get(
            "total_elapsed_seconds"
        ),
    }


def evaluate_benchmark(
    benchmark: dict[str, Any],
) -> dict[str, Any]:
    """Calculate deterministic metrics for a benchmark."""

    results = benchmark.get("results", [])
    metadata = benchmark.get("metadata", {})

    initial_evaluations = []
    follow_up_evaluations = []
    data_retrieval_evaluations = []

    for case in results:

        initial = evaluate_turn(case, "initial")

        if initial is not None:
            initial_evaluations.append(initial)

            data_retrieval_evaluations.append(
                evaluate_data_retrieval(case, "initial")
            )

        follow_up = evaluate_turn(case, "follow_up")

        if follow_up is not None:
            follow_up_evaluations.append(follow_up)

            data_retrieval_evaluations.append(
                evaluate_data_retrieval(case, "follow_up")
            )

    all_evaluations = (
        initial_evaluations + follow_up_evaluations
    )

    return {
        "metadata": metadata,
        "benchmark_summary": {
            "total_cases": len(results),
            "initial_turns": len(initial_evaluations),
            "follow_up_turns": len(follow_up_evaluations),
        },
        "functional_metrics": {
            "route_accuracy": {
                "initial": calculate_route_metrics(
                    initial_evaluations
                ),
                "follow_up": calculate_route_metrics(
                    follow_up_evaluations
                ),
                "overall": calculate_route_metrics(
                    all_evaluations
                ),
            },
            "data_retrieval_accuracy": (
                calculate_data_retrieval_metrics(
                    data_retrieval_evaluations
                )
            ),
            "clarification_accuracy": (
                calculate_clarification_metrics(
                    initial_evaluations
                )
            ),
        },
        "performance_metrics": calculate_performance_metrics(
            all_evaluations,
            metadata,
        ),
        "turn_results": all_evaluations,
    }


def format_percentage(value: Optional[float]) -> str:
    """Format a metric as a percentage."""

    if value is None:
        return "N/A"

    return f"{value:.2%}"


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Finance Spend Intelligence Assistant benchmark."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to the raw benchmark JSON file.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/results/reports"),
        help="Directory where evaluation reports will be saved.",
    )

    args = parser.parse_args()

    benchmark = load_benchmark(args.input)
    report = evaluate_benchmark(benchmark)

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        args.output_dir
        / f"metrics_{args.input.stem}.json"
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print("\nBENCHMARK EVALUATION")
    print("--------------------")

    summary = report["benchmark_summary"]

    print(f"Cases: {summary['total_cases']}")
    print(f"Initial turns: {summary['initial_turns']}")
    print(f"Follow-up turns: {summary['follow_up_turns']}")

    print("\nROUTE ACCURACY")

    route_metrics = report["functional_metrics"]["route_accuracy"]

    for turn_type, metrics in route_metrics.items():
        print(
            f"{turn_type}: "
            f"{metrics['correct']}/{metrics['total']} "
            f"({format_percentage(metrics['accuracy'])})"
        )

    print("\nDATA RETRIEVAL ACCURACY")

    retrieval = report["functional_metrics"][
        "data_retrieval_accuracy"
    ]

    print(
        f"Rows: {retrieval['correct_rows']}/"
        f"{retrieval['total_rows']} "
        f"({format_percentage(retrieval['accuracy'])})"
    )

    print(
        f"Evaluated cases: {retrieval['evaluated_cases']}"
    )

    print(
        f"Not applicable: {retrieval['not_applicable_cases']}"
    )

    print("\nCLARIFICATION ACCURACY")

    clarification = report["functional_metrics"][
        "clarification_accuracy"
    ]

    print(
        f"Deterministic: {clarification['correct']}/"
        f"{clarification['total']} "
        f"({format_percentage(clarification['accuracy'])})"
    )

    print("Semantic: pending LLM Judge evaluation")
    print("Combined: N/A")

    print("\nPERFORMANCE")

    performance = report["performance_metrics"]

    print(
        f"HTTP success rate: "
        f"{format_percentage(performance['http_success_rate'])}"
    )

    latency = performance["average_latency_seconds"]

    print(
        f"Average latency: "
        f"{f'{latency:.2f} s' if latency is not None else 'N/A'}"
    )

    runtime = performance["total_benchmark_time_seconds"]

    print(
        f"Total benchmark time: "
        f"{f'{runtime:.2f} s' if runtime is not None else 'N/A'}"
    )

    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()