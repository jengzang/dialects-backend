from pydantic import Field

from app.schemas.base import ShanghaiBaseModel


class WechatMiniCodeRequest(ShanghaiBaseModel):
    code: str = Field(min_length=1)


class WechatMiniRegisterRequest(ShanghaiBaseModel):
    code: str = Field(min_length=1)
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)
