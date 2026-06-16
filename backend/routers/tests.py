<<<<<<< HEAD
from fastapi import APIRouter
=======
from fastapi import APIRouter, Request
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
import subprocess
import sys

router = APIRouter(prefix="/tests", tags=["tests"])

@router.get("/")
<<<<<<< HEAD
def test_status():
    return {"status": "ok", "message": "Test runner ready"}

@router.post("/run")
def run_tests():
=======
def test_status(request: Request):
    return {"status": "ok", "message": "Test runner ready"}

@router.post("/run")
def run_tests(request: Request):
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True, text=True, timeout=60
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0
        }
    except Exception as e:
        return {"error": str(e), "passed": False}
