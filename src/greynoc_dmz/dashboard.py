from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import validate_all
from .models import ScenarioResult


class DashboardHandler(BaseHTTPRequestHandler):
    root = Path.cwd()

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        results = validate_all(self.root)
        body = render_dashboard(results)
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def render_dashboard(results: list[ScenarioResult]) -> str:
    rows = []
    passed = 0
    total = 0
    for item in results:
        total += 1
        passed += 1 if item.passed else 0
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.scenario_id)}</td>"
            f"<td>{html.escape(item.scenario_name)}</td>"
            f"<td>{'PASS' if item.passed else 'FAIL'}</td>"
            f"<td>{html.escape(', '.join(item.fired_rules) or 'none')}</td>"
            f"<td>{html.escape(', '.join(item.missing_rules) or 'none')}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GreyNOC DMZ</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #101418; color: #e9eef5; }}
    header {{ padding: 28px; background: #171d24; border-bottom: 1px solid #2a333d; }}
    main {{ padding: 28px; }}
    .card {{ background: #171d24; border: 1px solid #2a333d; border-radius: 12px; padding: 18px; margin-bottom: 18px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #2a333d; }}
    th {{ color: #aeb8c4; }}
    code {{ color: #b7d7ff; }}
  </style>
</head>
<body>
  <header>
    <h1>GreyNOC DMZ</h1>
    <p>Local detection validation lab</p>
  </header>
  <main>
    <section class="card">
      <h2>Validation status</h2>
      <p><code>{passed}/{total}</code> scenarios passing.</p>
    </section>
    <section class="card">
      <h2>Scenarios</h2>
      <table>
        <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Fired</th><th>Missing</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def serve(root: Path, host: str, port: int) -> None:
    DashboardHandler.root = root
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.serve_forever()
