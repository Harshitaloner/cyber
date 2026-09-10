import os
import csv
import random
import string
from datetime import datetime, timedelta

import pandas as pd
import networkx as nx
import streamlit as st
from pyvis.network import Network
import streamlit.components.v1 as components

# =============================================================================
# 0. SETUP PATHS & AUTOMATIC DATA GENERATION
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

EXCHANGE_CSV = os.path.join(DATA_DIR, "known_exchanges.csv")
CASES_CSV = os.path.join(DATA_DIR, "synthetic_cases.csv")
SAMPLE_WALLETS_CSV = os.path.join(DATA_DIR, "sample_search_wallets.csv")


def ensure_synthetic_data_exists():
    """Generates synthetic dataset if CSV files are not already present."""
    if (
        os.path.exists(EXCHANGE_CSV)
        and os.path.exists(CASES_CSV)
        and os.path.exists(SAMPLE_WALLETS_CSV)
    ):
        return

    random.seed(42)

    EXCHANGE_NAMES = [
        "ExchangeA-Deposit",
        "ExchangeB-Deposit",
        "ExchangeC-Deposit",
        "ExchangeD-Deposit",
        "ExchangeE-Deposit",
    ]

    def fake_wallet(prefix="bc1"):
        chars = string.ascii_lowercase + string.digits
        return prefix + "".join(random.choices(chars, k=20))

    known_exchanges = []
    exchange_wallets = []
    for name in EXCHANGE_NAMES:
        addr = fake_wallet(prefix="exch_")
        exchange_wallets.append(addr)
        known_exchanges.append({"exchange_name": name, "deposit_address": addr})

    with open(EXCHANGE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["exchange_name", "deposit_address"])
        writer.writeheader()
        writer.writerows(known_exchanges)

    TYPOLOGIES = ["rapid_layering", "peeling_chain", "mixer_hop", "standard_mule"]
    rows = []
    case_id = 1
    victim_start_wallets = []

    for _ in range(30):
        victim_wallet = fake_wallet(prefix="victim_")
        victim_start_wallets.append(victim_wallet)

        num_hops = random.choice([2, 3, 3, 4])
        typology = random.choice(TYPOLOGIES)

        if typology == "rapid_layering":
            gap = timedelta(minutes=random.randint(10, 90))
        else:
            gap = timedelta(hours=random.randint(2, 48))

        timestamp = datetime(
            2026,
            random.randint(1, 8),
            random.randint(1, 28),
            random.randint(0, 23),
            random.randint(0, 59),
        )

        chain_wallets = [victim_wallet]
        for h in range(num_hops - 1):
            chain_wallets.append(fake_wallet(prefix="mule_"))

        final_exchange = random.choice(exchange_wallets)
        chain_wallets.append(final_exchange)

        amount = round(random.uniform(0.05, 4.5), 4)

        for i in range(len(chain_wallets) - 1):
            from_w = chain_wallets[i]
            to_w = chain_wallets[i + 1]
            is_last_hop = i == len(chain_wallets) - 2

            rows.append(
                {
                    "case_id": case_id,
                    "from_wallet": from_w,
                    "to_wallet": to_w,
                    "amount_btc": amount,
                    "timestamp": timestamp.isoformat(),
                    "hop_type": (
                        "exchange"
                        if is_last_hop
                        else ("victim" if i == 0 else "mule")
                    ),
                    "typology": typology,
                }
            )
            timestamp += gap
            amount = round(amount * random.uniform(0.85, 0.98), 4)

        case_id += 1

    with open(CASES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "from_wallet",
                "to_wallet",
                "amount_btc",
                "timestamp",
                "hop_type",
                "typology",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    with open(SAMPLE_WALLETS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["victim_wallet"])
        for w in victim_start_wallets[:8]:
            writer.writerow([w])


# Ensure sample dataset is ready
ensure_synthetic_data_exists()

# =============================================================================
# 1. GRAPH BUILDER & TRACER ENGINE
# =============================================================================
def load_known_exchanges():
    """Returns dict: {deposit_address: exchange_name}"""
    df = pd.read_csv(EXCHANGE_CSV)
    return dict(zip(df["deposit_address"], df["exchange_name"]))


def build_graph():
    """Builds and returns a directed networkx graph from synthetic cases."""
    df = pd.read_csv(CASES_CSV)
    exchanges = load_known_exchanges()

    G = nx.DiGraph()

    for _, row in df.iterrows():
        from_w, to_w = row["from_wallet"], row["to_wallet"]

        if from_w not in G:
            G.add_node(
                from_w,
                node_type="victim" if row["hop_type"] == "victim" else "mule",
            )
        if to_w not in G:
            is_exchange = to_w in exchanges
            G.add_node(
                to_w,
                node_type="exchange" if is_exchange else "mule",
                exchange_name=exchanges.get(to_w, None),
            )

        G.add_edge(
            from_w,
            to_w,
            amount_btc=row["amount_btc"],
            timestamp=row["timestamp"],
            typology=row["typology"],
            case_id=row["case_id"],
        )

    return G, exchanges


def trace_to_exchange(G, start_wallet, exchanges):
    """Traces forward from start_wallet to find the nearest exchange deposit."""
    if start_wallet not in G:
        return {
            "found": False,
            "error": f"Wallet '{start_wallet}' not found in current graph.",
        }

    reachable_exchanges = [
        addr
        for addr in exchanges.keys()
        if addr in G and nx.has_path(G, start_wallet, addr)
    ]

    if not reachable_exchanges:
        return {"found": False, "error": "No path to any known exchange found."}

    best_path = None
    best_exchange = None
    for addr in reachable_exchanges:
        path = nx.shortest_path(G, start_wallet, addr)
        if best_path is None or len(path) < len(best_path):
            best_path = path
            best_exchange = addr

    hops = []
    typologies_seen = set()
    for i in range(len(best_path) - 1):
        u, v = best_path[i], best_path[i + 1]
        edge = G.edges[u, v]
        typologies_seen.add(edge["typology"])
        hops.append(
            {
                "from": u,
                "to": v,
                "amount_btc": edge["amount_btc"],
                "timestamp": edge["timestamp"],
                "typology": edge["typology"],
            }
        )

    return {
        "found": True,
        "start_wallet": start_wallet,
        "destination_exchange_address": best_exchange,
        "destination_exchange_name": exchanges.get(best_exchange, "Unknown"),
        "num_hops": len(best_path) - 1,
        "path": best_path,
        "hops": hops,
        "typologies_seen": list(typologies_seen),
    }


# =============================================================================
# 2. RISK SCORING ENGINE
# =============================================================================
TYPOLOGY_WEIGHTS = {
    "rapid_layering": 30,
    "mixer_hop": 35,
    "peeling_chain": 20,
    "standard_mule": 10,
}


def compute_risk_score(trace_result):
    """Calculates risk score (0-100) and plain-English rationale."""
    if not trace_result.get("found"):
        return {
            "score": 0,
            "risk_level": "N/A",
            "rationale": trace_result.get("error", "No trace available."),
        }

    score = 0
    reasons = []

    # Hop count weighting
    hops = trace_result["num_hops"]
    if hops <= 2:
        score += 30
        reasons.append(f"only {hops} hop(s) to cash-out (direct, low-obfuscation path)")
    elif hops == 3:
        score += 20
        reasons.append(f"{hops} hops to cash-out (moderate layering)")
    else:
        score += 10
        reasons.append(f"{hops} hops to cash-out (heavier layering, still traceable)")

    # Typology weighting
    typologies = trace_result["typologies_seen"]
    typology_score = (
        max(TYPOLOGY_WEIGHTS.get(t, 5) for t in typologies) if typologies else 0
    )
    score += typology_score
    if typologies:
        reasons.append(f"matches known typology: {', '.join(typologies)}")

    # Time speed weighting
    hop_details = trace_result["hops"]
    if len(hop_details) >= 2:
        try:
            t0 = datetime.fromisoformat(hop_details[0]["timestamp"])
            t_last = datetime.fromisoformat(hop_details[-1]["timestamp"])
            total_minutes = (t_last - t0).total_seconds() / 60
            if total_minutes < 180:
                score += 25
                reasons.append(
                    f"entire chain completed in {total_minutes:.0f} minutes (rapid movement)"
                )
            elif total_minutes < 1440:
                score += 15
                reasons.append(
                    f"chain completed in under 24 hours ({total_minutes/60:.1f} hrs)"
                )
            else:
                score += 5
                reasons.append("chain spread across multiple days")
        except Exception:
            pass

    # Destination match weighting
    score += 15
    reasons.append(
        f"terminal address matches known deposit address for "
        f"{trace_result['destination_exchange_name']}"
    )

    score = min(score, 100)

    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    rationale = f"Risk level {level} ({score}/100): " + "; ".join(reasons) + "."

    return {"score": score, "risk_level": level, "rationale": rationale}


# =============================================================================
# 3. STREAMLIT UI DASHBOARD
# =============================================================================
st.set_page_config(page_title="Blockchain Forensics Prototype", layout="wide")


@st.cache_resource
def get_graph():
    return build_graph()


G, exchanges = get_graph()
sample_wallets = pd.read_csv(SAMPLE_WALLETS_CSV)

st.title("🔎 Blockchain Forensics Prototype — Wallet-to-Exchange Tracer")
st.caption(
    "SIH26183 prototype · Real-Time Identification of Fraud-Linked Cryptocurrency "
    "Exchanges from Victim-Reported Suspect Wallet Addresses"
)
st.warning(
    "⚠️ DEMO DATA ONLY. All wallet addresses, exchange names, and transaction "
    "chains on this page are synthetically generated for demonstration purposes."
)

st.subheader("1. Enter a victim-reported suspect wallet")

col1, col2 = st.columns([3, 1])
with col1:
    wallet_input = st.text_input(
        "Wallet address",
        placeholder="e.g. " + sample_wallets["victim_wallet"].iloc[0],
    )
with col2:
    st.write("")
    st.write("")
    use_sample = st.selectbox(
        "Or pick a sample victim wallet",
        [""] + sample_wallets["victim_wallet"].tolist(),
    )

wallet_to_trace = wallet_input.strip() or use_sample

if st.button("Trace wallet ➜ exchange", type="primary") or wallet_to_trace:
    if not wallet_to_trace:
        st.info("Enter or select a wallet address above.")
    else:
        trace = trace_to_exchange(G, wallet_to_trace, exchanges)

        if not trace["found"]:
            st.error(trace["error"])
        else:
            risk = compute_risk_score(trace)

            st.subheader("2. Trace result")
            m1, m2, m3 = st.columns(3)
            m1.metric("Destination exchange", trace["destination_exchange_name"])
            m2.metric("Hops to cash-out", trace["num_hops"])
            m3.metric("Risk score", f"{risk['score']}/100", risk["risk_level"])

            st.subheader("3. Risk rationale (explainable output)")
            if risk["risk_level"] == "HIGH":
                st.error(risk["rationale"])
            elif risk["risk_level"] == "MEDIUM":
                st.warning(risk["rationale"])
            else:
                st.info(risk["rationale"])

            st.subheader("4. Transaction path")
            hops_df = pd.DataFrame(trace["hops"])
            st.dataframe(hops_df, use_container_width=True)

            st.subheader("5. Money-flow graph")
            net = Network(
                height="500px",
                width="100%",
                directed=True,
                bgcolor="#111111",
                font_color="white",
            )

            for node in trace["path"]:
                node_type = G.nodes[node].get("node_type", "mule")
                if node_type == "victim":
                    color = "#e74c3c"
                elif node_type == "exchange":
                    color = "#2ecc71"
                else:
                    color = "#3498db"
                label = G.nodes[node].get("exchange_name") or node[:14] + "..."
                net.add_node(node, label=label, color=color, title=node)

            for hop in trace["hops"]:
                net.add_edge(
                    hop["from"],
                    hop["to"],
                    title=f"{hop['amount_btc']} BTC @ {hop['timestamp']} ({hop['typology']})",
                    label=f"{hop['amount_btc']} BTC",
                )

            net.set_options(
                """
            var options = {
              "physics": {"enabled": true, "solver": "forceAtlas2Based"},
              "edges": {"arrows": {"to": {"enabled": true}}}
            }
            """
            )

            html_path = os.path.join(DATA_DIR, "_graph_tmp.html")
            net.save_graph(html_path)
            with open(html_path, "r", encoding="utf-8") as f:
                components.html(f.read(), height=520)

            st.caption(
                "🔴 Victim wallet · 🔵 Mule/intermediate wallet · 🟢 Exchange deposit address"
            )

st.divider()
st.caption(
    "Prototype only. Wallet attribution is probabilistic, not definitive identity "
    "attribution. Off-chain evidence and legal process are required for real "
    "attribution. Built on synthetic data — not connected to any live government "
    "system."
)
