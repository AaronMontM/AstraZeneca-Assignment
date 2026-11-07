import argparse
import json
import logging
import re
import sys

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model, ValidationError
from ollama import Client


# ---------------------------------------------------------------------
# Project paths and imports
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"

sys.path.insert(0, str(BACKEND_PATH))

from app.config import settings


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Judge configuration
# ---------------------------------------------------------------------

DEFAULT_JUDGE_MODEL = "gpt-oss:20b"

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "evaluation" / "results" / "judged"
)


# ---------------------------------------------------------------------
# Structured evaluation schema
# ---------------------------------------------------------------------

class MetricScore(BaseModel):
    """Score and explanation for an individual metric."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Evaluation score between 0 and 1.",
    )

    rationale: str = Field(
        description="Brief explanation supporting the score.",
    )


class JudgeEvaluation(BaseModel):
    """Structured evaluation returned by the LLM judge."""

    model_config = ConfigDict(extra="forbid")

    policy_answer_accuracy: Optional[MetricScore] = None
    both_answer_accuracy: Optional[MetricScore] = None

    factual_correctness: Optional[MetricScore] = None
    faithfulness: Optional[MetricScore] = None
    answer_relevancy: Optional[MetricScore] = None

    context_precision: Optional[MetricScore] = None
    context_recall: Optional[MetricScore] = None



def build_evaluation_model(
    applicable_metrics: list[str],
) -> type[BaseModel]:
    """
    Build a dynamic evaluation schema.

    Applicable metrics are required and cannot be null.
    Non-applicable metrics are required but can be null.
    """

    fields = {}

    for metric in JudgeEvaluation.model_fields:
        if metric in applicable_metrics:
            fields[metric] = (MetricScore, ...)
        else:
            fields[metric] = (Optional[MetricScore], ...)

    return create_model(
        "DynamicJudgeEvaluation",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save JSON data."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False,
        )


def load_policy(path: Path) -> str:
    """Load procurement policy."""

    if not path.exists():
        raise FileNotFoundError(
            f"Procurement policy not found: {path}"
        )

    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------

def parse_routes(value: Optional[str]) -> list[str]:
    """Parse acceptable routes."""

    if not value:
        return []

    return [
        route.strip().lower()
        for route in re.split(r"[;,|]", str(value))
        if route.strip()
    ]


def get_expected_routes(
    ground_truth: dict[str, Any],
    turn_type: str,
) -> list[str]:

    if turn_type == "initial":

        routes = parse_routes(
            ground_truth.get("Acceptable routes")
        )

        if routes:
            return routes

        expected_route = ground_truth.get("Expected route")

    else:

        expected_route = ground_truth.get(
            "Expected route after clarification"
        )

    return (
        [expected_route.strip().lower()]
        if expected_route
        else []
    )


def get_expected_answer(
    ground_truth: dict[str, Any],
    turn_type: str,
) -> Optional[str]:

    if turn_type == "follow_up":
        return ground_truth.get(
            "Expected answer after clarification"
        )

    return ground_truth.get("Expected answer")


def get_expected_table(
    ground_truth: dict[str, Any],
) -> Any:

    raw = ground_truth.get("Expected table (JSON)")

    if not raw:
        return None

    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


# ---------------------------------------------------------------------
# Metric applicability
# ---------------------------------------------------------------------

def get_applicable_metrics(
    expected_routes: list[str],
) -> list[str]:

    routes = set(expected_routes)

    metrics = []

    if "policy" in routes:
        metrics.append("policy_answer_accuracy")

    if "both" in routes:
        metrics.append("both_answer_accuracy")

    if routes.intersection({"data", "policy", "both"}):

        metrics.extend([
            "factual_correctness",
            "faithfulness",
            "answer_relevancy",
        ])

    if routes.intersection({"data", "both"}):

        metrics.extend([
            "context_precision",
            "context_recall",
        ])

    return metrics


# ---------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """
You are an independent evaluator of a Finance Spend Intelligence Assistant.

Your task is to evaluate the quality and correctness of an assistant response
using the user question, ground truth, retrieved evidence and procurement
policy when available.

You must evaluate only the metrics explicitly requested in the evaluation
instructions.

SCORING:

Return a score between 0.0 and 1.0.

- 1.00: Fully correct.
- 0.75: Mostly correct, with minor omissions or inaccuracies.
- 0.50: Partially correct, with relevant errors or omissions.
- 0.25: Mostly incorrect.
- 0.00: Completely incorrect or unsupported.

METRICS:

1. POLICY ANSWER ACCURACY

Evaluate whether the response correctly interprets and applies the
procurement policy to the user's question.

Compare the response against the expected answer and the actual policy.

Consider:
- Correct identification of applicable rules.
- Correct interpretation of approval thresholds and conditions.
- Completeness of the answer.
- Absence of invented policy requirements.

2. BOTH ANSWER ACCURACY

Evaluate whether the response correctly combines financial data and
procurement policy.

Consider:
- Correct use of financial information.
- Correct interpretation of procurement rules.
- Correct application of policy to the financial data.
- Correct final conclusion.

A response that retrieves correct data but applies the policy incorrectly
must not receive a high score.

3. FACTUAL CORRECTNESS

Evaluate whether the factual claims in the response agree with the ground
truth and expected answer.

Do not reward plausible but unsupported assumptions.

4. FAITHFULNESS

Evaluate whether the claims in the response are supported by the supplied
evidence and procurement policy.

Do not assume that information is supported merely because it is plausible.

5. ANSWER RELEVANCY

Evaluate whether the response directly and adequately answers the user's
question.

Consider unnecessary information, missing requested information and
failure to address the actual question.

6. CONTEXT PRECISION

Evaluate the relevance of the retrieved evidence to the user's question.

High scores require evidence that is relevant to the requested information.
Irrelevant or unrelated records should reduce the score.

7. CONTEXT RECALL

Evaluate whether the retrieved evidence contains the information necessary
to answer the user's question.

Compare the evidence against the ground truth and expected table when
available.

Missing relevant records or information should reduce the score.

IMPORTANT RULES:

- Evaluate each metric independently.
- Do not infer information that is not present in the supplied materials.
- Do not penalize the assistant for information that was not requested.
- Distinguish factual errors from minor wording differences.
- A null metric means that the metric cannot be evaluated with the supplied
  information. Do not replace null with zero.
- Provide a concise rationale for every evaluated metric.
- Return only the requested structured JSON.
"""


def build_judge_prompt(
    question: str,
    answer: str,
    expected_answer: Optional[str],
    expected_table: Any,
    evidence: Any,
    policy: Optional[str],
    applicable_metrics: list[str],
) -> str:

    evaluation_instructions = {
        metric: (
            "Evaluate this metric and return its score and rationale."
            if metric in applicable_metrics
            else "Return null."
        )
        for metric in JudgeEvaluation.model_fields
    }

    payload = {
        "user_question": question,
        "assistant_answer": answer,
        "expected_answer": expected_answer,
        "expected_table": expected_table,
        "retrieved_evidence": evidence,
        "procurement_policy": policy,
        "evaluation_instructions": evaluation_instructions,
    }

    return (
        "Evaluate the following assistant interaction.\n\n"
        "Return a score and rationale for each applicable metric. "
        "Return null for every metric marked as not applicable.\n\n"
        "INTERACTION DATA:\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False, default=str)}"
    )


# ---------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------

class LLMJudge:

    MAX_ATTEMPTS = 3

    def __init__(
        self,
        model: str,
        host: str,
    ):

        self.model = model
        self.client = Client(host=host)

    def evaluate(
        self,
        prompt: str,
        applicable_metrics: list[str],
    ) -> dict[str, Any]:

        evaluation_model = build_evaluation_model(
            applicable_metrics
        )

        last_error = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):

            logger.info(
                "Judge generation attempt %s/%s",
                attempt,
                self.MAX_ATTEMPTS,
            )

            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": JUDGE_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                format=evaluation_model.model_json_schema(),
                options={
                    "temperature": 0.0,
                    "num_ctx": 16384,
                    "num_predict": 4096,
                },
                think=False,
                stream=False,
            )

            content = response.message.content or ""

            message_data = response.message.model_dump()

            logger.info(
                "Judge message details: %s",
                {
                    "content_length": len(content),
                    "thinking_length": len(
                        message_data.get("thinking") or ""
                    ),
                    "message_fields": list(message_data.keys()),
                    "tool_calls": message_data.get("tool_calls"),
                },
            )

            logger.info(
                "Judge response metadata: %s",
                {
                    "attempt": attempt,
                    "model": response.model,
                    "done": response.done,
                    "done_reason": response.done_reason,
                    "prompt_eval_count": response.prompt_eval_count,
                    "eval_count": response.eval_count,
                    "total_duration": response.total_duration,
                    "load_duration": response.load_duration,
                    "content_length": len(content),
                },
            )

            # Empty response
            if not content.strip():

                last_error = ValueError(
                    "Judge returned empty content."
                )

                logger.warning(
                    "Judge returned empty content on attempt %s/%s.",
                    attempt,
                    self.MAX_ATTEMPTS,
                )

            else:

                # Validate structured JSON response
                try:

                    evaluation = evaluation_model.model_validate_json(
                        content
                    )

                    logger.info(
                        "Judge evaluation successfully validated "
                        "on attempt %s.",
                        attempt,
                    )

                    return evaluation.model_dump()

                except ValidationError as exc:

                    last_error = exc

                    logger.warning(
                        "Judge returned invalid structured output "
                        "on attempt %s/%s: %s",
                        attempt,
                        self.MAX_ATTEMPTS,
                        str(exc)[:1000],
                    )

            # Retry if attempts remain
            if attempt < self.MAX_ATTEMPTS:

                logger.info(
                    "Retrying judge evaluation..."
                )

        raise ValueError(
            f"Judge evaluation failed after "
            f"{self.MAX_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        ) from last_error


# ---------------------------------------------------------------------
# Turn evaluation
# ---------------------------------------------------------------------

def evaluate_turn(
    judge: LLMJudge,
    case: dict[str, Any],
    turn_type: str,
    policy: str,
) -> dict[str, Any]:

    turn_key = (
        "initial_turn"
        if turn_type == "initial"
        else "follow_up_turn"
    )

    turn = case.get(turn_key)

    ground_truth = case.get("ground_truth") or {}

    expected_routes = get_expected_routes(
        ground_truth,
        turn_type,
    )

    result = {
        "case_id": case.get("case_id"),
        "turn_type": turn_type,
        "expected_routes": expected_routes,
        "actual_route": None,
        "applicable_metrics": [],
        "evaluation": None,
        "status": None,
        "error": None,
    }

    if not turn:
        result["status"] = "missing_turn"
        return result

    if not turn.get("success"):
        result["status"] = "execution_failed"
        return result

    response = turn.get("response") or {}

    actual_route = response.get("route")

    result["actual_route"] = actual_route

    applicable_metrics = get_applicable_metrics(
        expected_routes
    )

    result["applicable_metrics"] = applicable_metrics

    if not applicable_metrics:
        result["status"] = "not_applicable"
        return result

    expected_answer = get_expected_answer(
        ground_truth,
        turn_type,
    )

    expected_table = get_expected_table(ground_truth)

    evidence = response.get("evidence") or []

    policy_context = (
        policy
        if set(expected_routes).intersection({"policy", "both"})
        else None
    )

    prompt = build_judge_prompt(
        question=turn.get("question", ""),
        answer=response.get("answer", ""),
        expected_answer=expected_answer,
        expected_table=expected_table,
        evidence=evidence,
        policy=policy_context,
        applicable_metrics=applicable_metrics,
    )

    evaluation = judge.evaluate(
        prompt=prompt,
        applicable_metrics=applicable_metrics,
    )

    result["evaluation"] = evaluation
    result["status"] = "completed"

    return result


# ---------------------------------------------------------------------
# Benchmark evaluation
# ---------------------------------------------------------------------

def evaluate_benchmark(
    benchmark: dict[str, Any],
    judge: LLMJudge,
    policy: str,
    output_path: Path,
    judge_model: str,
    limit: Optional[int] = None,
    force: bool = False,
) -> dict[str, Any]:

    cases = benchmark.get("results", [])

    if limit is not None:
        cases = cases[:limit]

    if output_path.exists() and not force:

        judged_results = load_json(output_path)

        existing_results = {
            (
                item["case_id"],
                item["turn_type"],
            ): item
            for item in judged_results.get("results", [])
        }

    else:

        existing_results = {}

        judged_results = {
            "metadata": {
                "judge_model": judge_model,
                "source_benchmark": benchmark.get(
                    "metadata", {}
                ),
            },
            "results": [],
        }

    total_turns = sum(
        1 + int(case.get("follow_up_turn") is not None)
        for case in cases
    )

    processed = 0

    for case in cases:

        case_id = case.get("case_id")

        for turn_type in ("initial", "follow_up"):

            turn_key = (
                case_id,
                turn_type,
            )

            turn = case.get(
                "initial_turn"
                if turn_type == "initial"
                else "follow_up_turn"
            )

            if not turn:
                continue

            existing = existing_results.get(turn_key)

            if (
                existing is not None
                and existing.get("status") != "error"
                and not force
            ):
                processed += 1
                continue

            logger.info(
                "Evaluating %s (%s) [%s/%s]",
                case_id,
                turn_type,
                processed + 1,
                total_turns,
            )

            try:

                result = evaluate_turn(
                    judge=judge,
                    case=case,
                    turn_type=turn_type,
                    policy=policy,
                )

            except Exception as exc:

                logger.exception(
                    "Judge evaluation failed for %s (%s)",
                    case_id,
                    turn_type,
                )

                result = {
                    "case_id": case_id,
                    "turn_type": turn_type,
                    "status": "error",
                    "error": str(exc),
                    "evaluation": None,
                }

            existing_results[turn_key] = result

            judged_results["results"] = list(
                existing_results.values()
            )

            save_json(
                judged_results,
                output_path,
            )

            processed += 1

    return judged_results


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description="Evaluate benchmark responses using an LLM judge."
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to the raw benchmark JSON.",
    )

    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="Ollama model used as the judge.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for judged results.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N benchmark cases.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-evaluate previously evaluated interactions.",
    )

    args = parser.parse_args()

    input_path = args.input.resolve()

    if not input_path.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: {input_path}"
        )

    benchmark = load_json(input_path)

    policy = load_policy(settings.POLICY_PATH)

    judge = LLMJudge(
        model=args.judge_model,
        host=settings.OLLAMA_HOST,
    )

    model_slug = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        args.judge_model,
    )

    output_path = (
        args.output_dir
        / f"judged_{input_path.stem}_{model_slug}.json"
    )

    logger.info("Benchmark: %s", input_path.name)
    logger.info("Judge model: %s", args.judge_model)
    logger.info("Output: %s", output_path)

    results = evaluate_benchmark(
        benchmark=benchmark,
        judge=judge,
        policy=policy,
        output_path=output_path,
        judge_model=args.judge_model,
        limit=args.limit,
        force=args.force,
    )

    completed = sum(
        item.get("status") == "completed"
        for item in results["results"]
    )

    errors = sum(
        item.get("status") == "error"
        for item in results["results"]
    )

    logger.info("Judge evaluation completed.")
    logger.info("Completed evaluations: %s", completed)
    logger.info("Errors: %s", errors)
    logger.info("Results saved to: %s", output_path)


if __name__ == "__main__":
    main()