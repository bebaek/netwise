from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class AuthRegister(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)


class AuthLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class AuthStatusRead(BaseModel):
    setup_required: bool
    public_signup_enabled: bool
    user: UserRead | None
