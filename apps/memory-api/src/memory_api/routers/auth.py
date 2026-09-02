from fastapi import APIRouter, Depends, HTTPException, Response, status

from memory_api.auth import get_session_user
from memory_api.config import settings
from memory_api.db.deps import get_google_verifier, get_identity_repository
from memory_api.db.identity import IdentityRepository
from memory_api.db.models import Org, User
from memory_api.schemas.auth import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    MeOut,
    OpenRouterOut,
    OpenRouterUpdate,
    OrgOut,
    UserOut,
)
from memory_api.services.api_keys import key_last4
from memory_api.services.google_auth import GoogleTokenError, GoogleTokenVerifier
from memory_api.services.secrets import encrypt_secret
from memory_api.services.session_tokens import issue_session_token

router = APIRouter()


@router.post("/auth/google", response_model=GoogleAuthResponse)
def google_auth(
    body: GoogleAuthRequest,
    response: Response,
    verifier: GoogleTokenVerifier = Depends(get_google_verifier),
    identities: IdentityRepository = Depends(get_identity_repository),
) -> GoogleAuthResponse:
    try:
        claims = verifier.verify(body.id_token)
    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        ) from exc
    user = identities.find_or_create_google_user(claims)
    token = issue_session_token(user)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return GoogleAuthResponse(token=token, user=UserOut.model_validate(user))


def _openrouter_out(org: Org) -> OpenRouterOut:
    return OpenRouterOut(
        configured=bool(org.openrouter_key_ciphertext),
        last4=org.openrouter_key_last4,
        model=org.openrouter_model,
    )


@router.get("/auth/me", response_model=MeOut)
def me(user: User = Depends(get_session_user)) -> MeOut:
    org = user.org
    return MeOut(
        user=UserOut.model_validate(user),
        org=OrgOut.model_validate(org),
        openrouter=_openrouter_out(org),
    )


@router.put("/auth/openrouter", response_model=OpenRouterOut)
def update_openrouter(
    body: OpenRouterUpdate,
    user: User = Depends(get_session_user),
    identities: IdentityRepository = Depends(get_identity_repository),
) -> OpenRouterOut:
    org = user.org
    ciphertext = org.openrouter_key_ciphertext
    last4 = org.openrouter_key_last4
    model = org.openrouter_model
    if body.api_key is not None:
        raw = body.api_key.strip()
        if raw == "":
            ciphertext = None
            last4 = None
            if body.model is None:
                model = None
        else:
            ciphertext = encrypt_secret(raw)
            last4 = key_last4(raw)
    if body.model is not None:
        model = body.model.strip() or None
    updated = identities.update_org_openrouter(
        org,
        ciphertext=ciphertext,
        last4=last4,
        model=model,
    )
    return _openrouter_out(updated)
