
"""
Error reporting service for OAK Manager
Handles collecting and optionally sending error logs
"""
import logging
import traceback
import json
from datetime import datetime
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

ERROR_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "error_reports.json")


def get_system_info() -> Dict[str, Any]:
    """Get basic system information for error reports"""
    import sys
    import platform
    try:
        from __main__ import VERSION as app_version
    except ImportError:
        app_version = "unknown"
    return {
        "app_version": app_version,
        "python_version": sys.version,
        "os": platform.system() + " " + platform.release(),
        "timestamp": datetime.now().isoformat(),
    }


def log_exception(
    exc_type: Optional[type],
    exc_value: Optional[Exception],
    exc_traceback: Optional[traceback],
    additional_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Log an exception to both the regular logger and error reports file
    """
    # Build error report
    error_report = get_system_info()
    if additional_context:
        error_report["context"] = additional_context

    if exc_type and exc_value and exc_traceback:
        error_report["error_type"] = exc_type.__name__
        error_report["error_message"] = str(exc_value)
        error_report["stack_trace"] = traceback.format_exception(exc_type, exc_value, exc_traceback)

    # Log to our regular logger
    logger.error(
        f"Exception occurred: {error_report.get('error_type', 'Unknown')}: {error_report.get('error_message', '')}"
    )
    if exc_traceback:
        logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))

    # Save to error reports file
    try:
        os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)

        if os.path.exists(ERROR_LOG_PATH):
            with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
                try:
                    reports = json.load(f)
                except Exception:
                    reports = []
        else:
            reports = []

        reports.append(error_report)

        # Keep only last 50 error reports
        if len(reports) > 50:
            reports = reports[-50:]

        with open(ERROR_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Could not save error report to file: {e}")

    return error_report


def get_error_reports(limit: int = 10) -> list:
    """
    Get recent error reports
    """
    try:
        if os.path.exists(ERROR_LOG_PATH):
            with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
                reports = json.load(f)
                return reports[-limit:]
    except Exception as e:
        logger.error(f"Could not load error reports: {e}")
        return []


def clear_error_reports() -> None:
    """Clear all saved error reports"""
    try:
        if os.path.exists(ERROR_LOG_PATH):
            os.remove(ERROR_LOG_PATH)
            logger.info("Error reports cleared successfully")
    except Exception as e:
        logger.error(f"Could not clear error reports: {e}")
