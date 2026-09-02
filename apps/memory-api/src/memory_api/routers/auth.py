from fastapi import APIRouter, Depends, HTTPException, Response, status

from memory_api.config import settings
from memory_api.db.deps import get_google_verifier, get_identity_repository
from memory_api.db.identity import IdentityRepository
from memory_api.schemas.auth import GoogleAuthRequest, GoogleAuthResponse, UserOut
from memory_api.services.google_auth import GoogleTokenError, GoogleTokenVerifier
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
