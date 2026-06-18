from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "collectai_db"
    
    # Path dataset untuk training (default fallback jika tidak pakai DB untuk fitur baru)
    DATASET_PATH: str = "Dataset_CollectAI_Dummy.xlsx"
    MODEL_PATH: str = "xgb_recovery_model.pkl"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
