from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from app.core.config import settings
from app.services.feishu_service import feishu_client
from app.services.email_service import email_service as imap_email_service
from app.services.mail_tm_service import MailTMService, is_mail_tm
from app.utils.file_handler import generate_resume_filename, save_resume_locally

def get_email_service():
    """根据配置获取正确的邮件服务"""
    if settings.EMAIL_ADDRESS and is_mail_tm(settings.EMAIL_ADDRESS):
        return MailTMService()
    return imap_email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resumes", tags=["resumes"])


class EmailStatus(BaseModel):
    email_address: str
    monitoring: bool
    poll_interval: int


class ManualUploadRequest(BaseModel):
    candidate_name: str
    email: str
    additional_fields: Optional[Dict[str, Any]] = None


@router.get("/status")
async def get_service_status():
    """获取服务状态"""
    service = get_email_service()
    return {
        "status": "running",
        "email_monitoring": getattr(service, '_running', False),
        "email_address": getattr(service, 'email_address', settings.EMAIL_ADDRESS),
        "poll_interval": getattr(service, 'poll_interval', settings.EMAIL_POLL_INTERVAL)
    }


@router.get("/email/status", response_model=EmailStatus)
async def get_email_status():
    """获取邮箱监控状态"""
    return EmailStatus(
        email_address=email_service.email_address,
        monitoring=email_service._running,
        poll_interval=email_service.poll_interval
    )


@router.post("/email/check")
async def trigger_email_check(background_tasks: BackgroundTasks):
    """手动触发邮件检查"""
    service = get_email_service()
    background_tasks.add_task(service.check_new_emails)
    return {"message": "邮件检查已触发", "email": getattr(service, 'email_address', settings.EMAIL_ADDRESS)}


@router.post("/upload")
async def upload_resume(
    candidate_name: str = Form(...),
    email: str = Form(...),
    file: UploadFile = File(...),
    additional_fields: Optional[str] = Form(None)
):
    """
    手动上传简历到飞书多维表格

    - **candidate_name**: 候选人姓名
    - **email**: 候选人邮箱
    - **file**: PDF简历文件
    - **additional_fields**: 额外字段(JSON字符串)
    """
    try:
        # 验证文件类型
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="只支持PDF文件")

        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="文件内容为空")

        # 保存本地备份
        new_filename = generate_resume_filename(file.filename, email)
        local_path = save_resume_locally(file_content, new_filename)
        logger.info(f"简历已保存到本地: {local_path}")

        # 解析额外字段
        extra_fields = {}
        if additional_fields:
            import json
            try:
                extra_fields = json.loads(additional_fields)
            except:
                pass

        # 上传到飞书
        result = await feishu_client.create_record_with_resume(
            candidate_name=candidate_name,
            email=email,
            file_name=new_filename,
            file_content=file_content,
            additional_fields=extra_fields
        )

        return {
            "success": True,
            "message": "简历上传成功",
            "record_id": result["data"]["record"]["record_id"],
            "filename": new_filename,
            "local_path": local_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传简历失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/email/manual-process")
async def process_email_by_content(
    sender_name: str = Form(...),
    sender_email: str = Form(...),
    subject: str = Form(...),
    file: UploadFile = File(...)
):
    """
    模拟邮件内容手动处理（用于测试）

    - **sender_name**: 发件人姓名
    - **sender_email**: 发件人邮箱
    - **subject**: 邮件主题
    - **file**: PDF附件
    """
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="只支持PDF文件")

        file_content = await file.read()
        new_filename = generate_resume_filename(file.filename, sender_email)
        save_resume_locally(file_content, new_filename)

        result = await feishu_client.create_record_with_resume(
            candidate_name=sender_name,
            email=sender_email,
            file_name=new_filename,
            file_content=file_content,
            additional_fields={
                "邮件主题": subject,
                "投递时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "原始文件名": file.filename
            }
        )

        return {
            "success": True,
            "message": "邮件简历处理成功",
            "record_id": result["data"]["record"]["record_id"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理邮件失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
