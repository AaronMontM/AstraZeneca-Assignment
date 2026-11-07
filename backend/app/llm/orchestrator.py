import json
import logging
import re

from typing import Any, Mapping, Optional, Sequence

from app.llm.client import OllamaClient
from app.llm.prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_PROMPT_TEMPLATE,
)
from app.llm.router import QueryRouter
from app.llm.guardrails import RoutingGuardrail, AnswerGuardrail
from app.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        llm: OllamaClient,
        router: QueryRouter,
        tool_registry: ToolRegistry,
        procurement_policy: str,
        history_store=None,
        runtime_config=None,
    ):
        self.llm = llm
        self.router = router
        self.tool_registry = tool_registry
        self.procurement_policy = procurement_policy
        self.history_store = history_store
        self.runtime_config = runtime_config

        self.routing_guardrail = RoutingGuardrail()
        self.answer_guardrail = AnswerGuardrail()

    def run(
        self,
        question: str,
        conversation_history: Optional[Sequence[Mapping[str, str]]] = None,
        router_history: Optional[Sequence[Mapping[str, str]]] = None,
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("The question cannot be empty.")

        question = question.strip()

        # 1. Route the current question.
        logger.info("Routing user question")

        decision = self.router.route(
            question=question,
            conversation_history=router_history,
            conversation_id=conversation_id,
        )

        logger.info("Selected route: %s", decision.route.value)

        # 2. Apply routing guardrails.
        early_response = self.routing_guardrail.process(decision)

        if early_response is not None:
            return {
                "answer": early_response,
                "route": decision.route.value,
                "decision_summary": decision.decision_summary,
                "evidence": [],
                "tools_used": [],
                "conversation_id": conversation_id,
            }

        # 3. Execute selected tools.
        evidence = []
        tools_used = []
        invoice_searches = []

        for tool_request in decision.required_tools:
            logger.info("Executing tool: %s", tool_request.name)

            arguments = dict(tool_request.arguments)

            is_invoice_listing = any(
                term in question.lower()
                for term in (
                    "all invoices",
                    "all the invoices",
                    "every invoice",
                    "every single invoice",
                    "list all",
                    "show all",
                    "which invoices",
                    "what invoices",
                    "list invoices",
                    "show invoices",
                )
            )

            if (
                tool_request.name == "search_invoices"
                and is_invoice_listing
            ):
                arguments["limit"] = 140

            result = self.tool_registry.execute(
                name=tool_request.name,
                arguments=arguments,
            )

            if tool_request.name == "search_invoices":
                invoices = result.get("invoices", [])

                logger.info(
                    "Invoice search result: total_matches=%s, "
                    "returned_records=%s, actual_records=%s",
                    result.get("total_matches"),
                    result.get("returned_records"),
                    len(invoices),
                )

                invoice_searches.append({
                    "arguments": arguments,
                    "result": result,
                })

            evidence.append({
                "tool": tool_request.name,
                "result": result,
            })

            tools_used.append(tool_request.name)

        # 4. Prepare evidence for the answer model.
        # Invoice rows are deliberately excluded from the LLM context.
        # They will be rendered deterministically from the original evidence.
        answer_evidence = self._prepare_answer_evidence(
            evidence=evidence,
            invoice_searches=invoice_searches,
        )

        evidence_context = json.dumps(
            answer_evidence,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        history_context = self._format_conversation_history(
            conversation_history
        )

        # 5. Check whether a deterministic answer can be generated.
        simple_answer = self._build_simple_invoice_answer(
            question=question,
            conversation_history=conversation_history or [],
            invoice_searches=invoice_searches,
        )

        response = None

        if simple_answer is not None:
            logger.info(
                "Generating deterministic invoice retrieval answer"
            )

            response_content = simple_answer

        else:
            # Build the answer prompt.
            system_prompt = ANSWER_SYSTEM_PROMPT.format(
                procurement_policy=self.procurement_policy
            )

            user_prompt = ANSWER_USER_PROMPT_TEMPLATE.format(
                conversation_history=history_context,
                evidence=evidence_context,
                question=question,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Generate a grounded answer.
            temperature = self._get_temperature()

            logger.info(
                "Generating answer using model %s (temperature=%s)",
                self.llm.model,
                temperature,
            )

            response = self.llm.chat(
                messages=messages,
                temperature=temperature,
            )

            response_content = response.message.content or ""

            logger.info(
                "LLM response metadata: done=%s, done_reason=%s, "
                "prompt_eval_count=%s, eval_count=%s, content_length=%s",
                getattr(response, "done", None),
                getattr(response, "done_reason", None),
                getattr(response, "prompt_eval_count", None),
                getattr(response, "eval_count", None),
                len(response_content),
            )

            if not response_content.strip():
                logger.error(
                    "Empty LLM response. Response metadata: %s",
                    response.model_dump(exclude={"message"}),
                )

        answer = self.answer_guardrail.validate(response_content)

        # Remove any Markdown tables generated by the model.
        # Invoice tables must come exclusively from the original tool data.
        if invoice_searches:
            answer = self._strip_markdown_tables(answer)

            invoice_section = self._render_invoice_results(
                invoice_searches,
                question,
            )

            if invoice_section:
                answer = (
                    answer.rstrip()
                    + "\n\n"
                    + invoice_section
                )

        # 6. Record usage only when the LLM was called.
        if response is not None:
            self._record_usage(
                response=response,
                operation="answer",
                conversation_id=conversation_id,
            )

        return {
            "answer": answer,
            "route": decision.route.value,
            "decision_summary": decision.decision_summary,
            "evidence": evidence,
            "tools_used": tools_used,
            "conversation_id": conversation_id,
        }

    @staticmethod
    def _prepare_answer_evidence(
        evidence: list[dict],
        invoice_searches: list[dict],
    ) -> list[dict]:
        """
        Prepare evidence for the answer model.

        Small invoice result sets are included in full.
        Larger result sets are represented by aggregate information
        to control context size.
        """

        answer_evidence = [
            item
            for item in evidence
            if item.get("tool") != "search_invoices"
        ]

        if not invoice_searches:
            return answer_evidence

        unique_invoices = {}
        status_totals = {}
        search_parameters = []

        for search in invoice_searches:
            arguments = search.get("arguments", {})
            result = search.get("result", {})

            if not isinstance(arguments, Mapping):
                arguments = {}

            # Preserve the parameters used to retrieve invoice records.
            sort_by = arguments.get("sort_by")
            sort_order = arguments.get("sort_order")
            limit = arguments.get("limit")

            search_parameters.append({
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": limit,
                "ranking_applied": (
                    sort_by is not None
                    and sort_order is not None
                    and limit is not None
                ),
            })

            status = arguments.get("vendor_status")

            if status:
                normalized_status = str(status).upper()

                status_totals[normalized_status] = (
                    status_totals.get(normalized_status, 0)
                    + int(result.get("total_matches", 0))
                )

            for invoice in result.get("invoices", []):
                invoice_number = invoice.get("invoice_number")

                if invoice_number is not None:
                    unique_invoices[str(invoice_number)] = invoice

        invoices = list(unique_invoices.values())

        if len(invoice_searches) == 1:
            total_matches = int(
                invoice_searches[0]["result"].get("total_matches", 0)
            )
        else:
            total_matches = None

        # Include complete invoice records when the result set is small.
        if len(invoices) <= 20:
            answer_evidence.append({
                "tool": "search_invoices",
                "result": {
                    "total_matches": total_matches,
                    "returned_records": len(invoices),
                    "search_parameters": search_parameters,
                    "invoices": invoices,
                },
            })

            return answer_evidence

        # Use aggregate information for larger result sets.
        flag_counts = {
            "missing_po": sum(
                invoice.get("missing_po") is True
                for invoice in invoices
            ),
            "missing_approver": sum(
                invoice.get("missing_approver") is True
                for invoice in invoices
            ),
            "maverick_spend": sum(
                invoice.get("maverick_spend") is True
                for invoice in invoices
            ),
            "requires_PE_escalation": sum(
                invoice.get("requires_PE_escalation") is True
                for invoice in invoices
            ),
        }

        answer_evidence.append({
            "tool": "invoice_search_summary",
            "result": {
                "total_matches": total_matches,
                "returned_records": len(invoices),
                "search_parameters": search_parameters,
                "status_totals": status_totals,
                "retrieved_invoice_flags": flag_counts,
                "sample_records": invoices[:5],
                "note": (
                    "This is a limited sample of the matching invoices. "
                    "Do not interpret sample statistics as totals "
                    "for all matching invoices."
                ),
            },
        })

        return answer_evidence

    @staticmethod
    def _render_invoice_results(
        invoice_searches: list[dict],
        question: str,
    ) -> str:
        """Build a contextual Markdown invoice table from tool results."""

        unique_invoices = {}

        for search in invoice_searches:
            result = search.get("result", {})

            for invoice in result.get("invoices", []):
                invoice_number = invoice.get("invoice_number")

                if invoice_number is not None:
                    unique_invoices[str(invoice_number)] = invoice

        invoices = list(unique_invoices.values())

        if not invoices:
            return ""

        total_matches = Orchestrator._get_total_matches(
            invoice_searches
        )

        returned_records = len(invoices)

        if total_matches is None:
            summary = (
                f"**Retrieved invoices:** {returned_records}. "
                "The combined total number of matches cannot be "
                "determined reliably from the available searches."
            )

        elif returned_records < total_matches:
            summary = (
                f"**Retrieved invoices:** {returned_records} of "
                f"{total_matches} matching invoices. "
                "The table contains only the retrieved records."
            )

        else:
            summary = (
                f"**Matching invoices:** {total_matches}. "
                f"All {returned_records} retrieved records are shown below."
            )

        # Select columns according to the information requested.
        normalized_question = question.lower()

        if any(
            term in normalized_question
            for term in (
                "missing approver",
                "missing an approver",
                "without approver",
                "approver record",
            )
        ):
            columns = [
                ("Invoice", "invoice_number"),
                ("Vendor", "vendor_name"),
                ("Amount (EUR)", "EUR_amount"),
                ("Required approver", "required_approver"),
                ("Approved by", "approved_by"),
            ]

        elif any(
            term in normalized_question
            for term in (
                "missing po",
                "missing purchase order",
                "without po",
                "without purchase order",
            )
        ):
            columns = [
                ("Invoice", "invoice_number"),
                ("Vendor", "vendor_name"),
                ("Amount (EUR)", "EUR_amount"),
                ("PO number", "po_number"),
                ("Maverick spend", "maverick_spend"),
            ]

        elif any(
            term in normalized_question
            for term in (
                "compliance",
                "compliant",
                "non-compliant",
                "policy",
                "audit",
                "maverick",
                "escalation",
                "vendor status",
                "approval status",
            )
        ):
            columns = [
                ("Invoice", "invoice_number"),
                ("Vendor", "vendor_name"),
                ("Amount (EUR)", "EUR_amount"),
                ("Vendor status", "vendor_status"),
                ("Cost center", "cost_center"),
                ("PO number", "po_number"),
                ("Approved by", "approved_by"),
                ("Missing PO", "missing_po"),
                ("Missing approver", "missing_approver"),
                ("Maverick spend", "maverick_spend"),
                ("PE escalation", "requires_PE_escalation"),
            ]

        else:
            columns = [
                ("Invoice", "invoice_number"),
                ("Vendor", "vendor_name"),
                ("Invoice date", "invoice_date"),
                ("Amount (EUR)", "EUR_amount"),
            ]

        headers = [header for header, _ in columns]

        rows = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]

        for invoice in invoices:
            values = []

            for header, field in columns:
                value = invoice.get(field)

                if field == "EUR_amount":
                    if value is None:
                        value = "—"
                    else:
                        try:
                            value = f"{float(value):,.2f}"
                        except (TypeError, ValueError):
                            value = str(value)

                values.append(
                    Orchestrator._format_table_value(value)
                )

            rows.append(
                "| " + " | ".join(values) + " |"
            )

        return (
            "## Retrieved invoice records\n\n"
            + summary
            + "\n\n"
            + "\n".join(rows)
        )

    @staticmethod
    def _get_total_matches(
        invoice_searches: list[dict],
    ) -> Optional[int]:
        """Return a combined total only when the searches are disjoint."""

        if len(invoice_searches) == 1:
            return int(
                invoice_searches[0]["result"].get("total_matches", 0)
            )

        statuses = []

        for search in invoice_searches:
            arguments = search.get("arguments", {})

            if not isinstance(arguments, Mapping):
                return None

            status = arguments.get("vendor_status")

            if not status:
                return None

            statuses.append(str(status).upper())

        if len(set(statuses)) != len(statuses):
            return None

        return sum(
            int(search["result"].get("total_matches", 0))
            for search in invoice_searches
        )

    @staticmethod
    def _format_table_value(value: Any) -> str:
        if value is None:
            return "—"

        if isinstance(value, bool):
            return "Yes" if value else "No"

        text = str(value)

        # Prevent values from breaking the Markdown table structure.
        return text.replace("|", "\\|").replace("\n", " ")

    @staticmethod
    def _strip_markdown_tables(text: str) -> str:
        """Remove Markdown tables so model-generated rows cannot be shown."""

        lines = text.splitlines()
        result = []
        index = 0

        while index < len(lines):
            current = lines[index]

            is_table_header = (
                "|" in current
                and index + 1 < len(lines)
                and re.search(
                    r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?",
                    lines[index + 1],
                )
            )

            if is_table_header:
                index += 2

                while index < len(lines) and "|" in lines[index]:
                    index += 1

                continue

            result.append(current)
            index += 1

        return "\n".join(result).strip()

    @staticmethod
    def _format_conversation_history(
        conversation_history: Optional[Sequence[Mapping[str, str]]],
    ) -> str:
        """Format a small amount of prior context for follow-up questions."""

        if not conversation_history:
            return "No previous conversation."

        relevant_messages = []

        for message in conversation_history[-6:]:
            role = message.get("role")
            content = message.get("content")

            if role not in {"user", "assistant"} or not content:
                continue

            content = str(content).strip()

            if len(content) > 1200:
                content = content[:1200] + " ...[truncated]"

            relevant_messages.append({
                "role": role,
                "content": content,
            })

        if not relevant_messages:
            return "No previous conversation."

        return json.dumps(
            relevant_messages,
            ensure_ascii=False,
            indent=2,
        )

    def _get_temperature(self) -> float:
        if self.runtime_config is None:
            return 0.0

        return self.runtime_config.temperature

    def _record_usage(
        self,
        response,
        operation: str,
        conversation_id: Optional[str],
    ) -> None:
        if self.history_store is None:
            return

        try:
            self.history_store.record_usage(
                operation=operation,
                model=self.llm.model,
                prompt_tokens=getattr(
                    response,
                    "prompt_eval_count",
                    None,
                ),
                completion_tokens=getattr(
                    response,
                    "eval_count",
                    None,
                ),
                conversation_id=conversation_id,
            )

        except Exception:
            # Usage tracking must not prevent a successful answer.
            logger.exception("Could not record model usage.")

    def _build_simple_invoice_answer(
        self,
        question: str,
        conversation_history: list,
        invoice_searches: list,
    ) -> Optional[str]:

        if len(invoice_searches) != 1:
            return None

        search_result = invoice_searches[0].get("result", {})
        arguments = invoice_searches[0].get("arguments", {})

        total_matches = search_result.get("total_matches")

        if total_matches is None:
            return None

        # Include previous user requests to handle clarification follow-ups.
        user_messages = [
            message.get("content", "")
            for message in conversation_history
            if message.get("role") == "user"
        ]

        request_text = " ".join(user_messages + [question]).lower()

        retrieval_intents = (
            "show invoices",
            "list invoices",
            "find invoices",
            "get invoices",
            "retrieve invoices",
            "display invoices",
            "which invoices",
            "what invoices",
            "all invoices",
            "every invoice",
        )

        if not any(intent in request_text for intent in retrieval_intents):
            return None

        # Keep the LLM for questions requiring interpretation or analysis.
        analytical_terms = (
            "compliance",
            "procurement policy",
            "approval requirements",
            "policy",
            "exception analysis",
            "compliance analysis",
            "explain",
            "why",
            "compare",
            "assess",
            "recommend",
            "risk assessment",
            "analyze",
            "analysis",
            "audit",
        )

        if any(term in request_text for term in analytical_terms):
            return None

        # Identify an exact calendar quarter from the search dates.
        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")

        if start_date and end_date:
            year = start_date[:4]
            month = int(start_date[5:7])
            quarter = (month - 1) // 3 + 1

            quarter_dates = {
                1: ("01-01", "03-31"),
                2: ("04-01", "06-30"),
                3: ("07-01", "09-30"),
                4: ("10-01", "12-31"),
            }

            expected_start, expected_end = quarter_dates[quarter]

            if (
                start_date == f"{year}-{expected_start}"
                and end_date == f"{year}-{expected_end}"
            ):
                return (
                    f"The resolved request is to retrieve invoices dated in "
                    f"Q{quarter} {year}; there are {total_matches} invoices."
                )

        noun = "invoice" if total_matches == 1 else "invoices"

        return f"I found {total_matches} matching {noun}."