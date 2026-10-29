"""Synthetic South African retail banking transactions with planted
money laundering typologies.

Real transaction data with confirmed laundering labels is not public, so
this module builds a book of normal customers and then plants three
typologies on top of it. Every planted customer carries a label, which is
what lets us measure how good the alerts are.

Normal behaviour
  salary or business income, card spend, EFTs out, and some cash deposits.
  Three innocent groups look suspicious on purpose, because they are where
  false positives come from in practice:
  small business  spaza shops, taxis and salons depositing a lot of cash,
                  some of it close to the reporting threshold
  stokvel         a treasurer collects from many members, then pays out
                  quickly, which looks a lot like a mule account
  low activity    quiet accounts (often pensioners) that now and then
                  receive a legitimate lump sum such as a pension payout

Typologies
  structuring   repeated cash deposits just under the cash threshold
  mule          many unrelated senders, money moved out again within hours
  dormant       account quiet for months, then a large burst of inflows

All amounts are in rand.
"""

import numpy as np
import pandas as pd

# FIC Act cash threshold report level. Check the current FIC guidance
# before relying on this number.
CASH_THRESHOLD = 49_999.99

DAYS = 120
START = pd.Timestamp("2026-01-01")


def _txn(cust, day, hour, amount, direction, channel, counterparty):
    return (cust, day, hour, round(float(amount), 2), direction, channel, counterparty)


def _normal_customer(rng, cid, segment, rows, start_day=0):
    if segment == "salaried":
        income = rng.lognormal(np.log(18_000), 0.5)
        for month_day in range(start_day + 25 - start_day % 30, DAYS, 30):
            rows.append(_txn(cid, month_day, 8, income, "in", "eft", "employer"))
        n_spend = rng.poisson(45)
        days = rng.integers(start_day, DAYS, n_spend)
        amts = rng.lognormal(np.log(350), 0.9, n_spend)
        for d, a in zip(days, amts):
            rows.append(_txn(cid, d, rng.integers(7, 22), a, "out", "card", "merchant"))
        for _ in range(rng.poisson(6)):
            rows.append(_txn(cid, rng.integers(start_day, DAYS), rng.integers(8, 20),
                             rng.lognormal(np.log(2_500), 0.7), "out", "eft",
                             f"payee_{rng.integers(0, 4000)}"))
        if rng.random() < 0.15:
            for _ in range(rng.poisson(2) + 1):
                rows.append(_txn(cid, rng.integers(start_day, DAYS), rng.integers(9, 16),
                                 rng.lognormal(np.log(3_000), 0.8), "in", "cash", "branch"))

    elif segment == "small_business":
        # cash heavy, and some deposit big rounded sums close to the threshold
        daily_cash = rng.lognormal(np.log(4_000), 0.6)
        near_threshold = rng.random() < 0.12
        for d in range(start_day, DAYS):
            if rng.random() < 0.35:
                amt = daily_cash * rng.uniform(1.5, 3.5)
                if near_threshold and rng.random() < 0.15:
                    amt = rng.uniform(0.85, 0.99) * CASH_THRESHOLD
                rows.append(_txn(cid, d, rng.integers(9, 16), amt, "in", "cash", "branch"))
        for _ in range(rng.poisson(25)):
            rows.append(_txn(cid, rng.integers(start_day, DAYS), rng.integers(8, 18),
                             rng.lognormal(np.log(6_000), 0.8), "out", "eft",
                             f"supplier_{rng.integers(0, 300)}"))
        for _ in range(rng.poisson(30)):
            rows.append(_txn(cid, rng.integers(start_day, DAYS), rng.integers(8, 20),
                             rng.lognormal(np.log(800), 0.8), "out", "card", "merchant"))
        # card and instant payment customers, so many small senders
        for _ in range(rng.poisson(40)):
            rows.append(_txn(cid, rng.integers(start_day, DAYS), rng.integers(8, 20),
                             rng.lognormal(np.log(250), 0.8), "in", "instant",
                             f"cust_{rng.integers(0, 50_000)}"))

    elif segment == "stokvel":
        _normal_customer(rng, cid, "salaried", rows, start_day)
        members = [f"member_{cid}_{k}" for k in range(rng.integers(8, 30))]
        contribution = rng.choice([500, 1000, 1500, 2000])
        for month_start in range(start_day, DAYS, 30):
            pay_day = month_start + rng.integers(0, 5)
            total = 0
            for m in members:
                d = pay_day + rng.integers(0, 4)
                rows.append(_txn(cid, d, rng.integers(7, 21), contribution, "in", "instant", m))
                total += contribution
            # payout to one member or a bulk grocery purchase within days
            rows.append(_txn(cid, pay_day + rng.integers(3, 7), rng.integers(9, 17),
                             total * rng.uniform(0.85, 1.0), "out",
                             rng.choice(["eft", "instant"]), rng.choice(members)))

    elif segment == "low_activity":
        n = rng.integers(3, 12)
        for d in np.sort(rng.integers(start_day, DAYS, n)):
            rows.append(_txn(cid, d, rng.integers(8, 18),
                             rng.lognormal(np.log(600), 0.6), "out", "card", "merchant"))
        if rng.random() < 0.25:
            d = rng.integers(70, DAYS - 3)
            amt = rng.uniform(50_000, 400_000)
            rows.append(_txn(cid, d, rng.integers(9, 16), amt, "in", "eft",
                             rng.choice(["pension_fund", "attorney_trust", "insurer"])))
            for _ in range(rng.integers(1, 4)):
                rows.append(_txn(cid, min(d + rng.integers(1, 10), DAYS - 1),
                                 rng.integers(9, 16), amt * rng.uniform(0.1, 0.4),
                                 "out", "eft", f"payee_{rng.integers(0, 4000)}"))


def _structuring(rng, cid, rows):
    # a few rounds of cash deposits just under the threshold, a few days apart
    for _ in range(rng.integers(2, 5)):
        d0 = rng.integers(10, DAYS - 10)
        for k in range(rng.integers(3, 6)):
            rows.append(_txn(cid, d0 + rng.integers(0, 5), rng.integers(9, 16),
                             rng.uniform(0.80, 0.99) * CASH_THRESHOLD, "in", "cash",
                             f"branch_{rng.integers(0, 20)}"))
    # then sent on
    for _ in range(rng.integers(2, 6)):
        rows.append(_txn(cid, rng.integers(20, DAYS), rng.integers(9, 17),
                         rng.uniform(60_000, 180_000), "out", "eft",
                         f"payee_x{rng.integers(0, 50)}"))


def _mule(rng, cid, rows):
    # a short active window with many unrelated senders, emptied within hours
    d0 = rng.integers(30, DAYS - 20)
    for _ in range(rng.integers(6, 30)):
        d = d0 + rng.integers(0, 14)
        h = rng.integers(6, 20)
        amt = rng.uniform(1_500, 15_000)
        rows.append(_txn(cid, d, h, amt, "in", "instant", f"victim_{rng.integers(0, 10**6)}"))
        out_h = h + rng.integers(1, 6)
        rows.append(_txn(cid, d + out_h // 24, out_h % 24, amt * rng.uniform(0.9, 0.98),
                         "out", rng.choice(["instant", "atm"]),
                         f"collector_{rng.integers(0, 10)}"))


def _dormant(rng, cid, rows):
    # a few early transactions, a long gap, then a burst
    for _ in range(rng.integers(1, 4)):
        rows.append(_txn(cid, rng.integers(0, 10), rng.integers(8, 20),
                         rng.lognormal(np.log(500), 0.6), "out", "card", "merchant"))
    d0 = rng.integers(85, DAYS - 5)
    for _ in range(rng.integers(3, 8)):
        rows.append(_txn(cid, d0 + rng.integers(0, 4), rng.integers(8, 20),
                         rng.uniform(20_000, 90_000), "in", "eft",
                         f"payer_{rng.integers(0, 10**6)}"))
    for _ in range(rng.integers(2, 5)):
        rows.append(_txn(cid, min(d0 + rng.integers(1, 5), DAYS - 1), rng.integers(8, 20),
                         rng.uniform(30_000, 120_000), "out", "eft",
                         f"payee_y{rng.integers(0, 50)}"))


def simulate(n_customers=5_000, bad_share=0.02, seed=7):
    """Return (customers, transactions).

    customers: one row per customer with segment, account age and label.
    transactions: one row per transaction.
    """
    rng = np.random.default_rng(seed)
    n_bad = int(n_customers * bad_share)
    n_good = n_customers - n_bad

    segments = rng.choice(["salaried", "small_business", "stokvel", "low_activity"],
                          n_good, p=[0.79, 0.14, 0.03, 0.04])
    typologies = rng.choice(["structuring", "mule", "dormant"], n_bad, p=[0.4, 0.4, 0.2])

    rows, cust = [], []
    for i, seg in enumerate(segments):
        cid = f"C{i:05d}"
        _normal_customer(rng, cid, seg, rows)
        cust.append((cid, seg, int(rng.integers(90, 4000)), "none"))

    for j, typ in enumerate(typologies):
        cid = f"C{n_good + j:05d}"
        if typ == "mule":
            # mules are usually new accounts, often lightly used before
            cust.append((cid, "salaried", int(rng.integers(10, 200)), typ))
            if rng.random() < 0.5:
                _normal_customer(rng, cid, "salaried", rows, start_day=60)
            _mule(rng, cid, rows)
        elif typ == "structuring":
            seg = rng.choice(["salaried", "small_business"])
            cust.append((cid, seg, int(rng.integers(90, 3000)), typ))
            _normal_customer(rng, cid, seg, rows)
            _structuring(rng, cid, rows)
        else:
            cust.append((cid, "salaried", int(rng.integers(400, 4000)), typ))
            _dormant(rng, cid, rows)

    tx = pd.DataFrame(rows, columns=["customer_id", "day", "hour", "amount",
                                     "direction", "channel", "counterparty"])
    tx = tx[tx["day"] < DAYS]
    tx["timestamp"] = START + pd.to_timedelta(tx["day"], "D") + pd.to_timedelta(tx["hour"], "h")
    tx = tx.sort_values(["customer_id", "timestamp"]).reset_index(drop=True)
    tx.insert(0, "txn_id", [f"T{i:07d}" for i in range(len(tx))])

    customers = pd.DataFrame(cust, columns=["customer_id", "segment",
                                            "account_age_days", "typology"])
    customers["is_suspicious"] = (customers["typology"] != "none").astype(int)
    return customers, tx.drop(columns=["day", "hour"])
