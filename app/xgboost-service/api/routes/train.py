from fastapi import APIRouter, HTTPException
from schemas.payload import TrainResponse
from services.train_service import train_model

router = APIRouter()

@router.post("/train", response_model=TrainResponse)
async def train_endpoint():
    try:
        result = train_model()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
