# A11y Agent

Audits web pages with axe-core, WAVE and Lighthouse. It works from a browser UI (`a11yagent.html`) or as an MCP server for Claude and other MCP clients.

Automated tools catch only part of WCAG. A clean result does not show conformance, and these tools don't exercise menus, dialogs or checkout flows.

## Set up the MCP server

Requires Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
cp .env.example a11y_agent.env   # then add your WAVE key
```

Lighthouse is optional: `npm install -g lighthouse`.

Add this to your MCP client's settings. In the Claude desktop app that file is `claude_desktop_config.json`. Use absolute paths, then restart the app.

```json
{
  "mcpServers": {
    "a11y-agent": {
      "command": "/absolute/path/to/A11y_Agent/.venv/bin/python",
      "args": ["/absolute/path/to/A11y_Agent/mcp_server.py"]
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `audit_url` | Audits one page |
| `start_batch_audit` | Starts a background audit from a URL list or `sitemap_url` |
| `get_batch_status` | Shows progress |
| `get_batch_report` | Summarizes results and writes `pages.csv` and `issues.csv` |
| `stop_batch_audit` | Stops after the current page |
| `resume_batch_audit` | Continues a run, skipping saved pages |
| `list_batch_audits` | Lists saved runs |
| `check_wave_credits` | Shows the WAVE credit balance saved from the last WAVE request (free); `live=True` makes a small paid WAVE request to refresh it |
| `list_access_topics` | Lists the access topics from Microsoft's Accessibility Considerations Toolkit |
| `get_access_consideration` | Returns one topic's checklist, assistive-tech models and test strategies, with required safeguards |
| `get_evaluation_guide` | Returns a methodology or heuristics document, such as the severity scale |
| `get_wcag_criterion` | Returns one WCAG 2.2 success criterion's text, for annotating findings |

Results are saved in `~/.a11y_agent/runs/<run_id>/`. Import the CSV files into Google Sheets or Excel.

## Accessibility Considerations Toolkit

The four toolkit tools cover what axe, WAVE and Lighthouse can't: keyboard, screen reader, zoom,
voice and cognitive checks, organized by EN 301 549. They read a pinned copy of
[Microsoft's toolkit](https://github.com/microsoft/Microsoft-Accessibility/tree/main/Accessibility-Considerations-Toolkit)
in `vendor/ms-act/`, so they work offline and don't change unless you update the copy.
See `vendor/ms-act/VENDORED.md` for the pinned commit, licenses and update steps.

## Use the browser page

1. Double-click `Start A11y Agent.command` in Finder. It starts the local server and opens
   `a11yagent.html`; close its Terminal window to stop the server. (Or run
   `.venv/bin/python audit_server.py` and open the page yourself.)
2. Choose **One page** and enter a page address, or **A whole site** and enter its sitemap
   (usually `/sitemap.xml`; WordPress uses `/wp-sitemap.xml`, or `/sitemap_index.xml` with Yoast SEO).
3. For a whole site, choose where WAVE and Lighthouse run. **One page of each type** keeps WAVE
   credit use low; axe still checks every page.

Site audits use the same engine as the MCP batch tools: results are saved under
`~/.a11y_agent/runs/`, the page shows progress and a summary, and **Stop audit** ends the run
after the current page.

## Batch behavior

- **Pacing:** one page at a time, with a 2-second delay by default.
- **WAVE credits:** WAVE and Lighthouse run on the first page of each template. Set `sampled_tools_per_template` to 0 to run them on every page. The start result shows the planned request count.
- **Blocking:** a page returning 403, 429 or 503 is retried once after 60 seconds. Five blocked pages in a row pause the run.
- **Grouping:** `issues.csv` lists each rule once, with its affected page count and templates. Template names are guessed from URL paths.

## Test

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
```

## License

A11y Agent is released under the [MIT License](LICENSE). Anyone may fork, use and adapt it,
including in commercial work, as long as the copyright and license notice stay with the code.

The vendored Microsoft Accessibility Considerations Toolkit in `vendor/ms-act/` keeps its own
license: MIT from Microsoft, plus W3C document license terms for the WCAG and cognitive
accessibility material it adapts. See `vendor/ms-act/VENDORED.md` for details.
