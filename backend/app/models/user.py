"""
User models for authentication and user management.

Pydantic models for user data validation and serialization.
"""
import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class Role(str, Enum):
    """User role enum."""

    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class UserBase(BaseModel):
    """
    Base user model with common fields.

    This model contains fields shared across all user models.
    """

    email: EmailStr = Field(..., description="User email address")
    display_name: str | None = Field(None, min_length=1, max_length=100, description="User display name")
    photo_url: str | None = Field(None, description="Profile photo URL")
    role: Role = Field(default=Role.USER, description="User role")

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url(cls, v: str | None) -> str | None:
        """Validate photo URL format."""
        if v is None:
            return v
        # Basic URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or IP
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if not url_pattern.match(v):
            raise ValueError("Invalid URL format")
        return v


class UserCreate(BaseModel):
    """
    Model for creating a new user.

    Used when creating users through the API.
    """

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=128, description="User password")
    display_name: str | None = Field(None, min_length=1, max_length=100, description="User display name")
    photo_url: str | None = Field(None, description="Profile photo URL")
    role: Role = Field(default=Role.USER, description="User role")
    email_verified: bool = Field(default=False, description="Whether email is verified")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength.

        Password must:
        - Be at least 6 characters
        - Contain at least one letter
        - Contain at least one number
        """
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url(cls, v: str | None) -> str | None:
        """Validate photo URL format."""
        if v is None:
            return v
        url_pattern = re.compile(
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if not url_pattern.match(v):
            raise ValueError("Invalid URL format")
        return v


class UserUpdate(BaseModel):
    """
    Model for updating user data.

    All fields are optional - only provided fields will be updated.
    """

    email: EmailStr | None = Field(None, description="User email address")
    display_name: str | None = Field(None, min_length=1, max_length=100, description="User display name")
    photo_url: str | None = Field(None, description="Profile photo URL")
    role: Role | None = Field(None, description="User role")
    disabled: bool | None = Field(None, description="Whether account is disabled")
    email_verified: bool | None = Field(None, description="Whether email is verified")

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url(cls, v: str | None) -> str | None:
        """Validate photo URL format."""
        if v is None:
            return v
        url_pattern = re.compile(
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        if not url_pattern.match(v):
            raise ValueError("Invalid URL format")
        return v


class UserInDB(UserBase):
    """
    User model with database fields.

    Includes uid and timestamp fields that are set by the database.
    """

    uid: str = Field(..., description="Firebase user ID")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    disabled: bool = Field(default=False, description="Whether account is disabled")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    last_sign_in: datetime | None = Field(None, description="Last sign-in timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True


class UserResponse(BaseModel):
    """
    User model for API responses.

    Excludes sensitive data and internal fields.
    """

    uid: str = Field(..., description="Firebase user ID")
    email: EmailStr = Field(..., description="User email address")
    display_name: str | None = Field(None, description="User display name")
    photo_url: str | None = Field(None, description="Profile photo URL")
    role: Role = Field(..., description="User role")
    created_at: datetime = Field(..., description="User creation timestamp")
    email_verified: bool = Field(..., description="Whether email is verified")
    disabled: bool = Field(..., description="Whether account is disabled")

    class Config:
        """Pydantic config."""

        from_attributes = True

    @classmethod
    def from_user_in_db(cls, user: UserInDB) -> "UserResponse":
        """
        Create UserResponse from UserInDB.

        Args:
            user: User from database

        Returns:
            UserResponse: Response model
        """
        return cls(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url,
            role=user.role,
            created_at=user.created_at,
            email_verified=user.email_verified,
            disabled=user.disabled,
        )
