"""
Authentication API endpoints
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field, validator

from src.core.database import get_db

logger = logging.getLogger(__name__)
from src.core.auth import (
    create_access_token,
    create_refresh_token,
    generate_token_family,
    refresh_access_token,
    get_current_user,
    get_current_active_user,
)
from src.services.user import UserService, InvalidCredentialsError, UserAlreadyExistsError
from src.models.database import User, UserRole, UserAddress
from src.core.config import settings


router = APIRouter(tags=["authentication"])


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
    
    @validator('id', pre=True)
    def convert_uuid_to_string(cls, v):
        return str(v) if v else v


class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = Field(None, max_length=50)
    locale: Optional[str] = Field(None, max_length=10)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            # Basic phone number validation (can be enhanced)
            v = ''.join(filter(str.isdigit, v))
            if len(v) < 10:
                raise ValueError('Phone number must have at least 10 digits')
        return v


class EmailUpdateRequest(BaseModel):
    new_email: EmailStr
    password: str = Field(..., description="Current password for verification")


class AddressRequest(BaseModel):
    address_line1: str = Field(..., max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., max_length=100)
    state_province: str = Field(..., max_length=100)
    postal_code: str = Field(..., max_length=20)
    country: str = Field(default="US", max_length=2)
    label: Optional[str] = Field(None, max_length=50)
    is_primary: bool = Field(default=False)
    
    @validator('postal_code')
    def validate_postal_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Postal code is required')
        return v.strip()
    
    @validator('state_province')
    def validate_state_province(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('State/Province is required')
        return v.strip()


class AddressUpdateRequest(BaseModel):
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state_province: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=2)
    
    @validator('postal_code')
    def validate_postal_code(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Postal code cannot be empty')
        return v.strip() if v else v
    
    @validator('state_province')
    def validate_state_province(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('State/Province cannot be empty')
        return v.strip() if v else v


class AddressResponse(BaseModel):
    id: str
    address_line1: str
    address_line2: Optional[str]
    city: str
    state_province: str
    postal_code: str
    country: str
    latitude: Optional[str]
    longitude: Optional[str]
    label: Optional[str]
    is_primary: bool
    verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    """Request to change password"""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH)


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
        import traceback
        logger.error(f"Registration failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {str(e)}"
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


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile information"""
    user_service = UserService(db)
    
    try:
        # Only update fields that were provided
        update_data = user_data.dict(exclude_unset=True)
        
        if update_data:
            updated_user = await user_service.update_user(
                user_id=current_user.id,
                **update_data
            )
            
            # Log profile update
            await user_service.create_audit_log(
                user_id=current_user.id,
                event_type="profile_updated",
                event_category="profile",
                event_description="User updated profile information"
            )
            
            return UserResponse.from_orm(updated_user)
        else:
            return UserResponse.from_orm(current_user)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.put("/email", response_model=MessageResponse)
async def update_user_email(
    email_data: EmailUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user email address (requires password verification)"""
    user_service = UserService(db)
    
    try:
        # Verify current password
        if not await user_service.verify_password(current_user.id, email_data.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password"
            )
        
        # Check if new email is already taken
        existing_user = await user_service.get_by_email(email_data.new_email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use"
            )
        
        # Update email
        await user_service.update_user(
            user_id=current_user.id,
            email=email_data.new_email,
            is_verified=False  # Require re-verification
        )
        
        # TODO: Send verification email to new address
        # For now, just log the change
        
        # Log email change
        await user_service.create_audit_log(
            user_id=current_user.id,
            event_type="email_changed",
            event_category="profile",
            event_description=f"User changed email from {current_user.email} to {email_data.new_email}"
        )
        
        return MessageResponse(message="Email updated successfully. Please verify your new email address.")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update email: {str(e)}"
        )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    user_service = UserService(db)
    
    try:
        await user_service.update_password(
            user_id=current_user.id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
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


@router.post("/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def add_user_address(
    address_data: AddressRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a new address for the current user"""
    user_service = UserService(db)
    
    try:
        address = await user_service.add_address(
            user_id=current_user.id,
            address_line1=address_data.address_line1,
            address_line2=address_data.address_line2,
            city=address_data.city,
            state_province=address_data.state_province,
            postal_code=address_data.postal_code,
            country=address_data.country,
            label=address_data.label,
            is_primary=address_data.is_primary
        )
        
        # Log address creation
        await user_service.create_audit_log(
            user_id=current_user.id,
            event_type="address_added",
            event_category="profile",
            event_description=f"User added address: {address_data.city}, {address_data.state_province}"
        )
        
        return AddressResponse.from_orm(address)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add address: {str(e)}"
        )


@router.get("/addresses/home", response_model=AddressResponse)
async def get_user_address(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the user's home address"""
    user_service = UserService(db)
    
    try:
        addresses = await user_service.get_user_addresses(current_user.id)
        home_address = next((addr for addr in addresses if addr.is_primary), None)
        
        if not home_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No home address found"
            )
        
        return AddressResponse.from_orm(home_address)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get address: {str(e)}"
        )


@router.put("/addresses/home", response_model=AddressResponse)
async def update_user_address(
    address_data: AddressUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update the user's home address"""
    user_service = UserService(db)
    
    try:
        # Get current home address
        addresses = await user_service.get_user_addresses(current_user.id)
        home_address = next((addr for addr in addresses if addr.is_primary), None)
        
        if not home_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No home address found to update"
            )
        
        # Only update fields that were provided
        update_data = address_data.dict(exclude_unset=True)
        
        if update_data:
            updated_address = await user_service.update_address(
                address_id=home_address.id,
                user_id=current_user.id,
                **update_data
            )
            
            # Log address update
            await user_service.create_audit_log(
                user_id=current_user.id,
                event_type="address_updated",
                event_category="profile",
                event_description=f"User updated home address: {update_data.get('city', 'Unknown')}, {update_data.get('state_province', 'Unknown')}"
            )
            
            return AddressResponse.from_orm(updated_address)
        else:
            return AddressResponse.from_orm(home_address)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update address: {str(e)}"
        )