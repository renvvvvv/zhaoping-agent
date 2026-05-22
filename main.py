import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api.resume_routes import router as resume_router
from app.api.config_routes import router as config_router
from app.api.task_routes import router as task_router
from app.api.monitor_routes import router as monitor_router
from app.services.email_service import email_service as imap_email_service
from app.services.mail_tm_service import MailTMService, is_mail_tm

# 根据邮箱类型选择服务
def get_email_service():
    if settings.EMAIL_ADDRESS and is_mail_tm(settings.EMAIL_ADDRESS):
        return MailTMService()
    return imap_email_service

email_service = get_email_service()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时创建上传目录和静态文件目录
    os.makedirs(settings.RESUME_UPLOAD_PATH, exist_ok=True)
    os.makedirs("static", exist_ok=True)
    logger.info(f"上传目录已准备: {settings.RESUME_UPLOAD_PATH}")

    # 邮件监控服务已禁用（仅保留前端展示功能）
    logger.info("邮件监控服务已禁用，仅提供前端展示功能")

    yield

    logger.info("应用关闭")


app = FastAPI(
    title="招聘AI服务API",
    description="自动接收邮件简历并写入飞书多维表格",
    version="1.0.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(resume_router)
app.include_router(config_router)
app.include_router(task_router)
app.include_router(monitor_router)

# 静态文件服务（前端页面）
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/landing.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level="info"
    )
