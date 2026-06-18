from fastapi import FastAPI
from api.routes import train, predict

app = FastAPI(
    title="XGBoost Recovery Predictor API",
    description="API untuk melatih model XGBoost dan memprediksi probabilitas bayar (RECOVERY_SCORE)",
    version="1.0.0"
)

app.include_router(train.router, prefix="/api/v1/model", tags=["Model Training"])
app.include_router(predict.router, prefix="/api/v1/model", tags=["Model Prediction"])

@app.get("/")
async def root():
    return {"message": "Welcome to XGBoost Recovery Predictor API. Go to /docs for Swagger UI."}
