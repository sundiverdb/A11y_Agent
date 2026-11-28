# Hand-off: A11y Agent

Last updated: November 26, 2026. Read this first when picking up work on the agent.

## Where things stand

- All work is on `main` (latest: French README, MIT license). 38 tests pass:
  `cd ~/developer/GitHub/A11y_Agent && .venv/bin/python -m pytest tests/unit tests/integration/test_audit_server.py`
- Two ways in:
  - **MCP server** `a11y-agent` (`mcp_server.py`), loaded by the Claude desktop app.
  - **Browser page** `a11yagent.html` with `audit_server.py`; double-click `Start A11y Agent.command`.
    One page, or a whole site from its sitemap.
- Batch runs and results: `~/.a11y_agent/runs/`. WAVE balance: `~/.a11y_agent/wave_credits.json`
  (`check_wave_credits`). WAVE runs on one page per page type unless asked otherwise.
- Microsoft's Accessibility Considerations Toolkit is pinned in `vendor/ms-act/`; see its `VENDORED.md` before updating.

## Next up

1. **Reports for several standards** from one set of results: WCAG 2.2, Section 508, EN 301 549
   (Canada federal and EU), RGAA 4.1.2 (France, in French), SGQRI 008 3.0 (Quebec, in French).
   One mapping data file per standard, so RGAA 5 or a 508 update means swapping a file.
   Start with Section 508. Reports are drafts: anything based only on automated scans is marked "to confirm".
   Open choice for the page: radio buttons, dropdown, or checkboxes (clients often need two reports).
2. **Testing behind a login**: save a signed-in Playwright session after a manual login (MFA and SSO included),
   then recorded task flows that run axe at every step. WAVE's online API can't see signed-in pages.
   Never commit session files or credentials. Practice on the OrangeHRM demo, then a WordPress admin
   with an Editor test user. Only test real SaaS products with written permission.
3. Later: Storybook story audits, when a project needs them.

## Conventions

- Never push to `main`: use `claude/...` branches and pull requests.
- Terminal instructions start with `cd ~/developer/GitHub/A11y_Agent`.
- UI labels say what the user wants to do ("Audit site"), not the mechanics ("Run").
- The pages the agent produces must meet WCAG 2.2 AA themselves.
