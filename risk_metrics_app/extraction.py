"""Utilities for proxying API data extraction within the Streamlit app."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .config import OUTPUT_DIR, logger


def parse_perimeter_input(perimeter_raw: str) -> list[str]:
    """Split a comma-separated perimeter string into clean entries."""
    if not perimeter_raw:
        return []
    return [value.strip() for value in perimeter_raw.split(",") if value.strip()]


def ensure_download_directory(download_dir: str | Path | None) -> Path:
    """Return a writable download directory, creating it when needed."""
    target_dir = Path(download_dir or OUTPUT_DIR).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _build_proxy_dataset(
    username: str, perimeters: Sequence[str], start_date: datetime | None = None, end_date: datetime | None = None
) -> pd.DataFrame:
    """Create a deterministic DataFrame that mirrors an API CSV payload."""
    effective_perimeters = list(perimeters) or ["GLOBAL"]
    rows: list[dict[str, object]] = []

    # If dates not provided, use current date and previous days based on perimeter count
    if start_date is None or end_date is None:
        base_date = datetime.utcnow().date()
        for idx, perimeter in enumerate(effective_perimeters):
            request_date = base_date - timedelta(days=idx)
            rows.append(
                {
                    "ValueDate": request_date.isoformat(),
                    "Perimeter": perimeter,
                    "Metric": "VaR",
                    "Value": round(0.08 + idx * 0.01, 4),
                    "RequestedBy": username,
                }
            )
            rows.append(
                {
                    "ValueDate": request_date.isoformat(),
                    "Perimeter": perimeter,
                    "Metric": "SVaR",
                    "Value": round(0.11 + idx * 0.012, 4),
                    "RequestedBy": username,
                }
            )
    else:
        # Generate dates within the specified range
        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date
        current_date = start
        date_idx = 0
        
        while current_date <= end:
            for perimeter in effective_perimeters:
                rows.append(
                    {
                        "ValueDate": current_date.isoformat(),
                        "Perimeter": perimeter,
                        "Metric": "VaR",
                        "Value": round(0.08 + date_idx * 0.01, 4),
                        "RequestedBy": username,
                    }
                )
                rows.append(
                    {
                        "ValueDate": current_date.isoformat(),
                        "Perimeter": perimeter,
                        "Metric": "SVaR",
                        "Value": round(0.11 + date_idx * 0.012, 4),
                        "RequestedBy": username,
                    }
                )
            current_date += timedelta(days=1)
            date_idx += 1

    return pd.DataFrame(rows)


def extract_data_via_proxy(
    username: str,
    password: str,
    perimeters: Iterable[str],
    download_dir: str | Path | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[Path, dict[str, object]]:
    """Simulate an API CSV download and persist it, returning path and diagnostics."""
    clean_perimeters = [item for item in perimeters if item]
    if not username:
        raise ValueError("Username is required")
    if not password:
        raise ValueError("Password is required")
    if not clean_perimeters:
        raise ValueError("At least one perimeter is required")
    
    # Validate date parameters
    if (start_date is None) != (end_date is None):
        raise ValueError("Both start_date and end_date must be provided together, or neither")
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")

    download_path = ensure_download_directory(download_dir)
    file_name = f"api_extract_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    file_path = download_path / file_name

    dataset = _build_proxy_dataset(
        username=username, perimeters=clean_perimeters, start_date=start_date, end_date=end_date
    )
    dataset.to_csv(file_path, index=False)

    password_checksum = sha256(password.encode("utf-8")).hexdigest()[:8]
    logger.info(
        "Proxy API extraction stored at %s for user=%s perimeters=%s start_date=%s end_date=%s",
        file_path,
        username,
        clean_perimeters,
        start_date,
        end_date,
    )

    payload_summary = {
        "username": username,
        "perimeters": clean_perimeters,
        "row_count": len(dataset),
        "download_path": str(file_path),
        "password_checksum": password_checksum,
        "generated_at": datetime.utcnow().isoformat(),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }

    return file_path, payload_summary
