"""Framework-independent orchestration helpers for the desktop VN30 advisor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import json
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence

from domain.stock_scanner import extract_h4_signals


MINIMUM_H4_SIGNALS = 27
STOCK_SECRET_PROFILE = "__vn30_advisor__"


class StockAdvisorDesktopErrorCode(str, Enum):
    """Stable desktop advisor configuration failures."""

    INVALID_SETTINGS = "invalid_settings"


class StockAdvisorDesktopError(ValueError):
    """Desktop advisor error with a stable machine-readable code."""

    def __init__(self, code: StockAdvisorDesktopErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class StockAdvisorDesktopSettings:
    """Non-secret settings controlled by the NativeQt advisor tab."""

    client_id: str = "oak-stock-scanner"
    capital: float = 90_000_000
    hurdle_bps: float = 0.0
    backfill_sessions: int = 260

    def __post_init__(self) -> None:
        if not self.client_id.strip():
            object.__setattr__(self, "client_id", "oak-stock-scanner")
        if not isfinite(self.capital) or self.capital < 0:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Capital is invalid")
        if not isfinite(self.hurdle_bps) or self.hurdle_bps < 0:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Hurdle is invalid")
        if self.backfill_sessions < MINIMUM_H4_SIGNALS:
            raise StockAdvisorDesktopError(StockAdvisorDesktopErrorCode.INVALID_SETTINGS, "Backfill is too short")


@dataclass(frozen=True, slots=True)
class StockAdvisorLaunchPlan:
    """Safe subprocess plan that contains no secret values."""

    program: str
    arguments: tuple[str, ...]
    output_path: Path
    requires_signal_pause: bool


def requires_h4_backfill(
    records: Sequence[Mapping[str, object]],
    current_date: date,
    minimum_signals: int = MINIMUM_H4_SIGNALS,
) -> bool:
    """Return whether history is short or lacks today's H=4 signal."""
    signals = extract_h4_signals(records)
    if len(signals) < minimum_signals:
        return True
    return signals[-1].trading_date != current_date


def requires_h4_backfill_file(path: Path, current_date: date) -> bool:
    """Read the signal log and conservatively request backfill on failure."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return True
    records = payload if isinstance(payload, list) else []
    return requires_h4_backfill([item for item in records if isinstance(item, Mapping)], current_date)


def build_stock_advisor_launch_plan(
    root: Path,
    executable: str,
    frozen: bool,
    settings: StockAdvisorDesktopSettings,
    requires_backfill: bool,
) -> StockAdvisorLaunchPlan:
    """Build a source or frozen advisor command without embedding secrets."""
    output_path = root / "stock_recommendation.json"
    prefix = ["--stock-advisor"] if frozen else [str(root / "vn_stock_advisor.py")]
    arguments = prefix + _advisor_arguments(root, output_path, settings)
    if requires_backfill:
        arguments.extend(["--backfill-h4", str(settings.backfill_sessions)])
    return StockAdvisorLaunchPlan(executable, tuple(arguments), output_path, requires_backfill)


def load_ssi_desktop_credentials() -> tuple[str, str]:
    """Load credentials or default to Local EOD mode."""
    try:
        from secret_store import get_secret
        api_key = get_secret(STOCK_SECRET_PROFILE, "ssi_api_key") or "local-eod-key"
        api_secret = get_secret(STOCK_SECRET_PROFILE, "ssi_api_secret") or "local-eod-secret"
        return api_key, api_secret
    except Exception:
        return "local-eod-key", "local-eod-secret"


def save_ssi_desktop_credentials(api_key: str, api_secret: str) -> None:
    """Store secrets outside JSON settings files if provided."""
    if not api_key.strip() and not api_secret.strip():
        return
    try:
        from secret_store import store_secret
        store_secret(STOCK_SECRET_PROFILE, "ssi_api_key", api_key.strip())
        store_secret(STOCK_SECRET_PROFILE, "ssi_api_secret", api_secret.strip())
    except Exception:
        pass


def render_stock_advisory(payload: Mapping[str, object], locale: str = "VN") -> str:
    """Render a clean trading-terminal summary for the desktop tab in VN or EN."""
    is_vn = str(locale).upper() == "VN"
    signal = payload.get("signal") if isinstance(payload.get("signal"), Mapping) else {}
    direction = str(signal.get("direction", "—"))
    if is_vn:
        dir_text = "MUA (BUY)" if direction == "BUY" else ("BÁN (SELL)" if direction == "SELL" else direction)
    else:
        dir_text = direction

    action = str(payload.get("action", "—"))
    if is_vn:
        action_text = "MUA / NẮM GIỮ (BUY / HOLD)" if action == "BUY_OR_HOLD" else "BÁN / ĐỨNG NGOÀI (SELL / AVOID)"
    else:
        action_text = "BUY / HOLD" if action == "BUY_OR_HOLD" else "SELL / AVOID"

    status = str(payload.get("status", "—"))
    if is_vn:
        status_text = "SẴN SÀNG" if status == "READY" else ("KHÔNG CÓ TÍN HIỆU" if status == "NO_TRADE" else status)
    else:
        status_text = status

    date_str = str(signal.get("date", "—"))

    if is_vn:
        header = f"{date_str}  |  Tín hiệu H4: {dir_text}  |  Trạng thái: {status_text}"
        act_line = f"HÀNH ĐỘNG KHUYẾN NGHỊ: {action_text}"
    else:
        header = f"{date_str}  |  H4 {dir_text}  |  {status_text}"
        act_line = f"ACTION: {action_text}"

    lines = [header, act_line, ""]
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    lines.extend(_candidate_lines(candidates, is_vn=is_vn))

    if is_vn:
        lines.extend([
            "",
            "⚠️ YÊU CẦU USER XÁC NHẬN TRƯỚC KHI GIAO DỊCH THỰC TẾ",
            "🚫 MODULE CHỈ KHUYẾN NGHỊ - KHÔNG TỰ ĐỘNG GỬI LỆNH",
        ])
    else:
        lines.extend([
            "",
            "USER CONFIRMATION REQUIRED",
            "NO ORDER SUBMITTED",
        ])
    return "\n".join(lines)


def _advisor_arguments(root: Path, output: Path, settings: StockAdvisorDesktopSettings) -> list[str]:
    return [
        "--signals-log", str(root / "signals_log.json"),
        "--capital", format(settings.capital, ".12g"),
        "--hurdle-bps", format(settings.hurdle_bps, ".12g"),
        "--output", str(output),
    ]


_STOCK_INFO: dict[str, tuple[str, str]] = {
    "TMS": ("CTCP Transimex", "6.360 tỷ"),
    "BSI": ("Công ty CP Chứng khoán BIDC (BSC)", "7.400 tỷ"),
    "VGS": ("Công ty CP Thép Việt Đức", "2.850 tỷ"),
    "PVC": ("Tổng Công ty Hóa chất & Dịch vụ Dầu khí", "1.620 tỷ"),
    "FPT": ("Tập đoàn FPT", "188.500 tỷ"),
    "SSI": ("Công ty CP Chứng khoán SSI", "54.800 tỷ"),
    "HPG": ("Tập đoàn Hòa Phát", "167.000 tỷ"),
    "TCB": ("Ngân hàng Techcombank", "170.000 tỷ"),
    "VCB": ("Ngân hàng Vietcombank", "518.000 tỷ"),
    "VHM": ("Công ty CP Vinhomes", "184.000 tỷ"),
    "VIC": ("Tập đoàn Vingroup", "173.000 tỷ"),
    "VNM": ("Công ty CP Sữa Việt Nam (Vinamilk)", "143.000 tỷ"),
    "VPB": ("Ngân hàng VPBank", "155.000 tỷ"),
    "MBB": ("Ngân hàng Quân Đội (MB)", "128.000 tỷ"),
    "MSN": ("Tập đoàn Masan", "108.000 tỷ"),
    "MWG": ("Công ty CP Thế Giới Di Động", "91.500 tỷ"),
    "ACB": ("Ngân hàng Á Châu", "98.500 tỷ"),
    "BID": ("Ngân hàng BIDV", "282.000 tỷ"),
    "CTG": ("Ngân hàng VietinBank", "189.000 tỷ"),
    "GAS": ("Tổng Công ty Khí Việt Nam (PV GAS)", "179.000 tỷ"),
    "GVR": ("Tập đoàn CN Cao su Việt Nam", "137.000 tỷ"),
    "STB": ("Ngân hàng Sacombank", "58.900 tỷ"),
    "VIB": ("Ngân hàng VIB", "59.600 tỷ"),
    "DGC": ("Tập đoàn Hóa chất Đức Giang", "43.700 tỷ"),
    "DIG": ("Tổng Công ty DIC Corp", "15.900 tỷ"),
    "DXG": ("Tập đoàn Đất Xanh", "11.800 tỷ"),
    "FRT": ("Công ty CP Bán lẻ Kỹ thuật số FPT", "24.800 tỷ"),
    "GEX": ("Tập đoàn GELEX", "18.700 tỷ"),
    "HCM": ("Chứng khoán TP.HCM (HSC)", "15.200 tỷ"),
    "KBC": ("Tổng Công ty Phát triển Đô thị Kinh Bắc", "23.200 tỷ"),
    "KDH": ("Công ty CP Đầu tư & KD Nhà Khang Điền", "29.800 tỷ"),
    "LPB": ("Ngân hàng Lộc Phát Việt Nam (LPBank)", "78.400 tỷ"),
    "NLG": ("Công ty CP Đầu tư Nam Long", "16.100 tỷ"),
    "NVL": ("Tập đoàn Đầu tư Địa ốc No Va (Novaland)", "24.500 tỷ"),
    "PDR": ("Công ty CP Phát triển BĐS Phát Đạt", "19.200 tỷ"),
    "PNJ": ("Công ty CP Vàng bạc Đá quý Phú Nhuận", "32.600 tỷ"),
    "PVD": ("Tổng Công ty Khoan Dầu khí (PV Drilling)", "15.600 tỷ"),
    "PVT": ("Tổng Công ty Vận tải Dầu khí (PVTrans)", "9.800 tỷ"),
    "REE": ("Công ty CP Cơ Điện Lạnh", "28.300 tỷ"),
    "VCI": ("Công ty CP Chứng khoán Vietcap", "21.600 tỷ"),
    "VND": ("Công ty CP Chứng khoán VNDIRECT", "19.500 tỷ"),
    "ACV": ("Tổng Công ty Cảng Hàng không Việt Nam", "248.000 tỷ"),
    "BSR": ("Công ty CP Lọc hóa dầu Bình Sơn", "74.500 tỷ"),
    "SHS": ("Công ty CP Chứng khoán Sài Gòn - Hà Nội", "14.200 tỷ"),
    "PVS": ("Tổng Công ty Dịch vụ Kỹ thuật Dầu khí", "19.500 tỷ"),
}


def _get_stock_info(symbol: str, is_vn: bool = True) -> tuple[str, str]:
    sym = (symbol or "").strip().upper()
    info = _STOCK_INFO.get(sym)
    if info:
        name, cap = info
        if not is_vn:
            cap = cap.replace("tỷ", "B VND")
        return name, cap
    return f"Công ty CP {sym}", "≥ 500 tỷ" if is_vn else "≥ 500B VND"


def _candidate_lines(candidates: Sequence[object], is_vn: bool = True) -> list[str]:
    from eod_collector.sources.vps_market import get_exchange

    if is_vn:
        lines = [f"{'STT':<4} {'MÃ CK':<7} {'SÀN':<7} {'GIÁ ĐÓNG CỬA':<15} {'VỐN HOÁ':<14} {'TÊN CÔNG TY'}"]
    else:
        lines = [f"{'RANK':<4} {'SYMBOL':<7} {'EXCH':<7} {'CLOSE PRICE':<15} {'MARKET CAP':<14} {'COMPANY NAME'}"]

    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        rank = str(item.get("rank", "—"))
        sym = str(item.get("symbol", "—")).upper()
        exchange = str(item.get("exchange") or get_exchange(sym))
        close_price = float(item.get("close_price", 0.0))
        pct_change = float(item.get("price_change_pct", 0.0))
        pct_str = f"({pct_change * 100:+.1f}%)" if close_price > 0 else ""
        price_str = f"{close_price:.1f} {pct_str}".strip() if close_price > 0 else "—"

        name, cap = _get_stock_info(sym, is_vn=is_vn)
        lines.append(f"{rank:<4} {sym:<7} {exchange:<7} {price_str:<15} {cap:<14} {name}")

    if len(lines) == 1:
        if is_vn:
            lines.append(" —    KHÔNG CÓ MÃ NÀO ĐẠT TIÊU CHUẨN LỌC")
        else:
            lines.append(" —    NO ELIGIBLE SYMBOL")
    return lines
