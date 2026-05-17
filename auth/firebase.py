import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)

def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    init_firebase()

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header manquant"
        )

    token = credentials.credentials

    try:
        decoded_token = auth.verify_id_token(token, clock_skew_seconds=10)        
        # Vérifier si l'utilisateur est désactivé par un admin
        if decoded_token.get("disabled", False):
            raise HTTPException(
                status_code=403,
                detail="Compte désactivé par un administrateur"
            )
        
        return decoded_token

    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expiré")

    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token révoqué")

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token Firebase invalide: {str(e)}"
        )


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Dépendance pour vérifier que l'utilisateur est un admin.
    Vérifie le custom claim Firebase "admin": true
    """
    init_firebase()

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header manquant"
        )

    token = credentials.credentials

    try:
        decoded_token = auth.verify_id_token(token, check_revoked=True, clock_skew_seconds=10)        
        # Vérifier le custom claim admin
        if not decoded_token.get("admin", False):
            raise HTTPException(
                status_code=403,
                detail="Accès refusé: Privilèges admin requis"
            )
        
        return decoded_token

    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expiré")

    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token révoqué")

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token Firebase invalide: {str(e)}"
        )