#!/usr/bin/env python3
"""
Deterministic evaluator for Finance Spend Intelligence Assistant benchmark JSON.

This first version evaluates execution, routing, follow-up completion and
structured evidence where the benchmark JSON exposes comparable rows.
It deliberately does NOT claim to judge free-text semantic correctness.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


FIELD_ALIASES = {
    "net_spend_eur": "total_eur_spend",
    "invoice_month": "invoice_month",
    "invoice_number": "invoice_number",
    "vendor_name": "vendor_name",
    "invoice_date": "invoice_date",
    "EUR_amount": "EUR_amount",
    "currency": "currency",
    "invoice_count": "invoice_count",
    "po_number": "po_number",
    "maverick_spend": "maverick_spend",
    "required_approver": "required_approver",
    "approved_by": "approved_by",
    "vendor_status": "vendor_status",
    "vendor_country": "vendor_country",
    "vendor_category": "vendor_category",
    "cost_center": "cost_center",
}


def parse_allowed_routes(value):
    if not value:
        return set()

    return {
        part.strip()
        for part in str(value).replace(";", ",").replace("|", ",").split(",")
        if part.strip()
    }


def flatten_evidence(response):
    rows = []

    for item in (response or {}).get("evidence", []) or []:
        result = item.get("result") or {}

        invoices = result.get("invoices")
        breakdown = result.get("breakdown")

        if isinstance(invoices, list):
            rows.extend(invoices)

        if isinstance(breakdown, list):
            rows.extend(breakdown)

    return rows


def values_equal(expected, actual):
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return abs(float(expected) - float(actual)) <= 0.01
        except (TypeError, ValueError):
            return False

    if isinstance(expected, bool):
        return actual is expected

    if expected is None:
        return actual is None

    return (
        str(expected).strip().casefold()
        == str(actual).strip().casefold()
    )


def compare_expected_table(gt, response):
    raw = gt.get("Expected table (JSON)")

    if not raw:
        return "NOT_AVAILABLE", None

    try:
        expected_rows = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return "UNPARSEABLE", None

    if not isinstance(expected_rows, list) or not expected_rows:
        return "NOT_AVAILABLE", None

    evidence_candidates = []

    for item in (response or {}).get("evidence", []) or []:
        result = item.get("result") or {}

        # Include aggregate-level totals as well as grouped/detail rows.
        evidence_candidates.append(result)

        if isinstance(result.get("invoices"), list):
            evidence_candidates.extend(result["invoices"])

        if isinstance(result.get("breakdown"), list):
            evidence_candidates.extend(result["breakdown"])

    if not evidence_candidates:
        return "NO_STRUCTURED_EVIDENCE", 0

    matched = 0
    comparable = 0

    for expected_row in expected_rows:
        row_comparable = False
        row_matched = False

        for actual_row in evidence_candidates:
            checks = []

            for expected_key, expected_value in expected_row.items():
                actual_key = FIELD_ALIASES.get(
                    expected_key,
                    expected_key,
                )

                if actual_key in actual_row:
                    row_comparable = True
                    checks.append(
                        values_equal(
                            expected_value,
                            actual_row[actual_key],
                        )
                    )

            if len(checks) >= 2 and all(checks):
                row_matched = True
                break

        if row_comparable:
            comparable += 1

        if row_matched:
            matched += 1

    if comparable == 0:
        return "NOT_COMPARABLE", None

    if matched == len(expected_rows):
        return "PASS", matched

    if matched:
        return "PARTIAL", matched

    return "FAIL", matched


def evaluate_case(case):
    gt = case.get("ground_truth") or {}
    initial = case.get("initial_turn") or {}
    response = initial.get("response") or {}

    allowed_routes = parse_allowed_routes(
        gt.get("Acceptable routes") or gt.get("Expected route")
    )

    actual_route = response.get("route")

    route_match = (
        actual_route in allowed_routes
        if allowed_routes
        else None
    )

    table_status, table_matched = compare_expected_table(
        gt,
        response,
    )

    follow_up = case.get("follow_up_turn")

    if follow_up is None:
        follow_up_status = "NOT_REQUESTED"
    elif follow_up.get("success"):
        follow_up_status = "PASS"
    else:
        follow_up_status = "FAIL"

    return {
        "case_id": case.get("case_id", gt.get("ID", "")),
        "category": case.get("category", gt.get("Category", "")),
        "initial_success": bool(initial.get("success")),
        "status_code": initial.get("status_code"),
        "expected_route": " | ".join(sorted(allowed_routes)),
        "actual_route": actual_route or "",
        "route_match": route_match,
        "tools_used": ", ".join(
            response.get("tools_used") or []
        ),
        "evidence_table_status": table_status,
        "evidence_rows_matched": table_matched,
        "follow_up_status": follow_up_status,
        "initial_error": initial.get("error") or "",
        "follow_up_error": (
            follow_up.get("error") or ""
            if follow_up
            else ""
        ),
    }


def pct(numerator, denominator):
    return (
        f"{(100 * numerator / denominator):.1f}%"
        if denominator
        else "N/A"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate benchmark JSON results."
    )

    parser.add_argument(
        "input",
        help="Path to benchmark_*.json",
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: <input directory>/reports)",
    )

    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else input_path.parent.parent / "reports"
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as handle:
        benchmark = json.load(handle)

    cases = [
        evaluate_case(case)
        for case in benchmark.get("results", [])
    ]

    total = len(cases)

    successful = sum(
        row["initial_success"]
        for row in cases
    )

    route_evaluable = [
        row
        for row in cases
        if row["route_match"] is not None
    ]

    route_correct = sum(
        row["route_match"] is True
        for row in route_evaluable
    )

    followups = [
        row
        for row in cases
        if row["follow_up_status"] != "NOT_REQUESTED"
    ]

    followups_ok = sum(
        row["follow_up_status"] == "PASS"
        for row in followups
    )

    table_evaluable = [
        row
        for row in cases
        if row["evidence_table_status"]
        in {"PASS", "PARTIAL", "FAIL"}
    ]

    table_pass = sum(
        row["evidence_table_status"] == "PASS"
        for row in table_evaluable
    )

    table_partial = sum(
        row["evidence_table_status"] == "PARTIAL"
        for row in table_evaluable
    )

    table_fail = sum(
        row["evidence_table_status"] == "FAIL"
        for row in table_evaluable
    )

    category_stats = defaultdict(
        lambda: {
            "total": 0,
            "success": 0,
            "route_ok": 0,
            "route_n": 0,
        }
    )

    for row in cases:
        stats = category_stats[row["category"]]

        stats["total"] += 1
        stats["success"] += int(row["initial_success"])

        if row["route_match"] is not None:
            stats["route_n"] += 1
            stats["route_ok"] += int(row["route_match"])

    # -----------------------------------------------------------------
    # CSV report
    # -----------------------------------------------------------------

    csv_path = (
        output_dir
        / f"{input_path.stem}_case_results.csv"
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=list(cases[0].keys()) if cases else [],
        )

        if cases:
            writer.writeheader()
            writer.writerows(cases)

    # -----------------------------------------------------------------
    # Markdown report
    # -----------------------------------------------------------------

    report_path = (
        output_dir
        / f"{input_path.stem}_report.md"
    )

    lines = [
        f"# Benchmark evaluation — {input_path.name}",
        "",
        "## Overall",
        "",
        f"- Cases: **{total}**",
        (
            f"- Initial execution: "
            f"**{successful}/{total} ({pct(successful, total)})**"
        ),
        (
            f"- Route match: "
            f"**{route_correct}/{len(route_evaluable)} "
            f"({pct(route_correct, len(route_evaluable))})**"
        ),
        (
            f"- Follow-ups: "
            f"**{followups_ok}/{len(followups)} "
            f"({pct(followups_ok, len(followups))})**"
        ),
        (
            f"- Structured evidence comparison: "
            f"**{table_pass} PASS, {table_partial} PARTIAL, "
            f"{table_fail} FAIL** "
            f"(evaluated cases: {len(table_evaluable)}; "
            f"others not comparable or unavailable)"
        ),
        "",
        (
            "> This report checks structured evidence where fields can "
            "be compared. It does not judge free-text semantic correctness, "
            "policy reasoning, or whether the final answer explains all "
            "relevant caveats. Review those separately."
        ),
        "",
        "## Results by category",
        "",
        "| Category | Cases | HTTP success | Route match |",
        "|---|---:|---:|---:|",
    ]

    for category, stats in sorted(category_stats.items()):
        lines.append(
            f"| {category} | {stats['total']} | "
            f"{stats['success']}/{stats['total']} "
            f"({pct(stats['success'], stats['total'])}) | "
            f"{stats['route_ok']}/{stats['route_n']} "
            f"({pct(stats['route_ok'], stats['route_n'])}) |"
        )

    # -----------------------------------------------------------------
    # Cases requiring attention
    # -----------------------------------------------------------------

    lines += [
        "",
        "## Cases requiring attention",
        "",
        (
            "| Case | HTTP | Expected route | Actual route "
            "| Evidence | Follow-up |"
        ),
        "|---|---:|---|---|---|---|",
    ]

    for row in cases:
        needs_attention = (
            not row["initial_success"]
            or row["route_match"] is False
            or row["evidence_table_status"] in {"PARTIAL", "FAIL"}
            or row["follow_up_status"] == "FAIL"
        )

        if needs_attention:
            lines.append(
                f"| {row['case_id']} | "
                f"{row['status_code'] or '-'} | "
                f"{row['expected_route'] or '-'} | "
                f"{row['actual_route'] or '-'} | "
                f"{row['evidence_table_status']} | "
                f"{row['follow_up_status']} |"
            )

    # -----------------------------------------------------------------
    # Execution errors
    # -----------------------------------------------------------------

    lines += [
        "",
        "## Execution errors",
        "",
    ]

    errors = [
        row
        for row in cases
        if not row["initial_success"]
    ]

    if errors:
        for row in errors:
            lines.append(
                f"- **{row['case_id']}** "
                f"(HTTP {row['status_code']}): "
                f"{row['initial_error']}"
            )
    else:
        lines.append("- None.")

    # -----------------------------------------------------------------
    # Follow-up errors
    # -----------------------------------------------------------------

    lines += [
        "",
        "## Follow-up errors",
        "",
    ]

    failed_followups = [
        row
        for row in cases
        if row["follow_up_status"] == "FAIL"
    ]

    if failed_followups:
        for row in failed_followups:
            lines.append(
                f"- **{row['case_id']}**: "
                f"{row['follow_up_error']}"
            )
    else:
        lines.append("- None.")

    report_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    # -----------------------------------------------------------------
    # Console summary
    # -----------------------------------------------------------------

    print(f"Evaluated {total} cases.")

    print(
        f"Initial execution: "
        f"{successful}/{total} ({pct(successful, total)})"
    )

    print(
        f"Route match: "
        f"{route_correct}/{len(route_evaluable)} "
        f"({pct(route_correct, len(route_evaluable))})"
    )

    print(
        f"Follow-ups: "
        f"{followups_ok}/{len(followups)} "
        f"({pct(followups_ok, len(followups))})"
    )

    print(f"Report: {report_path}")
    print(f"Case CSV: {csv_path}")


if __name__ == "__main__":
    main()