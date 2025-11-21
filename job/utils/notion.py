import sys
from typing import Any, Dict, Optional

import requests

from . import config
from .models import JobPosting

NOTION_VERSION = "2022-06-28"

class NotionClient:
    def __init__(self) -> None:
        self.token = config.NOTION_TOKEN
        self.database_id = config.NOTION_DATABASE_ID
        self.property_names = config.NOTION_PROPS.copy()
        
        if not self.token or not self.database_id:
            raise ValueError("NOTION_TOKEN and NOTION_DATABASE_ID must be set.")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )
        self.database_properties = self._fetch_properties()
        self.title_property = self._resolve_title_property()

    def _fetch_properties(self) -> Dict[str, Any]:
        resp = self.session.get(
            f"https://api.notion.com/v1/databases/{self.database_id}",
            timeout=config.DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("properties", {})

    def _resolve_title_property(self) -> str:
        desired = "title" # Logical name
        # In config, we don't map 'title' explicitly to a custom prop name usually, 
        # but let's check if we can find the actual title property in the DB.
        
        # Check if any property has type 'title'
        for name, meta in self.database_properties.items():
            if meta.get("type") == "title":
                return name
        raise RuntimeError("No title property found in the Notion database.")

    def _build_property_payload(self, job: JobPosting) -> Dict[str, Any]:
        title_text: Dict[str, Any] = {
            "content": job.title,
        }
        if job.url:
            title_text["link"] = {"url": job.url}
        
        props: Dict[str, Any] = {
            self.title_property: {
                "title": [{"text": title_text}]
            }
        }

        def maybe_set(prop_key: str, value: Optional[Any], kind: str) -> None:
            name = self.property_names.get(prop_key)
            if not name or name not in self.database_properties or value in (None, ""):
                return
            
            meta = self.database_properties[name]
            ptype = meta.get("type")
            
            if kind == "url" and ptype == "url":
                props[name] = {"url": value}
            elif kind == "date" and ptype == "date":
                props[name] = {"date": {"start": value}}
            elif kind == "rich_text" and ptype in {"rich_text", "title"}:
                props[name] = {"rich_text": [{"text": {"content": str(value)}}]}
            elif kind == "select" and ptype == "select":
                props[name] = {"select": {"name": str(value)}}
            elif kind == "multi_select" and ptype == "multi_select":
                props[name] = {
                    "multi_select": [{"name": str(item)} for item in value if item]
                }
            elif kind == "number" and ptype == "number":
                try:
                    props[name] = {"number": float(value)}
                except (ValueError, TypeError):
                    pass

        maybe_set("link", job.url, "url")
        maybe_set("company", job.company, "rich_text")
        maybe_set("team", job.team, "rich_text")
        maybe_set("role", job.role, "rich_text")
        maybe_set("employment", job.employment_type, "select")
        maybe_set("experience", job.experience, "select")
        maybe_set("location", job.location, "rich_text")
        maybe_set("detail_location", job.detail_location, "rich_text")
        maybe_set("due_date", job.due_date_iso(), "date")
        maybe_set("tags", job.tags or [], "multi_select")
        maybe_set("job_id", job.job_id, "number")
        maybe_set("source", job.source, "select")

        return props

    def create_page(self, job: JobPosting) -> str:
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": self._build_property_payload(job),
        }
        resp = self.session.post(
            "https://api.notion.com/v1/pages",
            json=payload,
            timeout=config.DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("id")
