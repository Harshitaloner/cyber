# Blockchain Forensics Prototype — SIH26183

Traces a victim-reported suspect crypto wallet forward through a transaction
graph to the nearest fraud-linked exchange cash-out point, and produces an
explainable risk score.

**Uses 100% synthetic data.** No real blockchain, NCRP, or FIU-IND data.

## What's in here

| File | Purpose |
|---|---|
| `generate_data.py` | Creates synthetic victim → mule → exchange transaction chains |
| `graph_builder.py` | Loads the CSV data into a NetworkX directed graph |
| `tracer.py` | Finds the shortest path from a suspect wallet to a known exchange |
| `risk_score.py` | Scores the traced path 0–100 with a plain-English rationale |
| `app.py` | Streamlit dashboard tying it all together with a graph visualization |

## Setup (do this once)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

## Run it

```bash
# 1. Generate the synthetic dataset (creates data/*.csv)
python generate_data.py

# 2. (optional) sanity-check the pipeline in the terminal
python graph_builder.py
python tracer.py
python risk_score.py

# 3. Launch the dashboard
streamlit run app.py
```

This opens a browser tab. Pick a sample victim wallet from the dropdown (or
paste one from `data/sample_search_wallets.csv`) and click **Trace wallet ➜
exchange**.

## Demo script (for judges)

1. "This is SIH26183 — victim reports a suspect wallet, we trace it to the
   exchange it cashed out through."
2. Paste/select a sample wallet → click trace.
3. Point at the risk score and rationale — "this is explainable, not a black
   box — every commercial vendor in this space (TRM, Elliptic, Chainalysis)
   markets explainability as a core feature, so we built it in from day one."
4. Point at the graph — victim (red) → mule hops (blue) → exchange (green).
5. Say plainly: "This runs on synthetic data modeling real reported
   typologies — mule-account layering, rapid movement, exchange cash-out.
   Real NCRP/FIU-IND integration would require an MoU we don't have as a
   student team, so we've mocked that boundary clearly rather than
   overclaiming live access."

## Honest scope (say this out loud, judges respect it)

- Wallet clustering, GNN-based anomaly detection, and live data integration
  are **not** implemented — this prototype focuses on one sharp slice
  (path-tracing + explainable scoring) end-to-end rather than many features
  half-built.
- The risk scorer is rule-based, not a trained ML model. That's a deliberate
  prototype choice for transparency and speed — a next iteration would
  validate a trained model (XGBoost vs GNN) against a temporal holdout on
  the Elliptic++ dataset before replacing this logic.
