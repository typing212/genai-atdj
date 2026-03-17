# AT-DJ: Agentic Tango DJ

A LangGraph-based agentic system that acts as an intelligent DJ for Argentine Tango milongas. It plans valid tanda/cortina sequences, adapts dynamically to live feedback, enhances historical audio quality, and answers natural-language queries about the track catalog — all demonstrated through a live Streamlit interface.

> **Status:** Early development — implementation begins Week 1 (3/22/2026).

---

## Project Structure

```
genai_atdj/
├── atdj/               # Main package (agent, audio, RAG, UI, schemas)
├── data/               # Catalog CSV, audio tracks, ChromaDB store
├── notebooks/          # Proof-of-concept and exploration notebooks
├── tests/              # Unit and integration tests
├── doc/                # Blueprint, ideas, knowledge base, course materials
├── main.py             # Entry point: streamlit run main.py
├── pyproject.toml      # Dependencies managed with uv
├── .env.example        # Environment variable template
└── .claude/            # Claude Code configuration (see Developer Guide below)
```

---

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (package manager)
- ffmpeg (for audio processing)
- An LLM API key — Google Gemini (default) or Anthropic Claude (fallback)

---

## Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd genai_atdj

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Fill in your API key(s) in .env

# 4. Run the app
uv run streamlit run main.py
```

---

## Environment Variables

See `.env.example` for all available variables. The key ones:

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | `gemini` (default) \| `claude` \| `ollama` |
| `GOOGLE_API_KEY` | Required if using Gemini |
| `ANTHROPIC_API_KEY` | Required if using Claude |
| `GEMINI_MODEL` | Gemini model ID (default: `gemini-2.0-flash`) |
| `CLAUDE_MODEL` | Claude model ID (default: `claude-sonnet-4-6`) |

> Never commit `.env` — it is gitignored. Only `.env.example` is tracked.

---

## Developer Guide: The `.claude/` Folder

This project uses [Claude Code](https://claude.ai/claude-code) as an AI development assistant. The `.claude/` folder contains project-level configuration that **every team member's Claude Code session will automatically load**.

### What's in `.claude/`

```
.claude/
├── settings.json           # Project hooks (auto-loaded by Claude Code)
├── hooks/
│   └── check_env_access.py # Hook script: blocks .env reads
└── commands/
    ├── knowledge.md        # /knowledge slash command
    └── idea.md             # /idea slash command
```

---

### Hooks (`settings.json`)

Hooks are shell commands that Claude Code runs automatically before or after certain actions. They fire **silently in the background** without any action needed from you.

This project has two `PreToolUse` hooks (run *before* Claude uses a tool):

#### 1. `.env` Access Guard
- **Triggers on:** Any `Read` or `Grep` tool call
- **What it does:** Blocks Claude from reading `.env` directly. `.env.example` is still accessible.
- **Why:** Prevents accidental exposure of API keys in Claude's context or conversation logs.
- **Script:** `.claude/hooks/check_env_access.py`

#### 2. Duplicate Code Prevention
- **Triggers on:** Any `Write` or `Edit` tool call
- **What it does:** Before writing code, Claude checks whether the function, class, or logic being added already exists elsewhere in the project. If a duplicate is detected, the write is blocked and Claude explains what already exists and where.
- **Why:** Keeps the codebase clean and avoids bugs from two versions of the same logic drifting apart.

---

### Slash Commands

Custom commands available in any Claude Code session in this project. Type them in the Claude Code prompt.

#### `/knowledge <question>`
Answers a question with focus on how it relates to AT-DJ, then saves a structured summary to `doc/knowledge/<topic>.md` for future reference. Use this when researching libraries, design patterns, or architecture decisions.

```
/knowledge what is the difference between langgraph and langchain?
```

#### `/idea <description>`
Records a feature idea or design proposal. Claude will first restate and clarify the idea, ask for your confirmation, then append it to `doc/ideas.md` in a structured format. Ideas are tracked as `- [ ]` (open) or `- [x]` (implemented).

```
/idea add an onboarding flow that plays 3 sample tracks to calibrate user preferences
```

---

### Notes for teammates

- All hooks run via `uv run python` — no separate Python installation needed.
- Do not commit real API keys. If you accidentally add them, rotate them immediately.
- The `doc/ideas.md` and `doc/knowledge/` files are worth reading before starting a new work package — they capture design decisions and research done during planning.
- `doc/blueprint.md` contains the full project specification: architecture, component breakdown, milestones, and technical decisions. Read it before starting any significant implementation work.
