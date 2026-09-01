import streamlit as st

from dashboard.services.session import current_state
from dashboard.ui.components import empty_state, technical_details
from dashboard.ui.navigation import shell

user, storage = shell("Operations", "Manage stock, purchase orders, and supplier invoices.")
state = current_state()
if not state:
    empty_state("No analysis yet", "Open Action Inbox and run the Procurement mismatch scenario.")
    st.stop()

alerts = state.get("stock_alerts", [])
po = state.get("po_draft")
c1, c2, c3 = st.columns(3)
c1.metric("Low-stock items", len(alerts))
c2.metric("Suggested order", "Yes" if po else "No")
c3.metric("Invoice flags", len([f for f in state.get("payment_flags", []) if f.get("flag_type") != "CLEAN"]))

st.subheader("Inventory and replenishment")
if alerts:
    st.dataframe([{"SKU": a["sku"], "Store": a["store_id"], "On hand": a["on_hand"],
                   "Recommended order": a["recommend_order_qty"], "Why": a["rationale"]} for a in alerts],
                 use_container_width=True, hide_index=True)
else:
    empty_state("Inventory looks healthy", "No items are currently below their reorder point.")

st.subheader("Purchase order")
if po:
    st.write(f"**{po['po_id']}** · {po['total_estimated_cost']} {po['currency']} · **Needs human approval**")
    st.dataframe(po["lines"], use_container_width=True, hide_index=True)
    technical_details("Why this order was suggested", po)
else:
    empty_state("No purchase order", "No replenishment is required for this run.")

st.subheader("Supplier invoice checks")
for flag in state.get("payment_flags", []):
    if flag.get("flag_type") != "CLEAN":
        st.warning(f"{flag['flag_type'].replace('_', ' ').title()}: {flag['description']}")

