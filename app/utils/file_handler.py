import os
import re
from datetime import datetime
from typing import Optional


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return filename.strip()


def generate_resume_filename(original_name: str, candidate_email: str) -> str:
    """生成规范化的简历文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_part = sanitize_filename(original_name.rsplit('.', 1)[0])
    email_prefix = candidate_email.split('@')[0]
    return f"{timestamp}_{email_prefix}_{name_part}.pdf"


def ensure_upload_dir() -> str:
    """确保上传目录存在"""
    from app.core.config import settings
    upload_dir = settings.RESUME_UPLOAD_PATH
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def save_resume_locally(file_content: bytes, filename: str) -> str:
    """本地备份保存简历"""
    upload_dir = ensure_upload_dir()
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(file_content)
    return filepath
