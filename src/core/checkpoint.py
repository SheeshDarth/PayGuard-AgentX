"""
LangGraph checkpointer factory for PayGuard-AgentX (short-term run memory).

Returns a SqliteSaver when langgraph-checkpoint-sqlite is installed, else None so
callers degrade to no persistence rather than crashing. On the demo laptop this
gives every agent in a run visibility into what earlier agents decided.
"""


def get_checkpointer(path="checkpoints.sqlite"):
    try:
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    except Exception:
        return None
