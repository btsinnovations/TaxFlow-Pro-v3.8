from fastapi import APIRouter, Request
import subprocess
import sys
import time

router = APIRouter(prefix="/tests", tags=["tests"])

@router.get("/")
def test_status(request: Request):
    return {
        "status": "ok",
        "message": "Test runner ready",
        "tests": [],
    }

@router.post("/run")
def run_tests(request: Request):
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True, text=True, timeout=60
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0,
            "elapsed": time.time() - start,
        }
    except Exception as e:
        return {"error": str(e), "passed": False, "elapsed": time.time() - start}
