from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.services import TokenPair


class LoginRequest(BaseModel):
    login: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    expires_in: int

    @classmethod
    def from_token_pair(cls, token_pair: TokenPair) -> TokenPairResponse:
        return cls.model_validate(token_pair)
