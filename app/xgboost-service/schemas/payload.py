from pydantic import BaseModel
from typing import List

class PredictResponseItem(BaseModel):
    contract_no: str
    cust_id: str
    dpd_current: int
    predicted_recovery_score: float

class PredictBatchResponse(BaseModel):
    status: str
    total_predicted: int
    data: List[PredictResponseItem]

class TrainResponse(BaseModel):
    status: str
    message: str
    mse: float
    r2_score: float
