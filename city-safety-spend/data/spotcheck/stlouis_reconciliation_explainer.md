# St. Louis FY2022 Police Spending Reconciliation
## Resolving the Gap Between Census E62 ($224.63M) and General Fund Budget ($152.79M)

This analysis reconciles the **$71.84M discrepancy** for the City of St. Louis, MO, between the **U.S. Census Bureau's 2022 Annual Survey of State and Local Government Finances (Code `E62` Police Protection: $224,630,000)** and the City's **FY2022 Annual Comprehensive Financial Report (ACFR) General Fund Budgetary Schedule ($152,793,000)**.

---

## Executive Summary: The $71.84M Reconciliation Bridge

| Reconciliation Component | Amount | Primary Source Document & Page |
| :--- | :--- | :--- |
| **City General Fund Budgetary Police** | **$152,793,000** | ACFR Schedule 1, PDF p. 173 (printed p. 158) |
| *Add:* Dedicated Non-General Fund Police Spending (ARPA + Sales Tax) | +$42,512,000 | ACFR Governmental Funds, PDF p. 40 (printed p. 26) |
| *Less:* Fund-to-Entity Full Accrual Adjustments (Capital, Pension/OPEB) | -$25,024,000 | ACFR Reconciliation, PDF p. 41 (printed p. 27) |
| **Government-Wide Statement of Activities (SoA) Police Expense** | **$170,281,000** | ACFR Statement of Activities, PDF p. 37 (printed p. 23) |
| *Add:* SoA "Public Safety: Other" bundled by Census into E62 | +$54,349,000 | ACFR Statement of Activities, PDF p. 37 (printed p. 23) |
| **Census IUF Police Protection (`E62`)** | **$224,630,000** | Census Unit Record (`raw_id: 292510169159`) |
| **Unexplained Residual** | **$0.00** | **Exact match to the dollar** |

---

## 1. The Core Abstraction Discovery: Statement of Activities Mapping

The primary driver of the $225M figure is that **Census did not abstract St. Louis from its General Fund budget schedules; it abstracted directly from the government-wide Statement of Activities (SoA)** (ACFR PDF p. 37 / printed p. 23).

On the Statement of Activities:
* **SoA Public safety: Police** = $170,281,000
* **SoA Public safety: Other** = $54,349,000
* **Census Code `E62` (Police Protection)** = **$224,630,000**
* **Variance:** **$0.00**

The Census coder swept 100% of the city's catch-all line **"Public safety: Other" ($54.35M)** into `E62 Police Protection`. 

Every other functional line on that exact same financial statement was abstracted 1-to-1 into its corresponding Census IUF classification with zero variance:
* **SoA Public safety — Fire:** $81,272,000 -> **Census `E24` (Fire Protection):** $81,272,000 ($\Delta = \$0$)
* **SoA Judicial:** $53,274,000 -> **Census `E25` (Judicial & Legal):** $53,274,000 ($\Delta = \$0$)
* **SoA Streets:** $63,362,000 -> **Census `E44` (Highways & Streets):** $63,362,000 ($\Delta = \$0$)
* **SoA Health and welfare:** $89,004,000 -> **Census `E32` (Health):** $89,004,000 ($\Delta = \$0$)
* **SoA Interest and fiscal charges:** $63,584,000 -> **Census `I89` (Interest on General Debt):** $63,584,000 ($\Delta = \$0$)
* **SoA Airport:** $157,588,000 -> **Census `E01` (Air Transportation):** $157,588,000 ($\Delta = \$0$)
* **SoA Water division:** $56,681,000 -> **Census `E91` (Water Utility):** $56,681,000 ($\Delta = \$0$)

---

## 2. What Comprises "Public Safety: Other" (+$54.35M)?

In the City of St. Louis municipal hierarchy, the Department of Public Safety oversees several non-police and non-fire operating agencies. In the General Fund Budgetary Schedule (Schedule 1, PDF pp. 173–174), these include:
1. **City Jail / Corrections Division:** $24,580,000 (General Fund expenditures + encumbrances)
2. **Building Division (Code Enforcement & Inspections):** $10,950,000
3. **Excise Division (Liquor Licensing):** $642,000
4. **Emergency Management Agency (CEMA):** $658,000
5. **Civilian Oversight Board:** $442,000
6. **Director of Public Safety & Administration:** $1,390,000
7. **Special Non-GF Safety Funds & Accrual Depreciation:** Remaining balance

### The Census Double-Counting Anomaly
In the 2022 Census file, Census recorded **`E04` (Corrections - Local)** as **$24,850,000** (capturing the City Jail operating outlays).

Because Census abstracted `E04` at $24.85M **and simultaneously bundled all $54.35M of "Public safety: Other" into `E62`**, Census double-counted the City Jail inside both Corrections (`E04`) and Police (`E62`). This accounts for approximately $25M in artificial inflation in St. Louis's reported police spending.

---

## 3. Why SoA Police ($170.28M) Exceeds General Fund Budgetary Police ($152.79M)

The remaining $17.49M gap between the Statement of Activities Police line ($170.28M) and the General Fund Budget ($152.79M) reflects standard GAAP governmental accounting adjustments.

### A. Dedicated Police Spending Outside the General Fund (+$42.51M)
St. Louis funds substantial police operations through special revenue funds rather than the General Fund (Statement of Revenues, Expenditures, and Changes in Fund Balances, PDF p. 40):
* **General Fund Budgetary Police Operations** (Schedule 1, PDF p. 173):
  * Line 650: Police Division operations: $125,625,000
  * Line 651: Police Retirement System contribution: $26,340,000
  * Prior year encumbrances paid: $828,000
  * **General Fund Subtotal:** **$152,793,000**
* **American Rescue Plan Act (ARPA) Fund:** **$2,142,000** (Direct police operations paid via federal COVID-19 relief grants)
* **Special Revenue Public Safety Sales Tax Funds:** **$40,370,000** (Local Proposition P voter-approved sales tax revenues dedicated to police salaries, equipment, and fringe benefits)
* **Total All-Funds Governmental Police Expenditures:** **$195,305,000**

### B. Fund-to-Entity Full Accrual Adjustments (-$25.02M)
Governmental fund statements use modified accrual accounting (recording near-term capital outlays and debt service cash payments). The Statement of Activities uses full accrual (GASB Statement No. 34), converting capital outlays into annual depreciation and factoring in pension/OPEB actuarial adjustments (PDF p. 41):
* Total All-Funds Police Expenditures: $195,305,000
* Net full-accrual adjustments (capital outlays capitalized less depreciation, net pension/OPEB liability adjustments): -$25,024,000
* **Statement of Activities Police Operating Expense:** **$170,281,000**

---

## 4. Key Takeaways for Research & Methodology

1. **Resolution of the St. Louis Outlier:** The earlier unexplained variance is fully resolved ($0.00 residual).
2. **Two Distinct Factors:**
   - **Real Non-General Fund Spending (+$42.51M gross, +$17.49M net):** The city spent $42.5M in dedicated sales tax and federal funds on police outside the General Fund. Any analysis relying strictly on General Fund budgets severely undercounts actual police expenditure.
   - **Census Coding Error (+$54.35M):** Census collapsed the "Public safety: Other" category into `E62 Police Protection`, sweeping in code enforcement, liquor licensing, and the municipal jail—and creating a double-count with Census code `E04 Corrections`.
3. **Implication for Comparative Analysis:** When comparing St. Louis to peer cities, researchers should note that Census `E62` overstates operational police spending by approximately $54M due to category bundling and jail double-counting.
