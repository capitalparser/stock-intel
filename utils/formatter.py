"""utils/formatter.py — 4개 data 모듈 결과를 텔레그램 메시지로 포맷."""


def _fmt_amount(won: int) -> str:
    """원 → 억원 (소수점 없음). 부호 포함.

    예) 123456789000 → "+1,234억"
        -89000000000 → "-890억"
    """
    awk = round(won / 1e8)
    sign = "+" if awk >= 0 else ""
    return f"{sign}{awk:,}억"


def _fmt_table_amount(won: int) -> str:
    awk = round(won / 1e8)
    sign = "+" if awk >= 0 else ""
    return f"{sign}{awk:,}"


def _fmt_akw(won: int | float | None, signed: bool = True) -> str:
    if won is None:
        return "-"
    awk = round(won / 1e8)
    sign = "+" if signed and awk > 0 else ""
    return f"{sign}{awk:,}"


def _fmt_price(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{int(value):,}"


def _fmt_pct(value: int | float | None, signed: bool = False) -> str:
    if value is None:
        return "-"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.1f}%"


def _fmt_ratio(value: int | float | None, suffix: str = "") -> str:
    if value is None:
        return "-"
    if suffix:
        return f"{value:.2f}{suffix}"
    return f"{value:,.0f}"


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
        "진입": "진입 후보 (추세+52주 필터+거래량)",
        "매도": "리스크 신호 (20/50일선 이탈 또는 과열)",
        "손절": "손절 구간 (지지선 이탈)",
        "중립": "중립/관찰",
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
    daily = supply.get("daily") or []
    if daily:
        lines.extend(
            [
                "  최근 10거래일 순매수(억원)",
                "  날짜       기관     외국인",
                "  -------------------------",
            ]
        )
        for row in daily[:10]:
            date = str(row["date"])[5:].replace("-", ".")
            inst_amt = _fmt_table_amount(row["institution"])
            fore_amt = _fmt_table_amount(row["foreigner"])
            lines.append(f"  {date:<5} {inst_amt:>8} {fore_amt:>10}")

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
    ma50 = technical.get("ma50")
    ma60 = technical["ma60"]
    ma150 = technical.get("ma150")
    ma200 = technical.get("ma200")
    rsi14 = technical["rsi14"]
    bb_pct = technical["bb_pct"]
    ma_trend = technical["ma_trend"]
    signal = technical["signal"]
    stoploss = technical.get("stoploss")
    trend_template = technical.get("trend_template", "-")
    setup_quality = technical.get("setup_quality", "관망")
    volume_ratio = technical.get("volume_ratio")
    volume_state = technical.get("volume_state", "-")
    from_52w_high_pct = technical.get("from_52w_high_pct")
    from_52w_low_pct = technical.get("from_52w_low_pct")
    comment = technical.get("technical_comment")

    bb_text = _bb_label(bb_pct) if bb_pct is not None else "-"
    signal_text = _signal_label(signal)
    rsi_text = str(int(rsi14)) if rsi14 is not None else "-"
    bb_pct_text = str(int(bb_pct)) if bb_pct is not None else "-"
    volume_text = f"{volume_ratio:.2f}x" if volume_ratio is not None else "-"

    lines = [
        "📈 기술적 위치",
        f"  현재가: {_fmt_price(price)}원  |  셋업: {setup_quality}",
        f"  20/50/150/200일선: {_fmt_price(ma20)} / {_fmt_price(ma50)} / {_fmt_price(ma150)} / {_fmt_price(ma200)}",
        f"  단기 5/20/60 배열: {_fmt_price(ma5)} / {_fmt_price(ma20)} / {_fmt_price(ma60)} ({ma_trend})",
        f"  트렌드 템플릿: {trend_template}  |  52주 위치: 고점 {_fmt_pct(from_52w_high_pct)}, 저점 {_fmt_pct(from_52w_low_pct, signed=True)}",
        f"  거래량: 50일 평균 대비 {volume_text} ({volume_state})",
        f"  RSI(14): {rsi_text}  |  볼린저: {bb_text}({bb_pct_text}%)",
        f"  → 판단: {signal_text}",
    ]
    if comment:
        lines.append(f"  코멘트: {comment}")
    if stoploss is not None:
        lines.append(f"  손절선: {stoploss:,}원")
    return "\n".join(lines)


def _section_fundamental(fundamental: dict) -> str:
    if "error" in fundamental:
        return "📚 펀더멘탈\n  ⚠️ 데이터를 가져올 수 없습니다"

    financials = fundamental.get("financials") or []
    ratios = fundamental.get("ratios") or {}
    comment = fundamental.get("comment")

    lines = ["📚 펀더멘탈"]
    if financials:
        year_count = len(financials[-3:])
        lines.extend(
            [
                f"  최근 {year_count}개년 재무(억원)",
                "  연도       매출   영업익   영업CF",
                "  ------------------------------",
            ]
        )
        for row in financials[-3:]:
            year = str(row.get("year", "-"))
            revenue = _fmt_akw(row.get("revenue"), signed=False)
            op_income = _fmt_akw(row.get("operating_income"))
            ocf = _fmt_akw(row.get("operating_cash_flow"))
            lines.append(f"  {year:<4} {revenue:>9} {op_income:>8} {ocf:>8}")
    else:
        lines.append("  최근 3개년 재무: DART 데이터 없음")

    if ratios:
        per = ratios.get("per")
        pbr = ratios.get("pbr")
        eps = ratios.get("eps")
        bps = ratios.get("bps")
        div = ratios.get("div")
        dps = ratios.get("dps")
        lines.append(
            "  지표: "
            f"PER {_fmt_ratio(per, 'x')} | "
            f"PBR {_fmt_ratio(pbr, 'x')} | "
            f"EPS {_fmt_ratio(eps)} | "
            f"BPS {_fmt_ratio(bps)}"
        )
        lines.append(
            "        "
            f"배당수익률 {_fmt_ratio(div, '%')} | "
            f"DPS {_fmt_ratio(dps)}"
        )
    else:
        lines.append("  지표: KRX 기본지표 없음")

    if comment:
        lines.append(f"  코멘트: {comment}")
    return "\n".join(lines)


def _section_audit_firm(audit_firm: dict) -> str:
    if "error" in audit_firm:
        return "🏢 감사법인\n  ⚠️ 데이터를 가져올 수 없습니다"

    recent = audit_firm.get("recent") or []
    if not recent:
        return "🏢 감사법인\n  ⚠️ 데이터를 가져올 수 없습니다"

    lines = ["🏢 감사법인"]
    for i, row in enumerate(recent):
        y = row.get("year")
        firm = row.get("firm") or "-"
        label = f"당해({y})" if i == 0 else f"직전({y})"
        badge = "  ⚠️ 교체" if row.get("changed_from_prev") else ""
        lines.append(f"  {label}: {firm}{badge}")
    return "\n".join(lines)


def format_message(
    name: str,
    ticker: str,
    supply: dict,
    short_sell: dict,
    technical: dict,
    fundamental: dict,
    audit_firm: dict,
) -> str:
    """5개 섹션을 합쳐 텔레그램 메시지 생성.

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
        _section_fundamental(fundamental),
        "",
        _section_audit_firm(audit_firm),
    ]
    return "\n".join(sections)
