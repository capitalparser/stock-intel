"""Historical rule-signal scanner for Master Score calibration."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signals.master_score import build_master_scorecard_for_payload


@dataclass(frozen=True)
class HistoricalSignalOutcome:
    ticker: str
    market: str
    signal_date: str
    price: float
    master_score: int | None
    rating: str | None
    returns: dict[str, float | None]
    payload: dict


_KR_TO_EN = {
    "시가": "Open",
    "고가": "High",
    "저가": "Low",
    "종가": "Close",
    "거래량": "Volume",
}


def scan_rule_signal_outcomes(
    *,
    ticker: str,
    market: str,
    ohlcv: pd.DataFrame,
    horizons: tuple[int, ...] = (5, 10, 20),
    min_volume_ratio: float = 1.5,
    min_signal_gap_bars: int = 10,
) -> list[HistoricalSignalOutcome]:
    df = _prepare_ohlcv(ohlcv)
    if df.empty:
        return []

    enriched = _with_indicators(df)
    outcomes: list[HistoricalSignalOutcome] = []
    last_signal_pos = -10_000
    for pos, (idx, row) in enumerate(enriched.iterrows()):
        if pos - last_signal_pos < min_signal_gap_bars:
            continue
        if not _is_entry_signal(row, min_volume_ratio=min_volume_ratio):
            continue

        payload = _payload_from_row(ticker=ticker, market=market, date=idx, row=row)
        scorecard = build_master_scorecard_for_payload(payload, independence_status="CLEAR")
        returns = _forward_returns(enriched, idx, float(row["Close"]), horizons)
        outcomes.append(
            HistoricalSignalOutcome(
                ticker=ticker,
                market=market,
                signal_date=idx.strftime("%Y-%m-%d"),
                price=float(row["Close"]),
                master_score=scorecard.total if scorecard else None,
                rating=scorecard.rating if scorecard else None,
                returns=returns,
                payload=payload,
            )
        )
        last_signal_pos = pos
    return outcomes


def format_historical_scan_report(outcomes: list[HistoricalSignalOutcome], *, title: str = "Rule Signal 사후검증") -> str:
    lines = [title, f"샘플: {len(outcomes)}건", ""]
    if not outcomes:
        lines.append("가격/거래량 규칙상 진입 시그널이 없습니다.")
        return "\n".join(lines)

    lines.append("ticker | date | price | score | rating | 5d | 10d | 20d")
    lines.append("-" * 72)
    for item in outcomes:
        lines.append(
            " | ".join(
                [
                    item.ticker,
                    item.signal_date,
                    _fmt_price(item.price),
                    "-" if item.master_score is None else str(item.master_score),
                    item.rating or "-",
                    _fmt_pct(item.returns.get("5d")),
                    _fmt_pct(item.returns.get("10d")),
                    _fmt_pct(item.returns.get("20d")),
                ]
            )
        )
    return "\n".join(lines)


def _prepare_ohlcv(ohlcv: pd.DataFrame) -> pd.DataFrame:
    df = ohlcv.rename(columns=_KR_TO_EN).copy()
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not set(required).issubset(df.columns):
        return pd.DataFrame(columns=required)
    df = df[required].dropna().sort_index()
    return df.astype(float)


def _with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["SMA_20"] = enriched["Close"].rolling(20).mean()
    enriched["SMA_50"] = enriched["Close"].rolling(50).mean()
    enriched["SMA_150"] = enriched["Close"].rolling(150).mean()
    enriched["SMA_200"] = enriched["Close"].rolling(200).mean()
    enriched["CLOSE_5D_AGO"] = enriched["Close"].shift(5)
    enriched["CLOSE_20D_AGO"] = enriched["Close"].shift(20)
    enriched["CLOSE_126D_AGO"] = enriched["Close"].shift(126)
    enriched["SMA_200_PREV_22"] = enriched["SMA_200"].shift(22)
    enriched["VOL_50"] = enriched["Volume"].rolling(50).mean()
    enriched["VOLUME_RATIO"] = enriched["Volume"] / enriched["VOL_50"]
    enriched["HIGH_52W"] = enriched["High"].rolling(252).max()
    enriched["LOW_52W"] = enriched["Low"].rolling(252).min()
    enriched["PRIOR_HIGH_20"] = enriched["High"].shift(1).rolling(20).max()
    enriched["PRIOR_LOW_20"] = enriched["Low"].shift(1).rolling(20).min()
    enriched["STD_20"] = enriched["Close"].rolling(20).std()
    return enriched.dropna()


def _is_entry_signal(row: pd.Series, *, min_volume_ratio: float) -> bool:
    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])
    candle_range = high - low
    close_strength = 1.0 if candle_range <= 0 else (close - low) / candle_range
    trend_template = (
        close > float(row["SMA_50"])
        and float(row["SMA_50"]) > float(row["SMA_150"])
        and float(row["SMA_150"]) > float(row["SMA_200"])
        and float(row["SMA_200"]) > float(row["SMA_200_PREV_22"])
    )
    near_high = close >= float(row["HIGH_52W"]) * 0.75
    off_low = close >= float(row["LOW_52W"]) * 1.30
    breakout = close > float(row["PRIOR_HIGH_20"])
    volume_confirmed = float(row["VOLUME_RATIO"]) >= min_volume_ratio
    return trend_template and near_high and off_low and breakout and volume_confirmed and close_strength >= 0.6


def _payload_from_row(*, ticker: str, market: str, date: pd.Timestamp, row: pd.Series) -> dict:
    close = float(row["Close"])
    low20 = float(row["PRIOR_LOW_20"])
    stop = round(low20 * 0.98, 2)
    volume_ratio = float(row["VOLUME_RATIO"])
    high = float(row["High"])
    low = float(row["Low"])
    candle_range = max(0.01, high - low)
    close_strength = (close - low) / candle_range
    upper_wick_pct = (high - close) / candle_range * 100
    stop_distance_pct = abs(close - stop) / close * 100 if close > 0 else None
    dist_sma20_pct = (close / float(row["SMA_20"]) - 1) * 100 if float(row["SMA_20"]) else None
    dist_sma50_pct = (close / float(row["SMA_50"]) - 1) * 100 if float(row["SMA_50"]) else None
    prior_5d_return = _safe_return(close, row.get("CLOSE_5D_AGO"))
    prior_20d_return = _safe_return(close, row.get("CLOSE_20D_AGO"))
    daily_return_126 = _safe_return(close, row.get("CLOSE_126D_AGO"))
    rs_proxy = _rs_proxy(daily_return_126)
    sb_z_score = 0.0
    if float(row["STD_20"]) > 0:
        sb_z_score = (close - float(row["SMA_20"])) / float(row["STD_20"])

    conviction = "S" if volume_ratio >= 3.0 and close_strength >= 0.8 else "A" if volume_ratio >= 2.0 else "B"
    return {
        "schema_version": "rule-scan-v0",
        "ticker": ticker,
        "name": ticker,
        "exchange": "KRX" if market == "KR" else "",
        "timeframe": "D",
        "action": "BUY",
        "type": "규칙형 돌파 진입",
        "price": close,
        "sl": stop,
        "rr": 2.0,
        "desc": "가격/거래량 시계열 기반 돌파 진입",
        "market": market,
        "ai_summary": "추세 템플릿 + 20일 고점 돌파 + 거래량 확인",
        "score": 85 if conviction == "S" else 80 if conviction == "A" else 74,
        "status": "Green(GO)",
        "signal": "돌파 GP:수급",
        "conviction": conviction,
        "ema_align": "정배열",
        "daily_trend": "BULL",
        "daily_ema_aligned": True,
        "daily_rs": rs_proxy,
        "daily_above_200ma": True,
        "daily_setup_stage": "COMPLETE",
        "daily_volume_trend": "ACCUMULATION",
        "daily_volume_ratio": round(volume_ratio, 2),
        "daily_dist_from_high": round((close / float(row["HIGH_52W"]) - 1) * 100, 2),
        "dist_sma20_pct": round(dist_sma20_pct, 2) if dist_sma20_pct is not None else None,
        "dist_sma50_pct": round(dist_sma50_pct, 2) if dist_sma50_pct is not None else None,
        "prior_5d_return_pct": round(prior_5d_return * 100, 2) if prior_5d_return is not None else None,
        "prior_20d_return_pct": round(prior_20d_return * 100, 2) if prior_20d_return is not None else None,
        "stop_distance_pct": round(stop_distance_pct, 2) if stop_distance_pct is not None else None,
        "candle_strength": round(close_strength * 100),
        "upper_wick_pct": round(upper_wick_pct, 2),
        "atr_dot": sb_z_score > 2.5,
        "sb_z_score": round(sb_z_score, 2),
        "signal_date": date.strftime("%Y-%m-%d"),
    }


def _forward_returns(
    df: pd.DataFrame,
    signal_date: pd.Timestamp,
    entry: float,
    horizons: tuple[int, ...],
) -> dict[str, float | None]:
    pos = df.index.get_loc(signal_date)
    returns: dict[str, float | None] = {}
    for horizon in horizons:
        target = pos + horizon
        if target >= len(df):
            returns[f"{horizon}d"] = None
        else:
            returns[f"{horizon}d"] = round((float(df.iloc[target]["Close"]) / entry - 1) * 100, 2)
    return returns


def _safe_return(current: float, previous) -> float | None:
    if previous is None or pd.isna(previous) or float(previous) == 0:
        return None
    return current / float(previous) - 1


def _rs_proxy(return_126d: float | None) -> int:
    if return_126d is None:
        return 75
    if return_126d >= 0.35:
        return 90
    if return_126d >= 0.2:
        return 85
    if return_126d >= 0.1:
        return 78
    return 70


def _fmt_price(value: float) -> str:
    return f"{value:,.0f}" if value >= 100 else f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
