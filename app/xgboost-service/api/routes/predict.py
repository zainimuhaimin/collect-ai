from fastapi import APIRouter, HTTPException
from schemas.payload import PredictBatchResponse
from services.predict_service import predict_batch

router = APIRouter()

@router.post("/predict/batch", response_model=PredictBatchResponse)
async def predict_batch_endpoint():
    try:
        result = predict_batch()
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
