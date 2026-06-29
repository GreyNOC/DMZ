from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .access import Role, can
from .ai import (
    AIReadiness,
    Fighter,
    check_ai_readiness,
    check_fighter_readiness,
    load_ai_config,
    load_roster,
)
from .ai.roster import ROSTER_RELATIVE_PATH
from .ai_battle import BattleResult, simulate_battle
from .auth import (
    AuthConfig,
    SessionStore,
    build_clear_cookie,
    build_session_cookie,
    load_auth_config,
    parse_cookie,
    verify_login,
)
from .config import load_lab_config
from .correlation import correlate
from .coverage import CoverageReport, coverage_for_root
from .engine import validate_all
from .integrations import IntegrationCheck, check_integration_config, load_integrations
from .models import ScenarioResult
from .reporting import write_report
from .store import read_history

# Minimum permission required to reach each route. Read-only viewers and
# analysts can see scenario status; the detection tooling (coverage map, AI
# battle) requires an engineer or admin role.
ROUTE_PERMISSIONS: dict[str, str] = {
    "/": "dashboard:read",
    "/index.html": "dashboard:read",
    "/api/status": "dashboard:read",
    "/scenario": "scenario:read",
    "/coverage": "rule:read",
    "/api/coverage": "rule:read",
    "/ai-battle": "rule:test",
    "/api/ai-battle": "rule:test",
    "/roster": "rule:test",
    "/api/roster": "rule:test",
    "/validate": "scenario:run",
}


class DashboardHandler(BaseHTTPRequestHandler):
    root = Path.cwd()
    auth_config: AuthConfig = load_auth_config()
    sessions = SessionStore()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/login":
            self._send_html(render_login(None), status=200)
            return
        if parsed.path == "/logout":
            token = parse_cookie(self.headers.get("Cookie"))
            self.sessions.delete(token)
            self._redirect("/login", clear_cookie=True)
            return
        if not self._is_authorized():
            self._redirect("/login")
            return
        required = ROUTE_PERMISSIONS.get(parsed.path)
        if required is not None and not self._has_permission(required):
            self.send_error(403, "insufficient role")
            return
        if parsed.path in {"/", "/index.html"}:
            integration_checks = [
                check_integration_config(config) for config in load_integrations(self.root)
            ]
            role = self._effective_role()
            if role is None:
                self.send_error(403, "insufficient role")
                return
            self._send_html(
                render_dashboard(
                    validate_all(self.root, persist=False),
                    read_history(self.root / ".dmz"),
                    coverage_for_root(self.root),
                    integration_checks,
                    check_ai_readiness(load_ai_config()),
                    self.auth_config.enabled,
                    role,
                )
            )
            return
        if parsed.path == "/coverage":
            role = self._effective_role()
            if role is None:
                self.send_error(403, "insufficient role")
                return
            self._send_html(render_coverage(coverage_for_root(self.root), role))
            return
        if parsed.path == "/api/coverage":
            self._send_json(coverage_for_root(self.root).to_dict())
            return
        if parsed.path == "/scenario":
            scenario_id = parse_qs(parsed.query).get("id", [""])[0]
            results = validate_all(self.root, persist=False)
            result = next((item for item in results if item.scenario_id == scenario_id), None)
            if result is None:
                self.send_error(404)
                return
            role = self._effective_role()
            if role is None:
                self.send_error(403, "insufficient role")
                return
            self._send_html(render_scenario_detail(result, self.auth_config.enabled, role))
            return
        if parsed.path == "/ai-battle":
            params = parse_qs(parsed.query)
            battle = _battle_from_params(params)
            role = self._effective_role()
            if role is None:
                self.send_error(403, "insufficient role")
                return
            self._send_html(render_ai_battle(battle, role))
            return
        if parsed.path == "/api/ai-battle":
            params = parse_qs(parsed.query)
            self._send_json(_battle_from_params(params).to_dict())
            return
        if parsed.path == "/roster":
            role = self._effective_role()
            if role is None:
                self.send_error(403, "insufficient role")
                return
            self._send_html(render_roster(_roster_status(self.root), role))
            return
        if parsed.path == "/api/roster":
            self._send_json(
                {
                    "fighters": [
                        {**fighter.to_dict(), "status": readiness.status.value}
                        for fighter, readiness in _roster_status(self.root)
                    ]
                }
            )
            return
        if parsed.path == "/api/status":
            results = validate_all(self.root, persist=False)
            integration_checks = [
                check_integration_config(config) for config in load_integrations(self.root)
            ]
            ai_readiness = check_ai_readiness(load_ai_config())
            coverage = coverage_for_root(self.root)
            covered, total = coverage.tactic_coverage_ratio
            role = self._effective_role()
            payload = {
                "app": "GreyNOC DMZ",
                "auth_enabled": self.auth_config.enabled,
                "role": role.value if role else None,
                "scenario_count": len(results),
                "passing": sum(1 for item in results if item.passed),
                "failing": sum(1 for item in results if not item.passed),
                "tactic_coverage": f"{covered}/{total}",
                "results": [item.model_dump(mode="json") for item in results],
                "integrations": [
                    {
                        "name": check.name,
                        "kind": check.kind.value,
                        "adapter": check.adapter,
                        "status": check.status.value,
                    }
                    for check in integration_checks
                ],
                "ai": {
                    "status": ai_readiness.status.value,
                    "provider": ai_readiness.provider,
                    "model": ai_readiness.model,
                    "external": ai_readiness.external,
                },
            }
            self._send_json(payload)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/validate":
            if not self._is_authorized():
                self._redirect("/login")
                return
            if not self._has_permission("scenario:run"):
                self.send_error(403, "insufficient role")
                return
            config = load_lab_config(self.root)
            for result in validate_all(self.root, persist=True):
                write_report(result, self.root / config.report_dir)
            self._redirect("/")
            return
        if parsed.path != "/login":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        params = parse_qs(body)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]
        if verify_login(self.auth_config, username, password):
            session = self.sessions.create(
                username or self.auth_config.username, self.auth_config.role
            )
            secure = self.headers.get("X-Forwarded-Proto") == "https"
            self._redirect("/", cookie=build_session_cookie(session, secure=secure))
            return
        self._send_html(render_login("Invalid username or password."), status=401)

    def _is_authorized(self) -> bool:
        if not self.auth_config.enabled:
            return True
        token = parse_cookie(self.headers.get("Cookie"))
        return self.sessions.get(token) is not None

    def _effective_role(self) -> Role | None:
        if not self.auth_config.enabled:
            return Role.admin
        token = parse_cookie(self.headers.get("Cookie"))
        session = self.sessions.get(token)
        return session.role if session else None

    def _has_permission(self, permission: str) -> bool:
        role = self._effective_role()
        return role is not None and can(role, permission)

    def _redirect(
        self, location: str, cookie: str | None = None, clear_cookie: bool = False
    ) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        if clear_cookie:
            self.send_header("Set-Cookie", build_clear_cookie())
        self.end_headers()

    def _send_html(self, body: str, status: int = 200) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
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


def _first(params: dict[str, list[str]], key: str, default: str) -> str:
    return params.get(key, [default])[0] or default


def _battle_from_params(params: dict[str, list[str]]) -> BattleResult:
    rounds_text = _first(params, "rounds", "5")
    try:
        rounds = int(rounds_text)
    except ValueError:
        rounds = 5

    return simulate_battle(
        _first(params, "one", "Sentinel"),
        _first(params, "two", "Phantom"),
        rounds,
        _first(params, "objective", "Establish operational dominance in a synthetic SOC exercise."),
        _first(params, "one_strategy", "balanced"),
        _first(params, "two_strategy", "adaptive"),
        _first(params, "seed", ""),
    )


def _roster_status(root: Path) -> list[tuple[Fighter, AIReadiness]]:
    """Readiness of each configured fighter. Never contacts a provider."""
    fighters = load_roster(root / ROSTER_RELATIVE_PATH)
    return [(fighter, check_fighter_readiness(fighter)) for fighter in fighters]


def _menu(role: Role | None) -> str:
    if role is None:
        return '<span>Login</span>'

    items = ['<a href="/">Scenarios</a>']
    if can(role, "rule:read"):
        items.append('<a href="/coverage">Coverage</a>')
    if can(role, "rule:test"):
        items.append('<a href="/ai-battle">AI Battle</a>')
    if can(role, "rule:test"):
        items.append('<a href="/roster">AI Roster</a>')
    if can(role, "dashboard:read"):
        items.append('<a href="/api/status">API</a>')
    items.append('<a href="/logout">Logout</a>')
    return "".join(items)


def _page(title: str, body: str, role: Role | None = Role.admin) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Tahoma, Verdana, Arial, sans-serif; font-size: 13px; background: #3a6ea5; color: #111; }}
    a {{ color: #000080; }}
    .desktop {{ padding: 14px; min-height: 100vh; }}
    .window {{ max-width: 1180px; margin: 0 auto; border: 2px solid #0a246a; background: #d4d0c8; box-shadow: 3px 3px 0 #1b1b1b; }}
    .titlebar {{ display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; color: white; background: linear-gradient(90deg, #0a246a, #a6caf0); font-weight: bold; }}
    .controls span {{ display: inline-block; min-width: 18px; padding: 0 4px; margin-left: 3px; text-align: center; border: 1px solid #333; background: #d4d0c8; color: #111; }}
    .menu {{ padding: 4px 8px; border-bottom: 1px solid #808080; }}
    .menu span, .menu a {{ margin-right: 18px; color: #111; text-decoration: none; }}
    .content {{ padding: 10px; }}
    .panel {{ border: 2px inset #fff; background: #f0f0f0; margin-bottom: 10px; padding: 10px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
    .metric {{ border: 1px solid #808080; background: white; padding: 8px; min-height: 58px; }}
    .metric b {{ display: block; font-size: 20px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ text-align: left; padding: 6px; border: 1px solid #b5b5b5; vertical-align: top; }}
    th {{ background: #d4d0c8; }}
    .status {{ display: inline-block; min-width: 46px; text-align: center; padding: 2px 5px; border: 1px solid #444; background: white; }}
    .status.pass {{ color: #0b5f17; }}
    .status.fail {{ color: #8a0000; }}
    .status.win {{ color: #0a246a; }}
    .footer {{ padding: 4px 8px; border-top: 1px solid #808080; font-size: 12px; }}
    code, pre {{ font-family: Consolas, monospace; }}
    input {{ width: 100%; padding: 5px; border: 2px inset #fff; background: white; }}
    button {{ padding: 4px 12px; border: 2px outset #fff; background: #d4d0c8; }}
    .form {{ max-width: 360px; }}
    .battle-form {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
    .error {{ color: #8a0000; }}
    @media (max-width: 800px) {{ .grid, .battle-form {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <div class="desktop">
    <div class="window">
      <div class="titlebar"><span>{html.escape(title)}</span><span class="controls"><span>_</span><span>[]</span><span>X</span></span></div>
      <div class="menu">{_menu(role)}</div>
      <div class="content">{body}</div>
      <div class="footer">GreyNOC DMZ local detection manager</div>
    </div>
  </div>
</body>
</html>
"""


def render_login(error: str | None) -> str:
    error_html = f"<p class='error'>{html.escape(error)}</p>" if error else ""
    return _page(
        "GreyNOC DMZ - Login",
        f"""
        <div class="panel form">
          <h3>Login</h3>
          {error_html}
          <form method="post" action="/login">
            <p><label>Username<br><input name="username" autocomplete="username"></label></p>
            <p><label>Password<br><input name="password" type="password" autocomplete="current-password"></label></p>
            <p><button type="submit">Login</button></p>
          </form>
          <p>Authentication is enabled when <code>GREYNOC_DMZ_PASSWORD</code> is set.</p>
        </div>
        """,
        role=None,
    )


def render_dashboard(
    results: list[ScenarioResult],
    history: list[dict[str, object]],
    coverage: CoverageReport,
    integration_checks: list[IntegrationCheck],
    ai_readiness: AIReadiness,
    auth_enabled: bool,
    role: Role,
) -> str:
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
            f"<td><a href='/scenario?id={html.escape(item.scenario_id)}'>{html.escape(item.scenario_id)}</a></td>"
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

    integration_rows = []
    for check in integration_checks:
        integration_rows.append(
            "<tr>"
            f"<td>{html.escape(check.name)}</td>"
            f"<td>{html.escape(check.kind.value)}</td>"
            f"<td>{html.escape(check.adapter)}</td>"
            f"<td><span class='status {'pass' if check.status.value == 'ready' else 'fail'}'>"
            f"{html.escape(check.status.value)}</span></td>"
            f"<td>{html.escape(check.detail)}</td>"
            "</tr>"
        )

    ai_status = ai_readiness.status.value
    ai_status_class = "pass" if ai_status == "ready" else "fail"
    ai_provider = html.escape(ai_readiness.provider)
    ai_model = html.escape(ai_readiness.model or "not set")
    ai_detail = html.escape(ai_readiness.detail)

    auth_label = "enabled" if auth_enabled else "disabled"
    covered, total_tactics = coverage.tactic_coverage_ratio
    validation_panel = (
        """
        <div class="panel">
          <form method="post" action="/validate">
            <button type="submit">Run Validation</button>
          </form>
        </div>
        """
        if can(role, "scenario:run")
        else ""
    )
    coverage_panel = (
        f"""
        <div class="panel">
          <h3>MITRE ATT&amp;CK coverage</h3>
          <p>Tactics covered: <b>{covered}/{total_tactics}</b>. <a href="/coverage">View coverage map</a> or call <code>/api/coverage</code>.</p>
        </div>
        """
        if can(role, "rule:read")
        else ""
    )
    battle_panel = (
        """
        <div class="panel">
          <h3>AI Battle Arena</h3>
          <p>Run two local AI profiles against each other in a synthetic SOC dominance exercise.</p>
          <p><a href="/ai-battle">Open AI Battle</a> or call <code>/api/ai-battle</code>.</p>
        </div>
        """
        if can(role, "rule:test")
        else ""
    )
    body = f"""
        {validation_panel}
        <div class="panel">
          <div class="grid">
            <div class="metric">Scenarios<b>{total}</b></div>
            <div class="metric">Passing<b>{passed}</b></div>
            <div class="metric">Failing<b>{total - passed}</b></div>
            <div class="metric">Alerts<b>{alert_count}</b></div>
          </div>
        </div>
        {coverage_panel}
        {battle_panel}
        <div class="panel">
          <h3>Scenario status</h3>
          <table>
            <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Fired</th><th>Missing</th><th>Unexpected</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
          </table>
        </div>
        <div class="panel">
          <h3>Recent validation history</h3>
          <table>
            <thead><tr><th>Recorded</th><th>Scenario</th><th>Status</th><th>Alerts</th></tr></thead>
            <tbody>{"".join(history_rows) or '<tr><td colspan="4">No history yet.</td></tr>'}</tbody>
          </table>
        </div>
        <div class="panel">
          <h3>Integrations</h3>
          <table>
            <thead><tr><th>Name</th><th>Kind</th><th>Adapter</th><th>Status</th><th>Detail</th></tr></thead>
            <tbody>{"".join(integration_rows) or '<tr><td colspan="5">No integrations configured.</td></tr>'}</tbody>
          </table>
        </div>
        <div class="panel">
          <h3>AI provider</h3>
          <table>
            <tr><th>Status</th><td><span class="status {ai_status_class}">{ai_status}</span></td></tr>
            <tr><th>Provider</th><td>{ai_provider}</td></tr>
            <tr><th>Model</th><td>{ai_model}</td></tr>
            <tr><th>Detail</th><td>{ai_detail}</td></tr>
          </table>
        </div>
        <div class="panel">Authentication: <code>{auth_label}</code>. Status API: <code>/api/status</code></div>
    """
    return _page("GreyNOC DMZ - Detection Manager", body, role=role)


def _lead_timeline(result: BattleResult) -> str:
    timeline = result.stats.lead_timeline
    if not timeline:
        return ""
    peak = max((abs(value) for value in timeline), default=1) or 1
    one_name = html.escape(result.ai_one.name)
    two_name = html.escape(result.ai_two.name)
    columns = []
    for index, value in enumerate(timeline, start=1):
        height = round(38 * abs(value) / peak)
        leader = result.ai_one.name if value > 0 else result.ai_two.name if value < 0 else "tied"
        up = (
            f"<div style='width:100%;height:{height}px;background:#0a246a'></div>"
            if value > 0
            else ""
        )
        down = (
            f"<div style='width:100%;height:{height}px;background:#8a0000'></div>"
            if value < 0
            else ""
        )
        columns.append(
            f"<div title='Round {index}: {html.escape(leader)} {value:+d}' "
            "style='flex:1;display:flex;flex-direction:column;height:80px;min-width:8px'>"
            f"<div style='flex:1;display:flex;align-items:flex-end'>{up}</div>"
            "<div style='height:1px;background:#808080'></div>"
            f"<div style='flex:1;display:flex;align-items:flex-start'>{down}</div>"
            "</div>"
        )
    return (
        "<div class='panel'>"
        "<h3>Lead timeline</h3>"
        f"<p>Cumulative score margin per round. Above the line <b style='color:#0a246a'>{one_name}</b> "
        f"leads; below, <b style='color:#8a0000'>{two_name}</b> leads.</p>"
        f"<div style='display:flex;gap:3px;align-items:stretch'>{''.join(columns)}</div>"
        "</div>"
    )


def render_ai_battle(result: BattleResult, role: Role = Role.admin) -> str:
    stats = result.stats
    one = result.ai_one
    two = result.ai_two
    one_name = html.escape(one.name)
    two_name = html.escape(two.name)

    round_rows = []
    for battle_round in result.rounds:
        margin_color = "#0b5f17" if battle_round.margin >= 0 else "#8a0000"
        round_rows.append(
            "<tr>"
            f"<td>{battle_round.round_number}</td>"
            f"<td>{html.escape(battle_round.focus)}</td>"
            f"<td align='right'><b>{battle_round.ai_one_score}</b></td>"
            f"<td align='right'><b>{battle_round.ai_two_score}</b></td>"
            f"<td align='right' style='color:{margin_color}'>{battle_round.margin:+d}</td>"
            f"<td><span class='status win'>{html.escape(battle_round.winner)}</span><br>"
            f"{html.escape(battle_round.reason)}</td>"
            "</tr>"
        )

    challenge_rows = []
    for item in stats.per_challenge:
        challenge_rows.append(
            "<tr>"
            f"<td>{html.escape(item.focus)}</td>"
            f"<td align='right'>{item.ai_one_score}</td>"
            f"<td align='right'>{item.ai_two_score}</td>"
            f"<td><span class='status win'>{html.escape(item.winner)}</span></td>"
            "</tr>"
        )

    upset_note = " <b>(upset)</b>" if stats.upset else ""
    comeback_note = (
        f"<tr><th>Comeback</th><td>{html.escape(stats.comeback_winner)} won after trailing</td></tr>"
        if stats.comeback_winner
        else ""
    )

    body = f"""
      <div class="panel">
        <form method="get" action="/ai-battle">
          <div class="battle-form">
            <label>AI One<br><input name="one" value="{one_name}"></label>
            <label>AI Two<br><input name="two" value="{two_name}"></label>
            <label>Rounds<br><input name="rounds" value="{len(result.rounds)}"></label>
            <label>AI One Strategy<br><input name="one_strategy" value="{html.escape(one.strategy)}"></label>
            <label>AI Two Strategy<br><input name="two_strategy" value="{html.escape(two.strategy)}"></label>
            <label>Seed<br><input name="seed" value="{html.escape(result.seed)}" placeholder="optional rematch seed"></label>
          </div>
          <label>Objective<br><input name="objective" value="{html.escape(result.objective)}"></label>
          <p><button type="submit">Start Battle</button></p>
        </form>
      </div>
      <div class="panel">
        <h3>Fighters</h3>
        <table>
          <thead><tr><th>AI</th><th>Strategy</th><th>Aggression</th><th>Defense</th><th>Adaptability</th><th>Power</th></tr></thead>
          <tbody>
            <tr><td>{one_name}</td><td>{html.escape(one.strategy)}</td><td align="right">{one.aggression}</td><td align="right">{one.defense}</td><td align="right">{one.adaptability}</td><td align="right"><b>{one.power}</b></td></tr>
            <tr><td>{two_name}</td><td>{html.escape(two.strategy)}</td><td align="right">{two.aggression}</td><td align="right">{two.defense}</td><td align="right">{two.adaptability}</td><td align="right"><b>{two.power}</b></td></tr>
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Dominance result</h3>
        <div class="grid">
          <div class="metric">Winner<b>{html.escape(result.winner)}</b></div>
          <div class="metric">Round record<b>{stats.ai_one_round_wins}&ndash;{stats.ai_two_round_wins}</b></div>
          <div class="metric">Decisiveness<b>{html.escape(stats.decisiveness)}</b></div>
          <div class="metric">Lead changes<b>{stats.lead_changes}</b></div>
        </div>
        <table>
          <tr><th>Objective</th><td>{html.escape(result.objective)} <span style="color:#555">(rewards {html.escape(result.emphasis)})</span></td></tr>
          <tr><th>{one_name} total</th><td>{result.ai_one_total} <span style="color:#555">({stats.dominance_share_one}% share)</span></td></tr>
          <tr><th>{two_name} total</th><td>{result.ai_two_total} <span style="color:#555">({stats.dominance_share_two}% share)</span></td></tr>
          <tr><th>Predicted by power</th><td>{html.escape(stats.predicted_winner)}{upset_note}</td></tr>
          {comeback_note}
          <tr><th>Summary</th><td>{html.escape(result.summary)}</td></tr>
        </table>
      </div>
      <div class="panel">
        <h3>Match stats</h3>
        <table>
          <thead><tr><th>Metric</th><th>{one_name}</th><th>{two_name}</th></tr></thead>
          <tbody>
            <tr><td>Round wins</td><td align="right">{stats.ai_one_round_wins}</td><td align="right">{stats.ai_two_round_wins}</td></tr>
            <tr><td>Average per round</td><td align="right">{stats.ai_one_avg}</td><td align="right">{stats.ai_two_avg}</td></tr>
            <tr><td>Consistency (lower is steadier)</td><td align="right">{stats.ai_one_consistency}</td><td align="right">{stats.ai_two_consistency}</td></tr>
            <tr><td>Best round</td><td align="right">{stats.ai_one_best_round}</td><td align="right">{stats.ai_two_best_round}</td></tr>
            <tr><td>Longest streak</td><td align="right">{stats.ai_one_longest_streak}</td><td align="right">{stats.ai_two_longest_streak}</td></tr>
          </tbody>
        </table>
        <p>Draws: {stats.draws} &nbsp;|&nbsp; largest margin: {stats.largest_margin} &nbsp;|&nbsp; closest margin: {stats.closest_margin}</p>
      </div>
      {_lead_timeline(result)}
      <div class="panel">
        <h3>Per-challenge breakdown</h3>
        <table>
          <thead><tr><th>Challenge focus</th><th>{one_name}</th><th>{two_name}</th><th>Winner</th></tr></thead>
          <tbody>{''.join(challenge_rows)}</tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Round log</h3>
        <table>
          <thead><tr><th>Round</th><th>Challenge focus</th><th>{one_name}</th><th>{two_name}</th><th>Margin</th><th>Winner</th></tr></thead>
          <tbody>{''.join(round_rows)}</tbody>
        </table>
      </div>
      <div class="panel">JSON API: <code>/api/ai-battle?one={one_name}&amp;two={two_name}&amp;rounds={len(result.rounds)}&amp;seed={html.escape(result.seed)}</code></div>
    """
    return _page("GreyNOC DMZ - AI Battle", body, role=role)


def render_roster(
    statuses: list[tuple[Fighter, AIReadiness]], role: Role = Role.admin
) -> str:
    rows = []
    for fighter, readiness in statuses:
        status_class = "pass" if readiness.status.value == "ready" else "fail"
        rows.append(
            "<tr>"
            f"<td>{html.escape(fighter.name)}</td>"
            f"<td>{html.escape(fighter.provider)}</td>"
            f"<td>{html.escape(fighter.model or 'not set')}</td>"
            f"<td>{html.escape(fighter.token_env or 'none')}</td>"
            f"<td>{'external' if readiness.external else 'local'}</td>"
            f"<td><span class='status {status_class}'>{html.escape(readiness.status.value)}</span></td>"
            f"<td>{html.escape(readiness.detail)}</td>"
            "</tr>"
        )

    body = f"""
      <div class="panel">
        <h3>AI battle roster</h3>
        <p>Fighters that can be fielded in a live or collaborative battle. API keys
        are referenced only by environment-variable name and are read at call time.
        Live battles run from the CLI (<code>greynoc-dmz live-battle</code>,
        <code>greynoc-dmz collab-battle</code>) because they make outbound provider
        calls; this view never contacts a provider.</p>
        <table>
          <thead><tr><th>Name</th><th>Provider</th><th>Model</th><th>Key env</th><th>Endpoint</th><th>Status</th><th>Detail</th></tr></thead>
          <tbody>{''.join(rows) or '<tr><td colspan="7">No fighters configured. Add them to configs/ai-roster.json.</td></tr>'}</tbody>
        </table>
      </div>
      <div class="panel">JSON API: <code>/api/roster</code>. External endpoints show as blocked until a battle is run with <code>--allow-external</code>.</div>
    """
    return _page("GreyNOC DMZ - AI Roster", body, role=role)


def render_coverage(coverage: CoverageReport, role: Role = Role.admin) -> str:
    covered, total = coverage.tactic_coverage_ratio
    tactic_rows = []
    for tactic in coverage.tactics:
        label = "PASS" if tactic.covered else "FAIL"
        status_text = "covered" if tactic.covered else "gap"
        tactic_rows.append(
            "<tr>"
            f"<td>{html.escape(tactic.tactic_id)}</td>"
            f"<td>{html.escape(tactic.name)}</td>"
            f"<td><span class='status {label.lower()}'>{status_text}</span></td>"
            f"<td>{html.escape(', '.join(tactic.rule_ids) or 'none')}</td>"
            "</tr>"
        )

    technique_rows = [
        "<tr>"
        f"<td>{html.escape(technique)}</td>"
        f"<td>{html.escape(', '.join(rule_ids))}</td>"
        "</tr>"
        for technique, rule_ids in coverage.techniques.items()
    ]

    unmapped = html.escape(", ".join(coverage.unmapped_rules) or "none")
    body = f"""
      <div class="panel">
        <h3>MITRE ATT&amp;CK tactic coverage ({covered}/{total})</h3>
        <table>
          <thead><tr><th>Tactic</th><th>Name</th><th>Status</th><th>Rules</th></tr></thead>
          <tbody>{''.join(tactic_rows)}</tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Techniques mapped</h3>
        <table>
          <thead><tr><th>Technique</th><th>Rules</th></tr></thead>
          <tbody>{''.join(technique_rows) or '<tr><td colspan="2">No techniques mapped.</td></tr>'}</tbody>
        </table>
      </div>
      <div class="panel">Rules without a MITRE mapping: <code>{unmapped}</code>. JSON API: <code>/api/coverage</code></div>
    """
    return _page("GreyNOC DMZ - Coverage", body, role=role)


def render_scenario_detail(result: ScenarioResult, auth_enabled: bool, role: Role) -> str:
    status = "PASS" if result.passed else "FAIL"
    alert_rows = []
    for alert in result.alerts:
        alert_rows.append(
            "<tr>"
            f"<td>{html.escape(alert.rule_id)}</td>"
            f"<td>{html.escape(alert.rule_name)}</td>"
            f"<td>{html.escape(alert.severity.value)}</td>"
            f"<td>{html.escape(alert.host)}</td>"
            f"<td>{html.escape(alert.user or 'n/a')}</td>"
            f"<td>{alert.event_count}</td>"
            f"<td>{alert.dwell_seconds:.0f}s</td>"
            f"<td>{html.escape(alert.runbook or 'n/a')}</td>"
            "</tr>"
        )

    incident_rows = []
    for incident in correlate(result.alerts):
        incident_rows.append(
            "<tr>"
            f"<td>{html.escape(incident.host)}</td>"
            f"<td>{html.escape(incident.severity.value)}</td>"
            f"<td>{html.escape(', '.join(incident.rule_ids))}</td>"
            f"<td>{html.escape(', '.join(incident.tactics) or 'none')}</td>"
            f"<td>{incident.alert_count}</td>"
            f"<td>{incident.dwell_seconds:.0f}s</td>"
            "</tr>"
        )
    body = f"""
      <div class="panel"><a href="/">Back to scenarios</a></div>
      <div class="panel">
        <h3>{html.escape(result.scenario_name)}</h3>
        <table>
          <tr><th>Scenario ID</th><td>{html.escape(result.scenario_id)}</td></tr>
          <tr><th>Status</th><td><span class='status {status.lower()}'>{status}</span></td></tr>
          <tr><th>Expected</th><td>{html.escape(", ".join(result.expected_rules) or "none")}</td></tr>
          <tr><th>Fired</th><td>{html.escape(", ".join(result.fired_rules) or "none")}</td></tr>
          <tr><th>Missing</th><td>{html.escape(", ".join(result.missing_rules) or "none")}</td></tr>
          <tr><th>Unexpected</th><td>{html.escape(", ".join(result.unexpected_rules) or "none")}</td></tr>
          <tr><th>Authentication</th><td>{"enabled" if auth_enabled else "disabled"}</td></tr>
        </table>
      </div>
      <div class="panel">
        <h3>Incidents</h3>
        <table>
          <thead><tr><th>Host</th><th>Severity</th><th>Rules</th><th>Tactics</th><th>Alerts</th><th>Dwell</th></tr></thead>
          <tbody>{''.join(incident_rows) or '<tr><td colspan="6">No incidents.</td></tr>'}</tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Alerts</h3>
        <table>
          <thead><tr><th>Rule</th><th>Name</th><th>Severity</th><th>Host</th><th>User</th><th>Events</th><th>Dwell</th><th>Runbook</th></tr></thead>
          <tbody>{"".join(alert_rows) or '<tr><td colspan="8">No alerts fired.</td></tr>'}</tbody>
        </table>
      </div>
    """
    return _page(f"GreyNOC DMZ - {result.scenario_id}", body, role=role)


def serve(root: Path, host: str, port: int) -> None:
    DashboardHandler.root = root
    DashboardHandler.auth_config = load_auth_config()
    DashboardHandler.sessions = SessionStore()
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.serve_forever()
