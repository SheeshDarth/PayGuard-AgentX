"""
PayGuard-AgentX web UI server.

Serves the operator dashboard (static HTML/CSS/JS in web/static) and a small
JSON API over the existing supervised pipeline. Built on http.server from the
standard library: no web framework, no new dependency, nothing to install.

Run:  python -m web.server        ->  http://127.0.0.1:8000

Endpoints
  GET  /api/bootstrap                 product metadata, scenarios, status, records
  POST /api/run       {scenario}      run a scenario, return the derived payload
  POST /api/decide    {kind,id,action,role}   record a signed operator decision
  POST /api/verify    {evidence_id,tamper}    re-verify a dossier signature
  POST /api/reset                     clear the demo workspace
  GET  /api/records                   stored runs / alerts / cases / decisions / evidence

Binds to loopback only. Everything runs offline: no API key, no GPU, no network.
"""

import json
import mimetypes
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.services.auth import ROLES, can, capability_matrix, current_user  # noqa: E402
from dashboard.services.config import load_settings                             # noqa: E402
from dashboard.services.session import (                                        # noqa: E402
    current_state, latest_records, record_operator_decision, reset as reset_workspace,
    run_and_save,
)
from dashboard.services.storage import get_storage                              # noqa: E402
from dashboard.services.workflows import (                                      # noqa: E402
    DEMO_SCENARIOS, agent_timeline, pending_actions, plain_alerts, ring_chain, ring_edges,
    system_status, why_flagged,
)
from src.core import audit                                                      # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
MAX_REQUEST_BYTES = 1_048_576

PRODUCT = {
    "name": "PayGuard-AgentX",
    "tagline": "Agentic Retail Operations + Procurement Integrity Copilot",
    "lede": ("AI agents analyze inventory, procurement, invoices, and supplier activity to "
             "recommend operational actions while keeping consequential financial decisions "
             "under human control."),
}

AGENTS = [
    {"name": "Supervisor", "purpose": "Chooses the smallest route needed for this input.",
     "type": "Orchestrator", "authority": "Routes only; never approves money."},
    {"name": "DQ-Sentinel", "purpose": "Rejects malformed, incomplete, or corrupted records before analysis.",
     "type": "Deterministic", "authority": "Data-quality gate."},
    {"name": "Demand-Forecaster", "purpose": "Estimates near-term demand for each store and product.",
     "type": "Analyst", "authority": "Recommendation only."},
    {"name": "Stock-Watcher", "purpose": "Finds products below reorder point or expected demand.",
     "type": "Analyst", "authority": "Recommendation only."},
    {"name": "Ops-Planner", "purpose": "Drafts a replenishment purchase order with rationale and cost.",
     "type": "Planner", "authority": "Human approval required."},
    {"name": "Payment-Auditor", "purpose": "Reconciles supplier invoices against purchase orders.",
     "type": "Auditor", "authority": "Drafts disputes; no payment execution."},
    {"name": "Regulatory-Auditor", "purpose": "Cites the relevant procurement or compliance clause.",
     "type": "Knowledge", "authority": "Evidence support only."},
    {"name": "Ring-Auditor", "purpose": "Detects circular payments and shell-supplier networks.",
     "type": "Graph analyst", "authority": "Human escalation required."},
    {"name": "PO / Dispute Critics", "purpose": "Review draft quality before anything reaches a human queue.",
     "type": "Reflection", "authority": "Can revise drafts; cannot execute."},
    {"name": "HITL Controller", "purpose": "Holds every consequential action for an operator decision.",
     "type": "Safety", "authority": "Terminates in signed human disposition."},
]


# --------------------------------------------------------------- payload shaping
def _decided(records):
    return {(d.get("subject_kind"), d.get("subject_id")) for d in records["decisions"]}


def _open_alerts(state, records):
    """Open alerts, scoped to the current run once one exists -- alerts are never
    auto-closed, so showing every historical alert would attribute an earlier
    run's findings to the one on screen."""
    alerts = [a for a in records["alerts"] if a.get("status", "OPEN") == "OPEN"]
    if state and state.get("run_id"):
        return [a for a in alerts if a.get("run_id") == state["run_id"]]
    return alerts


def _subject(state, kind, subject_id):
    if kind == "PO":
        po = state.get("po_draft") or {}
        return po if po.get("po_id") == subject_id else {}
    if kind == "DISPUTE":
        return next((d for d in state.get("dispute_drafts", [])
                     if d["dispute_id"] == subject_id), {})
    return next((r for r in state.get("mule_rings", []) if r["ring_id"] == subject_id), {})


def _valid_decision_subject(state, kind, subject_id, action):
    """Validate both the subject and the only disposition verbs it supports."""
    allowed = {
        "PO": {"APPROVED", "REJECTED"},
        "DISPUTE": {"APPROVED", "REJECTED"},
        "RING": {"ESCALATED", "DISMISSED"},
    }
    if kind not in allowed or action not in allowed[kind]:
        return False
    return bool(_subject(state, kind, subject_id))


def _fraud_block(state):
    rings = []
    for ring in state.get("mule_rings", []):
        edges = ring_edges(state, ring)
        chain, closes = ring_chain(ring, edges)
        members = []
        for member in ring["member_accounts"]:
            acc = next((a for a in state.get("mule_suspicious_accounts", [])
                        if a["account_id"] == member), None)
            members.append({"account_id": member,
                            "score": acc["suspicion_score"] if acc else None,
                            "patterns": acc["detected_patterns"] if acc else []})
        rings.append({**ring, "chain": chain, "closes_cycle": closes, "members": members,
                      "edges": edges,
                      "why": why_flagged(state, "RING", ring["ring_id"])})
    return {
        "rings": rings,
        "accounts": state.get("mule_suspicious_accounts", []),
        "transactions": state.get("mule_transactions", []),
        "payroll_flagged": any(a["account_id"] == "PAYROLL"
                               for a in state.get("mule_suspicious_accounts", [])),
        "scan_truncated": bool(state.get("mule_scan_truncated")),
    }


def run_payload(state, records):
    """Everything the browser needs for one run, derived from the run's own state."""
    if not state:
        return None
    decided = _decided(records)
    actions = []
    for action in pending_actions(state, decided):
        entry = {**action,
                 "why": why_flagged(state, action["kind"], action["id"]),
                 "raw": _subject(state, action["kind"], action["id"])}
        if action["kind"] == "RING":
            ring = _subject(state, "RING", action["id"])
            chain, closes = ring_chain(ring, ring_edges(state, ring))
            entry["chain"], entry["closes_cycle"] = chain, closes
        actions.append(entry)

    po = state.get("po_draft")
    flags = [f for f in state.get("payment_flags", []) if f.get("flag_type") != "CLEAN"]
    return {
        "run_id": state.get("run_id"), "preset": state.get("preset"),
        "route": state.get("route"), "logs": state.get("logs", []),
        "timeline": agent_timeline(state),
        "actions": actions,
        "alerts": _open_alerts(state, records),
        "kpis": {
            "processed": (len(state.get("valid_sales", []))
                          + len(state.get("valid_inventory", []))
                          + len(state.get("valid_invoices", []))),
            "fraud_flags": len(flags) + len(state.get("mule_rings", [])),
            "pending": len(actions),
            "quarantined": len(state.get("rejected", [])),
            "evidence": len(records["evidence"]),
        },
        "operations": {
            "stock_alerts": state.get("stock_alerts", []),
            "po": po,
            "po_why": why_flagged(state, "PO", po["po_id"]) if po else None,
            "flags": [{**f, "why": why_flagged(state, "INVOICE", f["invoice_id"])}
                      for f in flags],
            "clean_invoices": len([f for f in state.get("payment_flags", [])
                                   if f.get("flag_type") == "CLEAN"]),
            "rejected": state.get("rejected", []),
        },
        "fraud": _fraud_block(state),
        "dataset": {"label": state.get("dataset_label", "Synthetic demo data"),
                    "lineage": state.get("data_lineage", "Generated locally by the retail simulator."),
                    "source_rows": state.get("source_rows")},
    }


def records_payload(records):
    return {
        "alerts": records["alerts"],
        "cases": records["cases"],
        "decisions": records["decisions"],
        # The full state is retained server-side for restart recovery, but the
        # browser only needs run summaries. This keeps payloads bounded and
        # avoids leaking raw transaction detail into every API response.
        "runs": [{k: v for k, v in run.items() if k != "state"} for run in records["runs"]],
        "evidence": [{"evidence_id": e["evidence_id"], "subject_id": e["subject_id"],
                      "evidence_type": e["evidence_type"], "summary": e.get("summary", ""),
                      "dossier": e["dossier"],
                      "valid": audit.verify_dossier_dict(e["dossier"])}
                     for e in records["evidence"]],
        "audit_events": records.get("audit_events", []),
    }


def bootstrap_payload(role=None):
    storage = get_storage()
    records = latest_records(storage)
    settings = load_settings()
    user = current_user(role)
    return {
        "product": PRODUCT,
        "agents": AGENTS,
        "scenarios": [{"id": name, **meta} for name, meta in DEMO_SCENARIOS.items()],
        "status": system_status(storage),
        "user": user.model_dump(),
        "roles": ROLES,
        "demo_mode": settings.demo_mode,
        "capabilities": capability_matrix(),
        "records": records_payload(records),
        "run": run_payload(current_state(), records),
    }


# ------------------------------------------------------------------- HTTP layer
class Handler(BaseHTTPRequestHandler):
    server_version = "PayGuard/1.0"

    def log_message(self, fmt, *args):
        """Log API calls and anything that is not a plain 200, and stay quiet about
        static asset hits. args[0] is the request line for log_request but an int
        status for log_error, so it is coerced before being searched."""
        line = str(args[0]) if args else ""
        if "/api/" in line or "code" in fmt:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # -- helpers
    def _send(self, status, body, content_type="application/json", extra=None):
        """Write a response, tolerating a client that has already gone away --
        a browser navigating mid-request must not take a worker thread down."""
        try:
            self._write(status, body, content_type, extra)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _write(self, status, body, content_type, extra):
        raw = body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        # This UI loads nothing from anywhere else; say so explicitly.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; base-uri 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Invalid Content-Length")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large")
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # -- routing
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        try:
            if path.startswith("/api/"):
                return self._api_get(path)
            return self._static(path)
        except Exception:
            traceback.print_exc()
            self._send(500, {"error": "The server could not complete that request."})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            return self._api_post(path, self._body())
        except Exception as exc:
            traceback.print_exc()          # full detail stays in the log
            if isinstance(exc, FileNotFoundError):
                self._send(424, {"error": "The selected dataset is not installed. "
                                 "Run python scripts\\download_walmart_data.py and try again.",
                                 "detail": repr(exc)})
                return
            self._send(500, {"error": "That request could not be completed. The "
                                      "application stays in offline mode and your "
                                      "previous results are unchanged.",
                             "detail": repr(exc)})

    def _api_get(self, path):
        if path == "/api/bootstrap":
            return self._send(200, bootstrap_payload())
        if path == "/api/records":
            return self._send(200, records_payload(latest_records(get_storage())))
        return self._send(404, {"error": "Unknown endpoint."})

    def _api_post(self, path, body):
        storage = get_storage()
        if path == "/api/run":
            scenario = body.get("scenario")
            if scenario not in DEMO_SCENARIOS:
                return self._send(400, {"error": "Unknown scenario."})
            state = run_and_save(scenario, storage)
            records = latest_records(storage)
            return self._send(200, {"run": run_payload(state, records),
                                    "records": records_payload(records)})

        if path == "/api/decide":
            state = current_state()
            if not state:
                return self._send(409, {"error": "No analysis is loaded. Run a scenario first."})
            kind, subject_id = body.get("kind"), body.get("id")
            action = body.get("action")
            if action not in {"APPROVED", "REJECTED", "ESCALATED", "DISMISSED"}:
                return self._send(400, {"error": "Unknown action."})
            if not _valid_decision_subject(state, kind, subject_id, action):
                return self._send(400, {"error": "Decision action or subject is invalid for this run."})
            user = current_user(body.get("role"))
            capability = "review_fraud" if kind == "RING" else "approve_po"
            # Authorization is decided here, never in the browser.
            if not can(user, capability):
                return self._send(403, {"error": f"Role {user.role} cannot decide this item."})
            record_operator_decision(storage, user, kind, subject_id, action, state)
            records = latest_records(storage)
            return self._send(200, {"run": run_payload(state, records),
                                    "records": records_payload(records)})

        if path == "/api/verify":
            evidence = next((e for e in latest_records(storage)["evidence"]
                             if e["evidence_id"] == body.get("evidence_id")), None)
            if not evidence:
                return self._send(404, {"error": "No such evidence record."})
            dossier = json.loads(json.dumps(evidence["dossier"], default=str))
            if body.get("tamper"):
                dossier["payload"]["_injected"] = "attacker-controlled"
            return self._send(200, {"valid": audit.verify_dossier_dict(dossier),
                                    "dossier": dossier, "tampered": bool(body.get("tamper"))})

        if path == "/api/reset":
            settings = load_settings()
            user = current_user(body.get("role"))
            if not settings.demo_mode and not can(user, "manage_settings"):
                return self._send(403, {"error": "Only an administrator can reset a published workspace."})
            reset_workspace(storage)
            return self._send(200, {"records": records_payload(latest_records(storage)),
                                    "run": None})

        if path == "/api/bootstrap":
            return self._send(200, bootstrap_payload(body.get("role")))

        return self._send(404, {"error": "Unknown endpoint."})

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / rel).resolve()
        # Never serve outside the static directory, whatever the URL claims.
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            return self._send(404, b"Not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)


def serve(host="127.0.0.1", port=8000):
    httpd = ThreadingHTTPServer((host, port), Handler)
    print("=" * 70)
    print("PayGuard-AgentX -- operator dashboard")
    print("=" * 70)
    print(f"  http://{host}:{port}")
    print("  Offline: no API key, no GPU, no network. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
