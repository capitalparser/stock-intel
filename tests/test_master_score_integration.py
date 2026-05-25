from signals.master_score import format_master_score_for_payload


def test_formats_master_score_when_engine_is_available():
    text = format_master_score_for_payload(
        {
            "ticker": "AAPL",
            "price": 195.5,
            "action": "BUY",
            "score": 85,
            "conviction": "S",
            "signal": "GP:수급 Sigma:PB ",
            "ema_align": "정배열",
            "daily_above_200ma": True,
            "daily_ema_aligned": True,
            "daily_rs": 78,
            "daily_setup_stage": "COMPLETE",
            "daily_volume_trend": "ACCUMULATION",
            "daily_dist_from_high": -3.2,
            "sl": 188.2,
            "rr": 2.3,
        },
        independence_status="CLEAR",
    )

    assert text is not None
    assert "Master Score" in text
    assert "등급" in text

