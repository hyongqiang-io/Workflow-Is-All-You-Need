"""
工作流输出数据API
Workflow Output Data API
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.output_data_processor import OutputDataProcessor
from ..services.output_data_validator import OutputDataValidator
from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..utils.auth import get_current_user
from ..models.user import User


# 创建路由器
router = APIRouter(prefix="/api/workflow-outputs", tags=["workflow-outputs"])


# ==================== 请求/响应模型 ====================

class OutputQueryRequest(BaseModel):
    """输出数据查询请求模型"""
    workflow_base_ids: Optional[List[uuid.UUID]] = Field(None, description="工作流基础ID列表")
    executor_ids: Optional[List[uuid.UUID]] = Field(None, description="执行者ID列表")
    result_types: Optional[List[str]] = Field(None, description="结果类型列表: success, partial_success, failure")
    quality_score_range: Optional[tuple[float, float]] = Field(None, description="质量评分范围 (min, max)")
    date_range: Optional[tuple[str, str]] = Field(None, description="日期范围 (start_date, end_date)")
    status: Optional[str] = Field(None, description="工作流状态")
    limit: int = Field(50, ge=1, le=1000, description="返回结果数量限制")
    offset: int = Field(0, ge=0, description="偏移量")


class OutputStatisticsRequest(BaseModel):
    """输出统计请求模型"""
    time_period: str = Field("30d", description="时间周期: 7d, 30d, 90d, 1y")
    group_by: str = Field("day", description="分组方式: day, week, month")
    metrics: List[str] = Field(default_factory=lambda: ["success_rate", "quality_score"], 
                              description="统计指标列表")


class OutputExportRequest(BaseModel):
    """输出导出请求模型"""
    query: OutputQueryRequest
    export_format: str = Field("json", description="导出格式: json, csv, excel")
    include_fields: List[str] = Field(default_factory=lambda: ["basic", "summary", "quality"], 
                                    description="包含字段类型")


class OutputValidationRequest(BaseModel):
    """输出验证请求模型"""
    instance_ids: List[uuid.UUID] = Field(..., description="要验证的实例ID列表")
    validation_level: str = Field("standard", description="验证级别: basic, standard, strict")


# ==================== API端点 ====================

@router.get("/instances", summary="查询工作流输出实例")
async def query_workflow_outputs(
    workflow_base_ids: Optional[str] = Query(None, description="工作流基础ID列表,逗号分隔"),
    executor_ids: Optional[str] = Query(None, description="执行者ID列表,逗号分隔"),
    result_types: Optional[str] = Query(None, description="结果类型列表,逗号分隔"),
    quality_min: Optional[float] = Query(None, ge=0, le=1, description="最小质量评分"),
    quality_max: Optional[float] = Query(None, ge=0, le=1, description="最大质量评分"),
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="工作流状态"),
    limit: int = Query(50, ge=1, le=1000, description="结果数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user)
):
    """查询工作流输出实例"""
    try:
        workflow_repo = WorkflowInstanceRepository()
        
        # 构建查询条件
        conditions = []
        params = []
        param_count = 0
        
        # 基础查询
        base_query = """
        SELECT wi.*, w.name as workflow_name, u.username as executor_name
        FROM workflow_instance wi
        LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
        LEFT JOIN "user" u ON u.user_id = wi.executor_id
        WHERE wi.is_deleted = FALSE
        """
        
        # 添加查询条件
        if workflow_base_ids:
            workflow_ids = [uuid.UUID(wid.strip()) for wid in workflow_base_ids.split(',')]
            param_count += 1
            conditions.append(f"wi.workflow_base_id = ANY(${param_count})")
            params.append(workflow_ids)
        
        if executor_ids:
            executor_id_list = [uuid.UUID(eid.strip()) for eid in executor_ids.split(',')]
            param_count += 1
            conditions.append(f"wi.executor_id = ANY(${param_count})")
            params.append(executor_id_list)
        
        if status:
            param_count += 1
            conditions.append(f"wi.status = ${param_count}")
            params.append(status)
        
        if date_from:
            param_count += 1
            conditions.append(f"wi.created_at >= ${param_count}")
            params.append(datetime.fromisoformat(date_from))
        
        if date_to:
            param_count += 1
            conditions.append(f"wi.created_at <= ${param_count}")
            params.append(datetime.fromisoformat(date_to + "T23:59:59"))
        
        # 结果类型过滤（需要JSON查询）
        if result_types:
            types = [t.strip() for t in result_types.split(',')]
            param_count += 1
            conditions.append(f"(wi.execution_summary->>'execution_result'->>'result_type') = ANY(${param_count})")
            params.append(types)
        
        # 质量评分范围过滤
        if quality_min is not None:
            param_count += 1
            conditions.append(f"CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) >= ${param_count}")
            params.append(quality_min)
        
        if quality_max is not None:
            param_count += 1
            conditions.append(f"CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) <= ${param_count}")
            params.append(quality_max)
        
        # 构建完整查询
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += f" ORDER BY wi.created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
        params.extend([limit, offset])
        
        # 执行查询
        results = await workflow_repo.db.fetch_all(query, *params)
        
        # 处理结果
        formatted_results = []
        for result in results:
            result_dict = dict(result)
            
            # 解析JSON字段
            if result_dict.get('input_data'):
                result_dict['input_data'] = result_dict['input_data']
            if result_dict.get('output_data'):
                result_dict['output_data'] = result_dict['output_data']
            if result_dict.get('execution_summary'):
                result_dict['execution_summary'] = result_dict['execution_summary']
            if result_dict.get('quality_metrics'):
                result_dict['quality_metrics'] = result_dict['quality_metrics']
            if result_dict.get('data_lineage'):
                result_dict['data_lineage'] = result_dict['data_lineage']
            
            formatted_results.append(result_dict)
        
        # 获取总计数
        count_query = base_query.replace(
            "SELECT wi.*, w.name as workflow_name, u.username as executor_name",
            "SELECT COUNT(*)"
        )
        if conditions:
            count_query = count_query.replace(" AND " + " AND ".join(conditions), "")
            for condition in conditions:
                count_query += f" AND {condition}"
        
        total_count = await workflow_repo.db.fetch_val(count_query, *params[:-2])  # 排除limit和offset参数
        
        return {
            "success": True,
            "data": {
                "instances": formatted_results,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(formatted_results) < total_count
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询工作流输出失败: {str(e)}")


@router.get("/statistics", summary="获取工作流输出统计")
async def get_workflow_output_statistics(
    time_period: str = Query("30d", description="时间周期: 7d, 30d, 90d, 1y"),
    group_by: str = Query("day", description="分组方式: day, week, month"),
    workflow_base_id: Optional[str] = Query(None, description="特定工作流基础ID"),
    current_user: User = Depends(get_current_user)
):
    """获取工作流输出统计"""
    try:
        workflow_repo = WorkflowInstanceRepository()
        
        # 计算时间范围
        time_ranges = {
            "7d": 7,
            "30d": 30,
            "90d": 90,
            "1y": 365
        }
        
        if time_period not in time_ranges:
            raise HTTPException(status_code=400, detail="无效的时间周期")
        
        days = time_ranges[time_period]
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 构建基础查询
        conditions = ["wi.is_deleted = FALSE", "wi.created_at >= $1"]
        params = [start_date]
        
        if workflow_base_id:
            conditions.append("wi.workflow_base_id = $2")
            params.append(uuid.UUID(workflow_base_id))
        
        where_clause = " AND ".join(conditions)
        
        # 1. 总体统计
        overall_stats_query = f"""
        SELECT 
            COUNT(*) as total_instances,
            COUNT(CASE WHEN wi.status = 'completed' THEN 1 END) as completed_instances,
            COUNT(CASE WHEN wi.status = 'failed' THEN 1 END) as failed_instances,
            COUNT(CASE WHEN wi.status = 'cancelled' THEN 1 END) as cancelled_instances,
            AVG(CASE WHEN wi.quality_metrics->>'overall_quality_score' IS NOT NULL 
                THEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) END) as avg_quality_score,
            AVG(CASE WHEN wi.execution_summary->>'execution_stats'->>'total_duration_minutes' IS NOT NULL
                THEN CAST(wi.execution_summary->>'execution_stats'->>'total_duration_minutes' AS FLOAT) END) as avg_duration_minutes
        FROM workflow_instance wi
        WHERE {where_clause}
        """
        
        overall_stats = await workflow_repo.db.fetch_one(overall_stats_query, *params)
        
        # 2. 结果类型分布
        result_type_query = f"""
        SELECT 
            wi.execution_summary->>'execution_result'->>'result_type' as result_type,
            COUNT(*) as count
        FROM workflow_instance wi
        WHERE {where_clause} AND wi.execution_summary IS NOT NULL
        GROUP BY wi.execution_summary->>'execution_result'->>'result_type'
        """
        
        result_type_stats = await workflow_repo.db.fetch_all(result_type_query, *params)
        
        # 3. 时间序列统计
        if group_by == "day":
            date_trunc = "day"
        elif group_by == "week":
            date_trunc = "week"
        elif group_by == "month":
            date_trunc = "month"
        else:
            raise HTTPException(status_code=400, detail="无效的分组方式")
        
        time_series_query = f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', wi.created_at) as period,
            COUNT(*) as total_count,
            COUNT(CASE WHEN wi.status = 'completed' THEN 1 END) as completed_count,
            AVG(CASE WHEN wi.quality_metrics->>'overall_quality_score' IS NOT NULL 
                THEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) END) as avg_quality
        FROM workflow_instance wi
        WHERE {where_clause}
        GROUP BY DATE_TRUNC('{date_trunc}', wi.created_at)
        ORDER BY period
        """
        
        time_series_stats = await workflow_repo.db.fetch_all(time_series_query, *params)
        
        # 4. 质量分布统计
        quality_distribution_query = f"""
        SELECT 
            CASE 
                WHEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) >= 0.9 THEN 'excellent'
                WHEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) >= 0.7 THEN 'good'
                WHEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) >= 0.5 THEN 'fair'
                ELSE 'poor'
            END as quality_level,
            COUNT(*) as count
        FROM workflow_instance wi
        WHERE {where_clause} AND wi.quality_metrics->>'overall_quality_score' IS NOT NULL
        GROUP BY quality_level
        """
        
        quality_distribution = await workflow_repo.db.fetch_all(quality_distribution_query, *params)
        
        # 格式化结果
        return {
            "success": True,
            "data": {
                "overall_statistics": dict(overall_stats) if overall_stats else {},
                "result_type_distribution": [dict(row) for row in result_type_stats],
                "time_series": [dict(row) for row in time_series_stats],
                "quality_distribution": [dict(row) for row in quality_distribution],
                "time_period": time_period,
                "group_by": group_by,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")


@router.get("/instances/{instance_id}/summary", summary="获取特定实例的输出摘要")
async def get_instance_output_summary(
    instance_id: uuid.UUID,
    regenerate: bool = Query(False, description="是否重新生成摘要"),
    current_user: User = Depends(get_current_user)
):
    """获取特定实例的输出摘要"""
    try:
        workflow_repo = WorkflowInstanceRepository()
        output_processor = OutputDataProcessor()
        
        # 获取工作流实例
        instance = await workflow_repo.get_instance_by_id(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="工作流实例不存在")
        
        # 检查权限（可选：验证用户是否有权限查看此实例）
        # if instance['executor_id'] != current_user.user_id and not current_user.is_admin:
        #     raise HTTPException(status_code=403, detail="无权访问此实例")
        
        # 如果需要重新生成或摘要不存在，则生成新摘要
        if regenerate or not instance.get('output_summary'):
            output_summary = await output_processor.generate_workflow_output_summary(instance_id)
            if output_summary:
                # 更新数据库
                await output_processor.update_workflow_output_summary(instance_id)
                # 重新获取实例数据
                instance = await workflow_repo.get_instance_by_id(instance_id)
        
        return {
            "success": True,
            "data": {
                "instance_id": instance_id,
                "instance_name": instance.get('instance_name'),
                "workflow_name": instance.get('workflow_name'),
                "status": instance.get('status'),
                "output_summary": instance.get('output_summary'),
                "execution_summary": instance.get('execution_summary'),
                "quality_metrics": instance.get('quality_metrics'),
                "data_lineage": instance.get('data_lineage'),
                "created_at": instance.get('created_at'),
                "completed_at": instance.get('completed_at')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实例输出摘要失败: {str(e)}")


@router.post("/validate", summary="验证工作流输出数据")
async def validate_workflow_outputs(
    request: OutputValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """验证工作流输出数据"""
    try:
        workflow_repo = WorkflowInstanceRepository()
        validator = OutputDataValidator()
        
        validation_results = []
        
        for instance_id in request.instance_ids:
            # 获取实例数据
            instance = await workflow_repo.get_instance_by_id(instance_id)
            if not instance:
                validation_results.append({
                    "instance_id": instance_id,
                    "error": "实例不存在"
                })
                continue
            
            # 执行验证
            if request.validation_level == "basic":
                # 基础验证：只验证实例输出
                result = await validator.validate_workflow_instance_output(instance)
            else:
                # 标准/严格验证：验证完整的输出摘要
                if instance.get('output_summary'):
                    result = await validator.validate_workflow_output_summary(instance['output_summary'])
                else:
                    result = await validator.validate_workflow_instance_output(instance)
            
            validation_results.append({
                "instance_id": instance_id,
                "instance_name": instance.get('instance_name'),
                "validation_result": result.to_dict()
            })
        
        # 生成验证摘要
        validation_summary = await validator.get_validation_summary([
            result_item["validation_result"] for result_item in validation_results 
            if "validation_result" in result_item
        ])
        
        return {
            "success": True,
            "data": {
                "validation_results": validation_results,
                "validation_summary": validation_summary,
                "validation_level": request.validation_level,
                "total_instances": len(request.instance_ids)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证工作流输出失败: {str(e)}")


@router.get("/quality-report", summary="获取质量报告")
async def get_quality_report(
    workflow_base_id: Optional[str] = Query(None, description="特定工作流基础ID"),
    time_period: str = Query("30d", description="时间周期: 7d, 30d, 90d"),
    current_user: User = Depends(get_current_user)
):
    """获取工作流输出质量报告"""
    try:
        workflow_repo = WorkflowInstanceRepository()
        
        # 计算时间范围
        time_ranges = {"7d": 7, "30d": 30, "90d": 90}
        if time_period not in time_ranges:
            raise HTTPException(status_code=400, detail="无效的时间周期")
        
        days = time_ranges[time_period]
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 构建查询条件
        conditions = ["wi.is_deleted = FALSE", "wi.created_at >= $1", "wi.quality_metrics IS NOT NULL"]
        params = [start_date]
        
        if workflow_base_id:
            conditions.append("wi.workflow_base_id = $2")
            params.append(uuid.UUID(workflow_base_id))
        
        where_clause = " AND ".join(conditions)
        
        # 质量指标统计
        quality_stats_query = f"""
        SELECT 
            COUNT(*) as total_instances,
            AVG(CAST(wi.quality_metrics->>'data_completeness' AS FLOAT)) as avg_data_completeness,
            AVG(CAST(wi.quality_metrics->>'accuracy_score' AS FLOAT)) as avg_accuracy_score,
            AVG(CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT)) as avg_overall_quality,
            COUNT(CASE WHEN CAST(wi.quality_metrics->>'quality_gates_passed' AS BOOLEAN) = true THEN 1 END) as passed_quality_gates,
            COUNT(CASE WHEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) >= 0.9 THEN 1 END) as excellent_quality,
            COUNT(CASE WHEN CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) >= 0.7 THEN 1 END) as good_quality
        FROM workflow_instance wi
        WHERE {where_clause}
        """
        
        quality_stats = await workflow_repo.db.fetch_one(quality_stats_query, *params)
        
        # 质量趋势
        quality_trend_query = f"""
        SELECT 
            DATE_TRUNC('day', wi.created_at) as date,
            AVG(CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT)) as avg_quality_score,
            COUNT(*) as instance_count
        FROM workflow_instance wi
        WHERE {where_clause}
        GROUP BY DATE_TRUNC('day', wi.created_at)
        ORDER BY date
        """
        
        quality_trend = await workflow_repo.db.fetch_all(quality_trend_query, *params)
        
        # 问题统计
        issues_query = f"""
        SELECT 
            wi.instance_id,
            wi.instance_name,
            wi.quality_metrics->>'validation_errors' as validation_errors,
            CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) as quality_score
        FROM workflow_instance wi
        WHERE {where_clause}
        AND (
            CAST(wi.quality_metrics->>'overall_quality_score' AS FLOAT) < 0.7
            OR CAST(wi.quality_metrics->>'quality_gates_passed' AS BOOLEAN) = false
        )
        ORDER BY quality_score ASC
        LIMIT 10
        """
        
        problem_instances = await workflow_repo.db.fetch_all(issues_query, *params)
        
        # 计算质量评级
        total = quality_stats['total_instances'] if quality_stats else 0
        if total > 0:
            quality_gate_rate = quality_stats['passed_quality_gates'] / total
            excellent_rate = quality_stats['excellent_quality'] / total
            good_rate = quality_stats['good_quality'] / total
        else:
            quality_gate_rate = excellent_rate = good_rate = 0
        
        return {
            "success": True,
            "data": {
                "quality_statistics": dict(quality_stats) if quality_stats else {},
                "quality_rates": {
                    "quality_gate_pass_rate": quality_gate_rate,
                    "excellent_rate": excellent_rate,
                    "good_rate": good_rate
                },
                "quality_trend": [dict(row) for row in quality_trend],
                "problem_instances": [dict(row) for row in problem_instances],
                "time_period": time_period,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取质量报告失败: {str(e)}")


@router.post("/regenerate-summary/{instance_id}", summary="重新生成输出摘要")
async def regenerate_output_summary(
    instance_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """重新生成特定实例的输出摘要"""
    try:
        workflow_repo = WorkflowInstanceRepository()
        output_processor = OutputDataProcessor()
        
        # 检查实例是否存在
        instance = await workflow_repo.get_instance_by_id(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="工作流实例不存在")
        
        # 重新生成输出摘要
        success = await output_processor.update_workflow_output_summary(instance_id)
        
        if success:
            # 获取更新后的实例数据
            updated_instance = await workflow_repo.get_instance_by_id(instance_id)
            
            return {
                "success": True,
                "data": {
                    "instance_id": instance_id,
                    "message": "输出摘要重新生成成功",
                    "output_summary": updated_instance.get('output_summary'),
                    "regenerated_at": datetime.utcnow().isoformat()
                }
            }
        else:
            raise HTTPException(status_code=500, detail="重新生成输出摘要失败")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新生成输出摘要失败: {str(e)}")


# ==================== 辅助函数 ====================

def format_duration(minutes: Optional[float]) -> str:
    """格式化执行时长"""
    if minutes is None:
        return "未知"
    
    if minutes < 1:
        return f"{int(minutes * 60)}秒"
    elif minutes < 60:
        return f"{int(minutes)}分钟"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours}小时{mins}分钟"


def calculate_success_rate(success_count: int, total_count: int) -> float:
    """计算成功率"""
    if total_count == 0:
        return 0.0
    return success_count / total_count