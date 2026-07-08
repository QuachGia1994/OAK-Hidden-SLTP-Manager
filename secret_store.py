# -*- coding: utf-8 -*-
"""Secure token storage using Windows Credential Manager (keyring)."""
import json
import os
from oak_logger import setup_logger

log = setup_logger("secrets")

_SERVICE_NAME = "OAK Manager"


def _get_keyring():
    """Get keyring backend, fallback to file-based if unavailable."""
    try:
        import keyring
        return keyring
    except ImportError:
        log.warning("keyring not installed, falling back to plaintext storage")
        return None


def store_secret(profile_name, key, value):
    """Store a secret value for a profile."""
    kr = _get_keyring()
    identifier = f"{_SERVICE_NAME}:{profile_name}:{key}"
    if kr:
        try:
            kr.set_password(_SERVICE_NAME, identifier, value)
            log.info("Stored secret: %s", identifier)
            return True
        except Exception as e:
            log.warning("keyring store failed: %s, falling back to config", e)
    # Fallback: store in profiles.json with prefix
    return False


def get_secret(profile_name, key, default=""):
    """Retrieve a secret value for a profile."""
    kr = _get_keyring()
    identifier = f"{_SERVICE_NAME}:{profile_name}:{key}"
    if kr:
        try:
            val = kr.get_password(_SERVICE_NAME, identifier)
            if val:
                return val
        except Exception as e:
            log.warning("keyring get failed: %s", e)
    return default


def delete_secret(profile_name, key):
    """Delete a secret value for a profile."""
    kr = _get_keyring()
    identifier = f"{_SERVICE_NAME}:{profile_name}:{key}"
    if kr:
        try:
            kr.delete_password(_SERVICE_NAME, identifier)
            log.info("Deleted secret: %s", identifier)
            return True
        except Exception:
            pass
    return False


def migrate_plaintext_tokens(profiles):
    """One-time migration: move tele_token from profiles.json to keyring.

    Returns number of migrated tokens.
    """
    kr = _get_keyring()
    if not kr:
        log.info("keyring unavailable, skip token migration")
        return 0

    migrated = 0
    for name, data in profiles.items():
        token = data.get("tele_token", "")
        if token and not token.startswith("__vault__:"):
            try:
                kr.set_password(_SERVICE_NAME, f"{_SERVICE_NAME}:{name}:tele_token", token)
                data["tele_token"] = "__vault__"
                migrated += 1
                log.info("Migrated token for profile: %s", name)
            except Exception as e:
                log.warning("Migration failed for %s: %s", name, e)

    if migrated > 0:
        profiles_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")
        try:
            with open(profiles_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
            log.info("Saved profiles after migration (%d tokens)", migrated)
        except Exception as e:
            log.warning("Failed to save profiles after migration: %s", e)

    return migrated


def get_token_for_profile(profile_name):
    """Get Telegram token for a profile (from keyring or plaintext fallback)."""
    kr = _get_keyring()
    identifier = f"{_SERVICE_NAME}:{profile_name}:tele_token"
    if kr:
        try:
            val = kr.get_password(_SERVICE_NAME, identifier)
            if val:
                return val
        except Exception:
            pass
    # Fallback: read from profiles.json
    profiles_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")
    try:
        with open(profiles_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
        return profiles.get(profile_name, {}).get("tele_token", "")
    except Exception:
        return ""
