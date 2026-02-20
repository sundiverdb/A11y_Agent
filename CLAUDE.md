# CLAUDE.md — A11y_Agent

This file provides context and conventions for AI assistants (Claude Code and others) working on the **A11y_Agent** project. Read this before making any changes.

---

## Project Overview

**A11y_Agent** is an AI-powered accessibility (a11y) agent that helps developers audit, diagnose, and remediate web accessibility issues. The agent interprets WCAG guidelines, analyzes UI components, evaluates screen reader compatibility, and generates actionable remediation advice.

**Core responsibilities:**
- Audit web pages for WCAG 2.1 / 2.2 compliance via the WebAIM WAVE API
- Provide structured, prioritized issue counts by category (errors, contrast, alerts, features, structure, ARIA)
- Generate accessible code alternatives on request
- Support CI/CD integration for automated accessibility gating (planned)

**Current implementation status:** Early-stage prototype (MVP). The UI and WAVE API integration are functional; the core LLM-based auditor/remediator backend is planned but not yet built.

---

## Repository Structure

### Actual Current Layout

```
A11y_Agent/
├── CLAUDE.md              # This file — project conventions for AI assistants
├── dialog.html            # Main browser UI (accessible dialog, WAVE API results)
├── proxy.py               # Local HTTP proxy that forwards requests to the WAVE API
├── a11y_agent.env         # Environment variables — contains WAVE_API_KEY
│                          # WARNING: This file is tracked by git (see Security note below)
└── .gitignore             # Excludes .env, __pycache__, .venv, dist, node_modules
```

### Intended Future Layout

The following structure is the planned target as the project grows. Keep this section updated as directories are created.

```
A11y_Agent/
├── CLAUDE.md
├── README.md                  # User-facing documentation (not yet created)
├── .env.example               # Env var template (not yet created)
├── pyproject.toml             # Python project config — deps, build, linting (not yet created)
│
├── dialog.html                # Browser UI
├── proxy.py                   # WAVE API proxy
├── a11y_agent.env             # Secrets — never commit new keys here; migrate to .env
│
├── src/
│   └── a11y_agent/
│       ├── __init__.py
│       ├── agent.py           # Main LLM agent entrypoint (planned)
│       ├── auditor.py         # Accessibility auditing logic (planned)
│       ├── remediator.py      # Remediation suggestion generation (planned)
│       ├── rules/             # WCAG rule definitions (planned)
│       ├── tools/             # Tool integrations — WAVE, axe, Lighthouse (planned)
│       └── prompts/           # LLM prompt templates (planned)
│
├── tests/
│   ├── unit/                  # Not yet created
│   ├── integration/           # Not yet created
│   └── fixtures/              # Sample HTML, ARIA patterns (not yet created)
│
├── scripts/                   # Dev/CI helper scripts (not yet created)
├── .github/
│   └── workflows/             # CI/CD pipelines (not yet created)
└── docs/                      # Extended documentation (not yet created)
```

---

## Existing Components

### `dialog.html` — Browser UI (659 lines)

The primary user-facing interface. A fully self-contained accessible dialog rendered in the browser.

**Features:**
- `role="dialog"` with `aria-modal`, `aria-labelledby`, `aria-describedby`
- URL input field with client-side validation (`URL` API), `aria-invalid`, and live error messages
- Fieldset of 5 checkbox tests, each with WCAG SC citations in label hints:
  - Color Contrast (SC 1.4.3, 1.4.6)
  - Keyboard Traps (SC 2.1.2)
  - Alt-text for Images (SC 1.1.1)
  - Description for Images (SC 1.1.1 via `aria-describedby`)
  - Skip to Content Link (SC 2.4.1)
- Results section: 6 WAVE category cards (Errors, Contrast, Alerts, Features, Structure, ARIA) with color-coded styling
- `aria-live="polite"` status region for screen reader announcements
- Full keyboard focus trap (Tab/Shift+Tab cycles within dialog)
- XSS protection via `escHtml()` before inserting user-supplied URLs into the DOM

**JavaScript flow:**
1. Validate URL on input and on "Run Checks" click
2. `fetch()` to local proxy at `http://127.0.0.1:5000/check?url=<encoded-url>`
3. Parse WAVE API JSON response and render `renderResults(data)`
4. Update `aria-live` region with status announcement

**Dependencies:** None — vanilla HTML5, CSS3, JavaScript only.

---

### `proxy.py` — WAVE API Proxy (123 lines)

A minimal, zero-dependency local HTTP server that proxies WAVE API requests, adding the API key and CORS headers so `dialog.html` can call it from a `file://` or `localhost` origin.

**Key details:**
- Listens on `http://127.0.0.1:5000`
- Endpoint: `GET /check?url=<target-url>`
- Reads `WAVE_API_KEY` from `a11y_agent.env` (falls back to `WAVE_API_KEY` env var)
- Appends `reporttype=2` to all WAVE API requests (returns structured JSON)
- 30-second timeout on outbound WAVE requests
- CORS: `Access-Control-Allow-Origin: *` (permits `file://` and all localhost origins)

**Dependencies:** Python 3 stdlib only (`http.server`, `urllib`, `json`, `pathlib`).

**To run:**
```bash
python proxy.py
```

---

### `a11y_agent.env` — Environment Variables

> **Security Warning:** This file is currently committed to the git repository, which means `WAVE_API_KEY` is in version history. When rotating the key, remove this file from tracking:
> ```bash
> git rm --cached a11y_agent.env
> echo "a11y_agent.env" >> .gitignore
> ```
> Going forward, populate secrets via shell environment variables or a `.env` file that is properly gitignored.

| Variable | Required | Description |
|---|---|---|
| `WAVE_API_KEY` | Yes | [WebAIM WAVE API](https://wave.webaim.org/api/) key for accessibility scanning |
| `ANTHROPIC_API_KEY` | Planned | Anthropic API key for Claude LLM integration (not yet in use) |
| `LOG_LEVEL` | No | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `AXE_HEADLESS` | Planned | Run axe-core in headless mode (`true`/`false`) |

---

## Development Setup

### Prerequisites

- Python 3.11+ (for `proxy.py` — no external packages required)
- A modern browser (for `dialog.html`)
- A [WebAIM WAVE API key](https://wave.webaim.org/api/) — set `WAVE_API_KEY` in `a11y_agent.env`

### Running the Current Prototype

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd A11y_Agent

# 2. Set your WAVE API key
echo "WAVE_API_KEY=<your-key>" > a11y_agent.env

# 3. Start the local proxy
python proxy.py
# Output: Proxy listening on http://127.0.0.1:5000  —  Ctrl-C to stop.

# 4. Open the UI in a browser
open dialog.html       # macOS
xdg-open dialog.html   # Linux
# Or double-click dialog.html in your file manager
```

### Planned Python Package Setup (not yet implemented)

```bash
# Once pyproject.toml exists:
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Verify setup
python -m pytest tests/
```

---

## Key Conventions

### Git Workflow

- **Branch naming:** `claude/<short-description>-<session-id>` for AI-driven work; `feat/<name>`, `fix/<name>`, `chore/<name>` for human-driven work
- **Commits:** Use conventional commits format — `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- **Never push directly to `main`** — all changes go through pull/merge requests
- Always push with: `git push -u origin <branch-name>`

**Git history (as of 2026-02-20):**
| Hash | Message |
|------|---------|
| `72faaac` | `feat(dialog): add URL input, WAVE API proxy, and results display` |
| `0cbcc5d` | `Update WAVE_API_KEY in a11y_agent.env` |
| `ee0a39d` | `feat: add accessible dialog UI for accessibility check selection` |
| `759f346` | `docs: add initial CLAUDE.md with project structure and conventions` |

### Code Style

- Follow **PEP 8** for Python; use `ruff` for linting and `black` for formatting (tools not yet configured in project)
- For HTML/CSS/JavaScript: use `eslint` + `prettier` (tools not yet configured in project)
- Maximum line length: **100 characters**
- All public Python functions/classes must have docstrings
- Type annotations required for all Python function signatures

### Testing

- Write tests for all non-trivial logic before or alongside implementation
- Test files mirror source structure: `tests/unit/test_auditor.py` for `src/a11y_agent/auditor.py`
- Use `pytest` (Python)
- Minimum coverage target: **80%**
- Run tests before every commit:
  ```bash
  pytest tests/ --cov=src/a11y_agent --cov-report=term-missing
  ```
- **Current status:** No test suite exists yet. Add `tests/` when adding backend modules.

### Accessibility of the Agent Itself

- The agent's CLI output must be screen-reader friendly (no decorative ASCII art that obscures meaning)
- JSON output mode must always be available via `--json` flag
- Error messages must be descriptive and actionable
- All HTML/CSS produced by the agent must meet WCAG 2.1 AA minimum — the dialog UI itself serves as a reference implementation

---

## Architecture Decisions

### Current Stack

| Layer | Technology | Status |
|-------|-----------|--------|
| Browser UI | Vanilla HTML5 / CSS3 / JavaScript | Implemented |
| Accessibility scanner | WebAIM WAVE API (`wave.webaim.org/api`) | Integrated via proxy |
| Local proxy | Python 3 stdlib (`http.server`, `urllib`) | Implemented |
| LLM backend | Anthropic Claude API (planned) | Not yet implemented |
| Package tooling | `pyproject.toml`, `ruff`, `black`, `pytest` | Not yet configured |

### WAVE API Integration

The WAVE API is used as the primary accessibility scanner:
- Endpoint: `https://wave.webaim.org/api/request`
- Report type `2` returns structured JSON with category counts and detailed items
- The proxy (`proxy.py`) handles API key injection and CORS bridging
- Raw WAVE output is rendered directly in `dialog.html`; no normalization layer exists yet

**Planned evolution:** When the LLM backend is added, raw WAVE output will be normalized into a shared `Finding` schema before being processed by Claude.

### LLM Integration (Planned)

- Will use the **Anthropic Claude API** via the `anthropic` Python SDK
- Prompt templates will live in `src/a11y_agent/prompts/` as `.txt` or `.jinja2` files — never hardcoded in Python
- Use **structured outputs** (JSON mode or tool use) wherever the agent needs to return machine-parseable results
- Prefer **tool use / function calling** over free-text parsing for reliability

### Accessibility Scanning (Planned Expansion)

- WAVE API is the current scanner (via proxy)
- `axe-core` (via Playwright headless browser) is the next planned integration
- Lighthouse is planned for performance + accessibility scoring
- Raw scanner output will be normalized into a shared `Finding` schema before LLM processing

### Remediation Suggestions (Planned)

- The LLM will receive: original HTML snippet + violation details + relevant WCAG success criterion
- Suggestions will be returned as structured diffs (not prose), so they can be applied programmatically
- Always cite the specific WCAG criterion (e.g., WCAG 2.1 SC 1.4.3)

---

## Common Tasks

### Running the Proxy

```bash
python proxy.py
# Proxy listening on http://127.0.0.1:5000  —  Ctrl-C to stop.
```

If `WAVE_API_KEY` is missing, the proxy starts but returns a 500 error on all `/check` requests.

### Opening the UI

Open `dialog.html` directly in a browser. The proxy must be running first.

### Running Linting (once tooling is configured)

```bash
ruff check src/ tests/
black --check src/ tests/
```

### Adding a New WCAG Rule (once backend exists)

1. Create a rule definition in `src/a11y_agent/rules/<rule-id>.py`
2. Register the rule in `src/a11y_agent/rules/__init__.py`
3. Add corresponding test fixtures in `tests/fixtures/`
4. Write unit tests in `tests/unit/test_rules.py`

### Rotating the WAVE API Key

```bash
# Remove the env file from git tracking (one-time)
git rm --cached a11y_agent.env
echo "a11y_agent.env" >> .gitignore
git commit -m "chore: stop tracking a11y_agent.env secrets file"

# Update the key locally
echo "WAVE_API_KEY=<new-key>" > a11y_agent.env
```

---

## What AI Assistants Should Know

1. **Read before modifying.** Always read existing files before editing. Never guess at structure.
2. **Keep changes minimal.** Fix exactly what was asked. Don't refactor surrounding code unless instructed.
3. **No secrets in code.** Never hardcode API keys, tokens, or credentials. Always use environment variables.
4. **Update this file.** If you add new modules, change the architecture, or establish a new convention, update `CLAUDE.md` accordingly.
5. **Test your changes.** Run the test suite after every non-trivial change. Do not mark tasks complete if tests fail.
6. **Accessibility-first.** When generating HTML/CSS/JS output or examples, always ensure they meet WCAG 2.1 AA minimum. The existing `dialog.html` is the reference implementation.
7. **Conventional commits.** Write commit messages in the format `type(scope): description`.
8. **Branch discipline.** Develop on the designated feature branch. Never push to `main` directly.
9. **Structured outputs preferred.** When the agent needs to return data, use tool use or JSON mode — avoid free-text parsing.
10. **Document decisions.** If you make a non-obvious architectural choice, add a brief note under "Architecture Decisions" above.
11. **No package yet.** There is no `pyproject.toml`, `requirements.txt`, or Python package structure. Any new Python code currently runs as standalone scripts using the stdlib. When adding the first non-stdlib dependency, create `pyproject.toml` and document it here.
12. **Security debt.** `a11y_agent.env` is currently tracked in git. Do not add more secrets to any tracked file. Remind users to rotate the WAVE API key if they see it committed.

---

## Useful References

- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [WCAG 2.2 Guidelines](https://www.w3.org/TR/WCAG22/)
- [WebAIM WAVE API Docs](https://wave.webaim.org/api/)
- [axe-core Rule Descriptions](https://dequeuniversity.com/rules/axe/)
- [Anthropic Claude API Docs](https://docs.anthropic.com/)
- [WAI-ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [Playwright Python Docs](https://playwright.dev/python/)
