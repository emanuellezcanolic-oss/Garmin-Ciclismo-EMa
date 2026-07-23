"""Conexión con Garmin Connect usando python-garminconnect (cyberjunky).

Maneja login con usuario/contraseña, MFA (código por mail/SMS) y guarda la
sesión en disco (GARMIN_TOKEN_DIR) para no pedir login cada vez.
"""

import logging
import os
import shutil
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

logger = logging.getLogger(__name__)

TOKEN_DIR = str(Path(os.getenv("GARMIN_TOKEN_DIR", ".garmin_tokens")).expanduser())

_client: Garmin | None = None
_pending_mfa = None  # (garmin, client_state) mientras espera el código MFA


class MfaRequired(Exception):
    pass


def get_client() -> Garmin | None:
    """Devuelve el cliente logueado, intentando reutilizar la sesión guardada."""
    global _client
    if _client is not None:
        return _client
    # 1) sesión guardada en disco
    if Path(TOKEN_DIR).exists():
        try:
            g = Garmin()
            g.login(TOKEN_DIR)
            _client = g
            logger.info("Sesión de Garmin restaurada desde tokens guardados")
            return g
        except Exception as e:
            logger.warning("No se pudo restaurar la sesión guardada: %s", e)
    # 2) credenciales en .env
    email = os.getenv("GARMIN_EMAIL", "").strip()
    password = os.getenv("GARMIN_PASSWORD", "").strip()
    if email and password:
        try:
            return login(email, password)
        except MfaRequired:
            raise
        except Exception as e:
            logger.warning("Login automático con .env falló: %s", e)
    return None


def login(email: str, password: str) -> Garmin:
    """Login con usuario/contraseña. Lanza MfaRequired si Garmin pide código."""
    global _client, _pending_mfa
    g = Garmin(email=email, password=password, return_on_mfa=True)
    result1, result2 = g.login()
    if result1 == "needs_mfa":
        _pending_mfa = (g, result2)
        raise MfaRequired()
    _save_tokens(g)
    _client = g
    return g


def submit_mfa(code: str) -> Garmin:
    """Completa el login cuando Garmin pidió un código MFA."""
    global _client, _pending_mfa
    if _pending_mfa is None:
        raise GarminConnectAuthenticationError("No hay un login pendiente de MFA")
    g, client_state = _pending_mfa
    g.resume_login(client_state, code.strip())
    _pending_mfa = None
    _save_tokens(g)
    _client = g
    return g


def logout():
    """Borra la sesión guardada."""
    global _client, _pending_mfa
    _client = None
    _pending_mfa = None
    if Path(TOKEN_DIR).exists():
        shutil.rmtree(TOKEN_DIR, ignore_errors=True)


def _save_tokens(g: Garmin):
    Path(TOKEN_DIR).mkdir(parents=True, exist_ok=True)
    # garminconnect >= 0.3 guarda la sesión en g.client; versiones viejas en g.garth
    if hasattr(g, "client") and hasattr(g.client, "dump"):
        g.client.dump(TOKEN_DIR)
    else:
        g.garth.dump(TOKEN_DIR)
    logger.info("Tokens de Garmin guardados en %s", TOKEN_DIR)


def profile_name() -> str | None:
    g = get_client()
    if g is None:
        return None
    try:
        return g.get_full_name()
    except Exception:
        return None
