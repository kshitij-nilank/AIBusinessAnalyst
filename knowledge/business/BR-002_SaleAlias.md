Rule ID: BR-002
Name: SaleAlias
Category: Reporting
Priority: High
Business Owner: Business Team
Technical Owner: AI Business Analyst
Applies To:
  - Weekly Reports
  - Monthly Reports
  - Ad-hoc Reports
Version: 1.0
Status: Approved
Last Reviewed: 2026-07-04

## Rule Name

SaleAlias Validation (SaleAlias)

---

### Business Purpose

The SaleAlias rule converts auction sales from Sale 1–13 into Sale 54–66.

This creates a continuous auction sequence (14–66), allowing stakeholders to analyse an entire production season without the sale numbering restarting.

It is primarily used to sort the teas from sale 14 to 13 so that stakeholders receive consistent and accurate analysis.

---

### Business Definition

SaleAlias is a virtual reporting field.

It does not exist in the source database.

It is created during reporting to maintain a continuous sale sequence.



---

### Why It Exists

Tea auctions begin from Sale 14 every production season.

When the auction calendar reaches the end of the financial year, sale numbers restart from 1.

For reporting purposes, restarting the numbering makes year-long trend analysis difficult.

SaleAlias converts Sale 1–13 into Sale 54–66 so that analysts can compare an entire season continuously.

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
IF(
    SaleNo BETWEEN 1 AND 13,
    53 + SaleNo,
    SaleNo
) AS SaleAlias
```

Most reports should exclude invalid records using:

```sql
HAVING SaleAlies >= 1
```

---

### Edge Cases

The standard rule should NOT be applied when the stakeholder specifically requests:

- Calendar Year tea analysis
- Comparison with South India data

Applying the default filter in these scenarios will produce incorrect results.

---

### Validation Rules

Before generating SQL, the AI should verify the reporting requirement.

If the request is unclear, ask:

- From which sale no should the report start?
- Should Calendar Year is considered?


Never assume the answer.

---

### AI Guidance

Whenever a stakeholder requests a sale-wise report,
the AI should automatically use SaleAlias unless the stakeholder explicitly requests:

- Calendar Year
- Original Sale Numbers
- South India comparison

If unsure, ask a clarification question.

---

### Examples

#### Example 1 — Standard Report

Requirement

> Compare Sale wise Sold Quantity for Season 2026.

Result

Apply the SaleAlies rule.

SQL should contain:

```sql
where if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) AS SaleAlies
```

---

#### Example 2 — Historical Comparison

Requirement

> Compare sale wise this year vs last year

Result

Do NOT automatically apply:

```sql
where if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) AS SaleAlies
```

Instead, ask the stakeholder whether it is financial year or calendar year before generating the SQL.