import imaplib
import email
from email.message import EmailMessage
from email.header import decode_header
from typing import List, Optional, Tuple
import asyncio
import logging
from datetime import datetime

from app.core.config import settings
from app.services.feishu_service import feishu_client
from app.utils.file_handler import generate_resume_filename, save_resume_locally

logger = logging.getLogger(__name__)


class EmailService:
    """虚拟邮箱服务 - 监听邮件并自动处理简历"""

    def __init__(self):
        self.imap_server = settings.EMAIL_IMAP_SERVER
        self.imap_port = settings.EMAIL_IMAP_PORT
        self.email_address = settings.EMAIL_ADDRESS
        self.email_password = settings.EMAIL_PASSWORD
        self.poll_interval = settings.EMAIL_POLL_INTERVAL
        self._running = False

    def _decode_str(self, s: Optional[str]) -> str:
        """解码邮件头中的编码字符串"""
        if not s:
            return ""
        decoded = decode_header(s)
        result = ""
        for part, charset in decoded:
            if isinstance(part, bytes):
                try:
                    result += part.decode(charset or "utf-8", errors="replace")
                except:
                    result += part.decode("utf-8", errors="replace")
            else:
                result += part
        return result

    def _get_email_body(self, msg: EmailMessage) -> str:
        """获取邮件正文"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
                    except:
                        continue
                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                    except:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
            except:
                body = ""
        return body

    def _extract_pdf_attachments(self, msg: EmailMessage) -> List[Tuple[str, bytes]]:
        """提取邮件中的PDF附件"""
        attachments = []
        if not msg.is_multipart():
            return attachments

        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = self._decode_str(filename)
                    if filename.lower().endswith('.pdf'):
                        payload = part.get_payload(decode=True)
                        if payload:
                            attachments.append((filename, payload))
                            logger.info(f"发现PDF附件: {filename}")

        return attachments

    def _extract_sender_info(self, msg: EmailMessage) -> Tuple[str, str]:
        """提取发件人信息 (姓名, 邮箱)"""
        from_header = msg.get("From", "")
        # 尝试解析 "姓名 <邮箱>" 格式
        if '<' in from_header and '>' in from_header:
            name = from_header.split('<')[0].strip().strip('"')
            email_addr = from_header.split('<')[1].split('>')[0].strip()
        else:
            name = ""
            email_addr = from_header.strip()

        name = self._decode_str(name)
        return name or "未知候选人", email_addr

    async def _process_email(self, msg: EmailMessage):
        """处理单封邮件"""
        try:
            subject = self._decode_str(msg.get("Subject", ""))
            sender_name, sender_email = self._extract_sender_info(msg)
            date_str = msg.get("Date", "")

            logger.info(f"处理邮件 - 主题: {subject}, 发件人: {sender_name} <{sender_email}>")

            # 提取PDF附件
            pdf_attachments = self._extract_pdf_attachments(msg)

            if not pdf_attachments:
                logger.info("邮件中没有PDF附件，跳过")
                return

            # 处理每个PDF附件
            for original_filename, file_content in pdf_attachments:
                try:
                    # 生成规范文件名并本地备份
                    new_filename = generate_resume_filename(original_filename, sender_email)
                    local_path = save_resume_locally(file_content, new_filename)
                    logger.info(f"简历已保存到本地: {local_path}")

                    # 上传到飞书多维表格
                    result = await feishu_client.create_record_with_resume(
                        candidate_name=sender_name,
                        email=sender_email,
                        file_name=new_filename,
                        file_content=file_content,
                        additional_fields={
                            "邮件主题": subject,
                            "投递时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "原始文件名": original_filename
                        }
                    )
                    logger.info(f"简历已成功写入飞书多维表格，记录ID: {result['data']['record']['record_id']}")

                except Exception as e:
                    logger.error(f"处理附件 {original_filename} 失败: {e}")

        except Exception as e:
            logger.error(f"处理邮件失败: {e}")

    async def check_new_emails(self):
        """检查新邮件"""
        try:
            logger.info("开始检查新邮件...")

            # 连接IMAP服务器
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            mail.select("INBOX")

            # 搜索未读邮件
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.info("没有新邮件")
                mail.logout()
                return

            email_ids = messages[0].split()
            if not email_ids:
                logger.info("没有未读邮件")
                mail.logout()
                return

            logger.info(f"发现 {len(email_ids)} 封新邮件")

            for email_id in email_ids:
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    await self._process_email(msg)

                    # 标记为已读
                    mail.store(email_id, "+FLAGS", "\\Seen")

                except Exception as e:
                    logger.error(f"处理邮件 {email_id} 失败: {e}")

            mail.logout()
            logger.info("邮件检查完成")

        except Exception as e:
            logger.error(f"检查邮件失败: {e}")

    async def start_monitoring(self):
        """启动邮件监控循环"""
        self._running = True
        logger.info(f"启动虚拟邮箱监控: {self.email_address}")
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
        logger.info("停止虚拟邮箱监控")


# 全局邮件服务实例
email_service = EmailService()
