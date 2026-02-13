
import sys
import os
import traceback

print(f"CWD: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    print("Attempting to import routers.upload...")
    import routers.upload
    print(f"routers.upload imported successfully. File: {routers.upload.__file__}")
    print(f"v: {dir(routers.upload)}")
    if hasattr(routers.upload, 'router'):
        print("routers.upload has 'router' attribute")
    else:
        print("routers.upload DOES NOT have 'router' attribute")
except Exception:
    traceback.print_exc()

try:
    print("\nAttempting to import upload_router from routers...")
    from routers import upload_router
    print("Successfully imported upload_router from routers")
except Exception:
    traceback.print_exc()
