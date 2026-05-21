import json
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.models.task import (
    Task, TaskCreate, TaskUpdate, StatusTransition, TaskHistory,
    TaskStatus, STATUS_TRANSITIONS, STATUS_LABELS
)


class TaskService:
    """任务管理服务 - 基于JSON文件持久化"""

    DATA_FILE = "./data/tasks.json"

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._ensure_data_dir()
        self._load_data()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        Path(self.DATA_FILE).parent.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        """从JSON文件加载任务数据"""
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task_data in data.get("tasks", []):
                        task = Task(**task_data)
                        self._tasks[task.id] = task
            except Exception as e:
                print(f"加载任务数据失败: {e}")
                self._tasks = {}

    def _save_data(self):
        """保存任务数据到JSON文件"""
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                tasks_list = [task.model_dump() for task in self._tasks.values()]
                json.dump({"tasks": tasks_list}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务数据失败: {e}")

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def create_task(self, task_create: TaskCreate) -> Task:
        """创建新任务"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = self._now()

        history = [TaskHistory(
            timestamp=now,
            action="创建任务",
            to_status=TaskStatus.PENDING.value,
            operator="system"
        )]

        task = Task(
            id=task_id,
            title=task_create.title,
            description=task_create.description,
            status=TaskStatus.PENDING,
            task_type=task_create.task_type,
            priority=task_create.priority,
            assignee=task_create.assignee,
            candidate_name=task_create.candidate_name,
            candidate_email=task_create.candidate_email,
            due_date=task_create.due_date,
            related_record_id=task_create.related_record_id,
            created_at=now,
            updated_at=now,
            history=history
        )

        self._tasks[task_id] = task
        self._save_data()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取单个任务"""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc"
    ) -> List[Task]:
        """列出任务（支持筛选和搜索）"""
        tasks = list(self._tasks.values())

        # 筛选
        if status:
            tasks = [t for t in tasks if t.status == status]
        if task_type:
            tasks = [t for t in tasks if t.task_type.value == task_type]
        if priority:
            tasks = [t for t in tasks if t.priority.value == priority]
        if assignee:
            tasks = [t for t in tasks if t.assignee and assignee.lower() in t.assignee.lower()]
        if keyword:
            keyword_lower = keyword.lower()
            tasks = [
                t for t in tasks
                if keyword_lower in t.title.lower()
                or (t.description and keyword_lower in t.description.lower())
                or (t.candidate_name and keyword_lower in t.candidate_name.lower())
            ]

        # 排序
        reverse = sort_order == "desc"
        tasks.sort(key=lambda t: getattr(t, sort_by, t.updated_at), reverse=reverse)

        return tasks

    def update_task(self, task_id: str, task_update: TaskUpdate) -> Optional[Task]:
        """更新任务信息"""
        task = self._tasks.get(task_id)
        if not task:
            return None

        now = self._now()
        update_data = task_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if value is not None:
                setattr(task, key, value)

        task.updated_at = now

        # 记录历史
        task.history.append(TaskHistory(
            timestamp=now,
            action="更新任务信息",
            operator="system"
        ))

        self._save_data()
        return task

    def transition_status(self, task_id: str, transition: StatusTransition) -> Optional[Task]:
        """流转任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None

        current_status = task.status
        new_status = transition.new_status

        # 验证状态流转是否合法
        allowed_transitions = STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_transitions:
            raise ValueError(
                f"非法状态流转: {STATUS_LABELS.get(current_status, current_status)} -> {STATUS_LABELS.get(new_status, new_status)}"
            )

        now = self._now()
        old_status = task.status
        task.status = new_status
        task.updated_at = now

        if new_status == TaskStatus.COMPLETED:
            task.completed_at = now

        # 记录历史
        task.history.append(TaskHistory(
            timestamp=now,
            action="状态流转",
            from_status=old_status.value,
            to_status=new_status.value,
            comment=transition.comment,
            operator="system"
        ))

        self._save_data()
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save_data()
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        tasks = list(self._tasks.values())
        total = len(tasks)

        status_count = {}
        for status in TaskStatus:
            count = len([t for t in tasks if t.status == status])
            status_count[status.value] = count

        type_count = {}
        for task in tasks:
            ttype = task.task_type.value
            type_count[ttype] = type_count.get(ttype, 0) + 1

        priority_count = {}
        for priority in ["low", "medium", "high", "urgent"]:
            count = len([t for t in tasks if t.priority.value == priority])
            priority_count[priority] = count

        # 今日任务
        today = datetime.now().strftime("%Y-%m-%d")
        today_tasks = [t for t in tasks if t.created_at.startswith(today)]
        today_completed = [t for t in tasks if t.completed_at and t.completed_at.startswith(today)]

        # 逾期任务
        overdue = []
        for t in tasks:
            if t.due_date and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                if t.due_date < today:
                    overdue.append(t)

        return {
            "total": total,
            "status_distribution": status_count,
            "type_distribution": type_count,
            "priority_distribution": priority_count,
            "today_created": len(today_tasks),
            "today_completed": len(today_completed),
            "overdue_count": len(overdue),
            "overdue_tasks": [t.model_dump() for t in overdue[:10]]
        }


task_service = TaskService()
