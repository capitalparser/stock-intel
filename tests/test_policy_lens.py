from dashboard.policy_lens import (
    LOW_PBR_SEEDS,
    VALUE_UP_LENS,
    policy_lenses,
    low_pbr_seed_stocks,
    policy_seed_stocks,
)


def test_policy_lenses_includes_value_up_and_new_policy_lenses():
    lenses = policy_lenses()

    assert lenses[0] == VALUE_UP_LENS  # value_up은 첫 슬롯 유지
    ids = {lens.id for lens in lenses}
    assert {
        "value_up_low_pbr",
        "policy_chips_act",
        "policy_ira_clean_energy",
        "policy_k_defense",
    } <= ids
    # 모든 정책 렌즈 weights는 1.0으로 정규화
    for lens in lenses:
        assert abs(sum(lens.weights.values()) - 1.0) < 1e-9


def test_policy_seed_stocks_cover_new_lenses_and_link_correctly():
    stocks = {str(s["ticker"]): s for s in policy_seed_stocks()}
    # 저PBR + 신규 렌즈 시드가 모두 포함
    assert "004020" in stocks  # 저PBR
    for ticker, lens_id in (
        ("INTC", "policy_chips_act"),
        ("373220", "policy_ira_clean_energy"),
        ("012450", "policy_k_defense"),
    ):
        assert ticker in stocks, ticker
        assert lens_id in stocks[ticker]["lens_ids"]


def test_low_pbr_seed_stocks_are_non_empty_and_cover_all_seed_codes():
    stocks = low_pbr_seed_stocks()
    seed_codes = set(LOW_PBR_SEEDS)
    result_codes = {str(stock["ticker"]) for stock in stocks}

    assert stocks
    assert isinstance(LOW_PBR_SEEDS, list)
    assert len(seed_codes) == 10
    assert seed_codes <= result_codes


def test_low_pbr_seed_stock_shape_links_policy_lens():
    stock = next(
        stock
        for stock in low_pbr_seed_stocks()
        if stock["ticker"] == "004020"
    )

    assert stock["company"] == "현대제철"
    assert "value_up_low_pbr" in stock["lens_ids"]
    assert "밸류업" in stock["thesis"]
    assert all(
        key in stock
        for key in (
            "metrics",
            "evidence",
            "gaps",
            "next_action",
            "source_refs",
            "peer_group",
        )
    )


def test_policy_lens_main_prints_lens_and_first_three_seed_stocks(capsys):
    from dashboard.policy_lens import main

    main()

    out = capsys.readouterr().out
    assert "저PBR 밸류업" in out
    assert "004020" in out
    assert "011170" in out
    assert "011780" in out
