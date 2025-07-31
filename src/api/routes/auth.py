"""Authentication API endpoints"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field, validator

from src.core.database import get_db
from src.core.auth import (
    create_access_token,
    create_refresh_token,
    generate_token_family,
    refresh_access_token,
    get_current_user,
    get_current_active_user,
)
from src.services.user import UserService, InvalidCredentialsError, UserAlreadyExistsError
from src.models.database import User, UserRole
from src.core.config import settings


router = APIRouter(prefix="/auth", tags=["authentication"])


# Request/Response Models
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f'Password must be at least {settings.PASSWORD_MIN_LENGTH} characters')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: Optional[str] = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


# Utility functions
def get_client_info(request: Request) -> dict:
    """Extract client information from request"""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


# API Endpoints
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    user_service = UserService(db)
    
    try:
        user = await user_service.create_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            username=user_data.username,
            role=UserRole.USER,
        )
        
        # Log registration with client info
        client_info = get_client_info(request)
        await user_service.create_audit_log(
            user_id=user.id,
            event_type="user_registered",
            event_category="auth",
            event_description="User registered via API",
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )
        
        return UserResponse.from_orm(user)
        
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password"""
    user_service = UserService(db)
    
    try:
        # Authenticate user
        user = await user_service.authenticate(
            email=credentials.email,
            password=credentials.password
        )
        
        # Create tokens
        token_family = generate_token_family()
        access_token = create_access_token(
            user_id=str(user.id),
            role=user.role,
            permissions=user.permissions
        )
        refresh_token = create_refresh_token(
            user_id=str(user.id),
            token_family=token_family,
            device_id=credentials.device_name
        )
        
        # Store refresh token
        await user_service.create_refresh_token(
            user_id=user.id,
            token=refresh_token,
            token_family=token_family,
            expires_at=datetime.utcnow() + settings.refresh_token_expire_timedelta,
            device_name=credentials.device_name
        )
        
        # Create session
        client_info = get_client_info(request)
        await user_service.create_session(
            user_id=user.id,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            device_info={"device_name": credentials.device_name} if credentials.device_name else None
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to login"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        access_token, new_refresh_token = await refresh_access_token(
            refresh_token=token_data.refresh_token,
            db=db
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout current user (revoke all tokens)"""
    user_service = UserService(db)
    
    # Revoke all user sessions and tokens
    await user_service.revoke_all_user_sessions(current_user.id)
    await user_service.revoke_all_user_tokens(current_user.id)
    
    # Log logout
    await user_service.create_audit_log(
        user_id=current_user.id,
        event_type="user_logout",
        event_category="auth",
        event_description="User logged out, all tokens revoked"
    )
    
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return UserResponse.from_orm(current_user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    old_password: str = Field(..., description="Current password"),
    new_password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    user_service = UserService(db)
    
    try:
        await user_service.update_password(
            user_id=current_user.id,
            old_password=old_password,
            new_password=new_password
        )
        
        # Revoke all tokens after password change
        await user_service.revoke_all_user_tokens(current_user.id)
        
        return MessageResponse(message="Password changed successfully. Please login again.")
        
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )