import os
import shutil
import zipfile
import io
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

PROJECTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "projects")

def test_upload_project():
    # Create a dummy zip file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('main.py', 'print("Hello World")')
        zip_file.writestr('utils/helper.py', 'def help(): pass')
    
    zip_buffer.seek(0)
    
    response = client.post(
        "/api/upload",
        files={"file": ("test_project.zip", zip_buffer, "application/zip")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Project uploaded and extracted successfully"
    assert data["project_name"] == "test_project"
    
    # Verify extraction
    project_path = os.path.join(PROJECTS_DIR, "test_project")
    assert os.path.exists(os.path.join(project_path, "main.py"))
    assert os.path.exists(os.path.join(project_path, "utils", "helper.py"))
    
    # Cleanup
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

if __name__ == "__main__":
    test_upload_project()
    print("Test passed!")
