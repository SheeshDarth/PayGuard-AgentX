"""Enterprise agent-team planning for the retail control centre.

The pipeline remains deterministic and safety-bounded.  A team plan makes the
responsible operating unit explicit for each supervisor route; it is not a
mechanism for giving an LLM authority to buy, pay, or submit anything.
"""

from src.models.product import AgentTeam


TEAM_CATALOG = (
    {
        "team_id": "TEAM_STORE_OPS",
        "name": "Store Operations Team",
        "mission": "Validate store signals, project demand, and identify stockout risk.",
        "agents": ["DQ-Sentinel", "Demand-Forecaster", "Stock-Watcher", "Negotiation"],
        "active_routes": {"restock_only", "full"},
    },
    {
        "team_id": "TEAM_PROCUREMENT",
        "name": "Procurement Integrity Team",
        "mission": "Draft controlled replenishment plans and reconcile supplier invoices.",
        "agents": ["Ops-Planner", "Payment-Auditor", "Regulatory-Auditor", "PO / Dispute Critics"],
        "active_routes": {"restock_only", "audit_only", "full"},
    },
    {
        "team_id": "TEAM_RISK",
        "name": "Risk Intelligence Team",
        "mission": "Investigate suspicious payment relationships and supplier networks.",
        "agents": ["Ring-Auditor"],
        "active_routes": {"ring_only", "audit_only", "full"},
    },
    {
        "team_id": "TEAM_CONTROL",
        "name": "Enterprise Control Team",
        "mission": "Route work, preserve evidence, and hold consequential actions for people.",
        "agents": ["Supervisor", "HITL Controller"],
        "active_routes": {"restock_only", "audit_only", "full", "ring_only", "noop"},
    },
)

ALL_AGENT_NAMES = frozenset(agent for team in TEAM_CATALOG for agent in team["agents"])


def default_teams(workspace_id="demo"):
    return [AgentTeam(team_id=item["team_id"], name=item["name"], mission=item["mission"],
                      agents=item["agents"], workspace_id=workspace_id).model_dump()
            for item in TEAM_CATALOG]


def team_plan(route):
    """Return a serialisable execution plan for one supervisor route."""
    return [{"team_id": item["team_id"], "name": item["name"], "mission": item["mission"],
             "agents": item["agents"],
             "status": "ACTIVE" if route in item["active_routes"] else "STANDBY"}
            for item in TEAM_CATALOG]


def validate_custom_team(name, mission, agents):
    name, mission = str(name or "").strip(), str(mission or "").strip()
    cleaned = [str(agent).strip() for agent in (agents or []) if str(agent).strip()]
    if not 3 <= len(name) <= 80:
        raise ValueError("Team name must contain 3 to 80 characters.")
    if not 10 <= len(mission) <= 280:
        raise ValueError("Team mission must contain 10 to 280 characters.")
    if not 1 <= len(cleaned) <= 8:
        raise ValueError("Choose one to eight existing agents.")
    unknown = set(cleaned) - ALL_AGENT_NAMES
    if unknown:
        raise ValueError("Unknown agent selection: " + ", ".join(sorted(unknown)))
    return name, mission, list(dict.fromkeys(cleaned))
