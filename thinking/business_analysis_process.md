# Business Analysis Process

## Objective

Transform an incomplete stakeholder request into a complete business requirement before SQL generation.

---

## Step 1 – Understand the Requirement

Read the stakeholder request completely.

Identify:

- Report Type
- Stakeholder
- Business Objective

Do not think about SQL yet.

---

## Step 2 – Identify Missing Information

Determine whether the request contains:

- Season
- Sale Range
- Area
- Category
- Tea Type
- EST/BLF
- Required Output

If any mandatory information is missing, do not continue.

---

## Step 3 – Ask Clarification Questions

Use the Requirement Engine.

Ask only the questions necessary to complete the requirement.

Do not ask irrelevant questions.

---

## Step 4 – Identify Applicable Business Rules

Determine which business rules apply.

Examples:

- FYear
- SaleAlias
- AreaAlias

---

## Step 5 – Identify Database Objects

Determine:

- Tables
- Views
- Required Columns
- Required Joins

---

## Step 6 – Validate Requirement

Ensure:

- No ambiguity remains.
- Business rules are understood.
- SQL can be generated safely.

---

## Step 7 – Pass to SQL Generator

Only now should SQL generation begin.