"""User service for managing user operations"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import secrets
from sqlalchemy import select, update, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import hash_password, verify_password
from src.models.database import (
    User, UserAddress, UserSession, RefreshToken, 
    APIKey, AuditLog, UserRole
)
from src.core.config import settings


class UserNotFoundError(Exception):
    """User not found error"""
    pass


class UserAlreadyExistsError(Exception):
    """User already exists error"""
    pass


class InvalidCredentialsError(Exception):
    """Invalid credentials error"""
    pass


class UserService:
    """Service for managing users"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Create a new user"""
        # Check if user already exists
        existing_user = await self.get_by_email(email)
        if existing_user:
            raise UserAlreadyExistsError(f"User with email {email} already exists")
        
        if username:
            existing_username = await self.get_by_username(username)
            if existing_username:
                raise UserAlreadyExistsError(f"Username {username} is already taken")
        
        # Create user
        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            username=username,
            role=role,
            display_name=f"{first_name} {last_name}".strip() if first_name or last_name else email,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        # Log user creation
        await self.create_audit_log(
            user_id=user.id,
            event_type="user_created",
            event_category="auth",
            event_description=f"User account created for {email}"
        )
        
        return user
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def authenticate(self, email: str, password: str) -> User:
        """Authenticate user with email and password"""
        user = await self.get_by_email(email)
        
        if not user:
            raise InvalidCredentialsError("Invalid email or password")
        
        if not verify_password(password, user.password_hash):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account after too many failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            
            await self.db.commit()
            raise InvalidCredentialsError("Invalid email or password")
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise InvalidCredentialsError("Account is temporarily locked")
        
        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Log successful login
        await self.create_audit_log(
            user_id=user.id,
            event_type="user_login",
            event_category="auth",
            event_description="User logged in successfully"
        )
        
        return user
    
    async def update_user(
        self,
        user_id: str,
        **kwargs
    ) -> User:
        """Update user information"""
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        
        # Update allowed fields
        allowed_fields = {
            "first_name", "last_name", "display_name", "phone_number",
            "avatar_url", "bio", "timezone", "locale", "preferences",
            "notification_settings", "email", "is_verified"
        }
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def update_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> None:
        """Update user password"""
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        
        if not verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError("Invalid current password")
        
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Log password change
        await self.create_audit_log(
            user_id=user_id,
            event_type="password_changed",
            event_category="security",
            event_description="User changed their password"
        )
    
    async def verify_password(self, user_id: str, password: str) -> bool:
        """Verify a password for a user"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        return verify_password(password, user.password_hash)
    
    async def update_last_activity(self, user_id: str) -> None:
        """Update user's last activity timestamp"""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_activity_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def delete_user(self, user_id: str, reason: Optional[str] = None) -> None:
        """Soft delete a user"""
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        
        user.deleted_at = datetime.utcnow()
        user.deletion_reason = reason
        user.is_active = False
        
        await self.db.commit()
        
        # Log user deletion
        await self.create_audit_log(
            user_id=user_id,
            event_type="user_deleted",
            event_category="auth",
            event_description=f"User account deleted. Reason: {reason or 'No reason provided'}"
        )
    
    async def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> UserSession:
        """Create a new user session"""
        session_token = secrets.token_urlsafe(32)
        
        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        return session
    
    async def get_session(self, session_token: str) -> Optional[UserSession]:
        """Get session by token"""
        stmt = (
            select(UserSession)
            .where(
                and_(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def revoke_session(self, session_token: str, reason: Optional[str] = None) -> None:
        """Revoke a specific session"""
        session = await self.get_session(session_token)
        if session:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            session.revocation_reason = reason
            await self.db.commit()
    
    async def revoke_all_user_sessions(self, user_id: str) -> None:
        """Revoke all sessions for a user"""
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )
            .values(
                is_active=False,
                revoked_at=datetime.utcnow(),
                revocation_reason="User logout"
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def create_refresh_token(
        self,
        user_id: str,
        token: str,
        token_family: str,
        expires_at: datetime,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None
    ) -> RefreshToken:
        """Create a new refresh token"""
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            token_family=token_family,
            expires_at=expires_at,
            device_id=device_id,
            device_name=device_name
        )
        
        self.db.add(refresh_token)
        await self.db.commit()
        await self.db.refresh(refresh_token)
        
        return refresh_token
    
    async def get_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string"""
        stmt = (
            select(RefreshToken)
            .where(
                and_(
                    RefreshToken.token == token,
                    RefreshToken.is_active == True,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def rotate_refresh_token(
        self,
        old_token: str,
        new_token: str,
        token_family: str,
        expires_at: datetime
    ) -> RefreshToken:
        """Rotate refresh token (mark old as replaced, create new)"""
        # Mark old token as replaced
        old_refresh_token = await self.get_refresh_token(old_token)
        if old_refresh_token:
            old_refresh_token.is_active = False
            old_refresh_token.revoked_at = datetime.utcnow()
            old_refresh_token.replaced_by_token_id = None  # Will be set after new token is created
        
        # Create new token
        new_refresh_token = RefreshToken(
            user_id=old_refresh_token.user_id if old_refresh_token else None,
            token=new_token,
            token_family=token_family,
            expires_at=expires_at,
            device_id=old_refresh_token.device_id if old_refresh_token else None,
            device_name=old_refresh_token.device_name if old_refresh_token else None
        )
        
        self.db.add(new_refresh_token)
        await self.db.commit()
        await self.db.refresh(new_refresh_token)
        
        # Update old token with new token ID
        if old_refresh_token:
            old_refresh_token.replaced_by_token_id = new_refresh_token.id
            await self.db.commit()
        
        return new_refresh_token
    
    async def revoke_token_family(self, token_family: str) -> None:
        """Revoke all tokens in a family (for security)"""
        stmt = (
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.token_family == token_family,
                    RefreshToken.is_active == True
                )
            )
            .values(
                is_active=False,
                revoked_at=datetime.utcnow(),
                revocation_reason="Token family revoked"
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user"""
        stmt = (
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_active == True
                )
            )
            .values(
                is_active=False,
                revoked_at=datetime.utcnow(),
                revocation_reason="User logout"
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def add_address(
        self,
        user_id: str,
        address_line1: str,
        city: str,
        state_province: str,
        postal_code: str,
        country: str,
        address_line2: Optional[str] = None,
        label: Optional[str] = None,
        is_primary: bool = False,
        **kwargs
    ) -> UserAddress:
        """Add an address for a user"""
        # If setting as primary, unset other primary addresses
        if is_primary:
            stmt = (
                update(UserAddress)
                .where(
                    and_(
                        UserAddress.user_id == user_id,
                        UserAddress.is_primary == True
                    )
                )
                .values(is_primary=False)
            )
            await self.db.execute(stmt)
        
        address = UserAddress(
            user_id=user_id,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state_province=state_province,
            postal_code=postal_code,
            country=country,
            label=label,
            is_primary=is_primary,
            **kwargs
        )
        
        self.db.add(address)
        await self.db.commit()
        await self.db.refresh(address)
        
        # Update user's primary address if needed
        if is_primary:
            user = await self.get_by_id(user_id)
            if user:
                user.primary_address_id = address.id
                await self.db.commit()
        
        return address
    
    async def update_address(
        self,
        address_id: str,
        user_id: str,
        **kwargs
    ) -> UserAddress:
        """Update an address for a user"""
        # Get the address and verify ownership
        stmt = (
            select(UserAddress)
            .where(
                and_(
                    UserAddress.id == address_id,
                    UserAddress.user_id == user_id
                )
            )
        )
        result = await self.db.execute(stmt)
        address = result.scalar_one_or_none()
        
        if not address:
            raise UserNotFoundError(f"Address {address_id} not found for user {user_id}")
        
        # Update allowed fields
        allowed_fields = {
            "address_line1", "address_line2", "city", "state_province",
            "postal_code", "country", "label", "latitude", "longitude",
            "geocoding_accuracy", "property_size_sqm", "lawn_size_sqm",
            "terrain_type", "special_instructions"
        }
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(address, key, value)
        
        # Clear geocoding if address changed
        if any(key in kwargs for key in ["address_line1", "city", "state_province", "postal_code"]):
            address.latitude = None
            address.longitude = None
            address.geocoding_accuracy = None
            address.geocoded_at = None
        
        address.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(address)
        
        return address
    
    async def get_user_addresses(self, user_id: str) -> List[UserAddress]:
        """Get all addresses for a user"""
        stmt = (
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.is_primary.desc(), UserAddress.created_at)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    # Audit logging
    async def create_audit_log(
        self,
        user_id: str,
        event_type: str,
        event_category: str,
        event_description: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create an audit log entry"""
        audit_log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_category=event_category,
            event_description=event_description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata
        )
        
        self.db.add(audit_log)
        await self.db.commit()
    
    async def get_user_audit_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        event_category: Optional[str] = None
    ) -> List[AuditLog]:
        """Get audit logs for a user"""
        stmt = select(AuditLog).where(AuditLog.user_id == user_id)
        
        if event_category:
            stmt = stmt.where(AuditLog.event_category == event_category)
        
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()