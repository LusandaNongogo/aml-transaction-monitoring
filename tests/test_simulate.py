from src.simulate import simulate


def test_simulation_is_reproducible_and_labelled():
    c1, t1 = simulate(n_customers=300, seed=1)
    c2, t2 = simulate(n_customers=300, seed=1)
    assert t1["amount"].sum() == t2["amount"].sum()
    assert c1["is_suspicious"].sum() == 6
    assert set(t1["customer_id"]) <= set(c1["customer_id"])
    assert (t1["amount"] > 0).all()
