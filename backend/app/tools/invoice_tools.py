from typing import Literal, Optional

import pandas as pd

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# ---------------------------------------------------------------------
# Tool arguments
# ---------------------------------------------------------------------

class SearchInvoicesArgs(BaseModel):

    model_config = ConfigDict(extra="forbid")

    vendor_name: Optional[str] = None
    vendor_names: Optional[list[str]] = None
    vendor_country: Optional[str] = None
    vendor_category: Optional[str] = None
    vendor_status: Optional[str] = None
    vendor_statuses: Optional[list[str]] = None
    currency: Optional[str] = None
    cost_center: Optional[str] = None
    missing_po: Optional[bool] = None
    missing_approver: Optional[bool] = None
    maverick_spend: Optional[bool] = None
    min_eur_amount: Optional[float] = None
    max_eur_amount: Optional[float] = None
    min_eur_amount_exclusive: bool = False
    max_eur_amount_exclusive: bool = False
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    credit_note: Optional[bool] = None

    sort_by: Optional[
        Literal[
            "EUR_amount",
            "invoice_date",
            "amount"
        ]
    ] = None

    sort_order: Literal["asc", "desc"] = "desc"

    limit: int = Field(default=10, ge=1, le=140)

    @field_validator("limit", mode="before")
    @classmethod
    def normalize_limit(cls, value):
        if value is None or value < 1:
            return 10

        if value > 140:
            return 140

        return value


class InvoiceDetailsArgs(BaseModel):

    model_config = ConfigDict(extra="forbid")

    invoice_number: str


class SpendSummaryArgs(BaseModel):

    model_config = ConfigDict(extra="forbid")

    group_by: Literal[
        "currency",
        "vendor",
        "vendor_status",
        "vendor_category",
        "country",
        "month",
        "cost_center"
    ] = "currency"

    start_date: Optional[str] = None
    end_date: Optional[str] = None


# ---------------------------------------------------------------------
# Invoice tools
# ---------------------------------------------------------------------

class InvoiceTools:

    def __init__(self, invoices: pd.DataFrame):
        self.invoices = invoices.copy()

    @staticmethod
    def _clean_value(value):
        if pd.isna(value):
            return None

        if hasattr(value, "isoformat"):
            return value.isoformat()

        if hasattr(value, "item"):
            return value.item()

        return value

    @classmethod
    def _records(cls, df: pd.DataFrame) -> list[dict]:
        records = df.to_dict(orient="records")

        return [
            {
                key: cls._clean_value(value)
                for key, value in record.items()
            }
            for record in records
        ]

    def search_invoices(
        self,
        args: SearchInvoicesArgs
    ) -> dict:

        df = self.invoices.copy()

        if args.vendor_names:
            vendor_mask = pd.Series(False, index=df.index)

            for vendor_name in args.vendor_names:
                vendor_mask |= df["vendor_name"].str.contains(
                    vendor_name,
                    case=False,
                    na=False,
                    regex=False
                )

            df = df[vendor_mask]

        elif args.vendor_name:
            df = df[
                df["vendor_name"].str.contains(
                    args.vendor_name,
                    case=False,
                    na=False,
                    regex=False
                )
            ]

        if args.vendor_country:
            df = df[
                df["vendor_country"].str.casefold()
                == args.vendor_country.casefold()
            ]

        if args.vendor_category:
            df = df[
                df["vendor_category"].str.casefold()
                == args.vendor_category.casefold()
            ]

        if args.vendor_statuses:
            statuses = [
                status.upper()
                for status in args.vendor_statuses
            ]

            df = df[
                df["vendor_status"].str.upper().isin(statuses)
            ]

        elif args.vendor_status:
            df = df[
                df["vendor_status"].str.upper()
                == args.vendor_status.upper()
            ]

        if args.currency:
            df = df[
                df["currency"].str.upper()
                == args.currency.upper()
            ]

        if args.cost_center:
            df = df[
                df["cost_center"].str.upper()
                == args.cost_center.upper()
            ]

        if args.start_date:
            invoice_dates = pd.to_datetime(
                df["invoice_date"],
                errors="coerce"
            )
            df = df[invoice_dates >= args.start_date]

        if args.end_date:
            invoice_dates = pd.to_datetime(
                df["invoice_date"],
                errors="coerce"
            )
            df = df[invoice_dates <= args.end_date]

        if args.credit_note is not None:
            df = df[df["credit_note"] == args.credit_note]

        if args.missing_po is not None:
            df = df[df["missing_po"] == args.missing_po]

        if args.missing_approver is not None:
            df = df[
                df["missing_approver"] == args.missing_approver
            ]

        if args.maverick_spend is not None:
            df = df[
                df["maverick_spend"] == args.maverick_spend
            ]

        if args.min_eur_amount is not None:
            if args.min_eur_amount_exclusive:
                df = df[df["EUR_amount"] > args.min_eur_amount]
            else:
                df = df[df["EUR_amount"] >= args.min_eur_amount]

        if args.max_eur_amount is not None:
            if args.max_eur_amount_exclusive:
                df = df[df["EUR_amount"] < args.max_eur_amount]
            else:
                df = df[df["EUR_amount"] <= args.max_eur_amount]

        total_matches = len(df)

        if args.sort_by:
            df = df.sort_values(
                by=args.sort_by,
                ascending=args.sort_order == "asc",
                na_position="last"
            )

        df = df.head(args.limit)

        return {
            "total_matches": total_matches,
            "returned_records": len(df),
            "limit": args.limit,
            "invoices": self._records(df)
        }

    def get_invoice_details(
        self,
        args: InvoiceDetailsArgs
    ) -> dict:

        df = self.invoices[
            self.invoices["invoice_number"]
            == args.invoice_number
        ]

        if df.empty:
            return {
                "found": False,
                "invoice_number": args.invoice_number,
                "message": "Invoice not found."
            }

        return {
            "found": True,
            "invoice": self._records(df)[0]
        }

    def get_spend_summary(
        self,
        args: SpendSummaryArgs
    ) -> dict:

        # Apply optional date filters.
        df = self.invoices.copy()

        if args.start_date:
            invoice_dates = pd.to_datetime(
                df["invoice_date"],
                errors="coerce"
            )
            df = df[invoice_dates >= args.start_date]

        if args.end_date:
            invoice_dates = pd.to_datetime(
                df["invoice_date"],
                errors="coerce"
            )
            df = df[invoice_dates <= args.end_date]

        group_columns = {
            "currency": "currency",
            "vendor": "vendor_name",
            "vendor_status": "vendor_status",
            "vendor_category": "vendor_category",
            "country": "vendor_country",
            "month": "invoice_month",
            "cost_center": "cost_center"
        }

        column = group_columns[args.group_by]

        grouped = (
            df
            .groupby(column, dropna=False)
            .agg(
                invoice_count=("invoice_number", "count"),
                total_eur_spend=("EUR_amount", "sum")
            )
            .reset_index()
            .sort_values(
                "total_eur_spend",
                ascending=False
            )
        )

        if args.group_by == "cost_center":
            grouped = grouped.rename(
                columns={"total_eur_spend": "net_spend_eur"}
            )

        return {
            "grouped_by": args.group_by,
            "total_eur_spend": round(
                float(df["EUR_amount"].sum()), 2
            ),
            "invoice_count": len(df),
            "breakdown": self._records(grouped)
        }