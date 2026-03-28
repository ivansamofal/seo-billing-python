import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DB_HOST: str = os.environ["DB_HOST"]
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.environ["DB_NAME"]
    DB_USERNAME: str = os.environ["DB_USERNAME"]
    DB_PASSWORD: str = os.environ["DB_PASSWORD"]

    # External APIs
    BM_COMMON_API_URL: str = os.environ["BM_COMMON_API_URL"]
    BM_COMMON_API_TOKEN: str = os.environ["BM_COMMON_API_TOKEN"]

    # App config
    APP_ENV: str = os.getenv("APP_ENV", "prod")
    FREE_DAYS: int = int(os.getenv("FREE_DAYS", "3"))
    FREE_DAYS_API_ENTERED: int = int(os.getenv("FREE_DAYS_API_ENTERED", "7"))
    HISTORY_TXT: str = os.getenv("HISTORY_TXT", "Subscription payment")

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USERNAME}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )


settings = Settings()
