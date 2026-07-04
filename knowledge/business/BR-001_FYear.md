Rule ID: BR-001
Category: Financial Year
Priority: High
Status: Approved
Owner: Business Team
Last Reviewed: 2026-07-04

## Rule Name

Financial Year Validation (FYear)

---

### Business Purpose

The FYear rule ensures that only tea belonging to the correct production season is included in reports.

It is primarily used to separate current-season teas from old-season teas so that stakeholders receive consistent and accurate analysis.

---

### Business Definition

FYear is a derived field calculated from the Financial Year (`FinYear`) and the Production Season (`Season`).

If the starting year of the Financial Year matches the Production Season, the record is considered a valid current-season record.

Otherwise, the record is treated as an old-season or invalid record.

---

### Why It Exists

Tea auctions may contain both current-season and old-season teas.

Most business reports are intended to analyse only the current production season.

Without this validation, reports may accidentally mix teas from different production seasons, leading to incorrect business insights.

---

### Reports Using It

This rule is used in almost all operational reports, including:

- Garden Analysis
- Buyer Analysis
- Seller Analysis
- Weekly Reports
- Monthly Reports
- Annual Reports
- Ad-hoc Reports
- Price Trend Analysis
- Batting Order Reports

Unless explicitly requested otherwise, this rule should always be applied.

---

### Stakeholders

Primary Users

- Business Analysts
- PD Sir
- Marketing Team
- Management

Secondary Users

- Developers
- Product Team
- Reporting Team
- EDP Team

---

### SQL Implementation

```sql
CASE
    WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season
    THEN Season
    ELSE 0
END AS FYear
```

Most reports should exclude invalid records using:

```sql
HAVING FYear <> 0
```

---

### Edge Cases

The standard rule should NOT be applied when the stakeholder specifically requests:

- Old-season tea analysis
- Mixed-season analysis
- Comparison between current and old seasons
- Historical trend reports across multiple seasons

Applying the default filter in these scenarios will produce incorrect results.

---

### Validation Rules

Before generating SQL, the AI should verify the reporting requirement.

If the request is unclear, ask:

- Should the report include only current-season teas?
- Should old-season teas also be included?
- Is this a historical comparison report?

Never assume the answer.

---

### AI Guidance

Default Behaviour

- Apply the FYear rule.
- Exclude records where `FYear = 0`.
- Treat the report as current-season analysis.

Exception

If the stakeholder explicitly requests old-season or mixed-season data, do not apply the standard filter until confirmation is received.

The AI should always prefer asking a clarification question instead of making assumptions.

---

### Examples

#### Example 1 — Standard Report

Requirement

> Compare Garden-wise Sold Quantity for Season 2026.

Result

Apply the FYear rule.

SQL should contain:

```sql
HAVING FYear <> 0
```

---

#### Example 2 — Historical Comparison

Requirement

> Compare current-season and old-season teas.

Result

Do NOT automatically apply:

```sql
HAVING FYear <> 0
```

Instead, ask the stakeholder whether both seasons should be included before generating the SQL.