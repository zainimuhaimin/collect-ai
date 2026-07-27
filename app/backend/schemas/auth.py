from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"username": "admin", "password": "admin123"}})

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Budi Santoso", "role": "Regional Manager", "initials": "BS"}}
    )

    name: str
    role: str
    initials: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "user": {"name": "Budi Santoso", "role": "Regional Manager", "initials": "BS"},
            }
        }
    )

    token: str
    user: UserOut
