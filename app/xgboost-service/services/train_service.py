import pandas as pd
# pyrefly: ignore [missing-import]
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
# pyrefly: ignore [missing-import]
import joblib
from core.config import settings
from core.database import get_engine

def train_model():
    engine = get_engine()
    
    # Membaca data dari PostgreSQL
    df_cust = pd.read_sql("SELECT * FROM customer_master", con=engine)
    df_contr = pd.read_sql("SELECT * FROM contract_snapshot", con=engine)
    df_pay = pd.read_sql("SELECT * FROM payment_history", con=engine)
    df_lkp = pd.read_sql("SELECT * FROM lkp_interaction", con=engine)
    df_ai = pd.read_sql("SELECT * FROM ai_intelligence", con=engine)

    # Agregasi Payment History
    pay_agg = df_pay.groupby('CONTRACT_NO')['DELAY_DAYS'].mean().reset_index()
    pay_agg.rename(columns={'DELAY_DAYS': 'AVG_DELAY_DAYS'}, inplace=True)

    # Agregasi LKP
    lkp_agg = df_lkp.groupby('CONTRACT_NO')['INTERACTION_SCORE'].mean().reset_index()
    lkp_agg.rename(columns={'INTERACTION_SCORE': 'AVG_INTERACTION_SCORE'}, inplace=True)

    # Gabung semua data
    df_merged = df_contr.merge(pay_agg, on='CONTRACT_NO', how='left')
    df_merged = df_merged.merge(lkp_agg, on='CONTRACT_NO', how='left')
    df_merged = df_merged.merge(df_cust, on='CUST_ID', how='left')
    df_merged = df_merged.merge(df_ai[['CONTRACT_NO', 'RECOVERY_SCORE']], on='CONTRACT_NO', how='inner')

    # Handling Missing Values
    df_merged['AVG_DELAY_DAYS'] = df_merged['AVG_DELAY_DAYS'].fillna(0)
    df_merged['AVG_INTERACTION_SCORE'] = df_merged['AVG_INTERACTION_SCORE'].fillna(0)

    # Konversi Kategori
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

    X = df_merged[features]
    y = df_merged['RECOVERY_SCORE']

    # Train-Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Training Model
    model = xgb.XGBRegressor(
        objective='reg:squarederror', 
        n_estimators=100,      
        learning_rate=0.1,     
        max_depth=5,           
        random_state=42
    )

    model.fit(X_train, y_train)

    # Evaluasi
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Save Model
    joblib.dump(model, settings.MODEL_PATH)

    return {
        "status": "success",
        "message": f"Model berhasil ditrain dan disimpan di {settings.MODEL_PATH}",
        "mse": float(mse),
        "r2_score": float(r2)
    }
