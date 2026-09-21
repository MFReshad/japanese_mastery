from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Timestamped(OrmModel):
    created_at: datetime
    updated_at: datetime
