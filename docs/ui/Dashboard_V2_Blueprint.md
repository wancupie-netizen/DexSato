# DexSato Dashboard V2 Blueprint

Version: 1.0

Status: Architecture Locked

---

# Objective

Dashboard V2 represents the primary interface of DexSato.

The dashboard must:

- communicate market intelligence clearly
- expose adaptive learning history
- explain WHY a decision exists
- minimise cognitive load
- remain presentation-only

The dashboard MUST NOT:

- perform calculations
- query databases
- build intelligence
- perform adaptive learning

---

# Design Principles

1. One screen.
2. One token.
3. One decision.
4. Everything explainable.

---

# Layout

+------------------------------------------------------+
| Header                                               |
+------------------------------------------------------+

+----------------------+------------------------------+
| Decision Card        | Historical Intelligence      |
+----------------------+------------------------------+

+------------------------------------------------------+
| AI Analyst Summary                                  |
+------------------------------------------------------+

+----------------------+------------------------------+
| Evidence             | Market DNA                  |
+----------------------+------------------------------+

+------------------------------------------------------+
| Learning Timeline                                   |
+------------------------------------------------------+

---

# Component Tree

Dashboard

├── Header

├── Decision Card

├── Historical Panel

├── AI Summary

├── Evidence Panel

├── Market DNA

└── Timeline

---

# Component Responsibilities

Header

Shows:

- Token
- Last Updated
- Engine Version

Decision Card

Shows:

- Decision
- Confidence
- Confidence Level

Historical Panel

Shows:

- Seen Before
- Historical Success
- Sample Size

AI Summary

Shows:

- Decision explanation

Evidence

Shows:

- Supporting reasons

Market DNA

Shows:

- Interpretations
- Signals
- Behaviour profile

Timeline

Shows:

- Previous adaptive experiences

---

# Presentation Rules

Every component receives immutable data.

Components never mutate DashboardCard.

Components never access repositories.

Components never call services.

---

# Colour Language

WATCH

Blue

BUY

Green

SELL

Red

UNKNOWN

Grey

---

# Adaptive Language

Seen Before

YES / NO

Historical Success

Percentage

Sample Size

Number

---

# Future Expansion

Dashboard V3 may add:

- Risk Panel

- Multi-timeframe

- Confidence Breakdown

- AI Conversation

without changing the existing layout.