import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

class EmailHistoryService:
    """邮件历史记录服务 - 记录接收到的邮件及其处理状态"""

    DATA_FILE = "./data/email_history.json"

    def __init__(self):
        self._history: List[Dict[str, Any]] = []
        self._ensure_data_dir()
        self._load_data()

    def _ensure_data_dir(self):
        Path(self.DATA_FILE).parent.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._history = data.get("emails", [])
            except Exception:
                self._history = []

    def _save_data(self):
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump({"emails": self._history}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存邮件历史失败: {e}")

    def _extract_code(self, text: str) -> Optional[str]:
        """从邮件文本中提取验证码"""
        if not text:
            return None
        patterns = [
            r'验证码[是为：:\s]+(\d{4,8})',
            r'验证码[是为：:\s]*[\n\r]+\s*(\d{4,8})',
            r'verification\s*code[是为：:\s]+(\d{4,8})',
            r'code[是为：:\s]+(\d{4,8})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                code = match.group(1)
                if len(code) >= 4:
                    return code
        return None

    def add_email(self, email_id: str, sender_name: str, sender_email: str,
                  subject: str, received_at: str, has_pdf: bool = True,
                  body: str = "", email_type: str = "other") -> Dict[str, Any]:
        """添加新邮件记录"""
        code = self._extract_code(body)
        record = {
            "id": email_id,
            "sender_name": sender_name,
            "sender_email": sender_email,
            "subject": subject,
            "received_at": received_at,
            "has_pdf": has_pdf,
            "status": "received",
            "email_type": email_type,  # resume, verification, other
            "verification_code": code,
            "body_preview": body[:500] if body else "",
            "processed_at": None,
            "feishu_record_id": None,
            "error_message": None,
            "pdf_filename": None
        }
        self._history.insert(0, record)
        self._save_data()
        return record

    def update_status(self, email_id: str, status: str,
                      feishu_record_id: Optional[str] = None,
                      error_message: Optional[str] = None,
                      pdf_filename: Optional[str] = None):
        """更新邮件处理状态"""
        for email in self._history:
            if email["id"] == email_id:
                email["status"] = status
                email["processed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if feishu_record_id:
                    email["feishu_record_id"] = feishu_record_id
                if error_message:
                    email["error_message"] = error_message
                if pdf_filename:
                    email["pdf_filename"] = pdf_filename
                self._save_data()
                return True
        return False

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取邮件历史"""
        return self._history[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._history)
        success = len([e for e in self._history if e["status"] == "success"])
        failed = len([e for e in self._history if e["status"] == "failed"])
        processing = len([e for e in self._history if e["status"] == "processing"])
        received = len([e for e in self._history if e["status"] == "received"])
        verification = len([e for e in self._history if e.get("email_type") == "verification"])
        resume = len([e for e in self._history if e.get("email_type") == "resume"])

        today = datetime.now().strftime("%Y-%m-%d")
        today_emails = [e for e in self._history if e["received_at"].startswith(today)]

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "processing": processing,
            "received": received,
            "verification_count": verification,
            "resume_count": resume,
            "today_count": len(today_emails),
            "success_rate": round(success / total * 100, 1) if total > 0 else 0
        }

    def email_exists(self, email_id: str) -> bool:
        """检查邮件是否已记录"""
        return any(e["id"] == email_id for e in self._history)


email_history = EmailHistoryService()
