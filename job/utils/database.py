import sys
from datetime import datetime
from typing import Optional, List

from pymongo import MongoClient
from pymongo.collection import Collection

from . import config
from .models import JobPosting

_client: Optional[MongoClient] = None
_db = None

def get_db():
    global _client, _db
    if _db is not None:
        return _db
    
    try:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
        # Trigger connection check
        _client.server_info()
        _db = _client[config.MONGO_DB_NAME]
        return _db
    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)

def get_collection() -> Collection:
    db = get_db()
    return db[config.MONGO_COLLECTION_NAME]

def is_job_exists(job: JobPosting) -> bool:
    """
    Check if a job exists in the 'jobs' collection.
    Checks by job_id if present, otherwise by url.
    """
    col = get_collection()
    if job.job_id:
        if col.find_one({"job_id": job.job_id}):
            return True
    
    if job.url:
        if col.find_one({"url": job.url}):
            return True
            
    return False

def save_job(job: JobPosting) -> None:
    """Save a JobPosting to MongoDB."""
    col = get_collection()
    
    # Convert JobPosting to dict
    doc = {
        "job_id": job.job_id,
        "title": job.title,
        "url": job.url,
        "company": job.company,
        "team": job.team,
        "role": job.role,
        "employment_type": job.employment_type,
        "experience": job.experience,
        "location": job.location,
        "detail_location": job.detail_location,
        "due_date": job.due_date,
        "open_date": job.open_date,
        "tags": job.tags,
        "source": job.source,
        "crawled_at": datetime.now()
    }
    
    # Upsert based on job_id or url
    filter_query = {}
    if job.job_id:
        filter_query = {"job_id": job.job_id}
    elif job.url:
        filter_query = {"url": job.url}
    else:
        # Should not happen for valid jobs, but just insert if no unique key
        col.insert_one(doc)
        return

    col.update_one(
        filter_query,
        {"$set": doc},
        upsert=True
    )

def cleanup_stale_jobs(active_jobs: List[JobPosting], source: str) -> int:
    """
    Delete jobs from DB that are no longer in the active_jobs list for the given source.
    Returns the number of deleted documents.
    """
    col = get_collection()
    
    # Collect active IDs and URLs
    active_ids = [job.job_id for job in active_jobs if job.job_id]
    active_urls = [job.url for job in active_jobs if job.url]
    
    # Delete documents where:
    # 1. source matches the given source
    # 2. AND (job_id is NOT in active_ids)
    # 3. AND (url is NOT in active_urls)
    
    query = {
        "source": source,
        "$nor": [
            {"job_id": {"$in": active_ids}},
            {"url": {"$in": active_urls}}
        ]
    }
    
    result = col.delete_many(query)
    return result.deleted_count
