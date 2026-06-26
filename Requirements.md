# Dependencies

Install all dependencies with:

```bash
pip install -r requirements.txt
```

---

## Core

| Package | Version | Purpose |
|---|---|---|
| `pydantic` | >=2.0 | Data validation and schemas |
| `python-dotenv` | >=1.0 | Load API keys from `.env` file |

---

## Phase 2 — Windows Scanning

> Windows only. Requires admin privileges.

| Package | Version | Purpose |
|---|---|---|
| `pywin32` | >=306 | Read Windows Security Event Logs |
| `ldap3` | >=2.9 | Query Active Directory via LDAP |

---

## Phase 3, 5, 6 — LLM and Agentic Workflow

| Package | Version | Purpose |
|---|---|---|
| `openai` | >=1.30 | GPT-4 control mapping and narrative generation |
| `langchain` | >=0.2 | Agentic orchestration framework |
| `langchain-openai` | >=0.1 | LangChain and OpenAI integration |
| `langchain-community` | >=0.2 | Community tools and agent utilities |

---

## Phase 6 — PDF Report Generation

| Package | Version | Purpose |
|---|---|---|
| `reportlab` | >=4.0 | Generate structured PDF intelligence reports |

---

## Utilities

| Package | Version | Purpose |
|---|---|---|
| `tabulate` | >=0.9 | Pretty-print tables in the terminal |
| `rich` | >=13.0 | Colored terminal output and progress bars |

> `sqlite3` is part of the Python standard library — no install needed.

---

## Testing

| Package | Version | Purpose |
|---|---|---|
| `pytest` | >=8.0 | Test runner |
| `pytest-mock` | >=3.12 | Mocking utilities for unit tests |
