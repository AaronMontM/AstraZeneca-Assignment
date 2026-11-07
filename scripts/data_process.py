import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

df_invoices = pd.read_csv(RAW_DIR / "invoices_2025_clean.csv")
df_vendors = pd.read_csv(RAW_DIR / "vendor_master.csv")
df_ECB = pd.read_csv(RAW_DIR / "ECB_Data.csv")

# Merge invoices and vendors dataframes
df_merged = df_invoices.merge(
    df_vendors[['vendor_id', 'country', 'category', 'status']].rename(
        columns={
            'country': 'vendor_country',
            'category': 'vendor_category',
            'status': 'vendor_status'
        }
    ),
    on='vendor_id',
    how='left'
)

# Set datetime format
df_merged['invoice_date'] = pd.to_datetime(df_merged['invoice_date'])
df_ECB['DATE'] = pd.to_datetime(df_ECB['DATE'])

# Merge invoices/vendors and ECB dataframes
df_aux = df_merged.merge(df_ECB[['DATE', 'GBP/EUR', 'USD/EUR']], left_on='invoice_date', right_on='DATE', how='left')
df_merged['EUR_amount'] = df_aux.apply(
    lambda row: row['amount'] if row['currency'] == 'EUR'
    else (row['amount'] / row['GBP/EUR'] if row['currency'] == 'GBP'
    else (row['amount'] / row['USD/EUR'] if row['currency'] == 'USD' else None)),
    axis=1
).round(2)

# ---------------------------------------------------------
# ADD NEW FEATURES
# ---------------------------------------------------------

# Approver roles
bounds = [-np.inf, 5000, 50000, 250000, np.inf]
approvers = [
    'Cost Center Owner',
    'Department Head',
    'Finance Director',
    'CFO + Procurement Excellence'
]
df_merged['required_approver'] = pd.cut(df_merged['EUR_amount'], bins=bounds, labels=approvers)

# PO features
df_merged['requires_po'] = df_merged['EUR_amount']>= 1000
df_merged['missing_po'] = df_merged['po_number'].isna()
df_merged['maverick_spend'] = df_merged['requires_po'] & df_merged['missing_po']

# Other alerts
df_merged['requires_PE_escalation'] = df_merged['vendor_status']!='ACTIVE'
df_merged['missing_approver'] = df_merged['approved_by'].isna()
df_merged['credit_note'] = df_merged['EUR_amount']<0

# Time features
df_merged['invoice_quarter'] = 'Q' + df_merged['invoice_date'].dt.quarter.astype(str)
df_merged['invoice_week'] = 'W' + df_merged['invoice_date'].dt.isocalendar().week.astype(str)
df_merged['invoice_month'] = df_merged['invoice_date'].dt.strftime('%B')
df_merged['invoice_day_of_month'] = df_merged['invoice_date'].dt.day
df_merged['invoice_day_of_week'] = df_merged['invoice_date'].dt.strftime('%A')
df_merged['invoice_on_weekend'] = df_merged['invoice_date'].dt.day_of_week >= 5

# Reorder columns
column_order = ['invoice_number', 'invoice_date', 'invoice_quarter', 'invoice_week', 'invoice_month',
       'invoice_day_of_month', 'invoice_day_of_week', 'invoice_on_weekend', 'vendor_id', 'vendor_name',
       'vendor_country', 'vendor_category', 'vendor_status', 'description', 'amount', 'currency', 'EUR_amount',
       'credit_note', 'cost_center', 'po_number', 'approved_by', 'missing_approver', 'required_approver',
       'requires_po', 'missing_po', 'maverick_spend', 'requires_PE_escalation']
df_merged = df_merged[column_order]

df_merged.to_csv(PROCESSED_DIR / "enriched_invoices_2025.csv", index=False)