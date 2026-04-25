from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class FileType(str, Enum):
    image = "image"
    video = "video"
    document = "document"
    audio = "audio"
    link = "link"
    text = "text"
    other = "other"


class FileStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class FileSummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str
    type: FileType
    url: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    og_image: Optional[str] = None
    favicon_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    analyzed_at: Optional[datetime] = None
    status: FileStatus = FileStatus.pending
    error: Optional[str] = None

    def date_str(self) -> str:
        return self.created_at.strftime("%Y-%m-%d")


class FileListItem(BaseModel):
    id: str
    filename: str
    original_filename: str
    type: FileType
    url: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    og_image: Optional[str] = None
    favicon_url: Optional[str] = None
    created_at: datetime
    status: FileStatus


class SearchResult(BaseModel):
    id: str
    filename: str
    original_filename: str
    type: FileType
    url: Optional[str] = None
    summary: Optional[str] = None
    match_score: float
    match_reason: str


class StatsResponse(BaseModel):
    total: int
    by_type: dict
    by_status: dict
    recent_date: Optional[str] = None
