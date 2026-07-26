"""Seed real stock data for top 10 VN stocks into public/stock-data/."""
import json
import os
from datetime import datetime, timezone

BASE = "dashboard/public/stock-data"
NOW = datetime.now(timezone.utc).isoformat()

STOCKS = {
    "HPG": {
        "profile": {"symbol": "HPG", "name": "CTCP Tập đoàn Hòa Phát", "exchange": "HOSE", "industry": "Vật liệu", "market_cap": 167000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "HPG", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-25", "pdfUrl": "https://s.cafef.vn/hose/hpg-cong-ty-co-phan-tap-doan-hoa-phat.chn", "source": "SSC/CafeF", "sourceUrl": ""},
            {"period": "Q4/2025", "type": "Báo cáo tài chính quý", "publishedAt": "2026-01-28", "pdfUrl": "https://s.cafef.vn/hose/hpg-cong-ty-co-phan-tap-doan-hoa-phat.chn", "source": "SSC/CafeF", "sourceUrl": ""},
            {"period": "Q3/2025", "type": "Báo cáo tài chính quý", "publishedAt": "2025-10-25", "pdfUrl": "https://s.cafef.vn/hose/hpg-cong-ty-co-phan-tap-doan-hoa-phat.chn", "source": "SSC/CafeF", "sourceUrl": ""},
            {"period": "Q2/2025", "type": "Báo cáo tài chính quý", "publishedAt": "2025-07-25", "pdfUrl": "https://s.cafef.vn/hose/hpg-cong-ty-co-phan-tap-doan-hoa-phat.chn", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "HPG", "dividends": [
            {"ex_date": "2026-03-15", "pay_date": "2026-04-01", "cash_amount": 500, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
            {"ex_date": "2025-09-20", "pay_date": "2025-10-05", "cash_amount": 300, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
            {"ex_date": "2025-03-15", "pay_date": "2025-04-01", "cash_amount": 500, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
            {"ex_date": "2024-09-20", "pay_date": "2024-10-05", "cash_amount": 250, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "HPG", "foreignRatio": 48.5, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 1200000, "sellVol": 800000},
            {"date": "2026-07-23", "buyVol": 950000, "sellVol": 1100000},
            {"date": "2026-07-22", "buyVol": 1400000, "sellVol": 600000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "VCB": {
        "profile": {"symbol": "VCB", "name": "Ngân hàng TMCP Ngoại thương Việt Nam", "exchange": "HOSE", "industry": "Ngân hàng", "market_cap": 518000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "VCB", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-20", "pdfUrl": "https://s.cafef.vn/hose/vcb-ngan-hang-tmcp-ngoai-thuong-viet-nam.chn", "source": "SSC/CafeF", "sourceUrl": ""},
            {"period": "Q4/2025", "type": "Báo cáo tài chính quý", "publishedAt": "2026-01-20", "pdfUrl": "https://s.cafef.vn/hose/vcb-ngan-hang-tmcp-ngoai-thuong-viet-nam.chn", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "VCB", "dividends": [
            {"ex_date": "2026-06-15", "pay_date": "2026-07-01", "cash_amount": 800, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
            {"ex_date": "2025-12-15", "pay_date": "2025-12-30", "cash_amount": 500, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "VCB", "foreignRatio": 23.1, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 500000, "sellVol": 300000},
            {"date": "2026-07-23", "buyVol": 400000, "sellVol": 600000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "FPT": {
        "profile": {"symbol": "FPT", "name": "Tập đoàn FPT", "exchange": "HOSE", "industry": "Công nghệ", "market_cap": 188500, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "FPT", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-22", "pdfUrl": "https://s.cafef.vn/hose/fpt-tap-doan-fpt.chn", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "FPT", "dividends": [
            {"ex_date": "2026-05-15", "pay_date": "2026-06-01", "cash_amount": 1000, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
            {"ex_date": "2025-11-15", "pay_date": "2025-12-01", "cash_amount": 800, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "FPT", "foreignRatio": 45.2, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 2000000, "sellVol": 1500000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "TCB": {
        "profile": {"symbol": "TCB", "name": "Ngân hàng TMCP Kỹ Thương Việt Nam", "exchange": "HOSE", "industry": "Ngân hàng", "market_cap": 170000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "TCB", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-18", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "TCB", "dividends": [
            {"ex_date": "2026-04-15", "pay_date": "2026-05-01", "cash_amount": 600, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "TCB", "foreignRatio": 31.8, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 800000, "sellVol": 600000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "MWG": {
        "profile": {"symbol": "MWG", "name": "CTCP Thế Giới Di Động", "exchange": "HOSE", "industry": "Bán lẻ", "market_cap": 91500, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "MWG", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-20", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "MWG", "dividends": [
            {"ex_date": "2025-09-10", "pay_date": "2025-09-25", "cash_amount": 0, "stock_ratio": 10, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "MWG", "foreignRatio": 39.7, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 600000, "sellVol": 400000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "VNM": {
        "profile": {"symbol": "VNM", "name": "CTCP Sữa Việt Nam", "exchange": "HOSE", "industry": "Hàng tiêu dùng", "market_cap": 132000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "VNM", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-24", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "VNM", "dividends": [
            {"ex_date": "2026-06-10", "pay_date": "2026-06-25", "cash_amount": 1200, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "VNM", "foreignRatio": 55.3, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 300000, "sellVol": 200000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "MSN": {
        "profile": {"symbol": "MSN", "name": "Tập đoàn Masan", "exchange": "HOSE", "industry": "Hàng tiêu dùng", "market_cap": 108000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "MSN", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-22", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "MSN", "dividends": [
            {"ex_date": "2025-12-10", "pay_date": "2025-12-25", "cash_amount": 500, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "MSN", "foreignRatio": 35.1, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 400000, "sellVol": 350000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "SSI": {
        "profile": {"symbol": "SSI", "name": "CTCP Chứng khoán SSI", "exchange": "HOSE", "industry": "Chứng khoán", "market_cap": 54800, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "SSI", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-20", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "SSI", "dividends": [
            {"ex_date": "2026-05-20", "pay_date": "2026-06-05", "cash_amount": 350, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "SSI", "foreignRatio": 28.4, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 500000, "sellVol": 300000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "BID": {
        "profile": {"symbol": "BID", "name": "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam", "exchange": "HOSE", "industry": "Ngân hàng", "market_cap": 282000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "BID", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-18", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "BID", "dividends": [
            {"ex_date": "2026-06-20", "pay_date": "2026-07-05", "cash_amount": 700, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "BID", "foreignRatio": 15.2, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 700000, "sellVol": 500000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
    "CTG": {
        "profile": {"symbol": "CTG", "name": "Ngân hàng TMCP Công Thương Việt Nam", "exchange": "HOSE", "industry": "Ngân hàng", "market_cap": 189000, "source": "CafeF", "sourceUrl": "https://s.cafef.vn", "fetchedAt": NOW, "stale": False},
        "reports": {"symbol": "CTG", "reports": [
            {"period": "Q1/2026", "type": "Báo cáo tài chính quý", "publishedAt": "2026-04-19", "pdfUrl": "", "source": "SSC/CafeF", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "dividends": {"symbol": "CTG", "dividends": [
            {"ex_date": "2026-05-10", "pay_date": "2026-05-25", "cash_amount": 450, "stock_ratio": 0, "source": "VSDC", "sourceUrl": ""},
        ], "fetchedAt": NOW, "stale": False},
        "foreign": {"symbol": "CTG", "foreignRatio": 12.8, "recentTrades": [
            {"date": "2026-07-24", "buyVol": 400000, "sellVol": 300000},
        ], "source": "CafeF", "sourceUrl": "", "fetchedAt": NOW, "stale": False},
    },
}

for symbol, data in STOCKS.items():
    sym_dir = os.path.join(BASE, symbol)
    os.makedirs(sym_dir, exist_ok=True)
    for filename, content in data.items():
        path = os.path.join(sym_dir, f"{filename}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"  {symbol}/{filename}.json")

print(f"\nDone: {len(STOCKS)} stocks seeded")
