from typing import Literal
from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class MovementRequest(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    movement_type: Literal["IN", "OUT"]
    note: Optional[str] = Field(default=None, max_length=500)
