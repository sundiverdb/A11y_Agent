# A11y Agent

Audits web pages with axe-core, WAVE and Lighthouse. It works from a browser UI (`dialog.html`) or as an MCP server for Claude and other MCP clients.

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

Results are saved in `~/.a11y_agent/runs/<run_id>/`. Import the CSV files into Google Sheets or Excel.

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
