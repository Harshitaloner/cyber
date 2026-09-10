"""
generate_data.py
-----------------
Creates a SYNTHETIC dataset that simulates the real-world typology described
in Indian cybercrime cases: victim -> mule wallet(s) -> exchange cash-out.

This data is entirely fake / randomly generated. It is NOT real blockchain
data. It exists so we can demo the graph-tracing and risk-scoring logic
without needing real NCRP/FIU-IND access (which a hackathon team won't have).

Run:
    python generate_data.py
Produces:
    data/synthetic_cases.csv
    data/known_exchanges.csv
"""

import random
import string
import csv
import os
from datetime import datetime, timedelta

random.seed(42)  # reproducible demo data

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Fake "known exchange" deposit addresses
#    (fictional names -- do NOT present these as real company data)
# ---------------------------------------------------------------------------
EXCHANGE_NAMES = [
    "ExchangeA-Deposit", "ExchangeB-Deposit", "ExchangeC-Deposit",
    "ExchangeD-Deposit", "ExchangeE-Deposit",
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

with open(os.path.join(OUT_DIR, "known_exchanges.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["exchange_name", "deposit_address"])
    writer.writeheader()
    writer.writerows(known_exchanges)

# ---------------------------------------------------------------------------
# 2. Generate synthetic fraud chains
#    Each case: victim_wallet -> mule_1 -> (mule_2) -> (mule_3) -> exchange
#    hop_type marks what kind of node is on the RECEIVING end of that edge
# ---------------------------------------------------------------------------
TYPOLOGIES = ["rapid_layering", "peeling_chain", "mixer_hop", "standard_mule"]

rows = []
case_id = 1
victim_start_wallets = []  # so app.py demo can suggest a wallet to search

for _ in range(30):  # 30 synthetic cases
    victim_wallet = fake_wallet(prefix="victim_")
    victim_start_wallets.append(victim_wallet)

    num_hops = random.choice([2, 3, 3, 4])  # most chains are 3 hops
    typology = random.choice(TYPOLOGIES)

    # fast layering = hops happen within hours; slower = days
    if typology == "rapid_layering":
        gap = timedelta(minutes=random.randint(10, 90))
    else:
        gap = timedelta(hours=random.randint(2, 48))

    current_wallet = victim_wallet
    timestamp = datetime(2026, random.randint(1, 8), random.randint(1, 28),
                          random.randint(0, 23), random.randint(0, 59))

    chain_wallets = [victim_wallet]
    for h in range(num_hops - 1):
        next_wallet = fake_wallet(prefix="mule_")
        chain_wallets.append(next_wallet)

    # last hop always goes to a known exchange (that's the "cash-out")
    final_exchange = random.choice(exchange_wallets)
    chain_wallets.append(final_exchange)

    amount = round(random.uniform(0.05, 4.5), 4)  # fake BTC amount

    for i in range(len(chain_wallets) - 1):
        from_w = chain_wallets[i]
        to_w = chain_wallets[i + 1]
        is_last_hop = (i == len(chain_wallets) - 2)

        rows.append({
            "case_id": case_id,
            "from_wallet": from_w,
            "to_wallet": to_w,
            "amount_btc": amount,
            "timestamp": timestamp.isoformat(),
            "hop_type": "exchange" if is_last_hop else ("victim" if i == 0 else "mule"),
            "typology": typology,
        })
        timestamp = timestamp + gap
        # amount shrinks slightly each hop (layering fee / peeling)
        amount = round(amount * random.uniform(0.85, 0.98), 4)

    case_id += 1

with open(os.path.join(OUT_DIR, "synthetic_cases.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "case_id", "from_wallet", "to_wallet", "amount_btc",
        "timestamp", "hop_type", "typology"
    ])
    writer.writeheader()
    writer.writerows(rows)

# Save a few sample victim wallets so the UI can suggest them
with open(os.path.join(OUT_DIR, "sample_search_wallets.csv"), "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["victim_wallet"])
    for w in victim_start_wallets[:8]:
        writer.writerow([w])

print(f"Generated {len(rows)} transaction edges across {case_id - 1} synthetic cases.")
print(f"Files written to: {OUT_DIR}")
