import json
from pathlib import Path

from signals.market import classify_market
from signals.payload import TradingViewSignal


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_v6_2_payload_parses_sb_z_score():
    signal = TradingViewSignal.model_validate(load_fixture("tradingview_v6_2_buy_aapl.json"))
    assert signal.schema_version == "v6.2"
    assert signal.sb_z_score == 1.42
    assert signal.base_type() == "💰 정석 진입"
    assert signal.has_sr_flip() is True


def test_market_classification():
    assert classify_market("005930", "KRX").code == "KR"
    assert classify_market("AAPL", "NASDAQ").code == "US"
    assert classify_market("7203", "TSE").code == "JP"
    assert classify_market("ABC", "").code == "UNKNOWN"

