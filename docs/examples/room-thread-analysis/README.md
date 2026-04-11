# Room + Thread Analysis Example

This example demonstrates how the **bwrap_sandbox** room uses mounted
files from both the room level and the thread level to answer
questions that require combining documentation with data.

## Files

| File | Upload to | Purpose |
|------|-----------|---------|
| `model.md` | **Room** uploads | Business rules, data dictionary, and the TKV formula |
| `customers.csv` | **Thread** uploads | Customer demographics and loyalty tiers |
| `products.csv` | **Thread** uploads | Product catalog with wholesale/retail pricing |
| `transactions.csv` | **Thread** uploads | Individual sales transactions |

## Setup

1. Start the server with the `bwrap_sandbox` room enabled.
2. Upload `model.md` as a **room-level** file (shared across all
   threads in the room).
3. Create a new thread and upload the three CSV files as
   **thread-level** files.

## Test Prompt

Ask the following question:

> Calculate the total Tiered Kinetic Value (TKV) for transaction
> TXN-90004. Show your step-by-step work based strictly on the
> provided documentation.

## Expected Reasoning

The agent should:

1. **Read `model.md`** from `/sandbox/volumes/room/` to find the
   TKV formula and tier modifiers.
2. **Look up TXN-90004** in `transactions.csv`:
   - Customer: `C-1002`
   - Product: `P-501`
   - Quantity: `4`
3. **Look up P-501** in `products.csv`:
   - `retail_price`: $199.99
   - `wholesale_cost`: $85.00
4. **Compute unit profit**: $199.99 - $85.00 = **$114.99**
5. **Compute base profit**: $114.99 * 4 = **$459.96**
6. **Look up C-1002** in `customers.csv`:
   - Name: Marcus Chen
   - Loyalty tier: Silver
7. **Apply tier modifier** from `model.md`:
   - Silver Tier Modifier = **2.5**
8. **Final TKV**: $459.96 * 2.5 = **$1,149.90**

## Expected Answer

```
1149.90
```
