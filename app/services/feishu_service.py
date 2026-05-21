import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class FeishuClient:
    """飞书多维表格API客户端"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self):
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self.base_id = settings.FEISHU_BASE_ID
        self.table_id = settings.FEISHU_TABLE_ID
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: Optional[float] = None

    async def _get_tenant_access_token(self) -> str:
        """获取租户访问令牌"""
        if self._tenant_access_token and self._token_expire_time and asyncio.get_event_loop().time() < self._token_expire_time:
            return self._tenant_access_token

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                if data.get("code") != 0:
                    raise Exception(f"获取token失败: {data}")

                self._tenant_access_token = data["tenant_access_token"]
                self._token_expire_time = asyncio.get_event_loop().time() + data["expire"] - 300
                return self._tenant_access_token

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送带认证的请求"""
        token = await self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        url = f"{self.BASE_URL}{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                data = await response.json()
                if data.get("code") != 0:
                    logger.error(f"飞书API请求失败: {data}")
                    raise Exception(f"API请求失败: {data}")
                return data

    async def create_record(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        在多维表格中新增一行记录

        Args:
            fields: 字段数据，格式为 {"字段名": "值"}

        Returns:
            新增记录的信息
        """
        endpoint = f"/bitable/v1/apps/{self.base_id}/tables/{self.table_id}/records"
        payload = {"fields": fields}

        try:
            result = await self._request("POST", endpoint, json=payload)
            logger.info(f"成功创建记录: {result['data']['record']['record_id']}")
            return result
        except Exception as e:
            logger.error(f"创建记录失败: {e}")
            raise

    async def upload_file(self, file_name: str, file_content: bytes, file_type: str = "stream") -> str:
        """
        上传文件到飞书获取file_token

        Args:
            file_name: 文件名
            file_content: 文件二进制内容
            file_type: 文件类型

        Returns:
            file_token 用于在多维表格中引用
        """
        endpoint = f"/drive/v1/medias/upload_all"
        token = await self._get_tenant_access_token()

        data = aiohttp.FormData()
        data.add_field("file_name", file_name)
        data.add_field("parent_type", "bitable_file")
        data.add_field("parent_node", self.base_id)
        data.add_field("size", str(len(file_content)))
        data.add_field("file", file_content, filename=file_name, content_type="application/pdf")

        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.BASE_URL}{endpoint}", headers=headers, data=data) as response:
                result = await response.json()
                if result.get("code") != 0:
                    raise Exception(f"文件上传失败: {result}")
                return result["data"]["file_token"]

    async def create_record_with_resume(self,
                                       candidate_name: str,
                                       email: str,
                                       file_name: str,
                                       file_content: bytes,
                                       job_title: Optional[str] = None,
                                       location: Optional[str] = None,
                                       salary: Optional[str] = None,
                                       experience: Optional[str] = None,
                                       resume_source: Optional[str] = None,
                                       education: Optional[str] = None,
                                       school: Optional[str] = None,
                                       phone: Optional[str] = None,
                                       additional_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        上传简历PDF并创建记录

        Args:
            candidate_name: 候选人姓名
            email: 邮箱地址
            file_name: PDF文件名
            file_content: PDF文件二进制内容
            job_title: 岗位名称
            location: 工作地点
            salary: 薪资范围
            experience: 工作经验
            resume_source: 简历来源
            education: 学历
            school: 毕业院校
            phone: 联系方式
            additional_fields: 额外字段（邮件主题、投递时间等）

        Returns:
            创建的记录信息
        """
        # 先上传PDF文件
        file_token = await self.upload_file(file_name, file_content)

        # 构建记录字段（与飞书表格字段名匹配）
        fields = {
            "候选人": candidate_name,
            "邮箱": email,
            "候选人简历": [{"file_token": file_token}]
        }

        # 写入解析出的字段
        # 岗位名称(DuplexLink)不能直接写入，写入新建的"岗位"(Text)字段
        if job_title:
            fields["岗位"] = job_title
        if resume_source:
            fields["简历来源"] = resume_source
        if education:
            fields["学历"] = education
        if school:
            fields["毕业院校"] = school
        if phone:
            fields["联系方式"] = phone

        # 将额外字段合并写入"彩蛋"字段（表格中的备注字段）
        if additional_fields:
            extra_parts = []
            for k, v in additional_fields.items():
                extra_parts.append(f"{k}: {v}")
            if experience:
                extra_parts.append(f"工作经验: {experience}")
            if location:
                extra_parts.append(f"工作地点: {location}")
            if salary:
                extra_parts.append(f"薪资范围: {salary}")
            if extra_parts:
                fields["彩蛋"] = "\n".join(extra_parts)

        return await self.create_record(fields)


feishu_client = FeishuClient()
