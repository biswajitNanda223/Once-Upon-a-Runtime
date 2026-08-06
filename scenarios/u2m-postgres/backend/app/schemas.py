import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserSync(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    username: str | None = Field(default=None, max_length=255)

    @field_validator("external_user_id", "email", "username")
    @classmethod
    def strip_control_characters(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if any(ord(character) < 32 for character in clean):
            raise ValueError("control characters are not allowed")
        return clean or None


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str | None
    email: str | None
