# AI-Powered Security Control Analyzer

> An autonomous, production-grade AI application that scans enterprise security configurations, maps findings to NIST SP 800-53 compliance controls, performs gap analysis, and generates structured intelligence reports — end to end, with an agentic workflow layer.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![NIST SP 800-53](https://img.shields.io/badge/NIST-SP%20800--53%20Rev%205-green)](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
[![LangChain](https://img.shields.io/badge/LangChain-Agentic-orange)](https://www.langchain.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Phases](#project-phases)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Sample Output](#sample-output)
- [Roadmap](#roadmap)
- [Author](#author)

---

## Overview

The **AI-Powered Security Control Analyzer** is a portfolio-grade, multi-phase Python application built to demonstrate production-level thinking in applied AI, cybersecurity automation, and compliance engineering.

The system autonomously:

1. **Scans** Windows Event Logs and Active Directory configurations for security findings
2. **Maps** each finding to NIST SP 800-53 Rev 5 controls using an LLM reasoning engine (GPT-4)
3. **Analyzes** compliance gaps, flags missing controls, and computes risk scores
4. **Orchestrates** all of the above using an agentic AI pipeline (LangChain agents)
5. **Reports** findings as structured JSON and a formatted PDF for both technical and non-technical audiences

This project mirrors real-world enterprise GRC workflows and is designed to be extensible to other frameworks (ISO 27001, SOC 2, HIPAA) and additional data sources.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agentic Orchestration Layer                   │
│              (LangChain — Phase 5: Agent Controller)            │
└─────────┬──────────────┬──────────────┬──────────────┬──────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
   ┌─────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐
   │  Phase 1    │ │ Phase 2  │ │   Phase 3    │ │   Phase 4    │
   │ NIST Parser │ │ Scanner  │ │ LLM Control  │ │    Gap       │
   │ SQLite FTS5 │ │ Win Logs │ │   Mapper     │ │  Analyzer    │
   │  Database   │ │ AD Config│ │  GPT-4 +     │ │ Risk Scorer  │
   └─────────────┘ └──────────┘ │  Confidence  │ └──────────────┘
                                └──────────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │        Phase 6         │
                            │   Report Generator     │
                            │  JSON + PDF (ReportLab)│
                            └───────────────────────┘
```

---

## Project Phases

### ✅ Phase 1 — NIST Control Database
**Status: Complete**

- Downloads the official NIST SP 800-53 Rev 5 OSCAL JSON from NIST GitHub
- Parses the full control catalog (1000+ controls and enhancements)
- Stores everything in SQLite with FTS5 full-text search
- Exposes a `ControlDatabase` class used by all downstream phases
- Supports lookup by control ID, family code, and keyword search

```
phase1/
└── nist_parser.py       # Downloader, OSCAL parser, ControlDatabase class
```

---

### 🔧 Phase 2 — Windows Security Scanner
**Status: In Progress**

- Reads Windows Security Event Logs using the `pywin32` library
- Queries Active Directory configurations via LDAP (`ldap3`)
- Extracts structured security findings as normalized JSON
- Covers: failed logons (4625), privilege escalation (4672), policy changes (4719), account lockouts (4740), password policy, and AD group memberships

```
phase2/
├── event_log_scanner.py   # Windows Event Log reader
├── ad_scanner.py          # Active Directory LDAP scanner
└── finding_schema.py      # Pydantic finding data model
```

---

### 🔧 Phase 3 — LLM-Powered Control Mapper
**Status: Planned**

- Takes structured findings from Phase 2 as input
- Uses GPT-4 to reason over each finding and identify the most relevant NIST SP 800-53 control IDs
- Returns confidence scores (0.0–1.0) and natural-language rationale for each mapping
- Prompts are structured and reproducible for evaluation
- Lookups are cached against the Phase 1 SQLite database to avoid redundant API calls

```
phase3/
├── control_mapper.py      # GPT-4 mapping engine
├── prompt_templates.py    # Structured prompts
└── cache_layer.py         # SQLite-backed response cache
```

---

### 🔧 Phase 4 — Compliance Gap Analyzer
**Status: Planned**

- Compares LLM-mapped findings against a defined required-control baseline
- Flags controls with no evidence, insufficient evidence, or conflicting findings
- Computes a risk score per gap using a CVSS-aligned methodology (impact × likelihood)
- Outputs a structured gap report as JSON

```
phase4/
├── gap_analyzer.py        # Gap detection logic
├── risk_scorer.py         # CVSS-aligned risk scoring
└── baseline_profiles.py   # NIST Low/Moderate/High baseline definitions
```

---

### 🔧 Phase 5 — Agentic Workflow Layer
**Status: Planned**

- Builds a LangChain multi-agent pipeline that autonomously orchestrates Phases 2–4
- Agents: ScannerAgent, MapperAgent, GapAnalyzerAgent, OrchestratorAgent
- Agents communicate over a shared state object; each has tool access to the appropriate phase module
- The OrchestratorAgent decides sequencing, retries on failure, and writes results to disk
- Designed to run end to end without manual intervention

```
phase5/
├── orchestrator.py        # Master agent controller
├── scanner_agent.py       # Agent wrapper for Phase 2
├── mapper_agent.py        # Agent wrapper for Phase 3
└── gap_agent.py           # Agent wrapper for Phase 4
```

> **Why this matters:** Phase 5 mirrors how modern autonomous compliance platforms operate — continuous, unattended scanning and mapping at enterprise scale. This is the production-grade pattern used in AI-powered GRC and security operations tools.

---

### 🔧 Phase 6 — Structured Intelligence Report Generator
**Status: Planned**

- Consumes the gap analysis JSON from Phase 4
- Uses GPT-4 to write professional audit narratives for each gap (risk, impact, remediation)
- Generates a structured JSON report for machine consumers
- Generates a formatted PDF report for human stakeholders using ReportLab
- PDF sections: Executive Summary, Control Status Table, Gap Analysis, Risk Heat Map, Remediation Roadmap

```
phase6/
├── report_generator.py    # Orchestrates JSON + PDF generation
├── narrative_writer.py    # GPT-4 narrative generation
├── pdf_builder.py         # ReportLab PDF layout engine
└── templates/             # PDF layout templates
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Compliance Data | NIST SP 800-53 Rev 5 OSCAL JSON (public domain) |
| Database | SQLite with FTS5 full-text search |
| LLM Reasoning | OpenAI GPT-4 (`openai` SDK) |
| Agentic Framework | LangChain |
| Windows Scanning | `pywin32`, `ldap3` |
| PDF Generation | ReportLab |
| Data Validation | Pydantic |
| Version Control | Git / GitHub |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Windows 10/11 or Windows Server (for Phase 2 live scanning; mock mode available on all platforms)
- An OpenAI API key (for Phases 3 and 6)

### Installation

```bash
# Clone the repository
git clone https://github.com/Sreenidhi15/ai-security-control-analyzer.git
cd ai-security-control-analyzer

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
set OPENAI_API_KEY=sk-...     # Windows CMD
# export OPENAI_API_KEY=sk-... # macOS/Linux
```

### Phase 1 — Build the Control Database

```bash
# Download NIST SP 800-53 JSON and build the SQLite database
python phase1/nist_parser.py --refresh

# Look up a specific control
python phase1/nist_parser.py --lookup AC-2

# Search controls by keyword
python phase1/nist_parser.py --search "account management"

# List all control families
python phase1/nist_parser.py --family AC
```

---

## Usage

### Run the Full Pipeline (Phase 5 Agentic Mode)

```bash
# Once Phase 5 is complete — runs the full autonomous pipeline
python phase5/orchestrator.py --mode full --output reports/
```

### Run Individual Phases

```bash
# Phase 2: Scan Windows Event Logs (requires Windows + admin rights)
python phase2/event_log_scanner.py --hours 24 --output data/findings.json

# Phase 3: Map findings to NIST controls
python phase3/control_mapper.py --input data/findings.json --output data/mapped.json

# Phase 4: Gap analysis and risk scoring
python phase4/gap_analyzer.py --input data/mapped.json --baseline moderate

# Phase 6: Generate report
python phase6/report_generator.py --input data/gaps.json --format both
```

---

## Sample Output

### Finding (Phase 2 Output)
```json
{
  "finding_id": "EVT-4625-001",
  "source": "Windows Security Event Log",
  "event_id": 4625,
  "timestamp": "2025-06-01T03:17:42Z",
  "severity": "HIGH",
  "description": "23 failed logon attempts from 192.168.1.105 within 10 minutes",
  "raw_data": { "account": "svc_backup", "logon_type": 3 }
}
```

### Control Mapping (Phase 3 Output)
```json
{
  "finding_id": "EVT-4625-001",
  "mapped_controls": [
    {
      "control_id": "AC-7",
      "title": "Unsuccessful Logon Attempts",
      "confidence": 0.97,
      "rationale": "The finding directly reflects a violation of AC-7 lockout policy thresholds."
    },
    {
      "control_id": "SI-4",
      "title": "System Monitoring",
      "confidence": 0.81,
      "rationale": "Repeated logon failures should be detected by active monitoring per SI-4."
    }
  ]
}
```

### Gap Report Entry (Phase 4 Output)
```json
{
  "control_id": "AC-7",
  "status": "GAP",
  "evidence": "INSUFFICIENT",
  "risk_score": 8.4,
  "risk_level": "HIGH",
  "finding_ref": "EVT-4625-001",
  "recommendation": "Enforce account lockout after 5 failed attempts per AC-7(a)."
}
```

---

## Roadmap

- [x] Phase 1: NIST SP 800-53 control database with SQLite/FTS5
- [ ] Phase 2: Windows Event Log and AD scanner
- [ ] Phase 3: GPT-4 control mapping with confidence scoring
- [ ] Phase 4: Gap analysis and CVSS-aligned risk scoring
- [ ] Phase 5: LangChain agentic orchestration layer
- [ ] Phase 6: JSON + PDF intelligence report generation
- [ ] Stretch: ISO 27001 dual-mapping support
- [ ] Stretch: CI/CD pipeline with GitHub Actions for automated test runs

---

## Author

**Sreenidhi Ramani**
M.S. Electrical and Computer Engineering — Computer Systems and Software
Northeastern University | Boston, MA

Research Assistant, CactiLab (Prof. Ziming Zhao) — firmware security, embedded systems vulnerability research, fuzzing (LibFuzzer/Boofuzz), SARIF reporting

[GitHub](https://github.com/Sreenidhi15) · [LinkedIn](https://linkedin.com/in/sreenidhi-ramani)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

NIST SP 800-53 data is sourced from the [NIST OSCAL Content Repository](https://github.com/usnistgov/oscal-content) and is in the public domain.
