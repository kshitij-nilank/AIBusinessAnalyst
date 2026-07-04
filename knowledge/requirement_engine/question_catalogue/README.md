# Requirement Understanding Engine

## Purpose

The Requirement Understanding Engine is responsible for helping the AI Business Analyst understand stakeholder requirements before generating SQL.

Its primary responsibility is to identify missing information, ask clarification questions, and determine whether enough business context is available to proceed.

The engine must never generate SQL until all mandatory information has been collected.

---

# Objective

Convert an ambiguous stakeholder request into a complete, validated business requirement.

Example

Stakeholder Request

> Need Garden-wise Report.

↓

Requirement Understanding

- Season?
- Sale Range?
- Area?
- Category?
- EST / BLF?
- Tea Type?
- Output Required?

↓

Validated Requirement

↓

SQL Generation

---

# Design Principles

The engine should:

- Think like a Senior Business Analyst.
- Never assume missing information.
- Ask only relevant questions.
- Avoid unnecessary questions.
- Reuse previous answers whenever possible.
- Follow Parcon business rules.

---

# Workflow

```
Receive Requirement
        │
        ▼
Identify Report Type
        │
        ▼
Identify Missing Information
        │
        ▼
Ask Clarification Questions
        │
        ▼
Validate Business Rules
        │
        ▼
Generate Structured Requirement
        │
        ▼
Pass to SQL Generator
```

---

# Folder Structure

```
requirement_engine/

README.md

Q001_Season.md

Q002_SaleRange.md

Q003_Area.md

Q004_Category.md

Q005_EstBlf.md

Q006_TeaType.md

Q007_OutputColumns.md

Q008_ReportType.md

Q009_Garden.md

Q010_Buyer.md
```

---

# Naming Convention

Every requirement question should follow:

```
Q###_<QuestionName>.md
```

Example

```
Q001_Season.md

Q002_SaleRange.md

Q003_Area.md
```

---

# Standard Question Template

Every question should contain:

- Question ID
- Business Purpose
- Why It Exists
- Expected Answer Type
- Allowed Values
- Mandatory
- Applicable Reports
- Follow-up Questions
- AI Guidance
- Examples

---

# Definition of Done

A requirement is considered complete when:

- All mandatory questions have been answered.
- Business rules have been identified.
- Required filters are available.
- No ambiguity remains.
- SQL generation can begin without assumptions.

---

# Current Status

Status: MVP

Version: 1.0

Owner: AI Business Analyst Project

Last Updated: 2026-07-05