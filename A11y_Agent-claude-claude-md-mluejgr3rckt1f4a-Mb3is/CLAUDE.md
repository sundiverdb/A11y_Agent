# CLAUDE.md — A11y_Agent

This file provides context and conventions for AI assistants (Claude Code and others) working on the **A11y_Agent** project. Read this before making any changes.

---

## Project Overview

**A11y_Agent** is an AI-powered accessibility (a11y) agent that helps developers audit, diagnose, and remediate web accessibility issues. The agent interprets WCAG guidelines, analyzes UI components, evaluates screen reader compatibility, and generates actionable remediation advice.

**Core responsibilities:**
- Audit HTML/CSS/JS for WCAG 2.1 / 2.2 compliance
- Integrate with axe-core, Lighthouse, and other accessibility scanners
- Provide structured, prioritized remediation plans
- Generate accessible code alternatives on request
- Support CI/CD integration for automated accessibility gating

---

## Repository Structure

```
A11y_Agent/
├── CLAUDE.md                  # This file
├── README.md                  # User-facing documentation
├── .env.example               # Required environment variables (never commit .env)
├── pyproject.toml             # Python project config (deps, build, linting)
│   OR
├── package.json               # Node project config (if JS/TS)
│
├── src/
│   └── a11y_agent/
│       ├── __init__.py
│       ├── agent.py           # Main agent entrypoint
│       ├── auditor.py         # Accessibility auditing logic
│       ├── remediator.py      # Remediation suggestion generation
│       ├── rules/             # WCAG rule definitions
│       ├── tools/             # Tool integrations (axe, Lighthouse, etc.)
│       └── prompts/           # LLM prompt templates
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/              # Sample HTML, ARIA patterns
│
├── scripts/                   # Dev/CI helper scripts
├── .github/
│   └── workflows/             # CI/CD pipelines
└── docs/                      # Extended documentation
```

> **Note:** This structure is the intended target. As the project grows, keep this section updated to reflect the actual layout.

---

## Development Setup

### Prerequisites

- Python 3.11+ (preferred) **or** Node.js 20+ depending on final stack choice
- An Anthropic API key (set `ANTHROPIC_API_KEY` in `.env`)

### Initial Setup

```bash
# Clone and enter repo
git clone <repo-url>
cd A11y_Agent

# Python setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy env template
cp .env.example .env
# Then populate .env with real values

# Verify setup
python -m pytest tests/
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `LOG_LEVEL` | No | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `AXE_HEADLESS` | No | Run axe-core in headless mode (`true`/`false`) |

---

## Key Conventions

### Git Workflow

- **Branch naming:** `claude/<short-description>-<session-id>` for AI-driven work; `feat/<name>`, `fix/<name>`, `chore/<name>` for human-driven work
- **Commits:** Use conventional commits format — `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- **Never push directly to `main`** — all changes go through pull/merge requests
- Always push with: `git push -u origin <branch-name>`

### Code Style

- Follow **PEP 8** for Python; use `ruff` for linting and `black` for formatting
- For TypeScript/JavaScript: use `eslint` + `prettier`
- Maximum line length: **100 characters**
- All public functions/classes must have docstrings
- Type annotations required for all function signatures

### Testing

- Write tests for all non-trivial logic before or alongside implementation
- Test files mirror source structure: `tests/unit/test_auditor.py` for `src/a11y_agent/auditor.py`
- Use `pytest` (Python) or `vitest`/`jest` (JS/TS)
- Minimum coverage target: **80%**
- Run tests before every commit:
  ```bash
  pytest tests/ --cov=src/a11y_agent --cov-report=term-missing
  ```

### Accessibility of the Agent Itself

- The agent's CLI output must be screen-reader friendly (no decorative ASCII art that obscures meaning)
- JSON output mode must always be available via `--json` flag
- Error messages must be descriptive and actionable

---

## Architecture Decisions

### LLM Integration

- Uses the **Anthropic Claude API** via the `anthropic` Python SDK
- Prompt templates live in `src/a11y_agent/prompts/` as `.txt` or `.jinja2` files — not hardcoded in Python
- Use **structured outputs** (JSON mode or tool use) wherever the agent needs to return machine-parseable results
- Prefer **tool use / function calling** over free-text parsing for reliability

### Accessibility Scanning

- `axe-core` is the primary scanner, integrated via Playwright (headless browser)
- Lighthouse is used for performance + accessibility scoring
- Raw scanner output is normalized into a shared `Finding` schema before being processed by the LLM

### Remediation Suggestions

- The LLM receives: original HTML snippet + violation details + relevant WCAG success criterion
- Suggestions are returned as structured diffs (not prose), so they can be applied programmatically
- Always cite the specific WCAG criterion (e.g., WCAG 2.1 SC 1.4.3)

---

## Common Tasks

### Running the Agent

```bash
# Audit a local HTML file
python -m a11y_agent audit path/to/page.html

# Audit a live URL
python -m a11y_agent audit https://example.com

# Output as JSON
python -m a11y_agent audit https://example.com --json
```

### Running Linting

```bash
ruff check src/ tests/
black --check src/ tests/
```

### Adding a New WCAG Rule

1. Create a rule definition in `src/a11y_agent/rules/<rule-id>.py`
2. Register the rule in `src/a11y_agent/rules/__init__.py`
3. Add corresponding test fixtures in `tests/fixtures/`
4. Write unit tests in `tests/unit/test_rules.py`

---

## What AI Assistants Should Know

1. **Read before modifying.** Always read existing files before editing. Never guess at structure.
2. **Keep changes minimal.** Fix exactly what was asked. Don't refactor surrounding code unless instructed.
3. **No secrets in code.** Never hardcode API keys, tokens, or credentials. Always use environment variables.
4. **Update this file.** If you add new modules, change the architecture, or establish a new convention, update `CLAUDE.md` accordingly.
5. **Test your changes.** Run the test suite after every non-trivial change. Do not mark tasks complete if tests fail.
6. **Accessibility-first.** When generating HTML/CSS/JS output or examples, always ensure they meet WCAG 2.1 AA minimum.
7. **Conventional commits.** Write commit messages in the format `type(scope): description`.
8. **Branch discipline.** Develop on the designated feature branch. Never push to `main` directly.
9. **Structured outputs preferred.** When the agent needs to return data, use tool use or JSON mode — avoid free-text parsing.
10. **Document decisions.** If you make a non-obvious architectural choice, add a brief note under "Architecture Decisions" above.

---

## Useful References

- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [WCAG 2.2 Guidelines](https://www.w3.org/TR/WCAG22/)
- [axe-core Rule Descriptions](https://dequeuniversity.com/rules/axe/)
- [Anthropic Claude API Docs](https://docs.anthropic.com/)
- [WAI-ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [Playwright Python Docs](https://playwright.dev/python/)
