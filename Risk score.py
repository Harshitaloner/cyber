"""
risk_score.py
-------------
Turns a trace result into a 0-100 risk score PLUS a plain-English rationale.

This is a rule-based / weighted-heuristic scorer -- deliberately simple and
transparent for a prototype. Every commercial competitor (TRM, Elliptic,
Chainalysis) markets "explainable, court-ready" output as a core feature,
so the rationale string matters as much as the number.
"""

from datetime import datetime

TYPOLOGY_WEIGHTS = {
    "rapid_layering": 30,
    "mixer_hop": 35,
    "peeling_chain": 20,
    "standard_mule": 10,
}


def compute_risk_score(trace_result):
    """
    trace_result: the dict returned by tracer.trace_to_exchange()
    Returns: dict with score (0-100), risk_level, and rationale text.
    """
    if not trace_result.get("found"):
        return {
            "score": 0,
            "risk_level": "N/A",
            "rationale": trace_result.get("error", "No trace available."),
        }

    score = 0
    reasons = []

    # --- factor 1: hop count (fewer hops to cash-out = more direct = higher risk) ---
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

    # --- factor 2: typology matched ---
    typologies = trace_result["typologies_seen"]
    typology_score = max(TYPOLOGY_WEIGHTS.get(t, 5) for t in typologies) if typologies else 0
    score += typology_score
    if typologies:
        reasons.append(f"matches known typology: {', '.join(typologies)}")

    # --- factor 3: speed of movement between hops (rapid layering = suspicious) ---
    hop_details = trace_result["hops"]
    if len(hop_details) >= 2:
        try:
            t0 = datetime.fromisoformat(hop_details[0]["timestamp"])
            t_last = datetime.fromisoformat(hop_details[-1]["timestamp"])
            total_minutes = (t_last - t0).total_seconds() / 60
            if total_minutes < 180:  # under 3 hours end-to-end
                score += 25
                reasons.append(f"entire chain completed in {total_minutes:.0f} minutes (rapid movement)")
            elif total_minutes < 1440:  # under 24 hours
                score += 15
                reasons.append(f"chain completed in under 24 hours ({total_minutes/60:.1f} hrs)")
            else:
                score += 5
                reasons.append("chain spread across multiple days")
        except Exception:
            pass

    # --- factor 4: destination is a known/flagged exchange ---
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

    rationale = (
        f"Risk level {level} ({score}/100): " + "; ".join(reasons) + "."
    )

    return {"score": score, "risk_level": level, "rationale": rationale}


if __name__ == "__main__":
    from graph_builder import build_graph
    from tracer import trace_to_exchange
    import pandas as pd
    import os

    G, exchanges = build_graph()
    sample = pd.read_csv(os.path.join("data", "sample_search_wallets.csv"))
    test_wallet = sample["victim_wallet"].iloc[0]

    trace = trace_to_exchange(G, test_wallet, exchanges)
    risk = compute_risk_score(trace)
    print(f"Wallet: {test_wallet}")
    print(f"Score: {risk['score']}  Level: {risk['risk_level']}")
    print(f"Rationale: {risk['rationale']}")
