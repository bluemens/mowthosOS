"""JWT Authentication utilities"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import secrets
import uuid
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.models.database import User, RefreshToken
from src.services.user import UserService
from src.core.password import hash_password, verify_password


# JWT Bearer token security
security = HTTPBearer()


class AuthenticationError(Exception):
    """Authentication related errors"""
    pass


class TokenBlacklistError(Exception):
    """Token has been blacklisted"""
    pass


def generate_token_family() -> str:
    """Generate a new token family ID for refresh token rotation"""
    return str(uuid.uuid4())


def create_access_token(
    user_id: str,
    role: str,
    permissions: Dict[str, Any] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + settings.access_token_expire_timedelta
    
    payload = {
        "sub": user_id,  # Subject (user ID)
        "role": role,
        "permissions": permissions or {},
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
        "jti": str(uuid.uuid4()),  # JWT ID for potential blacklisting
    }
    
    encoded_jwt = jwt.encode(
        payload, 
        settings.JWT_SECRET_KEY.get_secret_value(), 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    user_id: str,
    token_family: str,
    device_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + settings.refresh_token_expire_timedelta
    
    payload = {
        "sub": user_id,
        "family": token_family,
        "device_id": device_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    
    encoded_jwt = jwt.encode(
        payload, 
        settings.JWT_REFRESH_SECRET_KEY.get_secret_value(), 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate an access token"""
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY.get_secret_value(), 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """Decode and validate a refresh token"""
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_REFRESH_SECRET_KEY.get_secret_value(), 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Refresh token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid refresh token: {str(e)}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token"""
    token = credentials.credentials
    
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise AuthenticationError("Invalid token payload")
        
        # Get user from database
        user_service = UserService(db)
        user = await user_service.get_by_id(user_id)
        
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
        
        # Update last activity
        await user_service.update_last_activity(user_id)
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure the current user is active"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


def require_role(required_role: str):
    """Dependency to require a specific role"""
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user
    return role_checker


def require_permission(permission: str):
    """Dependency to require a specific permission"""
    async def permission_checker(current_user: User = Depends(get_current_active_user)):
        user_permissions = current_user.permissions or {}
        
        # Admins have all permissions
        if current_user.role == "admin":
            return current_user
        
        # Check specific permission
        if not user_permissions.get(permission, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}"
            )
        return current_user
    return permission_checker


async def refresh_access_token(
    refresh_token: str,
    db: AsyncSession
) -> Tuple[str, str]:
    """
    Refresh an access token using a refresh token.
    Implements token rotation for security.
    Returns: (new_access_token, new_refresh_token)
    """
    try:
        # Decode the refresh token
        payload = decode_refresh_token(refresh_token)
        user_id = payload.get("sub")
        token_family = payload.get("family")
        
        if not user_id or not token_family:
            raise AuthenticationError("Invalid refresh token payload")
        
        # Check if token exists and is active
        user_service = UserService(db)
        stored_token = await user_service.get_refresh_token(refresh_token)
        
        if not stored_token:
            raise AuthenticationError("Refresh token not found")
        
        if not stored_token.is_active:
            # Token has been revoked - possible token reuse attack
            # Revoke all tokens in the family
            await user_service.revoke_token_family(token_family)
            raise TokenBlacklistError("Token has been revoked - possible security breach")
        
        # Get user
        user = await user_service.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        
        # Create new tokens
        new_access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
            permissions=user.permissions
        )
        
        new_refresh_token = create_refresh_token(
            user_id=str(user.id),
            token_family=token_family,
            device_id=payload.get("device_id")
        )
        
        # Store new refresh token and mark old one as replaced
        await user_service.rotate_refresh_token(
            old_token=refresh_token,
            new_token=new_refresh_token,
            token_family=token_family,
            expires_at=datetime.utcnow() + settings.refresh_token_expire_timedelta
        )
        
        return new_access_token, new_refresh_token
        
    except (AuthenticationError, TokenBlacklistError):
        raise
    except Exception as e:
        raise AuthenticationError(f"Failed to refresh token: {str(e)}")


def generate_api_key() -> Tuple[str, str]:
    """
    Generate a new API key.
    Returns: (full_key, key_prefix)
    """
    # Generate a secure random key
    key = secrets.token_urlsafe(32)
    # Prefix for identification (first 8 chars)
    prefix = key[:8]
    
    return key, prefix