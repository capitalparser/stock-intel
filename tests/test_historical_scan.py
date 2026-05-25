import pandas as pd

from signals.historical_scan import format_historical_scan_report, scan_rule_signal_outcomes


def test_scan_rule_signal_outcomes_uses_actual_signal_dates_only():
    df = _sample_ohlcv()

    outcomes = scan_rule_signal_outcomes(ticker="000001", market="KR", ohlcv=df, horizons=(5, 10, 20))

    assert len(outcomes) == 1
    assert outcomes[0].signal_date == "2025-10-07"
    assert outcomes[0].master_score is not None
    assert outcomes[0].rating in {"ENTRY", "LEADER"}
    assert outcomes[0].payload["type"] == "규칙형 돌파 진입"
    assert outcomes[0].returns["5d"] is not None


def test_format_historical_scan_report_handles_empty_result():
    text = format_historical_scan_report([])

    assert "샘플: 0건" in text
    assert "가격/거래량 규칙상 진입 시그널이 없습니다." in text


def _sample_ohlcv() -> pd.DataFrame:
    dates = pd.bdate_range("2024-10-01", periods=280)
    rows = []
    close = 100.0
    for i, _date in enumerate(dates):
        close += 0.22
        high = close + 0.8
        low = close - 0.8
        volume = 1_000_000
        if i == 265:
            close += 8.0
            high = close + 0.5
            low = close - 4.0
            volume = 2_500_000
        elif i > 265:
            close += 8.0 + (i - 265) * 0.3
            high = close + 0.8
            low = close - 0.8
        rows.append(
            {
                "Open": close - 1.0,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            }
        )
    return pd.DataFrame(rows, index=dates)
