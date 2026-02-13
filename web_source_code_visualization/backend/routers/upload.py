"""
Upload Router - Handle project uploads (zip format)
"""
import os
import shutil
import zipfile
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

router = APIRouter(prefix="/api", tags=["upload"])

# Directory to store uploaded projects
# In Docker: mounted at /projects via docker-compose volume
# Locally: fallback to ../projects relative to backend dir
PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "/projects")


def safe_extract(zip_ref, extract_path):
    """
    Safe extraction of zip files to prevent Zip Slip vulnerability.
    """
    for member in zip_ref.namelist():
        member_path = os.path.join(extract_path, member)
        # Verify that the canonical path starts with the extract_path
        if not os.path.abspath(member_path).startswith(os.path.abspath(extract_path)):
            raise Exception(f"Attempted Zip Slip: {member}")
    zip_ref.extractall(extract_path)


def cleanup_temp_file(path: str):
    """Remove temporary file."""
    if os.path.exists(path):
        os.remove(path)


@router.post("/upload")
async def upload_project(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a zip file containing a project source code.
    The zip file will be extracted to the 'projects' directory.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")

    # Create projects directory if it doesn't exist
    os.makedirs(PROJECTS_DIR, exist_ok=True)

    # Save uploaded file temporarily
    temp_file_path = os.path.join(PROJECTS_DIR, f"temp_{file.filename}")
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Extract zip file
        project_name = os.path.splitext(file.filename)[0]
        # Handle duplicate names by appending a counter? For now, overwrite or error.
        # Let's use a unique folder name if possible or just use the filename
        
        extract_path = os.path.join(PROJECTS_DIR, project_name)
        
        # If directory exists, maybe rename it or delete it?
        # For this implementation, we'll remove it if it exists to allow updates
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
            
        os.makedirs(extract_path, exist_ok=True)
        
        with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
            safe_extract(zip_ref, extract_path)
            
        return {
            "message": "Project uploaded and extracted successfully",
            "project_name": project_name,
            "path": extract_path
        }
        
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except Exception as e:
        # Clean up partial extraction if failed
        if 'extract_path' in locals() and os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")
    finally:
        # Schedule cleanup of temp file
        background_tasks.add_task(cleanup_temp_file, temp_file_path)
