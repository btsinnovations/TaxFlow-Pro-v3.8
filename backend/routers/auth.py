from fastapi import APIRouter
router = APIRouter()

@router.post("/login")
async def login():
    return {"token": "test-token"}

@router.post("/register")
async def register():
    return {"token": "test-token"}

@router.get("/me")
async def get_me():
    return {"user": "test"}
