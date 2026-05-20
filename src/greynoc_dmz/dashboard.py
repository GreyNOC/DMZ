from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import validate_all
from .models import ScenarioResult
from .store import read_history


class DashboardHandler(BaseHTTPRequestHandler):
    root = Path.cwd()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_html(render_dashboard(validate_all(self.root), read_history(self.root / ".dmz")))
            return
        if parsed.path == "/api/status":
            results = validate_all(self.root)
            payload = {
                "app": "GreyNOC DMZ",
                "scenario_count": len(results),
                "passing": sum(1 for item in results if item.passed),
                "failing": sum(1 for item in results if not item.passed),
                "results": [item.model_dump(mode="json") for item in results],
            }
            self._send_json(payload)
            return
        self.send_error(404)

    def _send_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: object) -> None:
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def render_dashboard(results: list[ScenarioResult], history: list[dict[str, object]]) -> str:
    rows = []
    passed = 0
    total = 0
    alert_count = 0
    for item in results:
        total += 1
        passed += 1 if item.passed else 0
        alert_count += len(item.alerts)
        status = "PASS" if item.passed else "FAIL"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.scenario_id)}</td>"
            f"<td>{html.escape(item.scenario_name)}</td>"
            f"<td><span class='status {status.lower()}'>{status}</span></td>"
            f"<td>{html.escape(', '.join(item.fired_rules) or 'none')}</td>"
            f"<td>{html.escape(', '.join(item.missing_rules) or 'none')}</td>"
            f"<td>{html.escape(', '.join(item.unexpected_rules) or 'none')}</td>"
            "</tr>"
        )

    history_rows = []
    for record in reversed(history[-10:]):
        scenario_id = str(record.get("scenario_id", "unknown"))
        recorded_at = str(record.get("recorded_at", "unknown"))
        result = "PASS" if bool(record.get("passed")) else "FAIL"
        history_rows.append(
            "<tr>"
            f"<td>{html.escape(recorded_at)}</td>"
            f"<td>{html.escape(scenario_id)}</td>"
            f"<td><span class='status {result.lower()}'>{result}</span></td>"
            f"<td>{html.escape(str(record.get('alert_count', 0)))}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GreyNOC DMZ</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Tahoma, Verdana, Arial, sans-serif; font-size: 13px; background: #3a6ea5; color: #111; }}
    .desktop {{ padding: 14px; min-height: 100vh; }}
    .window {{ max-width: 1180px; margin: 0 auto; border: 2px solid #0a246a; background: #d4d0c8; box-shadow: 3px 3px 0 #1b1b1b; }}
    .titlebar {{ display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; color: white; background: linear-gradient(90deg, #0a246a, #a6caf0); font-weight: bold; }}
    .controls span {{ display: inline-block; min-width: 18px; padding: 0 4px; margin-left: 3px; text-align: center; border: 1px solid #333; background: #d4d0c8; color: #111; }}
    .menu {{ padding: 4px 8px; border-bottom: 1px solid #808080; }}
    .menu span {{ margin-right: 18px; }}
    .content {{ padding: 10px; }}
    .panel {{ border: 2px inset #fff; background: #f0f0f0; margin-bottom: 10px; padding: 10px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
    .metric {{ border: 1px solid #808080; background: white; padding: 8px; min-height: 58px; }}
    .metric b {{ display: block; font-size: 20px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ text-align: left; padding: 6px; border: 1px solid #b5b5b5; }}
    th {{ background: #d4d0c8; }}
    .status {{ display: inline-block; min-width: 46px; text-align: center; padding: 2px 5px; border: 1px solid #444; background: white; }}
    .status.pass {{ color: #0b5f17; }}
    .status.fail {{ color: #8a0000; }}
    .footer {{ padding: 4px 8px; border-top: 1px solid #808080; font-size: 12px; }}
    code {{ font-family: Consolas, monospace; }}
    @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <div class="desktop">
    <div class="window">
      <div class="titlebar"><span>GreyNOC DMZ - Detection Manager</span><span class="controls"><span>_</span><span>[]</span><span>X</span></span></div>
      <div class="menu"><span>File</span><span>View</span><span>Scenarios</span><span>Reports</span><span>Help</span></div>
      <div class="content">
        <div class="panel">
          <div class="grid">
            <div class="metric">Scenarios<b>{total}</b></div>
            <div class="metric">Passing<b>{passed}</b></div>
            <div class="metric">Failing<b>{total - passed}</b></div>
            <div class="metric">Alerts<b>{alert_count}</b></div>
          </div>
        </div>
        <div class="panel">
          <h3>Scenario status</h3>
          <table>
            <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Fired</th><th>Missing</th><th>Unexpected</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>
        <div class="panel">
          <h3>Recent validation history</h3>
          <table>
            <thead><tr><th>Recorded</th><th>Scenario</th><th>Status</th><th>Alerts</th></tr></thead>
            <tbody>{''.join(history_rows) or '<tr><td colspan="4">No history yet.</td></tr>'}</tbody>
          </table>
        </div>
      </div>
      <div class="footer">Local only by default. API status endpoint: <code>/api/status</code></div>
    </div>
  </div>
</body>
</html>
"""


def serve(root: Path, host: str, port: int) -> None:
    DashboardHandler.root = root
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.serve_forever()
