from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class JobPosting:
    job_id: Optional[str]
    title: str
    url: str
    company: Optional[str] = None
    team: Optional[str] = None
    role: Optional[str] = None
    employment_type: Optional[str] = None
    experience: Optional[str] = None
    location: Optional[str] = None
    detail_location: Optional[str] = None
    due_date: Optional[datetime] = None
    open_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None

    def due_date_iso(self) -> Optional[str]:
        if not self.due_date:
            return None
        return self.due_date.isoformat()

    def due_date_display(self) -> Optional[str]:
        if not self.due_date:
            return None
        return self.due_date.astimezone().strftime("%Y-%m-%d %H:%M")
