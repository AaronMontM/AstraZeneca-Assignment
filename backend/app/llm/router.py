import json

from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.llm.client import OllamaClient
from app.runtime_config import RuntimeConfig
from app.config import settings
from app.llm.prompts import (
    ROUTER_SYSTEM_PROMPT,
    INVOICE_DATA_DESCRIPTION,
    ROUTER_RETRY_SYSTEM_PROMPT,
    ROUTER_RETRY_USER_PROMPT_TEMPLATE,
)

from typing import Literal


class Route(str, Enum):
    DATA = "data"
    POLICY = "policy"
    BOTH = "both"
    OUT_OF_SCOPE = "out_of_scope"
    CLARIFICATION = "clarification"


class ToolRequest(BaseModel):
    """
    Represents a tool requested by the router,
    including the arguments required for its execution.
    """

    model_config = ConfigDict(extra="forbid")

    name: Literal[
        "search_invoices",
        "get_invoice_details",
        "get_spend_summary",
        "get_compliance_overview",
    ]
    arguments: dict[str, Any] = Field(default_factory=dict)

class RoutingDecision(BaseModel):
    """
    Structured decision returned by the query router.
    """

    model_config = ConfigDict(extra="forbid")

    route: Route
    decision_summary: str
    required_tools: list[ToolRequest] = Field(
        default_factory=list,
        max_length=4,
    )
    clarification_question: Optional[str] = None

    @field_validator("required_tools")
    @classmethod
    def validate_unique_tools(
        cls,
        tools: list[ToolRequest],
    ) -> list[ToolRequest]:

        tool_names = [tool.name for tool in tools]

        if len(tool_names) != len(set(tool_names)):
            raise ValueError(
                "Each tool can only be requested once per routing decision."
            )

        return tools

class ToolSchemaProvider(Protocol):
    """
    Interface expected from the tool registry.
    """

    def get_llm_schemas(self) -> Sequence[Mapping[str, Any]]:
        ...

    def validate_arguments(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        ...


class QueryRouter:

    def __init__(
        self,
        llm: OllamaClient,
        tool_registry: ToolSchemaProvider,
        history_store=None,
        runtime_config: Optional[RuntimeConfig] = None,
    ):
        self.llm = llm
        self.tool_registry = tool_registry
        self.history_store = history_store
        self.runtime_config = runtime_config

        if self.runtime_config is None:
            raise ValueError("RuntimeConfig must be provided.")

    def route(
        self,
        question: str,
        conversation_history: Optional[
            Sequence[Mapping[str, str]]
        ] = None,
        conversation_id: Optional[str] = None,
    ) -> RoutingDecision:

        if not question or not question.strip():
            raise ValueError("The question cannot be empty.")

        available_tools = self.tool_registry.get_llm_schemas()

        available_tools_text = json.dumps(
            available_tools,
            indent=2,
            ensure_ascii=False,
        )

        conversation_history_text = json.dumps(
            list(conversation_history or []),
            indent=2,
            ensure_ascii=False,
        )

        # ---------------------------------------------------------
        # 1. Initial routing attempt
        # ---------------------------------------------------------

        from app.llm.prompts import ROUTER_USER_PROMPT_TEMPLATE

        user_prompt = ROUTER_USER_PROMPT_TEMPLATE.format(
            available_tools=available_tools_text,
            conversation_history=conversation_history_text,
            question=question,
        )

        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt(),
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        response = self.llm.chat(
            messages=messages,
            temperature=self.runtime_config.temperature,
            format=RoutingDecision.model_json_schema(),
        )

        self._record_usage(
            response=response,
            conversation_id=conversation_id,
        )

        previous_response = response.message.content

        try:
            return self._parse_and_validate_decision(
                content=previous_response,
                available_tools=available_tools,
            )

        except Exception as first_error:

            # -----------------------------------------------------
            # 2. Single recovery attempt
            # -----------------------------------------------------

            retry_user_prompt = (
                ROUTER_RETRY_USER_PROMPT_TEMPLATE.format(
                    available_tools=available_tools_text,
                    conversation_history=conversation_history_text,
                    question=question,
                    previous_decision=previous_response,
                    validation_error=str(first_error),
                )
            )

            retry_system_prompt = (
                ROUTER_RETRY_SYSTEM_PROMPT.format(
                    procurement_policy=settings.POLICY_PATH.read_text(
                        encoding="utf-8"
                    ),
                    invoice_data_description=INVOICE_DATA_DESCRIPTION,
                )
            )

            retry_messages = [
                {
                    "role": "system",
                    "content": retry_system_prompt,
                },
                {
                    "role": "user",
                    "content": retry_user_prompt,
                },
            ]

            retry_response = self.llm.chat(
                messages=retry_messages,
                temperature=self.runtime_config.temperature,
                format=RoutingDecision.model_json_schema(),
            )

            self._record_usage(
                response=retry_response,
                conversation_id=conversation_id,
            )

            # -----------------------------------------------------
            # 3. Validate recovery result
            # -----------------------------------------------------

            try:
                return self._parse_and_validate_decision(
                    content=retry_response.message.content,
                    available_tools=available_tools,
                )

            except Exception as retry_error:
                raise ValueError(
                    "Router failed to produce a valid routing "
                    "decision after one retry. "
                    f"Initial error: {first_error}. "
                    f"Retry error: {retry_error}."
                ) from retry_error

    def _parse_and_validate_decision(
        self,
        content: str,
        available_tools: Sequence[Mapping[str, Any]],
    ) -> RoutingDecision:

        try:
            decision = RoutingDecision.model_validate_json(content)
        except Exception as exc:
            raise ValueError(
                "Ollama returned an invalid routing decision."
            ) from exc

        available_tool_names = {
            tool["function"]["name"]
            for tool in available_tools
        }

        for tool_request in decision.required_tools:

            if tool_request.name not in available_tool_names:
                raise ValueError(
                    f"Unknown tool requested by router: "
                    f"{tool_request.name}"
                )

        self._validate_decision(decision)

        # Validate all tool arguments before returning the decision.
        for tool_request in decision.required_tools:

            self.tool_registry.validate_arguments(
                name=tool_request.name,
                arguments=tool_request.arguments,
            )

        return decision

    @staticmethod
    def _get_system_prompt() -> str:

        procurement_policy = settings.POLICY_PATH.read_text(encoding="utf-8")

        return ROUTER_SYSTEM_PROMPT.format(
            procurement_policy=procurement_policy,
            invoice_data_description=INVOICE_DATA_DESCRIPTION,
        )

    def _record_usage(
        self,
        response,
        conversation_id: Optional[str],
    ) -> None:

        if self.history_store is None:
            return

        self.history_store.record_usage(
            operation="router",
            model=self.llm.model,
            prompt_tokens=getattr(
                response, "prompt_eval_count", None
            ),
            completion_tokens=getattr(
                response, "eval_count", None
            ),
            conversation_id=conversation_id,
        )

    @staticmethod
    def _validate_decision(
        decision: RoutingDecision,
    ) -> None:

        if decision.route in {
            Route.POLICY,
            Route.OUT_OF_SCOPE,
            Route.CLARIFICATION,
        }:
            if decision.required_tools:
                raise ValueError(
                    f"Route '{decision.route.value}' "
                    "cannot request tools."
                )

        if decision.route in {
            Route.DATA,
            Route.BOTH,
        }:
            if not decision.required_tools:
                raise ValueError(
                    f"Route '{decision.route.value}' "
                    "requires at least one tool."
                )

        if decision.route == Route.CLARIFICATION:
            if not decision.clarification_question:
                raise ValueError(
                    "A clarification question is required "
                    "for the CLARIFICATION route."
                )