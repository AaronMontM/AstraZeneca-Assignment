from typing import Optional

from app.llm.router import (
    RoutingDecision,
    Route
)


class RoutingGuardrail:

    @staticmethod
    def process(
        decision: RoutingDecision
    ) -> Optional[str]:

        if decision.route == Route.OUT_OF_SCOPE:

            return (
                "I'm sorry, but I can only help with questions "
                "related to company spending, invoices, vendors "
                "and procurement policies."
            )

        if decision.route == Route.CLARIFICATION:

            return decision.clarification_question

        return None


class AnswerGuardrail:

    @staticmethod
    def validate(answer: str) -> str:

        if not answer or not answer.strip():
            raise ValueError(
                "The LLM returned an empty answer."
            )

        return answer.strip()