from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from app.services.email_history_service import email_history
from app.services.mail_tm_service import MailTMService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/system/status")
async def get_system_status():
    """获取系统整体状态"""
    try:
        # 检查飞书连接
        feishu_ok = False
        feishu_msg = "未配置"
        if settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET:
            try:
                from app.services.feishu_service import feishu_client
                import asyncio
                loop = asyncio.get_event_loop()
                token = await feishu_client._get_tenant_access_token()
                feishu_ok = True
                feishu_msg = "已连接"
            except Exception as e:
                feishu_msg = f"连接失败: {str(e)[:50]}"

        # 检查邮箱连接
        email_ok = False
        email_msg = "未配置"
        if settings.EMAIL_ADDRESS and settings.EMAIL_PASSWORD:
            try:
                service = MailTMService()
                await service._get_token()
                email_ok = True
                email_msg = "已连接"
            except Exception as e:
                email_msg = f"连接失败: {str(e)[:50]}"

        return {
            "service": {
                "status": "running",
                "uptime": "运行中"
            },
            "feishu": {
                "configured": bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET),
                "connected": feishu_ok,
                "app_id": mask_string(settings.FEISHU_APP_ID),
                "base_id": mask_string(settings.FEISHU_BASE_ID),
                "table_id": mask_string(settings.FEISHU_TABLE_ID),
                "message": feishu_msg
            },
            "email": {
                "configured": bool(settings.EMAIL_ADDRESS and settings.EMAIL_PASSWORD),
                "connected": email_ok,
                "address": settings.EMAIL_ADDRESS,
                "server": settings.EMAIL_IMAP_SERVER,
                "message": email_msg
            },
            "target": {
                "name": "招聘简历收集表",
                "url": f"https://vnet.feishu.cn/base/{settings.FEISHU_BASE_ID}?table={settings.FEISHU_TABLE_ID}"
            }
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return {"error": str(e)}


@router.get("/emails")
async def get_email_history(limit: int = 50):
    """获取邮件处理历史"""
    try:
        history = email_history.get_history(limit)
        stats = email_history.get_statistics()
        return {
            "emails": history,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"获取邮件历史失败: {e}")
        return {"emails": [], "statistics": {}}


@router.get("/emails/stats")
async def get_email_stats():
    """获取邮件统计"""
    try:
        return email_history.get_statistics()
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return {}


@router.get("/emails/{email_id}")
async def get_email_detail(email_id: str):
    """获取单封邮件详情"""
    try:
        # 从历史记录中查找
        email = None
        for e in email_history.get_history(1000):
            if e["id"] == email_id:
                email = e
                break

        if not email:
            raise HTTPException(status_code=404, detail="邮件不存在")

        # 如果是验证码邮件，尝试从mail.tm获取完整内容
        raw_body = ""
        if email.get("email_type") == "verification":
            try:
                service = MailTMService()
                token = await service._get_token()
                detail = await service._api_request("GET", f"/messages/{email_id}")

                # 提取正文
                text_content = detail.get('text', '')
                if isinstance(text_content, list) and text_content:
                    raw_body = text_content[0].get('content', '') if isinstance(text_content[0], dict) else str(text_content[0])
                else:
                    raw_body = str(text_content) if text_content else ''

                if not raw_body:
                    html_content = detail.get('html', '')
                    if isinstance(html_content, list) and html_content:
                        html = html_content[0].get('content', '') if isinstance(html_content[0], dict) else str(html_content[0])
                    else:
                        html = str(html_content) if html_content else ''
                    import re
                    raw_body = re.sub(r'<[^>]+>', ' ', html)
                    raw_body = re.sub(r'\s+', ' ', raw_body).strip()
            except Exception as e:
                logger.warning(f"获取邮件原始内容失败: {e}")
                raw_body = email.get("body_preview", "")
        else:
            raw_body = email.get("body_preview", "")

        return {
            **email,
            "body": raw_body
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮件详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mailbox/current")
async def get_current_mailbox():
    """获取当前邮箱信息"""
    return {
        "email_address": settings.EMAIL_ADDRESS,
        "imap_server": settings.EMAIL_IMAP_SERVER,
        "imap_port": settings.EMAIL_IMAP_PORT,
        "is_configured": bool(settings.EMAIL_ADDRESS and settings.EMAIL_PASSWORD)
    }


def mask_string(s: str, visible: int = 4) -> str:
    """脱敏字符串"""
    if not s or len(s) <= visible * 2:
        return "*" * len(s) if s else ""
    return s[:visible] + "*" * (len(s) - visible * 2) + s[-visible:]
