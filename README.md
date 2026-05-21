# 招聘AI服务API

自动接收邮件简历并写入飞书多维表格的后端服务。

## 功能特性

- **虚拟邮箱监听**: 通过IMAP协议自动监听邮箱，接收带PDF附件的邮件
- **自动解析**: 自动提取发件人信息、邮件主题和PDF简历附件
- **飞书集成**: 自动调用飞书多维表格API，新增记录并上传简历文件
- **手动上传**: 提供API接口手动上传简历到多维表格
- **本地备份**: 所有简历自动保存到本地目录备份

## 项目结构

```
recruitment-api/
├── app/
│   ├── api/
│   │   └── resume_routes.py      # API路由定义
│   ├── core/
│   │   └── config.py             # 配置管理
│   ├── services/
│   │   ├── email_service.py      # 邮件监听服务
│   │   └── feishu_service.py     # 飞书API客户端
│   └── utils/
│       └── file_handler.py       # 文件处理工具
├── main.py                        # FastAPI入口
├── requirements.txt               # 依赖包
├── .env.example                   # 环境变量模板
└── README.md                      # 项目说明
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 飞书多维表格API配置
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_BASE_ID=xxxxxxxxxxxxxxxx
FEISHU_TABLE_ID=xxxxxxxxxxxxxxxx

# 虚拟邮箱配置（推荐使用 ethereal.email 免费测试邮箱）
EMAIL_IMAP_SERVER=imap.ethereal.email
EMAIL_IMAP_PORT=993
EMAIL_ADDRESS=your_ethereal_email@ethereal.email
EMAIL_PASSWORD=your_ethereal_password
```

### 3. 获取飞书配置

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 **App ID** 和 **App Secret**
4. 开启多维表格权限：
   - `bitable:record`
   - `bitable:file`
   - `drive:file:read`
   - `drive:file:write`
5. 发布应用并获取 **Base ID** 和 **Table ID**

### 4. 获取虚拟邮箱

推荐使用 **Ethereal Email**（免费测试邮箱）：

```bash
# 使用npm快速生成
npx ethereal-email
```

或访问 https://ethereal.email/ 手动创建。

### 5. 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动。

## API接口

### 查看服务状态
```bash
GET /
```

### 健康检查
```bash
GET /health
```

### 获取邮箱监控状态
```bash
GET /api/resumes/email/status
```

### 手动触发邮件检查
```bash
POST /api/resumes/email/check
```

### 手动上传简历
```bash
POST /api/resumes/upload
Content-Type: multipart/form-data

参数:
- candidate_name: 候选人姓名
- email: 候选人邮箱
- file: PDF文件
- additional_fields: 额外字段(JSON字符串，可选)
```

示例:
```bash
curl -X POST "http://localhost:8000/api/resumes/upload" \
  -F "candidate_name=张三" \
  -F "email=zhangsan@example.com" \
  -F "file=@/path/to/resume.pdf"
```

### 模拟邮件处理（测试用）
```bash
POST /api/resumes/email/manual-process
Content-Type: multipart/form-data

参数:
- sender_name: 发件人姓名
- sender_email: 发件人邮箱
- subject: 邮件主题
- file: PDF附件
```

## 飞书多维表格字段要求

多维表格中需要包含以下字段（字段名需匹配）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 姓名 | 文本 | 候选人姓名 |
| 邮箱 | 文本 | 候选人邮箱 |
| 简历 | 附件 | PDF简历文件 |
| 邮件主题 | 文本 | 原邮件主题（可选） |
| 投递时间 | 文本/日期 | 投递时间（可选） |
| 原始文件名 | 文本 | 原始文件名（可选） |

## 邮件接收流程

```
招聘平台/候选人
      ↓
发送邮件到虚拟邮箱 (含PDF附件)
      ↓
服务定时轮询检查 (默认60秒)
      ↓
解析邮件 → 提取发件人 + PDF附件
      ↓
本地备份保存简历
      ↓
上传PDF到飞书获取file_token
      ↓
调用多维表格API新增一行记录
      ↓
完成！简历自动归档到飞书
```

## 注意事项

1. **安全性**: 生产环境请使用真实企业邮箱，ethereal.email仅适合测试
2. **轮询间隔**: 默认60秒检查一次，可通过 `EMAIL_POLL_INTERVAL` 调整
3. **文件大小**: 飞书对上传文件有大小限制（通常100MB以内）
4. **并发处理**: 当前为单线程轮询，大量邮件时建议调整轮询间隔或使用webhook方案

## 技术栈

- **FastAPI**: Web框架
- **aiohttp**: 异步HTTP客户端（调用飞书API）
- **imaplib**: IMAP邮件协议
- **Python 3.8+**: 运行环境
