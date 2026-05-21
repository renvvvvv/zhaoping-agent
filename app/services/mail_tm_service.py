import aiohttp
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from email.message import EmailMessage
from email.header import decode_header
import email
from datetime import datetime

from app.core.config import settings
from app.services.feishu_service import feishu_client
from app.services.email_history_service import email_history
from app.utils.file_handler import generate_resume_filename, save_resume_locally
from app.utils.email_parser import parse_boss_subject, parse_boss_email_body, get_resume_source, extract_contact_from_pdf_filename

logger = logging.getLogger(__name__)


class MailTMService:
    """Mail.tm 临时邮箱服务 - 通过REST API监听邮件"""

    BASE_URL = "https://api.mail.tm"

    def __init__(self):
        self.email_address = settings.EMAIL_ADDRESS
        self.email_password = settings.EMAIL_PASSWORD
        self.poll_interval = settings.EMAIL_POLL_INTERVAL
        self._running = False
        self._token: Optional[str] = None
        self._seen_message_ids: set = set()

    async def _get_token(self) -> str:
        """获取JWT Token"""
        if self._token:
            return self._token

        url = f"{self.BASE_URL}/token"
        payload = {
            "address": self.email_address,
            "password": self.email_password
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                self._token = data["token"]
                return self._token

    async def _api_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送API请求"""
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        url = f"{self.BASE_URL}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 204:
                    return {}
                return await response.json()

    async def get_messages(self) -> List[Dict[str, Any]]:
        """获取邮件列表"""
        try:
            data = await self._api_request("GET", "/messages")
            return data.get("hydra:member", [])
        except Exception as e:
            logger.error(f"获取邮件列表失败: {e}")
            return []

    async def get_message_detail(self, message_id: str) -> Dict[str, Any]:
        """获取邮件详情"""
        try:
            return await self._api_request("GET", f"/messages/{message_id}")
        except Exception as e:
            logger.error(f"获取邮件详情失败: {e}")
            return {}

    def _decode_str(self, s: Optional[str]) -> str:
        """解码字符串"""
        if not s:
            return ""
        return s

    def _get_email_body(self, detail: Dict[str, Any]) -> str:
        """提取邮件正文"""
        # mail.tm 返回 text 和 html 字段
        text_content = detail.get('text', '')
        if isinstance(text_content, list) and text_content:
            text = text_content[0].get('content', '') if isinstance(text_content[0], dict) else str(text_content[0])
        else:
            text = str(text_content) if text_content else ''

        if not text:
            html_content = detail.get('html', '')
            if isinstance(html_content, list) and html_content:
                html = html_content[0].get('content', '') if isinstance(html_content[0], dict) else str(html_content[0])
            else:
                html = str(html_content) if html_content else ''
            # 简单去除HTML标签
            import re
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _detect_email_type(self, subject: str, body: str, has_pdf: bool) -> str:
        """检测邮件类型"""
        subject_lower = subject.lower()
        body_lower = body.lower()

        # 验证码邮件
        if any(k in subject_lower or k in body_lower for k in ['验证码', 'verification', 'code', '验证']):
            return "verification"

        # 简历邮件
        if has_pdf or any(k in subject_lower for k in ['简历', 'cv', 'resume']):
            return "resume"

        return "other"

    async def _process_email(self, message: Dict[str, Any]):
        """处理单封邮件"""
        msg_id = message.get("id")
        is_resume = False
        try:
            if msg_id in self._seen_message_ids:
                return
            self._seen_message_ids.add(msg_id)

            # 获取邮件详情
            detail = await self.get_message_detail(msg_id)
            if not detail:
                return

            sender_name = detail.get("from", {}).get("name", "未知")
            sender_email = detail.get("from", {}).get("address", "")
            subject = detail.get("subject", "")
            received_at = detail.get("createdAt", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # 替换T为空格，简化时间格式
            if 'T' in received_at:
                received_at = received_at.replace('T', ' ')[:19]

            # 提取邮件正文
            body = self._get_email_body(detail)

            # 检测是否有PDF附件
            has_attachments = detail.get("hasAttachments", False)
            has_pdf = False
            if has_attachments:
                attachments = detail.get("attachments", [])
                has_pdf = any(att.get("filename", "").lower().endswith('.pdf') for att in attachments)

            # 检测邮件类型
            email_type = self._detect_email_type(subject, body, has_pdf)

            logger.info(f"处理邮件 - 类型: {email_type}, 主题: {subject}, 发件人: {sender_name} <{sender_email}>")

            # 记录邮件
            if not email_history.email_exists(msg_id):
                email_history.add_email(
                    email_id=msg_id,
                    sender_name=sender_name,
                    sender_email=sender_email,
                    subject=subject,
                    received_at=received_at,
                    has_pdf=has_pdf,
                    body=body,
                    email_type=email_type
                )

            # 验证码邮件：只记录，不上传飞书，不删除
            if email_type == "verification":
                logger.info(f"验证码邮件已记录: {msg_id}")
                email_history.update_status(msg_id, "success")
                return

            # 非简历邮件且无PDF：记录为其他
            if not has_pdf:
                logger.info("邮件中无PDF附件，跳过飞书上传")
                email_history.update_status(msg_id, "success")
                return

            # 更新为处理中
            email_history.update_status(msg_id, "processing")
            is_resume = True

            # 处理PDF附件并上传飞书
            attachments = detail.get("attachments", [])
            pdf_found = False
            feishu_record_id = None
            pdf_filename = None

            for att in attachments:
                filename = att.get("filename", "")
                if filename.lower().endswith('.pdf'):
                    att_id = att.get("id")
                    if att_id:
                        try:
                            # 下载附件
                            token = await self._get_token()
                            url = f"{self.BASE_URL}/messages/{msg_id}/attachment/{att_id}"
                            headers = {"Authorization": f"Bearer {token}"}

                            async with aiohttp.ClientSession() as session:
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        file_content = await resp.read()
                                        # 处理PDF
                                        new_filename = generate_resume_filename(filename, sender_email)
                                        local_path = save_resume_locally(file_content, new_filename)
                                        logger.info(f"简历已保存到本地: {local_path}")
                                        pdf_filename = new_filename

                                        # 解析邮件主题和正文，提取候选人信息
                                        parsed = parse_boss_subject(subject)
                                        body_info = parse_boss_email_body(body)

                                        # 确定候选人姓名（优先从主题解析，其次从PDF文件名，最后 fallback 到发件人）
                                        candidate_name = parsed.get("candidate_name") or extract_contact_from_pdf_filename(filename) or sender_name

                                        # 确定候选人邮箱（优先从正文解析，其次用发件邮箱）
                                        candidate_email = body_info.get("candidate_email") or sender_email

                                        # 简历来源
                                        resume_source = get_resume_source(sender_email)

                                        logger.info(f"解析结果: 姓名={candidate_name}, 岗位={parsed.get('job_title')}, "
                                                   f"经验={parsed.get('experience')}, 地点={parsed.get('location')}, "
                                                   f"薪资={parsed.get('salary')}, 来源={resume_source}")

                                        # 上传到飞书
                                        result = await feishu_client.create_record_with_resume(
                                            candidate_name=candidate_name,
                                            email=candidate_email,
                                            file_name=new_filename,
                                            file_content=file_content,
                                            job_title=parsed.get("job_title"),
                                            location=parsed.get("location"),
                                            salary=parsed.get("salary"),
                                            experience=parsed.get("experience"),
                                            resume_source=resume_source,
                                            education=body_info.get("education"),
                                            school=body_info.get("school"),
                                            phone=body_info.get("candidate_phone"),
                                            additional_fields={
                                                "邮件主题": subject,
                                                "投递时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                "原始文件名": filename
                                            }
                                        )
                                        feishu_record_id = result.get("data", {}).get("record", {}).get("record_id")
                                        logger.info(f"简历已成功写入飞书多维表格，记录ID: {feishu_record_id}")
                                        pdf_found = True
                        except Exception as e:
                            logger.error(f"处理附件 {filename} 失败: {e}")
                            email_history.update_status(msg_id, "failed", error_message=str(e))
                            return

            if not pdf_found:
                logger.info("邮件中没有PDF附件")
                email_history.update_status(msg_id, "failed", error_message="无PDF附件")
                return

            # 更新为成功
            email_history.update_status(
                msg_id, "success",
                feishu_record_id=feishu_record_id,
                pdf_filename=pdf_filename
            )

            # 删除已处理的简历邮件
            try:
                await self._api_request("DELETE", f"/messages/{msg_id}")
                logger.info(f"已删除处理完成的邮件: {msg_id}")
            except Exception as e:
                logger.warning(f"删除邮件失败: {e}")

        except Exception as e:
            logger.error(f"处理邮件失败: {e}")
            if msg_id:
                email_history.update_status(msg_id, "failed", error_message=str(e))

    async def check_new_emails(self):
        """检查新邮件"""
        try:
            logger.info("开始检查mail.tm新邮件...")
            messages = await self.get_messages()

            if not messages:
                logger.info("没有新邮件")
                return

            logger.info(f"发现 {len(messages)} 封新邮件")
            for msg in messages:
                await self._process_email(msg)

            logger.info("邮件检查完成")

        except Exception as e:
            logger.error(f"检查邮件失败: {e}")

    async def start_monitoring(self):
        """启动邮件监控循环"""
        self._running = True
        logger.info(f"启动mail.tm邮箱监控: {self.email_address}")
        logger.info(f"轮询间隔: {self.poll_interval}秒")

        while self._running:
            try:
                await self.check_new_emails()
            except Exception as e:
                logger.error(f"监控循环异常: {e}")

            await asyncio.sleep(self.poll_interval)

    def stop_monitoring(self):
        """停止邮件监控"""
        self._running = False
        logger.info("停止mail.tm邮箱监控")


# 判断是否是mail.tm邮箱
def is_mail_tm(email: str) -> bool:
    return email.endswith("@wshu.net") or email.endswith("@mail.tm")
