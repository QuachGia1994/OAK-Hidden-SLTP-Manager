# -*- coding: utf-8 -*-
"""Secure token storage using Windows Credential Manager (keyring)."""
import json
import os
from oak_logger import setup_logger

log = setup_logger("secrets")

_SERVICE_NAME = "OAK Manager"


def _get_keyring():
    """Get keyring backend. Raises if unavailable."""
    try:
        import keyring
        return keyring
    except ImportError:
        raise RuntimeError("keyring not installed. Run: pip install keyring")


def is_keyring_available():
    """Check if keyring is available without raising."""
    try:
        import keyring
        return True
    except ImportError:
        return False


def store_secret(profile_name, key, value):
    """Store a secret value for a profile. Raises RuntimeError if keyring unavailable."""
    kr = _get_keyring()
    identifier = f"{_SERVICE_NAME}:{profile_name}:{key}"
    try:
        kr.set_password(_SERVICE_NAME, identifier, value)
        log.info("Stored secret: %s", identifier)
        return True
    except Exception as e:
        log.error("keyring store failed: %s", e)
        raise RuntimeError(f"Failed to store secret: {e}")


def get_secret(profile_name, key, default=""):
    """Retrieve a secret value for a profile."""
    try:
        kr = _get_keyring()
    except RuntimeError:
        return default
    identifier = f"{_SERVICE_NAME}:{profile_name}:{key}"
    try:
        val = kr.get_password(_SERVICE_NAME, identifier)
        if val:
            return val
    except Exception:
        pass
    return default


def delete_secret(profile_name, key):
    """Delete a secret value for a profile."""
    try:
        kr = _get_keyring()
    except RuntimeError:
        return False
    identifier = f"{_SERVICE_NAME}:{profile_name}:{key}"
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
    try:
        kr = _get_keyring()
    except RuntimeError:
        log.warning("keyring unavailable, skip token migration")
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
    """Get Telegram token for a profile (from keyring only, no plaintext fallback)."""
    try:
        kr = _get_keyring()
    except RuntimeError:
        return ""
    identifier = f"{_SERVICE_NAME}:{profile_name}:tele_token"
    try:
        val = kr.get_password(_SERVICE_NAME, identifier)
        if val:
            return val
    except Exception:
        pass
    return ""


def resolve_telegram_token(profile_name, raw_token=None, global_fallback=""):
    """Resolve Telegram token: real token -> return as-is, __vault__/empty -> keyring lookup,
    then global fallback if keyring fails.

    Returns real token string, or empty string on failure. Never returns __vault__.
    """
    if raw_token and raw_token != "__vault__":
        return raw_token
    if profile_name:
        token = get_token_for_profile(profile_name)
        if token:
            return token
    return global_fallback
