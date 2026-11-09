import argparse
import json
import os
import time

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd


# ---------------------------------------------------------
# Paths and configuration
# ---------------------------------------------------------

EVALUATION_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVALUATION_DIR / "ground_truth_data" / "ground_truth.xlsx"
RAW_RESULTS_DIR = EVALUATION_DIR / "results" / "raw"

API_URL = os.getenv(
    "FINANCE_ASSISTANT_API_URL",
    "http://localhost:8000"
).rstrip("/")

DEFAULT_TIMEOUT = 300


# ---------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------

def load_ground_truth(
    dataset_path: Path
) -> list[dict[str, Any]]:
    """
    Load benchmark cases from the Ground Truth worksheet.
    """

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Ground Truth dataset not found: {dataset_path}"
        )

    dataframe = pd.read_excel(
        dataset_path,
        sheet_name="Ground Truth"
    )

    required_columns = {
        "ID",
        "Category",
        "Question",
        "Expected route",
        "Acceptable routes",
        "Expected operation",
        "Expected tool concept",
        "Expected answer",
        "Follow-up user message",
        "Expected route after clarification",
        "Expected answer after clarification",
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            "Missing required columns in Ground Truth worksheet: "
            + ", ".join(sorted(missing_columns))
        )

    # Remove completely empty rows.
    dataframe = dataframe.dropna(
        subset=["ID", "Question"]
    )

    cases = []

    for _, row in dataframe.iterrows():

        case = {}

        for column, value in row.items():

            if pd.isna(value):
                value = None

            case[column] = value

        # Normalize fields used by the benchmark.
        case["ID"] = str(case["ID"]).strip()
        case["Category"] = str(case["Category"]).strip().lower()
        case["Question"] = str(case["Question"]).strip()

        if case["Follow-up user message"] is not None:
            case["Follow-up user message"] = str(
                case["Follow-up user message"]
            ).strip()

        cases.append(case)

    return cases


# ---------------------------------------------------------
# API execution
# ---------------------------------------------------------

def call_assistant(
    question: str,
    conversation_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """
    Send a question to the Finance Spend Intelligence API.
    """

    payload = {
        "question": question
    }

    if conversation_id:
        payload["conversation_id"] = conversation_id

    request = Request(
        url=f"{API_URL}/ask",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    start_time = time.perf_counter()

    try:

        with urlopen(request, timeout=timeout) as response:

            response_body = response.read().decode("utf-8")

            elapsed_time = time.perf_counter() - start_time

            try:
                response_data = json.loads(response_body)
            except json.JSONDecodeError:
                response_data = {
                    "raw_response": response_body
                }

            return {
                "success": True,
                "status_code": response.status,
                "elapsed_seconds": round(elapsed_time, 3),
                "response": response_data,
                "error": None
            }

    except HTTPError as exc:

        elapsed_time = time.perf_counter() - start_time
        error_body = exc.read().decode("utf-8", errors="replace")

        return {
            "success": False,
            "status_code": exc.code,
            "elapsed_seconds": round(elapsed_time, 3),
            "response": None,
            "error": error_body
        }

    except (URLError, TimeoutError, OSError) as exc:

        elapsed_time = time.perf_counter() - start_time

        return {
            "success": False,
            "status_code": None,
            "elapsed_seconds": round(elapsed_time, 3),
            "response": None,
            "error": str(exc)
        }


# ---------------------------------------------------------
# Benchmark case execution
# ---------------------------------------------------------

def execute_case(
    case: dict[str, Any],
    timeout: int
) -> dict[str, Any]:
    """
    Execute one benchmark case.

    Clarification cases include an initial question and,
    when available, a follow-up message in the same conversation.
    """

    case_id = case["ID"]

    print(f"[{case_id}] Running initial question...")

    initial_result = call_assistant(
        question=case["Question"],
        timeout=timeout
    )

    result = {
        "case_id": case_id,
        "category": case["Category"],
        "ground_truth": case,
        "initial_turn": {
            "question": case["Question"],
            **initial_result
        },
        "follow_up_turn": None
    }

    # Execute the follow-up only when the dataset provides one.
    follow_up = case.get("Follow-up user message")

    if follow_up:

        initial_response = initial_result.get("response") or {}

        conversation_id = initial_response.get(
            "conversation_id"
        )

        if not conversation_id:

            result["follow_up_turn"] = {
                "question": follow_up,
                "success": False,
                "status_code": None,
                "elapsed_seconds": 0,
                "response": None,
                "error": (
                    "The initial response did not return "
                    "a conversation_id. Follow-up was not executed."
                )
            }

        else:

            print(f"[{case_id}] Running clarification follow-up...")

            follow_up_result = call_assistant(
                question=follow_up,
                conversation_id=conversation_id,
                timeout=timeout
            )

            result["follow_up_turn"] = {
                "question": follow_up,
                **follow_up_result
            }

    return result


# ---------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------

def run_benchmark(
    cases: list[dict[str, Any]],
    timeout: int
) -> dict[str, Any]:

    results = []

    total_cases = len(cases)

    print()
    print("=" * 60)
    print("FINANCE SPEND INTELLIGENCE - BENCHMARK")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Cases: {total_cases}")
    print("=" * 60)
    print()

    benchmark_start = time.perf_counter()

    for index, case in enumerate(cases, start=1):

        print(
            f"Progress: {index}/{total_cases} "
            f"| Case: {case['ID']}"
        )

        try:

            result = execute_case(
                case=case,
                timeout=timeout
            )

        except Exception as exc:

            result = {
                "case_id": case["ID"],
                "category": case["Category"],
                "ground_truth": case,
                "initial_turn": {
                    "question": case["Question"],
                    "success": False,
                    "status_code": None,
                    "elapsed_seconds": 0,
                    "response": None,
                    "error": str(exc)
                },
                "follow_up_turn": None
            }

        results.append(result)

        print()

    total_elapsed = time.perf_counter() - benchmark_start

    successful_initial = sum(
        1
        for result in results
        if result["initial_turn"]["success"]
    )

    successful_followups = sum(
        1
        for result in results
        if (
            result["follow_up_turn"] is not None
            and result["follow_up_turn"]["success"]
        )
    )

    total_followups = sum(
        1
        for result in results
        if result["follow_up_turn"] is not None
    )

    benchmark_output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "api_url": API_URL,
            "dataset": str(DATASET_PATH),
            "total_cases": total_cases,
            "successful_initial_requests": successful_initial,
            "total_follow_up_requests": total_followups,
            "successful_follow_up_requests": successful_followups,
            "total_elapsed_seconds": round(total_elapsed, 3)
        },
        "results": results
    }

    RAW_RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_path = RAW_RESULTS_DIR / (
        f"benchmark_{timestamp}.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            benchmark_output,
            file,
            indent=2,
            ensure_ascii=False,
            default=str
        )

    print("=" * 60)
    print("BENCHMARK COMPLETED")
    print("=" * 60)
    print(f"Cases executed: {total_cases}")
    print(
        f"Successful initial requests: "
        f"{successful_initial}/{total_cases}"
    )
    print(
        f"Successful follow-ups: "
        f"{successful_followups}/{total_followups}"
    )
    print(f"Elapsed time: {total_elapsed:.2f} seconds")
    print(f"Results saved to: {output_path}")
    print("=" * 60)

    return benchmark_output


# ---------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Run the Finance Spend Intelligence benchmark."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of cases to execute."
    )

    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Execute only cases from a specific category."
    )

    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Comma-separated case IDs, e.g. INV01,CL01."
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="API request timeout in seconds."
    )

    args = parser.parse_args()

    cases = load_ground_truth(DATASET_PATH)

    if args.category:

        category = args.category.strip().lower()

        cases = [
            case
            for case in cases
            if case["Category"] == category
        ]

    if args.ids:

        selected_ids = {
            case_id.strip()
            for case_id in args.ids.split(",")
        }

        cases = [
            case
            for case in cases
            if case["ID"] in selected_ids
        ]

    if args.limit is not None:

        cases = cases[:args.limit]

    if not cases:
        raise ValueError(
            "No benchmark cases selected."
        )

    run_benchmark(
        cases=cases,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()