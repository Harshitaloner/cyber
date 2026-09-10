"""
tracer.py
---------
Core "SIH26183" logic: given a victim-reported suspect wallet, trace forward
through the transaction graph to find the nearest fraud-linked exchange
cash-out point.
"""

import networkx as nx


def trace_to_exchange(G, start_wallet, exchanges):
    """
    Walks forward from start_wallet following transaction edges until it
    reaches a node flagged as a known exchange deposit address.

    Returns a dict with the path, hop count, total typologies seen, and
    the destination exchange -- or an error message if no path exists.
    """
    if start_wallet not in G:
        return {"found": False, "error": f"Wallet '{start_wallet}' not found in graph."}

    # BFS/DFS forward from start_wallet, look for any known exchange node reachable
    reachable_exchanges = [
        addr for addr in exchanges.keys()
        if addr in G and nx.has_path(G, start_wallet, addr)
    ]

    if not reachable_exchanges:
        return {"found": False, "error": "No path to any known exchange found."}

    # pick the CLOSEST exchange (fewest hops) -- most likely real cash-out point
    best_path = None
    best_exchange = None
    for addr in reachable_exchanges:
        path = nx.shortest_path(G, start_wallet, addr)
        if best_path is None or len(path) < len(best_path):
            best_path = path
            best_exchange = addr

    # collect edge details along the path (amounts, timestamps, typology)
    hops = []
    typologies_seen = set()
    for i in range(len(best_path) - 1):
        u, v = best_path[i], best_path[i + 1]
        edge = G.edges[u, v]
        typologies_seen.add(edge["typology"])
        hops.append({
            "from": u,
            "to": v,
            "amount_btc": edge["amount_btc"],
            "timestamp": edge["timestamp"],
            "typology": edge["typology"],
        })

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


if __name__ == "__main__":
    from graph_builder import build_graph
    import pandas as pd
    import os

    G, exchanges = build_graph()
    sample = pd.read_csv(os.path.join("data", "sample_search_wallets.csv"))
    test_wallet = sample["victim_wallet"].iloc[0]

    result = trace_to_exchange(G, test_wallet, exchanges)
    print(f"Tracing wallet: {test_wallet}")
    print(result)
