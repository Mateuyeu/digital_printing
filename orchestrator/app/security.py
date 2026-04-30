"""Authentification basique (HTTP Basic) - simple, suffisant pour MSSP interne.
Pour exposition publique, mettre derriere un reverse proxy avec OIDC/SSO."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from .config import get_settings

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    settings = get_settings()
    correct_user = secrets.compare_digest(credentials.username.encode("utf-8"),
                                          settings.admin_user.encode("utf-8"))
    correct_pwd = secrets.compare_digest(credentials.password.encode("utf-8"),
                                         settings.admin_password.encode("utf-8"))
    if not (correct_user and correct_pwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
