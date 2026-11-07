import pandas as pd

from pydantic import BaseModel, ConfigDict


class ComplianceOverviewArgs(BaseModel):

    model_config = ConfigDict(extra="forbid")


class ComplianceTools:

    def __init__(self, invoices: pd.DataFrame):
        self.invoices = invoices.copy()

    def get_compliance_overview(
        self,
        args: ComplianceOverviewArgs
    ) -> dict:

        df = self.invoices

        total = len(df)

        metrics = {
            "total_invoices": total,

            "missing_purchase_orders": int(
                df["missing_po"].sum()
            ),

            "maverick_spend": int(
                df["maverick_spend"].sum()
            ),

            "missing_approvers": int(
                df["missing_approver"].sum()
            ),

            "invoices_requiring_procurement_escalation": int(
                df["requires_PE_escalation"].sum()
            ),

            "credit_notes": int(
                df["credit_note"].sum()
            ),

            "weekend_invoices": int(
                df["invoice_on_weekend"].sum()
            )
        }

        vendor_status = (
            df["vendor_status"]
            .value_counts(dropna=False)
            .to_dict()
        )

        metrics["invoices_by_vendor_status"] = {
            str(key): int(value)
            for key, value in vendor_status.items()
        }

        metrics["missing_po_percentage"] = round(
            metrics["missing_purchase_orders"] / total * 100,
            2
        ) if total else 0.0

        return {
            "metrics": metrics,
            "limitations": [
                "The dataset does not contain requester information, "
                "so segregation of duties cannot be verified.",
                "The dataset does not establish whether purchase orders "
                "were approved and issued before the work or shipment.",
                "Payment dates and invoice receipt dates are unavailable, "
                "so payment terms cannot be verified.",
                "Credit note matching to original invoices cannot be "
                "verified with the available fields.",
                "Emergency purchase exceptions cannot be verified "
                "without the Exception Register."
            ]
        }