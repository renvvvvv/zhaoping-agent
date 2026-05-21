from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from app.core.config import settings, update_settings
from app.services.email_service import EmailService
from app.services.mail_tm_service import MailTMService, is_mail_tm
from app.services.feishu_service import FeishuClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])


class FeishuConfig(BaseModel):
    app_id: str
    app_secret: str
    base_id: str
    table_id: str


class EmailConfig(BaseModel):
    imap_server: str = "imap.ethereal.email"
    imap_port: int = 993
    email_address: str
    email_password: str


class ServiceConfig(BaseModel):
    poll_interval: int = 60


@router.get("/")
async def get_all_config():
    """获取当前所有配置（敏感信息脱敏）"""
    return {
        "feishu": {
            "app_id": mask_string(settings.FEISHU_APP_ID),
            "app_secret": mask_string(settings.FEISHU_APP_SECRET),
            "base_id": mask_string(settings.FEISHU_BASE_ID),
            "table_id": mask_string(settings.FEISHU_TABLE_ID),
            "configured": bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET)
        },
        "email": {
            "imap_server": settings.EMAIL_IMAP_SERVER,
            "imap_port": settings.EMAIL_IMAP_PORT,
            "email_address": settings.EMAIL_ADDRESS,
            "email_password": mask_string(settings.EMAIL_PASSWORD),
            "configured": bool(settings.EMAIL_ADDRESS and settings.EMAIL_PASSWORD)
        },
        "service": {
            "poll_interval": settings.EMAIL_POLL_INTERVAL,
            "upload_path": settings.RESUME_UPLOAD_PATH
        }
    }


@router.post("/feishu")
async def update_feishu_config(config: FeishuConfig):
    """更新飞书配置"""
    try:
        update_settings(
            FEISHU_APP_ID=config.app_id,
            FEISHU_APP_SECRET=config.app_secret,
            FEISHU_BASE_ID=config.base_id,
            FEISHU_TABLE_ID=config.table_id
        )
        # 重新初始化飞书客户端
        from app.services import feishu_service
        feishu_service.feishu_client = FeishuClient()

        logger.info("飞书配置已更新")
        return {"success": True, "message": "飞书配置已更新"}
    except Exception as e:
        logger.error(f"更新飞书配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email")
async def update_email_config(config: EmailConfig):
    """更新邮箱配置"""
    try:
        update_settings(
            EMAIL_IMAP_SERVER=config.imap_server,
            EMAIL_IMAP_PORT=config.imap_port,
            EMAIL_ADDRESS=config.email_address,
            EMAIL_PASSWORD=config.email_password
        )
        logger.info("邮箱配置已更新，请重启服务使新配置生效")
        return {"success": True, "message": "邮箱配置已更新，请重启服务"}
    except Exception as e:
        logger.error(f"更新邮箱配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/service")
async def update_service_config(config: ServiceConfig):
    """更新服务配置"""
    try:
        update_settings(EMAIL_POLL_INTERVAL=config.poll_interval)
        logger.info("服务配置已更新")
        return {"success": True, "message": "服务配置已更新"}
    except Exception as e:
        logger.error(f"更新服务配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-feishu")
async def test_feishu_connection():
    """测试飞书连接"""
    try:
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            return {"success": False, "message": "飞书配置不完整"}

        from app.services.feishu_service import feishu_client
        token = await feishu_client._get_tenant_access_token()
        return {"success": True, "message": "飞书连接成功", "token_prefix": token[:10] + "..."}
    except Exception as e:
        return {"success": False, "message": f"飞书连接失败: {str(e)}"}


@router.post("/test-email")
async def test_email_connection():
    """测试邮箱连接"""
    try:
        if not settings.EMAIL_ADDRESS or not settings.EMAIL_PASSWORD:
            return {"success": False, "message": "邮箱配置不完整"}

        # mail.tm 使用 REST API 测试
        if is_mail_tm(settings.EMAIL_ADDRESS):
            service = MailTMService()
            await service._get_token()
            return {"success": True, "message": "mail.tm 邮箱连接成功"}
        else:
            # IMAP 测试
            import imaplib
            mail = imaplib.IMAP4_SSL(settings.EMAIL_IMAP_SERVER, settings.EMAIL_IMAP_PORT)
            mail.login(settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD)
            mail.logout()
            return {"success": True, "message": "IMAP 邮箱连接成功"}
    except Exception as e:
        return {"success": False, "message": f"邮箱连接失败: {str(e)}"}


def mask_string(s: str, visible: int = 4) -> str:
    """脱敏字符串"""
    if not s or len(s) <= visible * 2:
        return "*" * len(s) if s else ""
    return s[:visible] + "*" * (len(s) - visible * 2) + s[-visible:]
