import pandas as pd
# pyrefly: ignore [missing-import]
import joblib
import os
from core.config import settings
from core.database import get_engine
from schemas.payload import PredictBatchResponse, PredictResponseItem

def predict_batch() -> PredictBatchResponse:
    if not os.path.exists(settings.MODEL_PATH):
        raise FileNotFoundError(f"Model {settings.MODEL_PATH} belum ditrain. Silakan jalankan endpoint /train terlebih dahulu.")
        
    model = joblib.load(settings.MODEL_PATH)
    engine = get_engine()
    
    # Membaca data dari PostgreSQL
    df_cust = pd.read_sql("SELECT * FROM customer_master", con=engine)
    df_contr = pd.read_sql("SELECT * FROM contract_snapshot", con=engine)
    df_pay = pd.read_sql("SELECT * FROM payment_history", con=engine)
    df_lkp = pd.read_sql("SELECT * FROM lkp_interaction", con=engine)

    # Feature Engineering
    pay_agg = df_pay.groupby('CONTRACT_NO')['DELAY_DAYS'].mean().reset_index()
    pay_agg.rename(columns={'DELAY_DAYS': 'AVG_DELAY_DAYS'}, inplace=True)

    lkp_agg = df_lkp.groupby('CONTRACT_NO')['INTERACTION_SCORE'].mean().reset_index()
    lkp_agg.rename(columns={'INTERACTION_SCORE': 'AVG_INTERACTION_SCORE'}, inplace=True)

    df_merged = df_contr.merge(pay_agg, on='CONTRACT_NO', how='left')
    df_merged = df_merged.merge(lkp_agg, on='CONTRACT_NO', how='left')
    df_merged = df_merged.merge(df_cust, on='CUST_ID', how='left')

    df_merged['AVG_DELAY_DAYS'] = df_merged['AVG_DELAY_DAYS'].fillna(0)
    df_merged['AVG_INTERACTION_SCORE'] = df_merged['AVG_INTERACTION_SCORE'].fillna(0)

    cycle_mapping = {'C0': 0, 'C1': 1, 'C2': 2, 'C3+': 3}
    df_merged['CYCLE_NUM'] = df_merged['CYCLE_AKHIR'].map(cycle_mapping)

    features = [
        'DPD_CURRENT', 
        'PRNC_OTS', 
        'CUST_AGE', 
        'AVG_DELAY_DAYS', 
        'AVG_INTERACTION_SCORE', 
        'CYCLE_NUM'
    ]

    X_new = df_merged[features]

    # Prediksi
    predictions = model.predict(X_new)
    df_merged['PREDICTED_RECOVERY_SCORE'] = predictions

    # Format hasil sesuai schema
    results = []
    for _, row in df_merged.iterrows():
        item = PredictResponseItem(
            contract_no=row['CONTRACT_NO'],
            cust_id=row['CUST_ID'],
            dpd_current=row['DPD_CURRENT'],
            predicted_recovery_score=float(row['PREDICTED_RECOVERY_SCORE'])
        )
        results.append(item)

    return PredictBatchResponse(
        status="success",
        total_predicted=len(results),
        data=results
    )
