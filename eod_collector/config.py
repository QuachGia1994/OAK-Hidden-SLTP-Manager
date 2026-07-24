"""Configuration loader for Local EOD Market Data Collector."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import json as tomllib  # type: ignore


@dataclass(slots=True)
class DatabaseConfig:
    path: Path = Path("data/market.db")


@dataclass(slots=True)
class CollectorConfig:
    raw_data_dir: Path = Path("data/raw")
    manual_data_dir: Path = Path("data/manual")
    request_timeout_seconds: int = 30
    max_retries: int = 3
    minimum_symbols_hose: int = 30
    minimum_symbols_hnx: int = 10
    minimum_symbols_upcom: int = 10
    holidays: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourcesConfig:
    hose_enabled: bool = True
    hnx_enabled: bool = True
    upcom_enabled: bool = True


@dataclass(slots=True)
class Config:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    root_dir: Path = field(default_factory=lambda: Path.cwd())

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> Config:
        root = Path.cwd()
        path = Path(config_path) if config_path else root / "config.toml"
        if not path.exists():
            path = root / "config.example.toml"
        
        cfg = cls(root_dir=root)
        if path.exists():
            try:
                data = path.read_text(encoding="utf-8")
                if hasattr(tomllib, "loads"):
                    parsed = tomllib.loads(data)
                else:
                    parsed = {}
                cfg._apply_dict(parsed)
            except Exception:
                pass
        return cfg

    def _apply_dict(self, data: dict[str, Any]) -> None:
        db_cfg = data.get("database", {})
        if "path" in db_cfg:
            self.database.path = Path(db_cfg["path"])

        col_cfg = data.get("collector", {})
        if "raw_data_dir" in col_cfg:
            self.collector.raw_data_dir = Path(col_cfg["raw_data_dir"])
        if "manual_data_dir" in col_cfg:
            self.collector.manual_data_dir = Path(col_cfg["manual_data_dir"])
        if "request_timeout_seconds" in col_cfg:
            self.collector.request_timeout_seconds = int(col_cfg["request_timeout_seconds"])
        if "max_retries" in col_cfg:
            self.collector.max_retries = int(col_cfg["max_retries"])
        if "minimum_symbols_hose" in col_cfg:
            self.collector.minimum_symbols_hose = int(col_cfg["minimum_symbols_hose"])
        if "minimum_symbols_hnx" in col_cfg:
            self.collector.minimum_symbols_hnx = int(col_cfg["minimum_symbols_hnx"])
        if "minimum_symbols_upcom" in col_cfg:
            self.collector.minimum_symbols_upcom = int(col_cfg["minimum_symbols_upcom"])
        if "holidays" in col_cfg and isinstance(col_cfg["holidays"], list):
            self.collector.holidays = [str(h) for h in col_cfg["holidays"]]

        src_cfg = data.get("sources", {})
        if "hose_enabled" in src_cfg:
            self.sources.hose_enabled = bool(src_cfg["hose_enabled"])
        if "hnx_enabled" in src_cfg:
            self.sources.hnx_enabled = bool(src_cfg["hnx_enabled"])
        if "upcom_enabled" in src_cfg:
            self.sources.upcom_enabled = bool(src_cfg["upcom_enabled"])
