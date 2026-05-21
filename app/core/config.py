from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # 飞书配置
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_BASE_ID: str = ""
    FEISHU_TABLE_ID: str = ""

    # 邮箱配置
    EMAIL_IMAP_SERVER: str = "imap.ethereal.email"
    EMAIL_IMAP_PORT: int = 993
    EMAIL_ADDRESS: str = ""
    EMAIL_PASSWORD: str = ""

    # 服务配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    EMAIL_POLL_INTERVAL: int = 60

    # 文件存储
    RESUME_UPLOAD_PATH: str = "./uploads/resumes"

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

def update_settings(**kwargs) -> Settings:
    """运行时更新配置"""
    global settings
    # 清除lru_cache
    get_settings.cache_clear()
    # 创建新配置，合并更新
    current = {k: v for k, v in settings.dict().items()}
    current.update(kwargs)
    settings = Settings(**current)
    # 同步更新环境变量
    for key, value in kwargs.items():
        os.environ[key] = str(value)
    return settings

settings = get_settings()
