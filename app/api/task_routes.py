from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging

from app.models.task import (
    TaskCreate, TaskUpdate, StatusTransition, Task, TaskStatus,
    STATUS_TRANSITIONS, STATUS_LABELS, STATUS_COLORS,
    PRIORITY_LABELS, PRIORITY_COLORS
)
from app.services.task_service import task_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=Task)
async def create_task(task_create: TaskCreate):
    """创建新任务"""
    try:
        task = task_service.create_task(task_create)
        logger.info(f"创建任务: {task.id} - {task.title}")
        return task
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Task])
async def list_tasks(
    status: Optional[str] = Query(None, description="状态筛选"),
    task_type: Optional[str] = Query(None, description="任务类型筛选"),
    priority: Optional[str] = Query(None, description="优先级筛选"),
    assignee: Optional[str] = Query(None, description="负责人筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    sort_by: str = Query("updated_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc")
):
    """获取任务列表"""
    try:
        status_enum = TaskStatus(status) if status else None
        tasks = task_service.list_tasks(
            status=status_enum,
            task_type=task_type,
            priority=priority,
            assignee=assignee,
            keyword=keyword,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return tasks
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"无效的状态值: {status}")
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """获取任务统计信息"""
    try:
        return task_service.get_statistics()
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status-flow")
async def get_status_flow():
    """获取状态流转规则"""
    flow = {}
    for status, allowed in STATUS_TRANSITIONS.items():
        flow[status.value] = {
            "label": STATUS_LABELS[status],
            "color": STATUS_COLORS[status],
            "allowed_transitions": [
                {"value": s.value, "label": STATUS_LABELS[s], "color": STATUS_COLORS[s]}
                for s in allowed
            ]
        }
    return flow


@router.get("/metadata")
async def get_metadata():
    """获取任务元数据（状态、类型、优先级定义）"""
    from app.models.task import TaskType
    return {
        "statuses": [
            {"value": s.value, "label": STATUS_LABELS[s], "color": STATUS_COLORS[s]}
            for s in TaskStatus
        ],
        "priorities": [
            {"value": p.value, "label": PRIORITY_LABELS[p], "color": PRIORITY_COLORS[p]}
            for p in PRIORITY_LABELS.keys()
        ],
        "types": [
            {"value": "resume_screening", "label": "简历筛选"},
            {"value": "interview_arrange", "label": "面试安排"},
            {"value": "offer_process", "label": "Offer流程"},
            {"value": "onboarding", "label": "入职办理"},
            {"value": "communication", "label": "候选人沟通"},
            {"value": "other", "label": "其他"},
        ]
    }


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """获取单个任务详情"""
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.put("/{task_id}", response_model=Task)
async def update_task(task_id: str, task_update: TaskUpdate):
    """更新任务信息"""
    task = task_service.update_task(task_id, task_update)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    logger.info(f"更新任务: {task_id}")
    return task


@router.post("/{task_id}/transition", response_model=Task)
async def transition_task_status(task_id: str, transition: StatusTransition):
    """流转任务状态"""
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        task = task_service.transition_status(task_id, transition)
        logger.info(f"任务状态流转: {task_id} -> {transition.new_status.value}")
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"状态流转失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    success = task_service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    logger.info(f"删除任务: {task_id}")
    return {"success": True, "message": "任务已删除"}
