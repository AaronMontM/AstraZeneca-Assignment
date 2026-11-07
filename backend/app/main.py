import logging

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import UUID

import pandas as pd

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.history import HistoryStore
from app.runtime_config import RuntimeConfig

from app.llm.client import OllamaClient
from app.llm.router import QueryRouter
from app.llm.orchestrator import Orchestrator

from app.tools.registry import ToolRegistry


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# API request models
# ---------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: Optional[UUID] = None


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None


class ConfigUpdate(BaseModel):
    model: Optional[str] = Field(default=None, min_length=1)
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    max_history_messages: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
    )


# ---------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Initializing Finance Spend Intelligence Assistant")

    # 1. Initialize PostgreSQL
    history_store = HistoryStore(settings.DATABASE_URL)

    # 2. Load invoice dataset
    invoices = pd.read_csv(settings.DATA_PATH)

    logger.info("Loaded %s invoices", len(invoices))

    # 3. Load procurement policy
    procurement_policy = settings.POLICY_PATH.read_text(
        encoding="utf-8"
    )

    # 4. Initialize runtime configuration
    runtime_config = RuntimeConfig.from_settings()

    # 5. Initialize Ollama client
    llm = OllamaClient(
        model=runtime_config.model,
        host=settings.OLLAMA_HOST,
    )

    # 6. Initialize tools
    tool_registry = ToolRegistry(invoices)

    # 7. Initialize query router
    router = QueryRouter(
        llm=llm,
        tool_registry=tool_registry,
        history_store=history_store,
        runtime_config=runtime_config,
    )

    # 8. Initialize orchestrator
    orchestrator = Orchestrator(
        llm=llm,
        router=router,
        tool_registry=tool_registry,
        procurement_policy=procurement_policy,
        history_store=history_store,
        runtime_config=runtime_config,
    )

    # 9. Store dependencies in application state
    app.state.history_store = history_store
    app.state.runtime_config = runtime_config
    app.state.llm = llm
    app.state.tool_registry = tool_registry
    app.state.invoices = invoices.copy()
    app.state.router = router
    app.state.orchestrator = orchestrator

    logger.info(
        "Finance Spend Intelligence Assistant initialized"
    )

    yield

    logger.info("Shutting down Finance Spend Intelligence Assistant")


# ---------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered assistant for financial spend analysis "
        "and procurement policy queries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def get_available_models() -> list[str]:
    """
    Retrieve the models currently available in Ollama.
    """

    response = app.state.llm.client.list()

    return sorted([
        model.model
        for model in response.models
    ])

def get_conversation_history(
    conversation: dict,
    max_messages: int,
    router_only: bool = False,
) -> list[dict[str, str]]:
    """
    Extract recent conversation messages.

    When router_only is enabled, only user messages and assistant
    clarification messages are included.
    """

    messages = conversation.get("messages", [])

    history = []

    for message in messages:

        if message["role"] == "user":
            history.append({
                "role": "user",
                "content": message["content"],
            })

        elif message["role"] == "assistant":

            if router_only and message.get("route") != "CLARIFICATION":
                continue

            history.append({
                "role": "assistant",
                "content": message["content"],
            })

    return history[-max_messages:]

# ---------------------------------------------------------------------
# Health and status
# ---------------------------------------------------------------------

@app.get("/status")
def get_status():

    database_status = "available"
    ollama_status = "available"

    try:
        app.state.history_store.get_usage_summary()
    except Exception:
        logger.exception("PostgreSQL health check failed")
        database_status = "unavailable"

    try:
        app.state.llm.client.list()
    except Exception:
        logger.exception("Ollama health check failed")
        ollama_status = "unavailable"

    overall_status = (
        "healthy"
        if database_status == "available"
        and ollama_status == "available"
        else "degraded"
    )

    return {
        "status": overall_status,
        "services": {
            "database": database_status,
            "ollama": ollama_status,
        },
    }


# ---------------------------------------------------------------------
# Configuration endpoints
# ---------------------------------------------------------------------

@app.get("/config")
def get_config():
    """
    Return the current runtime configuration.
    """

    return app.state.runtime_config.to_dict()


@app.patch("/config")
def update_config(config_update: ConfigUpdate):
    """
    Partially update the runtime configuration.
    """

    updates = config_update.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    if not updates:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one configuration parameter "
                "must be provided."
            ),
        )

    # Validate model availability before applying changes.
    if "model" in updates:

        try:
            available_models = get_available_models()

        except Exception as exc:
            logger.exception("Could not retrieve Ollama models")

            raise HTTPException(
                status_code=503,
                detail="Ollama is currently unavailable.",
            ) from exc

        if updates["model"] not in available_models:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Model not available in Ollama.",
                    "available_models": available_models,
                },
            )

    # Update runtime configuration.
    app.state.runtime_config.update(**updates)

    # Apply the selected model to the shared Ollama client.
    if "model" in updates:
        app.state.llm.model = updates["model"]

    logger.info(
        "Runtime configuration updated: %s",
        updates,
    )

    return {
        "message": "Configuration updated successfully.",
        "config": app.state.runtime_config.to_dict(),
    }


# ---------------------------------------------------------------------
# Financial summary
# ---------------------------------------------------------------------

@app.get("/summary")
def get_summary():

    tool_registry = app.state.tool_registry

    currency_summary = tool_registry.execute(
        name="get_spend_summary",
        arguments={
            "group_by": "currency",
        },
    )

    vendor_status_summary = tool_registry.execute(
        name="get_spend_summary",
        arguments={
            "group_by": "vendor_status",
        },
    )

    return {
        "total_net_spend_eur": currency_summary[
            "total_eur_spend"
        ],
        "invoice_count": currency_summary["invoice_count"],
        "by_currency": currency_summary["breakdown"],
        "by_vendor_status": vendor_status_summary["breakdown"],
    }


# ---------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------

@app.get("/dashboard")
def get_dashboard():
    """Return deterministic aggregates used by the dashboard charts."""

    df = app.state.invoices.copy()

    # Review indicators are overlapping counts: one invoice can trigger
    # more than one indicator, so these values must not be added together.
    alert_columns = {
        "maverick_spend": "Maverick spend",
        "requires_PE_escalation": "Procurement Excellence escalation",
        "credit_note": "Credit note",
        "missing_approver": "Missing approver",
        "invoice_on_weekend": "Weekend invoice",
    }
    alerts = [
        {
            "key": key,
            "label": label,
            "count": int(df[key].fillna(False).astype(bool).sum()),
        }
        for key, label in alert_columns.items()
    ]

    # This is a comparison of the recorded approver identifier and the
    # required role. It does NOT verify the person's actual authority.
    approver_df = df.copy()
    approver_df["approved_by"] = approver_df["approved_by"].fillna(
        "Missing approver"
    )
    approver_df["required_approver"] = approver_df[
        "required_approver"
    ].fillna("Unknown role")
    approver_matrix = (
        approver_df.groupby(["approved_by", "required_approver"])
        .size()
        .unstack(fill_value=0)
    )
    approver_roles = {
        "roles": [str(role) for role in approver_matrix.columns],
        "rows": [
            {
                "approved_by": str(approver),
                "counts": {
                    str(role): int(approver_matrix.loc[approver, role])
                    for role in approver_matrix.columns
                },
            }
            for approver in approver_matrix.index
        ],
    }

    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    
    monthly = (
        df.groupby("invoice_month", dropna=False)
        .agg(
            net_spend_eur=("EUR_amount", "sum"),
            invoice_count=("invoice_number", "count"),
        )
        .reset_index()
    )
    monthly["month_order"] = monthly["invoice_month"].apply(
        lambda month: month_order.index(month)
        if month in month_order else len(month_order)
    )
    monthly = monthly.sort_values("month_order")
    total_net_spend = float(df["EUR_amount"].sum())
    monthly_expenses = [
        {
            "month": str(row["invoice_month"]),
            "net_spend_eur": round(float(row["net_spend_eur"]), 2),
            "invoice_count": int(row["invoice_count"]),
            "share_percent": round(
                float(row["net_spend_eur"]) / total_net_spend * 100, 2
            ) if total_net_spend else 0.0,
        }
        for _, row in monthly.iterrows()
    ]

    # KPI metrics
    alert_flags = list(alert_columns.keys())

    invoices_with_alerts = int(
        df[alert_flags]
        .fillna(False)
        .astype(bool)
        .any(axis=1)
        .sum()
    )

    kpis = {
        "total_net_spend_eur": round(total_net_spend, 2),
        "invoice_count": int(len(df)),
        "invoices_with_alerts": invoices_with_alerts,
    }

    def expense_breakdown(column: str) -> list[dict]:
        grouped = (
            df.groupby(column, dropna=False)
            .agg(
                net_spend_eur=("EUR_amount", "sum"),
                invoice_count=("invoice_number", "count"),
            )
            .reset_index()
            .sort_values("net_spend_eur", ascending=False)
        )
        return [
            {
                "name": "Unknown" if pd.isna(row[column]) else str(row[column]),
                "net_spend_eur": round(float(row["net_spend_eur"]), 2),
                "invoice_count": int(row["invoice_count"]),
            }
            for _, row in grouped.iterrows()
        ]

    return {
        "kpis": kpis,
        "alerts": {
            "description": (
                "Counts are overlapping indicators; a single invoice may "
                "appear in more than one category."
            ),
            "items": alerts,
        },
        "approver_roles": {
            "description": (
                "Compares the recorded approver identifier with the required "
                "role; actual authority cannot be verified from this dataset."
            ),
            **approver_roles,
        },
        "monthly_expenses": {
            "basis": "EUR_amount",
            "measure": "Net spend, including negative credit notes",
            "total_net_spend_eur": round(total_net_spend, 2),
            "items": monthly_expenses,
        },
        "expenses_by": {
            "vendors": expense_breakdown("vendor_name"),
            "countries": expense_breakdown("vendor_country"),
            "categories": expense_breakdown("vendor_category"),
        },
    }


# ---------------------------------------------------------------------
# Invoice data explorer
# ---------------------------------------------------------------------

@app.get("/invoice-filter-options")
def get_invoice_filter_options():
    """Return the available values for invoice filters."""

    df = app.state.invoices

    def get_unique_values(column: str) -> list[str]:
        values = (
            df[column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        return sorted(
            value
            for value in values.unique().tolist()
            if value
        )

    return {
        "vendor_statuses": get_unique_values("vendor_status"),
        "countries": get_unique_values("vendor_country"),
        "categories": get_unique_values("vendor_category"),
        "currencies": get_unique_values("currency"),
        "cost_centers": get_unique_values("cost_center"),
    }

@app.get("/invoices")
def get_invoices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    search_by: str = Query(
        default="all",
        pattern=(
            "^(all|invoice_number|vendor_name|vendor_id|"
            "cost_center|vendor_country|po_number|approved_by)$"
        ),
    ),
    vendor_status: Optional[str] = None,
    vendor_country: Optional[str] = None,
    vendor_category: Optional[str] = None,
    currency: Optional[str] = None,
    cost_center: Optional[str] = None,
    missing_po: Optional[bool] = None,
    missing_approver: Optional[bool] = None,
    maverick_spend: Optional[bool] = None,
    requires_pe_escalation: Optional[bool] = None,
    sort_by: str = Query(default="invoice_date"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    """Search, filter, sort and paginate the processed invoice dataset."""

    df = app.state.invoices.copy()

    # Free-text search
    searchable_columns = {
        "invoice_number": ["invoice_number"],
        "vendor_name": ["vendor_name"],
        "vendor_id": ["vendor_id"],
        "cost_center": ["cost_center"],
        "vendor_country": ["vendor_country"],
        "po_number": ["po_number"],
        "approved_by": ["approved_by"],
    }

    if search:
        columns = (
            list(df.columns.intersection(searchable_columns.keys()))
            if search_by == "all"
            else searchable_columns[search_by]
        )

        search_mask = pd.Series(False, index=df.index)

        for column in columns:
            search_mask |= (
                df[column]
                .fillna("")
                .astype(str)
                .str.contains(
                    search,
                    case=False,
                    na=False,
                    regex=False,
                )
            )

        df = df[search_mask]

    # Structured filters
    if vendor_status:
        df = df[
            df["vendor_status"].str.upper() == vendor_status.upper()
        ]

    if vendor_country:
        df = df[
            df["vendor_country"].str.upper() == vendor_country.upper()
        ]

    if vendor_category:
        df = df[
            df["vendor_category"].str.upper() == vendor_category.upper()
        ]

    if currency:
        df = df[
            df["currency"].str.upper() == currency.upper()
        ]

    if cost_center:
        df = df[
            df["cost_center"].str.upper() == cost_center.upper()
        ]

    if missing_po is not None:
        df = df[
            df["missing_po"].fillna(False) == missing_po
        ]

    if missing_approver is not None:
        df = df[
            df["missing_approver"].fillna(False) == missing_approver
        ]

    if maverick_spend is not None:
        df = df[
            df["maverick_spend"].fillna(False) == maverick_spend
        ]

    if requires_pe_escalation is not None:
        df = df[
            df["requires_PE_escalation"].fillna(False)
            == requires_pe_escalation
        ]

    # Sorting
    allowed_sort_columns = {
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "vendor_status",
        "amount",
        "currency",
        "EUR_amount",
        "cost_center",
        "approved_by",
    }

    if sort_by not in allowed_sort_columns:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported sort field.",
                "allowed_fields": sorted(allowed_sort_columns),
            },
        )

    df = df.sort_values(
        by=sort_by,
        ascending=(sort_order == "asc"),
        na_position="last",
    )

    # Pagination
    total = len(df)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size

    page_df = df.iloc[start:start + page_size]

    # Convert pandas/numpy values to JSON-compatible Python values
    raw_records = page_df.to_dict(orient="records")
    records = []

    for record in raw_records:
        clean_record = {}

        for key, value in record.items():
            if pd.isna(value):
                clean_record[key] = None
            elif hasattr(value, "isoformat"):
                clean_record[key] = value.isoformat()
            elif hasattr(value, "item"):
                clean_record[key] = value.item()
            else:
                clean_record[key] = value

        records.append(clean_record)

    return {
        "items": records,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total,
            "total_pages": total_pages,
        },
        "filters": {
            "search": search,
            "search_by": search_by,
            "vendor_status": vendor_status,
            "vendor_country": vendor_country,
            "vendor_category": vendor_category,
            "currency": currency,
            "cost_center": cost_center,
            "missing_po": missing_po,
            "missing_approver": missing_approver,
            "maverick_spend": maverick_spend,
            "requires_pe_escalation": requires_pe_escalation,
        },
    }


# ---------------------------------------------------------------------
# Ask endpoint
# ---------------------------------------------------------------------

@app.post("/ask")
def ask(request: AskRequest):

    history_store = app.state.history_store

    try:

        # 1. Create or retrieve conversation
        if request.conversation_id is None:

            conversation_id = history_store.create_conversation(
                title=request.question[:80]
            )

            conversation = history_store.get_conversation(
                conversation_id
            )

        else:

            conversation_id = str(request.conversation_id)

            conversation = history_store.get_conversation(
                conversation_id
            )

            if conversation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )

        # 2. Retrieve previous messages.
        conversation_history = get_conversation_history(
            conversation=conversation,
            max_messages=app.state.runtime_config.max_history_messages,
        )

        router_history = get_conversation_history(
            conversation=conversation,
            max_messages=app.state.runtime_config.max_history_messages,
            router_only=True,
        )

        # 3. Save current user message.
        history_store.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.question,
        )

        # 4. Run orchestrator.
        result = app.state.orchestrator.run(
            question=request.question,
            conversation_history=conversation_history,
            router_history=router_history,
            conversation_id=conversation_id,
        )

        # 5. Save assistant response
        history_store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=result["answer"],
            route=result["route"],
            evidence=result["evidence"],
            tools_used=result["tools_used"],
        )

        return result

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception("Error processing /ask request")

        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the question.",
        ) from exc


# ---------------------------------------------------------------------
# Conversation endpoints
# ---------------------------------------------------------------------

@app.post("/conversations")
def create_conversation(
    request: ConversationCreateRequest,
):

    conversation_id = app.state.history_store.create_conversation(
        title=request.title
    )

    return {
        "conversation_id": conversation_id,
    }


@app.get("/conversations")
def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
):

    return app.state.history_store.list_conversations(
        limit=limit
    )


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID):

    conversation = app.state.history_store.get_conversation(
        str(conversation_id)
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return conversation


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: UUID):

    deleted = app.state.history_store.delete_conversation(
        str(conversation_id)
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return {
        "message": "Conversation deleted successfully.",
    }


# ---------------------------------------------------------------------
# Usage metrics
# ---------------------------------------------------------------------

@app.get("/usage")
def get_usage(
    conversation_id: Optional[UUID] = None,
):

    return app.state.history_store.get_usage_summary(
        conversation_id=(
            str(conversation_id)
            if conversation_id is not None
            else None
        )
    )