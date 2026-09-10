"""
graph_builder.py
-----------------
Loads synthetic_cases.csv into a NetworkX directed graph.
Nodes = wallet addresses. Edges = transactions (amount, timestamp, typology).

This is intentionally simple (in-memory NetworkX, not Neo4j) -- correct
choice for a hackathon prototype. Swap in Neo4j later if this becomes a
real product.
"""

import os
import pandas as pd
import networkx as nx

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_known_exchanges():
    """Returns dict: {deposit_address: exchange_name}"""
    df = pd.read_csv(os.path.join(DATA_DIR, "known_exchanges.csv"))
    return dict(zip(df["deposit_address"], df["exchange_name"]))


def build_graph():
    """Builds and returns a directed graph from the synthetic transaction CSV."""
    df = pd.read_csv(os.path.join(DATA_DIR, "synthetic_cases.csv"))
    exchanges = load_known_exchanges()

    G = nx.DiGraph()

    for _, row in df.iterrows():
        from_w, to_w = row["from_wallet"], row["to_wallet"]

        # tag node types for the UI (victim / mule / exchange)
        if from_w not in G:
            G.add_node(from_w, node_type="victim" if row["hop_type"] == "victim" else "mule")
        if to_w not in G:
            is_exchange = to_w in exchanges
            G.add_node(
                to_w,
                node_type="exchange" if is_exchange else "mule",
                exchange_name=exchanges.get(to_w, None),
            )

        G.add_edge(
            from_w, to_w,
            amount_btc=row["amount_btc"],
            timestamp=row["timestamp"],
            typology=row["typology"],
            case_id=row["case_id"],
        )

    return G, exchanges


if __name__ == "__main__":
    G, exchanges = build_graph()
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Known exchange deposit addresses loaded: {len(exchanges)}")
