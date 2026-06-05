from dashboard.policy_lens import (
    LOW_PBR_SEEDS,
    VALUE_UP_LENS,
    policy_lenses,
    low_pbr_seed_stocks,
)


def test_policy_lenses_returns_value_up_lens():
    lenses = policy_lenses()

    assert len(lenses) == 1
    assert lenses[0] == VALUE_UP_LENS
    assert lenses[0].id == "value_up_low_pbr"


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
