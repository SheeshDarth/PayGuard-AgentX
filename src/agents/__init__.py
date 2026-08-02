"""ShelfGuard-AgentX agent pipeline."""
from src.agents.pipeline import (
    ShelfGuardState,
    dq_sentinel,
    demand_forecaster,
    stock_watcher,
    ops_planner,
    payment_auditor,
    run_pipeline,
    build_graph,
    AGENTS,
)
