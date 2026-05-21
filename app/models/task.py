from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"                    # 待处理
    PROCESSING = "processing"              # 进行中
    WAITING_FEEDBACK = "waiting_feedback"  # 等待反馈
    COMPLETED = "completed"                # 已完成
    CANCELLED = "cancelled"                # 已取消


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(str, Enum):
    RESUME_SCREENING = "resume_screening"      # 简历筛选
    INTERVIEW_ARRANGE = "interview_arrange"    # 面试安排
    OFFER_PROCESS = "offer_process"            # Offer流程
    ONBOARDING = "onboarding"                  # 入职办理
    COMMUNICATION = "communication"            # 候选人沟通
    OTHER = "other"                            # 其他


# 状态流转规则
STATUS_TRANSITIONS = {
    TaskStatus.PENDING: [TaskStatus.PROCESSING, TaskStatus.CANCELLED],
    TaskStatus.PROCESSING: [TaskStatus.WAITING_FEEDBACK, TaskStatus.COMPLETED, TaskStatus.CANCELLED],
    TaskStatus.WAITING_FEEDBACK: [TaskStatus.PROCESSING, TaskStatus.COMPLETED, TaskStatus.CANCELLED],
    TaskStatus.COMPLETED: [],
    TaskStatus.CANCELLED: [],
}


STATUS_LABELS = {
    TaskStatus.PENDING: "待处理",
    TaskStatus.PROCESSING: "进行中",
    TaskStatus.WAITING_FEEDBACK: "等待反馈",
    TaskStatus.COMPLETED: "已完成",
    TaskStatus.CANCELLED: "已取消",
}


STATUS_COLORS = {
    TaskStatus.PENDING: "#fa8c16",
    TaskStatus.PROCESSING: "#1890ff",
    TaskStatus.WAITING_FEEDBACK: "#722ed1",
    TaskStatus.COMPLETED: "#52c41a",
    TaskStatus.CANCELLED: "#bfbfbf",
}


PRIORITY_LABELS = {
    TaskPriority.LOW: "低",
    TaskPriority.MEDIUM: "中",
    TaskPriority.HIGH: "高",
    TaskPriority.URGENT: "紧急",
}


PRIORITY_COLORS = {
    TaskPriority.LOW: "#52c41a",
    TaskPriority.MEDIUM: "#faad14",
    TaskPriority.HIGH: "#fa541c",
    TaskPriority.URGENT: "#f5222d",
}


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    task_type: TaskType = TaskType.OTHER
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: Optional[str] = Field(None, max_length=100)
    candidate_name: Optional[str] = Field(None, max_length=100)
    candidate_email: Optional[str] = Field(None, max_length=100)
    due_date: Optional[str] = None  # YYYY-MM-DD
    related_record_id: Optional[str] = None  # 关联的飞书记录ID


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    task_type: Optional[TaskType] = None
    priority: Optional[TaskPriority] = None
    assignee: Optional[str] = Field(None, max_length=100)
    candidate_name: Optional[str] = Field(None, max_length=100)
    candidate_email: Optional[str] = Field(None, max_length=100)
    due_date: Optional[str] = None
    related_record_id: Optional[str] = None


class StatusTransition(BaseModel):
    new_status: TaskStatus
    comment: Optional[str] = Field(None, max_length=500)


class TaskHistory(BaseModel):
    timestamp: str
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    comment: Optional[str] = None
    operator: Optional[str] = None


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    task_type: TaskType = TaskType.OTHER
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    due_date: Optional[str] = None
    related_record_id: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    history: List[TaskHistory] = []
