# Product Requirements Document (PRD)

# Product Name

AI Business Analyst

Version: 1.0

Author: Kshitij Nilank

Status: Draft

---

# 1. Vision

Develop an AI-powered Business Analyst that understands Parcon's business, reporting ecosystem, database, and stakeholder requirements.

The AI should think like an experienced Business Analyst instead of functioning as a generic SQL generator.

Its primary objective is to convert business requirements into technically correct and optimized BigQuery SQL while following Parcon's reporting standards.

---

# 2. Problem Statement

Business Analysts repeatedly perform similar activities:

- Understanding stakeholder requirements
- Identifying missing information
- Writing SQL
- Reviewing SQL
- Explaining SQL
- Modifying existing reports
- Creating ad-hoc reports

The knowledge required to perform these tasks is currently distributed across:

- SQL files
- Excel reports
- Emails
- Personal experience
- Documentation
- Team discussions

When experienced analysts leave the organization, a significant amount of business knowledge is lost.

---

# 3. Goal

Create an AI assistant capable of understanding Parcon's business domain and acting as a Business Analyst.

The assistant should reduce the time required to understand requirements and generate SQL while maintaining reporting standards.

---

# 4. Target Users

Primary Users

- Business Analysts

Secondary Users

- Product Managers
- Developers
- New Employees
- Reporting Team

---

# 5. Out of Scope (Version 1)

The following are intentionally excluded from the MVP:

- Running SQL queries
- Editing production databases
- Sending emails
- Dashboard creation
- Python automation
- Power BI automation
- Looker Studio automation
- Excel formatting

The focus is understanding and SQL generation.

---

# 6. Success Criteria

The AI should be able to:

✔ Understand business terminology

✔ Understand stakeholder intent

✔ Ask clarifying questions

✔ Generate optimized BigQuery SQL

✔ Explain generated SQL

✔ Review SQL

✔ Suggest improvements

---

# 7. Functional Requirements

## Requirement Understanding

The AI should identify:

- Missing filters
- Missing season
- Missing sale range
- Missing area
- Missing output format

before generating SQL.

---

## Business Understanding

The AI should understand:

- Tea auction terminology
- Business entities
- Reporting standards
- Stakeholder preferences

---

## SQL Generation

Generate production-quality BigQuery SQL.

Requirements:

- Readable
- Modular
- Optimized
- Documented

---

## SQL Review

Review SQL for:

- Performance
- Readability
- Correctness
- Business logic
- Best practices

---

## Documentation

Generate explanations for every SQL query.

---

# 8. Non-Functional Requirements

Performance

- SQL generation under 30 seconds

Maintainability

- Knowledge stored in Markdown

Scalability

- Support future reports

Reliability

- Avoid hallucinations

---

# 9. MVP Features

Version 1

- Knowledge Base
- Requirement Understanding
- SQL Generator
- SQL Reviewer

---

# 10. Knowledge Sources

The AI should learn from:

- Existing SQL
- Existing reports
- Business documentation
- Database schema
- Business rules

---

# 11. Future Versions

Version 2

- Python generation

Version 3

- Excel automation

Version 4

- Dashboard generation

Version 5

- Workflow automation

Version 6

- Multi-agent architecture

---

# 12. Risks

Potential risks:

- Outdated documentation
- Incorrect business rules
- Ambiguous stakeholder requests
- Large SQL codebase

Mitigation:

- Version-controlled knowledge base
- Continuous updates