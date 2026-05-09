"""utils/formatter.py — 4개 data 모듈 결과를 텔레그램 메시지로 포맷."""


def _fmt_amount(won: int) -> str:
    """원 → 억원 (소수점 없음). 부호 포함.

    예) 123456789000 → "+1,234억"
        -89000000000 → "-890억"
    """
    awk = round(won / 1e8)
    sign = "+" if awk >= 0 else ""
    return f"{sign}{awk:,}억"


def _flow_arrow(won: int) -> str:
    """순매수/매도 방향 이모지."""
    if won > 0:
        return "▲"
    elif won < 0:
        return "▼"
    return "—"


def _bb_label(bb_pct: float) -> str:
    """볼린저 밴드 위치 텍스트."""
    if bb_pct < 0:
        return "하단 이탈"
    elif bb_pct < 20:
        return "하단"
    elif bb_pct <= 80:
        return "중단"
    elif bb_pct <= 100:
        return "상단"
    else:
        return "상단 돌파"


def _signal_label(signal: str) -> str:
    """signal 코드 → 사람이 읽기 좋은 텍스트."""
    mapping = {
        "진입": "진입 신호 (RSI<35, 정배열)",
        "매도": "매도 신호 (RSI>70 또는 볼린저 상단)",
        "손절": "손절 구간 (지지선 이탈)",
        "중립": "중립 (진입 조건 미충족)",
    }
    return mapping.get(signal, signal)


def _section_supply(supply: dict) -> str:
    if "error" in supply:
        return "💰 수급현황 (D-1)\n  ⚠️ 데이터를 가져올 수 없습니다"

    inst = supply["institution"]
    fore = supply["foreigner"]

    inst_today = _fmt_amount(inst["today"])
    inst_5d = _fmt_amount(inst["5d"])
    inst_arrow = _flow_arrow(inst["5d"])

    fore_today = _fmt_amount(fore["today"])
    fore_5d = _fmt_amount(fore["5d"])
    fore_arrow = _flow_arrow(fore["5d"])

    inst_label = "순매수" if inst["today"] >= 0 else "순매도"
    fore_label = "순매수" if fore["today"] >= 0 else "순매도"

    lines = [
        "💰 수급현황 (D-1)",
        f"  기관: {inst_label} {inst_today}  (5일: {inst_5d} {inst_arrow})",
        f"  외국인: {fore_label} {fore_today}  (5일: {fore_5d} {fore_arrow})",
    ]
    return "\n".join(lines)


def _section_short_sell(short_sell: dict) -> str:
    if "error" in short_sell:
        return "🔻 공매도\n  ⚠️ 데이터를 가져올 수 없습니다"

    ratio_today = short_sell["ratio_today"]
    ratio_avg = short_sell["ratio_20d_avg"]
    trend = short_sell["trend"]

    lines = [
        "🔻 공매도",
        f"  오늘 비율: {ratio_today}%  (20일 평균 {ratio_avg}% 대비 {trend})",
    ]
    return "\n".join(lines)


def _section_technical(technical: dict) -> str:
    if "error" in technical:
        return "📈 기술적 위치\n  ⚠️ 데이터를 가져올 수 없습니다"

    price = technical["price"]
    ma5 = technical["ma5"]
    ma20 = technical["ma20"]
    ma60 = technical["ma60"]
    rsi14 = technical["rsi14"]
    bb_pct = technical["bb_pct"]
    ma_trend = technical["ma_trend"]
    signal = technical["signal"]
    stoploss = technical.get("stoploss")

    bb_text = _bb_label(bb_pct)
    signal_text = _signal_label(signal)

    lines = [
        "📈 기술적 위치",
        f"  현재가: {price:,}원",
        f"  5/20/60 이평: {ma5:,} / {ma20:,} / {ma60:,} ({ma_trend})",
        f"  RSI(14): {int(rsi14)}  |  볼린저: {bb_text}({int(bb_pct)}%)",
        f"  → 판단: {signal_text}",
    ]
    if stoploss is not None:
        lines.append(f"  손절선: {stoploss:,}원")
    return "\n".join(lines)


def _section_audit_firm(audit_firm: dict) -> str:
    if "error" in audit_firm:
        return "🏢 감사법인\n  ⚠️ 데이터를 가져올 수 없습니다"

    cy = audit_firm["current_year"]
    cf = audit_firm["current_firm"]
    py = audit_firm.get("prev_year")
    pf = audit_firm.get("prev_firm")
    changed = audit_firm.get("changed", False)

    change_badge = "⚠️ 교체" if changed else "(변경 없음)"

    lines = ["🏢 감사법인", f"  당해({cy}): {cf}"]
    if pf is not None and py is not None:
        lines.append(f"  직전({py}): {pf}  {change_badge}")
    return "\n".join(lines)


def format_message(
    name: str,
    ticker: str,
    supply: dict,
    short_sell: dict,
    technical: dict,
    audit_firm: dict,
) -> str:
    """4개 섹션을 합쳐 텔레그램 메시지 생성.

    텔레그램 parse_mode=None (plain text) — MarkdownV2 이스케이프 불필요.
    각 섹션은 데이터 에러 시에도 "데이터를 가져올 수 없습니다" 로 graceful 처리.
    """
    # 날짜: 섹션 중 사용 가능한 첫 번째 date 사용
    date_str = (
        supply.get("date")
        or short_sell.get("date")
        or technical.get("date")
        or "날짜 불명"
    )

    header = f"📊 {name} ({ticker})  {date_str} 기준"

    sections = [
        header,
        "",
        _section_supply(supply),
        "",
        _section_short_sell(short_sell),
        "",
        _section_technical(technical),
        "",
        _section_audit_firm(audit_firm),
    ]
    return "\n".join(sections)
