from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence, Type

from pydantic import BaseModel, ValidationError

import pandas as pd

from app.tools.invoice_tools import (
    InvoiceTools,
    SearchInvoicesArgs,
    InvoiceDetailsArgs,
    SpendSummaryArgs
)

from app.tools.compliance_tools import (
    ComplianceTools,
    ComplianceOverviewArgs
)


@dataclass
class ToolDefinition:
    name: str
    description: str
    args_model: Type[BaseModel]
    handler: Callable


class ToolRegistry:

    def __init__(self, invoices: pd.DataFrame):

        invoice_tools = InvoiceTools(invoices)
        compliance_tools = ComplianceTools(invoices)

        self._tools: dict[str, ToolDefinition] = {}

        self.register(
            ToolDefinition(
                name="search_invoices",
                description=(
                    "Search and retrieve invoices using the available filters, "
                    "including one or multiple vendors, vendor status, currency, "
                    "cost center, invoice date and EUR amount. "
                    "Use vendor_name for a single vendor and vendor_names "
                    "for multiple vendors in the same search."
                ),
                args_model=SearchInvoicesArgs,
                handler=invoice_tools.search_invoices
            )
        )

        self.register(
            ToolDefinition(
                name="get_invoice_details",
                description=(
                    "Retrieve all available information about a specific "
                    "invoice using its invoice number."
                ),
                args_model=InvoiceDetailsArgs,
                handler=invoice_tools.get_invoice_details
            )
        )

        self.register(
            ToolDefinition(
                name="get_spend_summary",
                description=(
                    "Calculate total EUR spend and invoice counts, "
                    "grouped by currency, vendor, vendor status, "
                    "vendor category, country or month."
                ),
                args_model=SpendSummaryArgs,
                handler=invoice_tools.get_spend_summary
            )
        )

        self.register(
            ToolDefinition(
                name="get_compliance_overview",
                description=(
                    "Retrieve deterministic procurement compliance "
                    "indicators and limitations of the available dataset."
                ),
                args_model=ComplianceOverviewArgs,
                handler=compliance_tools.get_compliance_overview
            )
        )

    def register(self, tool: ToolDefinition) -> None:

        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered."
            )

        self._tools[tool.name] = tool

    def get_llm_schemas(self) -> Sequence[Mapping[str, Any]]:

        schemas = []

        for tool in self._tools.values():

            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_model.model_json_schema()
                }
            })

        return schemas

    def validate_arguments(
        self,
        name: str,
        arguments: dict[str, Any]
    ) -> BaseModel:

        if name not in self._tools:
            raise ValueError(
                f"Tool '{name}' is not registered."
            )

        tool = self._tools[name]

        try:
            return tool.args_model.model_validate(arguments)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid arguments for tool '{name}': {exc}"
            ) from exc

    def execute(
        self,
        name: str,
        arguments: dict[str, Any]
    ) -> Any:

        validated_args = self.validate_arguments(
            name=name,
            arguments=arguments
        )

        return self._tools[name].handler(validated_args)