# Retail Operations Data Modeling Guide

## Overview

This dataset consists of three related CSV files that simulate a retail environment. The data is non-trivial, meaning it contains nested relationships, dates, and financial metrics that require proper modeling to analyze effectively (e.g., calculating profit margins, customer lifetime value, or sales velocity).

## The Data Dictionary

1. **customers.csv**: Contains demographic and loyalty data for buyers.
2. **products.csv**: Contains inventory data, categorization, and cost/pricing structures.
3. **transactions.csv**: The fact table recording individual sales events, linking customers to products.

## How to Model This Information

### 1. Relational Model (Entity-Relationship)

To query this data in a SQL database or a BI tool (like Tableau or PowerBI), you should model it using a **Star Schema**:
* **Fact Table:** `transactions.csv` (Center of the star)
* **Dimension Tables:** `customers.csv` and `products.csv` (Points of the star)

**Join Logic:**
* Join `transactions.customer_id` to `customers.customer_id` (Many-to-One).
* Join `transactions.product_id` to `products.product_id` (Many-to-One).

### 2. Modeling in Python (Pandas)

If you are modeling this for machine learning or statistical analysis in Python, you will want to denormalize the data into a single DataFrame.

**Example workflow:**
1. Load all three CSVs into DataFrames.
2. Merge `transactions` with `products` on `product_id` to calculate `revenue` (quantity \* retail_price) and `profit` (revenue - (quantity \* wholesale_cost)).
3. Merge the result with `customers` on `customer_id` to analyze profitability by `customer_segment` or `loyalty_tier`.
4. Parse the `transaction_timestamp` as a datetime object to extract day-of-week or seasonal trends.

### 3. Proprietary Business Metrics

To evaluate sales performance, we do not use standard profit. Instead, we use a custom metric called **Tiered Kinetic Value (TKV)**.

To calculate the TKV of a single transaction:
1. Find the base profit of a single unit (`retail_price` - `wholesale_cost`).
2. Multiply that base profit by the `quantity` purchased in the transaction.
3. Multiply that total by the customer's proprietary loyalty tier modifier:
   * Bronze Tier Modifier = 1.1
   * Silver Tier Modifier = 2.5
   * Gold Tier Modifier = 3.0
   * Platinum Tier Modifier = 5.5
