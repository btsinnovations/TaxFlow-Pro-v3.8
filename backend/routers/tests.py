from fastapi import APIRouter
import subprocess
import sys

router = APIRouter(prefix="/tests", tags=["tests"])

@router.get("/")
def test_status():
    return {"status": "ok", "message": "Test runner ready"}

@router.post("/run")
def run_tests():
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
