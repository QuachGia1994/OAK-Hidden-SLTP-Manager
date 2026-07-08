
"""
Auto-update module for OAK Manager
Checks GitHub releases for updates and offers to install them
"""

import requests
import packaging.version
import os
import sys
import webbrowser
import logging
from typing import Optional, Dict, Any

# Get logger
logger = logging.getLogger(__name__)

GITHUB_REPO_OWNER = "QuachGia1994"
GITHUB_REPO_NAME = "OAK-Hidden-SLTP-Manager"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"


def get_current_version() -> str:
    """Get current app version from OAK_Hidden_SLTP_Manager.py"""
    version = "0.0.0"  # Default fallback
    try:
        from __main__ import VERSION as main_version
        return main_version
    except ImportError:
        # If running not from main, try to read directly
        try:
            main_path = os.path.join(os.path.dirname(__file__), "..", "OAK_Hidden_SLTP_Manager.py")
            if os.path.exists(main_path):
                import re
                with open(main_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
                    if match:
                        return match.group(1)
        except Exception as e:
            logger.warning(f"Could not read current version: {e}")
    return version


def check_for_update() -> Optional[Dict[str, Any]]:
    """
    Check GitHub for latest release
    Returns: None if no update, or dict with release info if update available
    """
    current_ver_str = get_current_version()
    try:
        current_ver = packaging.version.parse(current_ver_str)
        logger.info(f"Current version: {current_ver_str}")

        response = requests.get(GITHUB_API_URL, timeout=10)
        if response.status_code == 200:
            release = response.json()
            latest_ver_str = release.get("tag_name", "v0.0.0").lstrip("v")
            latest_ver = packaging.version.parse(latest_ver_str)
            logger.info(f"Latest version on GitHub: {latest_ver_str}")

            if latest_ver > current_ver:
                return {
                    "version": latest_ver_str,
                    "url": release.get("html_url"),
                    "assets": release.get("assets", []),
                    "body": release.get("body", ""),
                }
            else:
                logger.info("You are running the latest version!")
                return None
        else:
            logger.warning(f"Failed to check updates, status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return None


def open_release_page(release_url: str):
    """Open GitHub release page in browser"""
    try:
        webbrowser.open(release_url)
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)
    update_info = check_for_update()
    if update_info:
        print(f"New version available: {update_info['version']}")
        print(f"URL: {update_info['url']}")
    else:
        print("No update available")
