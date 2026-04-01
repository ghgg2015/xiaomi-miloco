# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
RTSP source schema models.
"""

from typing import Optional

from pydantic import BaseModel, Field


class RTSPSourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    rtsp_url: str = Field(..., min_length=1, max_length=2048)
    enabled: bool = Field(default=True)
    username: Optional[str] = Field(default=None, max_length=128)
    password: Optional[str] = Field(default=None, max_length=128)
    home_name: Optional[str] = Field(default="RTSP")
    room_name: Optional[str] = Field(default="Custom Camera")


class RTSPSourceCreate(RTSPSourceBase):
    source_id: Optional[str] = Field(default=None, max_length=128)


class RTSPSourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    rtsp_url: Optional[str] = Field(default=None, min_length=1, max_length=2048)
    enabled: Optional[bool] = None
    username: Optional[str] = Field(default=None, max_length=128)
    password: Optional[str] = Field(default=None, max_length=128)
    home_name: Optional[str] = Field(default=None, max_length=128)
    room_name: Optional[str] = Field(default=None, max_length=128)


class RTSPSource(RTSPSourceBase):
    source_id: str = Field(..., min_length=1, max_length=128)


class RTSPSourcePublic(BaseModel):
    source_id: str
    name: str
    enabled: bool
    home_name: Optional[str] = None
    room_name: Optional[str] = None
    source_type: str = "rtsp"
    stream_type: str = "jpeg"
