import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import requests

DEFAULT_TIMEOUT = 30
NOTION_VERSION = "2022-06-28"
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATHS = [SCRIPT_DIR / ".env"]


def load_env() -> None:
    """Load key=value pairs from known .env files into os.environ."""
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        with env_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                cleaned_key = key.strip().lstrip("\ufeff")
                os.environ.setdefault(cleaned_key, value.strip())


def build_property_map() -> Dict[str, Optional[str]]:
    """Return the mapping between logical fields and Notion property names."""
    return {
        "title": None,
        "link": os.getenv("NOTION_LINK_PROP", "Link"),
        "company": os.getenv("NOTION_COMPANY_PROP", "\ud68c\uc0ac"),
        "team": os.getenv("NOTION_TEAM_PROP", "\ud300"),
        "role": os.getenv("NOTION_ROLE_PROP", "\uc9c1\ubb34"),
        "employment": os.getenv("NOTION_EMPLOYMENT_PROP", "\uace0\uc6a9\ud615\ud0dc"),
        "experience": os.getenv("NOTION_EXPERIENCE_PROP", "\uacbd\ub825"),
        "location": os.getenv("NOTION_LOCATION_PROP", "\uadfc\ubb34\uc9c0"),
        "detail_location": os.getenv("NOTION_DETAIL_LOCATION_PROP", "\uc0c1\uc138 \uadfc\ubb34\uc9c0"),
        "due_date": os.getenv("NOTION_DEADLINE_PROP", "\ub0a0\uc9dc"),
        "tags": os.getenv("NOTION_TAGS_PROP", "\ud0dc\uadf8"),
        "job_id": os.getenv("NOTION_JOB_ID_PROP", "Job ID"),
        "source": os.getenv("NOTION_SOURCE_PROP", "\ud50c\ub7ab\ud3fc"),
    }


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


class NotionClient:
    def __init__(
        self,
        token: str,
        database_id: str,
        property_names: Dict[str, Optional[str]],
    ) -> None:
        self.database_id = database_id
        self.property_names = property_names
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )
        self.database_properties = self._fetch_properties()
        self.title_property = self._resolve_title_property()

    def _fetch_properties(self) -> Dict[str, Any]:
        resp = self.session.get(
            f"https://api.notion.com/v1/databases/{self.database_id}",
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("properties", {})

    def _resolve_title_property(self) -> str:
        desired = self.property_names.get("title")
        if desired and desired in self.database_properties:
            meta = self.database_properties[desired]
            if meta.get("type") == "title":
                return desired
        for name, meta in self.database_properties.items():
            if meta.get("type") == "title":
                self.property_names["title"] = name
                return name
        raise RuntimeError("No title property found in the Notion database.")

    def _extract_text(self, prop: Dict[str, Any]) -> Optional[str]:
        if not prop:
            return None
        ptype = prop.get("type")
        if ptype == "rich_text":
            parts = prop.get("rich_text") or []
            return "".join(part.get("plain_text", "") for part in parts)
        if ptype == "title":
            parts = prop.get("title") or []
            return "".join(part.get("plain_text", "") for part in parts)
        if ptype == "select":
            option = prop.get("select")
            if option:
                return option.get("name")
        if ptype == "multi_select":
            options = prop.get("multi_select") or []
            return ",".join(option.get("name", "") for option in options)
        if ptype == "url":
            return prop.get("url")
        if ptype == "number":
            number = prop.get("number")
            return str(number) if number is not None else None
        return None

    def _extract_date(self, prop: Dict[str, Any]) -> Optional[str]:
        if not prop:
            return None
        data = prop.get("date")
        if not data:
            return None
        return data.get("start")

    def fetch_existing_indexes(self) -> Dict[str, Any]:
        indexes: Dict[str, Any] = {
            "job_ids": set(),
            "links": set(),
            "titles": set(),
            "meta_by_job_id": {},
            "meta_by_title": {},
        }
        job_id_prop = self.property_names.get("job_id")
        link_prop = self.property_names.get("link")
        source_prop = self.property_names.get("source")
        due_date_prop = self.property_names.get("due_date")

        payload: Dict[str, Any] = {"page_size": 100}
        while True:
            resp = self.session.post(
                f"https://api.notion.com/v1/databases/{self.database_id}/query",
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                title_property = props.get(self.title_property) or {}
                title_rich = title_property.get("title") or []
                title_link = None
                if title_rich:
                    link_info = title_rich[0].get("text", {}).get("link")
                    if link_info:
                        title_link = link_info.get("url")
                title = self._extract_text(props.get(self.title_property))
                source_value = None
                if source_prop and source_prop in props:
                    source_value = self._extract_text(props.get(source_prop))
                due_date_value = None
                if due_date_prop and due_date_prop in props:
                    due_date_value = self._extract_date(props.get(due_date_prop))
                page_id = page.get("id")
                if title:
                    indexes["titles"].add(title)
                    indexes["meta_by_title"][title] = {
                        "page_id": page_id,
                        "source": source_value,
                        "due_date": due_date_value,
                        "title_link": title_link,
                    }
                if link_prop and link_prop in props:
                    link_value = self._extract_text(props.get(link_prop))
                    if link_value:
                        indexes["links"].add(link_value)
                job_id_value = None
                if job_id_prop and job_id_prop in props:
                    job_id_value = self._extract_text(props.get(job_id_prop))
                    if job_id_value:
                        indexes["job_ids"].add(job_id_value)
                        meta = indexes["meta_by_job_id"].setdefault(
                            job_id_value, {"page_id": page_id}
                        )
                        meta["source"] = source_value
                        meta["due_date"] = due_date_value
                        meta["title_link"] = title_link
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data.get("next_cursor")
        return indexes

    def _build_property_payload(
        self,
        job: JobPosting,
    ) -> Dict[str, Any]:
        title_text: Dict[str, Any] = {
            "content": job.title,
        }
        if job.url:
            title_text["link"] = {"url": job.url}
        props: Dict[str, Any] = {
            self.title_property: {
                "title": [
                    {
                        "text": title_text,
                    }
                ]
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
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("id")

    def update_select_property(
        self,
        page_id: str,
        property_key: str,
        value: Optional[str],
    ) -> bool:
        if not value:
            return False
        name = self.property_names.get(property_key)
        if not name or name not in self.database_properties:
            return False
        if self.database_properties[name].get("type") != "select":
            return False
        payload = {
            "properties": {
                name: {
                    "select": {"name": value},
                }
            }
        }
        resp = self.session.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return True

    def update_date_property(
        self,
        page_id: str,
        property_key: str,
        value: Optional[str],
    ) -> bool:
        if not value:
            return False
        name = self.property_names.get(property_key)
        if not name or name not in self.database_properties:
            return False
        if self.database_properties[name].get("type") != "date":
            return False
        payload = {
            "properties": {
                name: {
                    "date": {
                        "start": value,
                    }
                }
            }
        }
        resp = self.session.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return True

    def update_title_link(
        self,
        page_id: str,
        title: str,
        url: Optional[str],
    ) -> bool:
        if not title:
            return False
        title_text: Dict[str, Any] = {"content": title}
        if url:
            title_text["link"] = {"url": url}
        payload = {
            "properties": {
                self.title_property: {
                    "title": [
                        {
                            "text": title_text,
                        }
                    ]
                }
            }
        }
        resp = self.session.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return True


def send_discord_notification(
    webhook_url: Optional[str],
    jobs: List[JobPosting],
    source_label: Optional[str] = None,
) -> None:
    if not webhook_url:
        return

    default_prefix = "\ucc44\uc6a9 \uacf5\uace0\uac00 \uc5c5\ub370\uc774\ud2b8\ub418\uc5c8\uc2b5\ub2c8\ub2e4."
    prefix = (
        f"{source_label} \ucc44\uc6a9 \uacf5\uace0\uac00 \uc5c5\ub370\uc774\ud2b8\ub418\uc5c8\uc2b5\ub2c8\ub2e4."
        if source_label
        else default_prefix
    )

    chunks = [jobs[i : i + 10] for i in range(0, len(jobs), 10)]
    for chunk in chunks:
        embeds = []
        for job in chunk:
            description_parts: List[str] = []
            if job.role:
                description_parts.append(job.role)
            if job.employment_type:
                description_parts.append(job.employment_type)
            if job.experience:
                description_parts.append(job.experience)
            if job.due_date_display():
                description_parts.append(f"마감 {job.due_date_display()}")
            description = " | ".join(description_parts)
            embed = {
                "title": job.title,
                "url": job.url,
                "description": description or None,
                "fields": [],
            }
            if job.location:
                embed["fields"].append(
                    {"name": "\uadfc\ubb34\uc9c0", "value": job.location, "inline": True}
                )
            if job.company:
                embed["fields"].append(
                    {"name": "\ud68c\uc0ac", "value": job.company, "inline": True}
                )
            embeds.append(embed)

        payload = {
            "content": prefix,
            "embeds": embeds,
        }
        resp = requests.post(webhook_url, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()


def should_skip(job: JobPosting, indexes: Dict[str, Set[str]]) -> bool:
    if job.job_id and job.job_id in indexes["job_ids"]:
        return True
    if job.url in indexes["links"]:
        return True
    if job.title in indexes["titles"]:
        return True
    return False
