"""
工作流Tab补全API
提供智能节点和连接建议的API端点
"""

import json
import re
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from loguru import logger

from ..services.workflow_tab_prediction import tab_prediction_service
from ..services.user_interaction_tracker import interaction_tracker, InteractionEventType, SuggestionType
from ..utils.middleware import get_current_user_context, CurrentUser

router = APIRouter(prefix="/api/tab-completion", tags=["tab-completion"])


# ==================== 请求/响应模型 ====================

class NodePredictionRequest(BaseModel):
    """节点预测请求"""
    context_summary: str = Field(..., description="工作流上下文摘要")
    max_suggestions: int = Field(3, description="最大建议数量", ge=1, le=5)
    trigger_type: str = Field("empty_space_click", description="触发类型")
    cursor_position: Dict[str, float] = Field(default={"x": 0, "y": 0}, description="光标位置")


class ConnectionPredictionRequest(BaseModel):
    """连接预测请求"""
    context_summary: str = Field(..., description="工作流上下文摘要")
    source_node_id: str = Field(..., description="源节点ID")
    max_suggestions: int = Field(3, description="最大建议数量", ge=1, le=5)


class WorkflowCompletionRequest(BaseModel):
    """工作流完整性预测请求"""
    context_summary: str = Field(..., description="当前工作流状态")
    partial_description: str = Field(..., description="部分任务描述")


class PredictionResponse(BaseModel):
    """预测响应基类"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    suggestions: List[Dict[str, Any]] = Field(..., description="建议列表")
    context_analysis: Dict[str, Any] = Field(default={}, description="上下文分析结果")


class InteractionTrackingRequest(BaseModel):
    """交互跟踪请求"""
    workflow_id: str = Field(..., description="工作流ID")
    session_id: str = Field(..., description="会话ID")
    event_type: str = Field(..., description="事件类型")
    suggestion_type: Optional[str] = Field(None, description="建议类型")
    event_data: Optional[Dict[str, Any]] = Field(default={}, description="事件数据")
    context_summary: Optional[str] = Field(None, description="上下文摘要")


class BatchInteractionTrackingRequest(BaseModel):
    """批量交互跟踪请求"""
    interactions: List[InteractionTrackingRequest] = Field(..., description="交互事件列表")


class UserSatisfactionRequest(BaseModel):
    """用户满意度请求"""
    interaction_id: str = Field(..., description="交互记录ID")
    satisfaction: str = Field(..., description="满意度级别")


# ==================== API端点 ====================

@router.post("/predict-nodes", response_model=PredictionResponse)
async def predict_next_nodes(
    request: NodePredictionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """预测下一个可能的节点"""
    try:
        logger.info(f"🔮 [API] 收到节点预测请求")
        logger.info(f"🔮 [API] 用户: {current_user.user_id}")
        logger.info(f"🔮 [API] 触发类型: {request.trigger_type}")
        logger.info(f"🔮 [API] 上下文长度: {len(request.context_summary)}")

        # 调用预测服务
        suggestions = await tab_prediction_service.predict_next_nodes(
            context_summary=request.context_summary,
            max_suggestions=request.max_suggestions
        )

        # 分析上下文
        context_analysis = _analyze_prediction_context(request.context_summary)

        logger.info(f"🔮 [API] ✅ 节点预测完成，建议数量: {len(suggestions)}")

        return PredictionResponse(
            success=True,
            message=f"成功生成 {len(suggestions)} 个节点建议",
            suggestions=suggestions,
            context_analysis=context_analysis
        )

    except Exception as e:
        logger.error(f"🔮 [API] ❌ 节点预测失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"节点预测失败: {str(e)}"
        )


@router.post("/predict-connections", response_model=PredictionResponse)
async def predict_next_connections(
    request: ConnectionPredictionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """预测从指定节点出发的可能连接"""
    try:
        logger.info(f"🔮 [API] 收到连接预测请求")
        logger.info(f"🔮 [API] 用户: {current_user.user_id}")
        logger.info(f"🔮 [API] 源节点: {request.source_node_id}")

        # 调用预测服务
        suggestions = await tab_prediction_service.predict_next_connections(
            context_summary=request.context_summary,
            source_node_id=request.source_node_id,
            max_suggestions=request.max_suggestions
        )

        # 分析上下文
        context_analysis = _analyze_prediction_context(request.context_summary)

        logger.info(f"🔮 [API] ✅ 连接预测完成，建议数量: {len(suggestions)}")

        return PredictionResponse(
            success=True,
            message=f"成功生成 {len(suggestions)} 个连接建议",
            suggestions=suggestions,
            context_analysis=context_analysis
        )

    except Exception as e:
        logger.error(f"🔮 [API] ❌ 连接预测失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"连接预测失败: {str(e)}"
        )


@router.post("/predict-completion", response_model=PredictionResponse)
async def predict_workflow_completion(
    request: WorkflowCompletionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """预测工作流的完整结构"""
    try:
        logger.info(f"🔮 [API] 收到工作流完整性预测请求")
        logger.info(f"🔮 [API] 用户: {current_user.user_id}")

        # 调用预测服务
        suggestions = await tab_prediction_service.predict_workflow_completion(
            context_summary=request.context_summary,
            partial_description=request.partial_description
        )

        # 分析上下文
        context_analysis = _analyze_prediction_context(request.context_summary)

        logger.info(f"🔮 [API] ✅ 工作流完整性预测完成")

        return PredictionResponse(
            success=True,
            message="工作流完整性分析完成",
            suggestions=suggestions,
            context_analysis=context_analysis
        )

    except Exception as e:
        logger.error(f"🔮 [API] ❌ 工作流完整性预测失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"工作流完整性预测失败: {str(e)}"
        )


@router.post("/track-interaction")
async def track_user_interaction(
    request: InteractionTrackingRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """跟踪用户交互事件"""
    try:
        logger.info(f"🔍 [API] 收到交互跟踪请求")
        logger.info(f"🔍 [API] 用户: {current_user.user_id}")
        logger.info(f"🔍 [API] 事件类型: {request.event_type}")
        logger.info(f"🔍 [API] 工作流: {request.workflow_id}")

        # 转换事件类型
        try:
            event_type = InteractionEventType(request.event_type)
        except ValueError:
            logger.warning(f"🔍 [API] 未知事件类型: {request.event_type}")
            event_type = InteractionEventType.TRIGGER_ACTIVATED

        # 转换建议类型
        suggestion_type = None
        if request.suggestion_type:
            try:
                suggestion_type = SuggestionType(request.suggestion_type)
            except ValueError:
                logger.warning(f"🔍 [API] 未知建议类型: {request.suggestion_type}")

        # 记录交互
        interaction_id = await interaction_tracker.track_interaction(
            user_id=current_user.user_id,
            workflow_id=request.workflow_id,
            event_type=event_type,
            suggestion_type=suggestion_type,
            suggestion_data=request.event_data,
            context_data={'context_summary': request.context_summary} if request.context_summary else None,
            session_id=request.session_id
        )

        logger.info(f"🔍 [API] ✅ 交互跟踪完成: {interaction_id}")

        return {
            "success": True,
            "interaction_id": interaction_id,
            "message": "交互事件已记录"
        }

    except Exception as e:
        logger.error(f"🔍 [API] ❌ 交互跟踪失败: {str(e)}")
        # 交互跟踪失败不应阻塞主要功能
        return {
            "success": False,
            "message": f"交互跟踪失败: {str(e)}"
        }


@router.get("/user-behavior-analysis")
async def get_user_behavior_analysis(
    days_back: int = 30,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取用户行为分析"""
    try:
        logger.info(f"🔍 [API] 收到用户行为分析请求")
        logger.info(f"🔍 [API] 用户: {current_user.user_id}")
        logger.info(f"🔍 [API] 分析天数: {days_back}")

        # 获取用户行为模式
        behavior_patterns = await interaction_tracker.get_user_behavior_patterns(
            user_id=current_user.user_id,
            days_back=days_back
        )

        logger.info(f"🔍 [API] ✅ 用户行为分析完成")

        return {
            "success": True,
            "behavior_patterns": behavior_patterns,
            "message": "用户行为分析完成"
        }

    except Exception as e:
        logger.error(f"🔍 [API] ❌ 用户行为分析失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"用户行为分析失败: {str(e)}"
        )


@router.get("/global-statistics")
async def get_global_statistics(
    days_back: int = 7,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取全局统计信息"""
    try:
        logger.info(f"🔍 [API] 收到全局统计请求")
        logger.info(f"🔍 [API] 分析天数: {days_back}")

        # 获取全局统计
        global_stats = await interaction_tracker.get_global_statistics(days_back=days_back)

        logger.info(f"🔍 [API] ✅ 全局统计完成")

        return {
            "success": True,
            "global_statistics": global_stats,
            "message": "全局统计完成"
        }

    except Exception as e:
        logger.error(f"🔍 [API] ❌ 全局统计失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"全局统计失败: {str(e)}"
        )


@router.post("/clear-cache")
async def clear_prediction_cache(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """清空预测缓存"""
    try:
        tab_prediction_service.clear_cache()
        logger.info(f"🔮 [API] 用户 {current_user.user_id} 清空了预测缓存")

        return {
            "success": True,
            "message": "预测缓存已清空"
        }
    except Exception as e:
        logger.error(f"🔮 [API] 清空缓存失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"清空缓存失败: {str(e)}"
        )


# ==================== 辅助函数 ====================

def _analyze_prediction_context(context_summary: str) -> Dict[str, Any]:
    """分析预测上下文，提供额外的分析信息"""
    try:
        import json
        context_data = json.loads(context_summary)

        return {
            "workflow_completeness": _calculate_completeness(context_data),
            "suggested_priority": _determine_priority(context_data),
            "complexity_score": _calculate_complexity(context_data),
            "pattern_match": _identify_patterns(context_data)
        }
    except:
        return {
            "workflow_completeness": "unknown",
            "suggested_priority": "medium",
            "complexity_score": 0.5,
            "pattern_match": "none"
        }


def _calculate_completeness(context_data: Dict[str, Any]) -> str:
    """计算工作流完整性"""
    node_count = context_data.get("nodeCount", 0)
    has_start = context_data.get("hasStart", False)
    has_end = context_data.get("hasEnd", False)

    if node_count == 0:
        return "empty"
    elif not has_start:
        return "missing_start"
    elif node_count == 1 and has_start:
        return "needs_processing"
    elif not has_end:
        return "missing_end"
    else:
        return "complete"


def _determine_priority(context_data: Dict[str, Any]) -> str:
    """确定建议优先级"""
    completeness = _calculate_completeness(context_data)

    if completeness in ["empty", "missing_start"]:
        return "high"
    elif completeness in ["needs_processing", "missing_end"]:
        return "medium"
    else:
        return "low"


def _calculate_complexity(context_data: Dict[str, Any]) -> float:
    """计算工作流复杂度分数"""
    node_count = context_data.get("nodeCount", 0)
    edge_count = context_data.get("edgeCount", 0)

    if node_count == 0:
        return 0.0

    # 基于节点数量和连接密度计算复杂度
    connection_density = edge_count / node_count if node_count > 0 else 0
    complexity = min(1.0, (node_count * 0.1) + (connection_density * 0.3))

    return round(complexity, 2)


def _identify_patterns(context_data: Dict[str, Any]) -> str:
    """识别工作流模式"""
    node_count = context_data.get("nodeCount", 0)
    processor_count = context_data.get("processorCount", 0)

    if node_count <= 2:
        return "simple_linear"
    elif processor_count == 1:
        return "single_step"
    elif processor_count > 3:
        return "multi_step"
    else:
        return "standard"


# ========== 新增：统一的图操作建议系统 ==========

# 图操作类型
class GraphOperationType:
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    UPDATE_NODE = "update_node"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    UPDATE_EDGE = "update_edge"

# 图操作定义
class GraphOperation(BaseModel):
    id: str
    type: str  # GraphOperationType
    data: Dict[str, Any]
    reasoning: str

# 图建议
class GraphSuggestion(BaseModel):
    id: str
    name: str
    description: str
    operations: List[GraphOperation]
    confidence: float
    reasoning: str
    preview: Optional[Dict[str, Any]] = None

# 工作流上下文
class WorkflowContext(BaseModel):
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    workflow_description: Optional[str] = None

    current_nodes: List[Dict[str, Any]] = []
    current_edges: List[Dict[str, Any]] = []

    cursor_position: Optional[Dict[str, float]] = None
    selected_node_id: Optional[str] = None
    recent_actions: Optional[List[Dict[str, Any]]] = []

    completion_status: Dict[str, Any] = {}

# 请求模型
class GraphSuggestionRequest(BaseModel):
    workflow_context: WorkflowContext
    trigger_type: str  # 'canvas_click', 'node_select', 'manual_request'
    max_suggestions: int = 3

# 响应模型
class GraphSuggestionResponse(BaseModel):
    success: bool
    suggestions: List[GraphSuggestion] = []
    context_analysis: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# 操作执行跟踪
class OperationExecutionTrack(BaseModel):
    suggestion_id: str
    operations: List[GraphOperation]
    success: bool
    executed_at: str

@router.post("/predict-graph-operations", response_model=GraphSuggestionResponse)
async def predict_graph_operations(
    request: GraphSuggestionRequest,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取图操作建议（幽灵编辑模式）"""
    try:
        logger.info(f"🔮 [GRAPH-API] 收到图操作建议请求")
        logger.info(f"🔮 [GRAPH-API] 用户: {current_user.user_id}")
        logger.info(f"🔮 [GRAPH-API] 触发类型: {request.trigger_type}")
        logger.info(f"🔮 [GRAPH-API] 工作流: {request.workflow_context.workflow_id}")

        # 分析当前工作流状态
        context = request.workflow_context
        analysis = analyze_workflow_context(context)

        # 构建给LLM的prompt
        prompt = build_graph_operations_prompt(context, analysis, request.trigger_type)

        # 获取Function Calling schema
        functions = [get_graph_operations_function_schema()]

        # 使用Function Calling调用AI服务
        ai_result = await tab_prediction_service.ai_generator._call_real_api_with_functions(
            prompt,
            functions,
            function_call="generate_graph_operations"
        )

        # 处理响应
        if ai_result['type'] == 'function_call':
            # 解析Function Call结果
            suggestions = parse_function_call_response(ai_result['function_call'], context)
        else:
            # DeepSeek不支持Function Calling，使用改进的文本解析
            logger.info("🔮 [GRAPH-API] 使用文本解析模式")
            logger.debug(f"🔮 [GRAPH-API] AI原始响应: {ai_result['content'][:1000]}...")
            suggestions = parse_ai_graph_suggestions_improved(ai_result['content'], context)

        logger.info(f"🔮 [GRAPH-API] ✅ 生成了 {len(suggestions)} 个图操作建议")

        return GraphSuggestionResponse(
            success=True,
            suggestions=suggestions,
            context_analysis=analysis,
            message="图操作建议生成成功"
        )

    except Exception as e:
        logger.error(f"🔮 [GRAPH-API] ❌ 图操作建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"图操作建议失败: {str(e)}")

@router.post("/track-operation-execution")
async def track_operation_execution(
    request: OperationExecutionTrack,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """跟踪图操作执行结果"""
    try:
        logger.info(f"🔮 [TRACK] 收到操作执行跟踪")
        logger.info(f"🔮 [TRACK] 建议ID: {request.suggestion_id}")
        logger.info(f"🔮 [TRACK] 操作数量: {len(request.operations)}")
        logger.info(f"🔮 [TRACK] 执行结果: {request.success}")

        # 记录到用户交互跟踪器
        await interaction_tracker.track_interaction(
            user_id=current_user.user_id,
            workflow_id=request.suggestion_id,  # 暂时用建议ID作为工作流ID
            event_type=InteractionEventType.SUGGESTION_ACCEPTED if request.success else InteractionEventType.SUGGESTION_REJECTED,
            suggestion_type=SuggestionType.WORKFLOW_COMPLETION,
            suggestion_data={
                'suggestion_id': request.suggestion_id,
                'operations_count': len(request.operations),
                'success': request.success,
                'executed_at': request.executed_at
            }
        )

        return {
            "success": True,
            "message": "操作执行跟踪完成"
        }

    except Exception as e:
        logger.error(f"🔮 [TRACK] ❌ 操作执行跟踪失败: {str(e)}")
        return {
            "success": False,
            "message": f"跟踪失败: {str(e)}"
        }

def analyze_workflow_context(context: WorkflowContext) -> Dict[str, Any]:
    """分析工作流上下文"""
    nodes = context.current_nodes
    edges = context.current_edges

    has_start = any(n.get('type') == 'start' for n in nodes)
    has_end = any(n.get('type') == 'end' for n in nodes)
    node_count = len(nodes)
    edge_count = len(edges)

    # 计算完整度
    completeness = 0
    if has_start:
        completeness += 0.3
    if has_end:
        completeness += 0.3
    if node_count > 2:
        completeness += 0.2
    if edge_count >= max(0, node_count - 1):
        completeness += 0.2

    completeness = min(completeness, 1.0)

    # 识别缺失组件
    missing_components = []
    if not has_start:
        missing_components.append("开始节点")
    if not has_end:
        missing_components.append("结束节点")
    if node_count < 2:
        missing_components.append("处理节点")
    if edge_count == 0 and node_count > 1:
        missing_components.append("节点连接")

    # 建议下一步
    suggested_steps = []
    if not has_start and node_count == 0:
        suggested_steps.append("创建开始节点")
    elif has_start and not any(n.get('type') == 'processor' for n in nodes):
        suggested_steps.append("添加处理节点")
    elif node_count > 1 and edge_count == 0:
        suggested_steps.append("连接节点")
    elif has_start and node_count > 1 and not has_end:
        suggested_steps.append("添加结束节点")
    else:
        suggested_steps.append("优化工作流结构")

    return {
        "workflow_completeness": completeness,
        "missing_components": missing_components,
        "suggested_next_steps": suggested_steps,
        "node_types_distribution": {
            "start": sum(1 for n in nodes if n.get('type') == 'start'),
            "processor": sum(1 for n in nodes if n.get('type') == 'processor'),
            "end": sum(1 for n in nodes if n.get('type') == 'end')
        },
        "connectivity_analysis": {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "is_connected": edge_count >= node_count - 1 if node_count > 0 else True
        }
    }

def build_graph_operations_prompt(
    context: WorkflowContext,
    analysis: Dict[str, Any],
    trigger_type: str
) -> str:
    """构建给LLM的图操作建议prompt"""

    # 基础信息
    workflow_info = ""
    if context.workflow_name:
        workflow_info += f"工作流名称: {context.workflow_name}\n"
    if context.workflow_description:
        workflow_info += f"工作流描述: {context.workflow_description}\n"

    # 当前状态
    current_state = f"""当前工作流状态:
- 节点数量: {len(context.current_nodes)}
- 连接数量: {len(context.current_edges)}
- 完整度: {analysis['workflow_completeness']:.1%}
- 缺失组件: {', '.join(analysis['missing_components']) if analysis['missing_components'] else '无'}

当前节点信息:
"""

    for i, node in enumerate(context.current_nodes):
        current_state += f"- 节点{i+1}: {node.get('name', '未命名')} ({node.get('type', 'processor')})\n"

    # 触发上下文
    trigger_context = f"触发方式: {trigger_type}\n"
    if context.cursor_position:
        trigger_context += f"光标位置: ({context.cursor_position['x']:.0f}, {context.cursor_position['y']:.0f})\n"
    if context.selected_node_id:
        trigger_context += f"选中节点: {context.selected_node_id}\n"

    prompt = f"""你是一个工作流设计助手。用户正在设计工作流，请根据当前状态生成最合适的图操作建议。

{workflow_info}

{current_state}

{trigger_context}

请生成一个图操作序列建议，以JSON格式返回:

{{
  "suggestions": [
    {{
      "id": "suggestion_1",
      "name": "建议名称（如：添加数据处理流程）",
      "description": "详细描述这个建议的作用和价值",
      "operations": [
        {{
          "id": "op_1",
          "type": "add_node",
          "data": {{
            "node": {{
              "id": "temp_node_1",
              "name": "节点名称",
              "type": "start|processor|end",
              "task_description": "节点功能描述",
              "position": {{"x": 100, "y": 200}},
              "processor_id": null
            }}
          }},
          "reasoning": "添加此节点的理由"
        }},
        {{
          "id": "op_2",
          "type": "add_edge",
          "data": {{
            "edge": {{
              "source_node_id": "temp_node_1",
              "target_node_id": "existing_node_id",
              "connection_type": "normal",
              "condition_config": null
            }}
          }},
          "reasoning": "添加此连接的理由"
        }}
      ],
      "confidence": 0.85,
      "reasoning": "整体建议的推理过程",
      "preview": {{
        "nodes_to_add": 1,
        "edges_to_add": 1,
        "estimated_completion_improvement": 0.3
      }}
    }}
  ]
}}

要求:
1. 根据工作流完整度和缺失组件，优先建议最需要的操作
2. 操作序列要逻辑连贯，先创建节点再创建连接
3. 节点位置要合理，避免重叠
4. confidence表示整体建议的置信度(0-1)
5. 每个操作都要有清晰的reasoning
6. 确保返回有效的JSON格式
7. 建议要实用且符合工作流设计最佳实践

请生成最多1个最佳建议（幽灵编辑模式）："""

    return prompt


def get_graph_operations_function_schema():
    """获取图操作的Function Calling schema"""
    return {
        "name": "generate_graph_operations",
        "description": "生成工作流图的操作序列，包括添加节点、连接节点、修改节点等操作",
        "parameters": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "description": "图操作建议列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "建议的唯一ID"
                            },
                            "name": {
                                "type": "string",
                                "description": "建议的名称"
                            },
                            "description": {
                                "type": "string",
                                "description": "建议的详细描述"
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": "建议的置信度(0-1)"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "建议的理由和解释"
                            },
                            "operations": {
                                "type": "array",
                                "description": "具体的图操作列表",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "description": "操作的唯一ID"
                                        },
                                        "type": {
                                            "type": "string",
                                            "enum": ["add_node", "add_edge", "update_node", "delete_node", "delete_edge"],
                                            "description": "操作类型"
                                        },
                                        "reasoning": {
                                            "type": "string",
                                            "description": "该操作的理由"
                                        },
                                        "data": {
                                            "type": "object",
                                            "description": "操作的具体数据",
                                            "properties": {
                                                "node": {
                                                    "type": "object",
                                                    "description": "节点数据",
                                                    "properties": {
                                                        "id": {"type": "string"},
                                                        "type": {"type": "string", "enum": ["start", "processor", "end"]},
                                                        "name": {"type": "string"},
                                                        "description": {"type": "string"},
                                                        "processor_type": {"type": "string", "enum": ["human", "agent"]},
                                                        "position": {
                                                            "type": "object",
                                                            "properties": {
                                                                "x": {"type": "number"},
                                                                "y": {"type": "number"}
                                                            }
                                                        }
                                                    }
                                                },
                                                "edge": {
                                                    "type": "object",
                                                    "description": "边数据",
                                                    "properties": {
                                                        "id": {"type": "string"},
                                                        "source": {"type": "string"},
                                                        "target": {"type": "string"},
                                                        "type": {"type": "string", "enum": ["normal", "conditional"]},
                                                        "label": {"type": "string"}
                                                    }
                                                },
                                                "updates": {
                                                    "type": "object",
                                                    "description": "更新数据"
                                                }
                                            }
                                        }
                                    },
                                    "required": ["id", "type", "data", "reasoning"]
                                }
                            }
                        },
                        "required": ["id", "name", "description", "operations", "confidence", "reasoning"]
                    }
                }
            },
            "required": ["suggestions"]
        }
    }


def parse_function_call_response(function_call: dict, context: WorkflowContext) -> List[GraphSuggestion]:
    """解析Function Calling响应为图建议对象"""
    try:
        import json
        arguments = json.loads(function_call['arguments'])
        suggestions = []

        for suggestion_data in arguments.get('suggestions', []):
            # 转换操作
            operations = []
            for op_data in suggestion_data.get('operations', []):
                operation = GraphOperation(
                    id=op_data.get('id', str(uuid.uuid4())),
                    type=op_data.get('type', 'add_node'),
                    data=op_data.get('data', {}),
                    reasoning=op_data.get('reasoning', '无说明')
                )
                operations.append(operation)

            # 创建建议对象
            suggestion = GraphSuggestion(
                id=suggestion_data.get('id', str(uuid.uuid4())),
                name=suggestion_data.get('name', '未命名建议'),
                description=suggestion_data.get('description', ''),
                operations=operations,
                confidence=suggestion_data.get('confidence', 0.5),
                reasoning=suggestion_data.get('reasoning', ''),
                preview=None
            )
            suggestions.append(suggestion)

        logger.info(f"🤖 [FUNCTION-PARSE] ✅ 解析了 {len(suggestions)} 个建议")
        return suggestions

    except Exception as e:
        logger.error(f"🤖 [FUNCTION-PARSE] ❌ Function Call响应解析失败: {str(e)}")
        return []


def parse_ai_graph_suggestions_improved(ai_response: str, context: WorkflowContext) -> List[GraphSuggestion]:
    """改进的AI图建议解析，支持多种格式"""
    try:
        logger.info(f"🔮 [PARSE-IMPROVED] 开始解析AI响应，长度: {len(ai_response)}")

        # 方法1：尝试标准JSON解析
        json_suggestions = _try_standard_json_parse(ai_response, context)
        if json_suggestions:
            logger.info(f"🔮 [PARSE-IMPROVED] JSON解析成功，建议数: {len(json_suggestions)}")
            return json_suggestions

        # 方法2：尝试智能模式解析（从AI自然语言中提取结构）
        intelligent_suggestions = _try_intelligent_parse(ai_response, context)
        if intelligent_suggestions:
            logger.info(f"🔮 [PARSE-IMPROVED] 智能解析成功，建议数: {len(intelligent_suggestions)}")
            return intelligent_suggestions

        # 方法3：基于关键词的最简解析
        keyword_suggestions = _try_keyword_parse(ai_response, context)
        if keyword_suggestions:
            logger.info(f"🔮 [PARSE-IMPROVED] 关键词解析成功，建议数: {len(keyword_suggestions)}")
            return keyword_suggestions

        logger.warning("🔮 [PARSE-IMPROVED] 所有解析方法都失败了")
        return []

    except Exception as e:
        logger.error(f"🔮 [PARSE-IMPROVED] ❌ 改进解析失败: {str(e)}")
        return []


def _try_standard_json_parse(ai_response: str, context: WorkflowContext) -> List[GraphSuggestion]:
    """尝试标准JSON解析"""
    try:
        # 使用原有的JSON清理逻辑
        json_content = _extract_and_clean_json(ai_response)
        if not json_content:
            return []

        parsed_data = json.loads(json_content)
        return _convert_parsed_data_to_suggestions(parsed_data, context)

    except Exception as e:
        logger.debug(f"🔮 [JSON-PARSE] 标准JSON解析失败: {str(e)}")
        return []


def _try_intelligent_parse(ai_response: str, context: WorkflowContext) -> List[GraphSuggestion]:
    """智能解析：从AI的自然语言中提取结构化信息"""
    try:
        # 分析AI回复中的关键信息
        lines = ai_response.split('\n')
        suggestions = []
        current_suggestion = None
        current_operations = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测建议开始
            if '建议' in line or 'suggestion' in line.lower() or '推荐' in line:
                if current_suggestion and current_operations:
                    # 保存上一个建议
                    current_suggestion['operations'] = current_operations
                    suggestions.append(_create_suggestion_from_dict(current_suggestion, context))

                current_suggestion = {
                    'id': f'suggestion_{len(suggestions) + 1}',
                    'name': line,
                    'description': line,
                    'confidence': 0.8,
                    'reasoning': '基于AI分析'
                }
                current_operations = []

            # 检测操作
            elif '添加' in line or 'add' in line.lower() or '创建' in line:
                operation = _parse_operation_from_text(line, 'add_node')
                if operation:
                    current_operations.append(operation)

            elif '连接' in line or 'connect' in line.lower() or '链接' in line:
                operation = _parse_operation_from_text(line, 'add_edge')
                if operation:
                    current_operations.append(operation)

        # 保存最后一个建议
        if current_suggestion and current_operations:
            current_suggestion['operations'] = current_operations
            suggestions.append(_create_suggestion_from_dict(current_suggestion, context))

        return suggestions

    except Exception as e:
        logger.debug(f"🔮 [INTELLIGENT-PARSE] 智能解析失败: {str(e)}")
        return []


def _try_keyword_parse(ai_response: str, context: WorkflowContext) -> List[GraphSuggestion]:
    """基于关键词的最简解析"""
    try:
        # 如果工作流为空，生成一个开始节点的建议
        if not context.nodes:
            return [_create_default_start_suggestion()]

        # 根据现有节点生成简单的扩展建议
        if len(context.nodes) == 1:
            # 只有一个节点时，建议添加处理节点并连接
            existing_node = context.nodes[0]
            return [_create_processor_with_connection_suggestion(existing_node)]

        # 如果有多个节点但没有结束节点，建议添加结束节点
        has_end = any(node.get('type') == 'end' for node in context.nodes)
        if not has_end and len(context.nodes) >= 2:
            # 找到最后一个处理节点
            last_processor = None
            for node in reversed(context.nodes):
                if node.get('type') == 'processor':
                    last_processor = node
                    break

            if last_processor:
                return [_create_end_with_connection_suggestion(last_processor)]

        # 默认：添加一个新的处理节点
        return [_create_default_processor_suggestion()]

    except Exception as e:
        logger.debug(f"🔮 [KEYWORD-PARSE] 关键词解析失败: {str(e)}")
        return []


def _create_processor_with_connection_suggestion(existing_node: dict) -> GraphSuggestion:
    """创建处理节点并连接到现有节点"""
    processor_id = f'processor_{uuid.uuid4().hex[:8]}'

    return GraphSuggestion(
        id='connect_processor',
        name='添加处理节点并连接',
        description=f'添加新的处理节点并连接到"{existing_node.get("name", "现有节点")}"',
        operations=[
            # 先添加节点
            GraphOperation(
                id='op_add_processor',
                type='add_node',
                data={
                    'node': {
                        'id': processor_id,
                        'type': 'processor',
                        'name': '处理任务',
                        'description': '执行具体的处理任务',
                        'processor_type': 'human',
                        'position': {'x': 400, 'y': 200}
                    }
                },
                reasoning='添加新的处理节点'
            ),
            # 再添加连接
            GraphOperation(
                id='op_add_connection',
                type='add_edge',
                data={
                    'edge': {
                        'id': f'edge_{uuid.uuid4().hex[:8]}',
                        'source_node_id': existing_node.get('node_base_id', existing_node.get('id')),
                        'target_node_id': processor_id,
                        'connection_type': 'normal',
                        'condition_config': None,
                        'label': '连接'
                    }
                },
                reasoning='连接现有节点到新节点'
            )
        ],
        confidence=0.8,
        reasoning='扩展工作流处理能力',
        preview=None
    )


def _create_end_with_connection_suggestion(last_processor: dict) -> GraphSuggestion:
    """创建结束节点并连接到最后的处理节点"""
    end_id = f'end_{uuid.uuid4().hex[:8]}'

    return GraphSuggestion(
        id='connect_end',
        name='添加结束节点',
        description=f'添加结束节点并连接到"{last_processor.get("name", "处理节点")}"',
        operations=[
            # 先添加结束节点
            GraphOperation(
                id='op_add_end',
                type='add_node',
                data={
                    'node': {
                        'id': end_id,
                        'type': 'end',
                        'name': '结束',
                        'description': '工作流结束节点',
                        'position': {'x': 600, 'y': 300}
                    }
                },
                reasoning='添加工作流结束节点'
            ),
            # 再添加连接
            GraphOperation(
                id='op_add_end_connection',
                type='add_edge',
                data={
                    'edge': {
                        'id': f'edge_{uuid.uuid4().hex[:8]}',
                        'source_node_id': last_processor.get('node_base_id', last_processor.get('id')),
                        'target_node_id': end_id,
                        'connection_type': 'normal',
                        'condition_config': None,
                        'label': '完成'
                    }
                },
                reasoning='连接处理节点到结束节点'
            )
        ],
        confidence=0.9,
        reasoning='完善工作流结构',
        preview=None
    )


def _parse_operation_from_text(text: str, operation_type: str) -> dict:
    """从文本中解析操作"""
    try:
        return {
            'id': f'op_{uuid.uuid4().hex[:8]}',
            'type': operation_type,
            'reasoning': text,
            'data': _extract_operation_data_from_text(text, operation_type)
        }
    except:
        return None


def _extract_operation_data_from_text(text: str, operation_type: str) -> dict:
    """从文本中提取操作数据"""
    if operation_type == 'add_node':
        # 简单的节点创建
        return {
            'node': {
                'id': f'node_{uuid.uuid4().hex[:8]}',
                'type': 'processor',
                'name': '处理节点',
                'description': text,
                'processor_type': 'human',
                'position': {'x': 200, 'y': 200}
            }
        }
    elif operation_type == 'add_edge':
        # 简单的连接创建 - 需要实际的节点ID
        return {
            'edge': {
                'id': f'edge_{uuid.uuid4().hex[:8]}',
                'source_node_id': 'requires_real_node_id',  # 需要在使用时替换为真实节点ID
                'target_node_id': 'requires_real_node_id',  # 需要在使用时替换为真实节点ID
                'connection_type': 'normal',
                'condition_config': None,
                'label': '连接'
            }
        }
    return {}


def _create_suggestion_from_dict(data: dict, context: WorkflowContext) -> GraphSuggestion:
    """从字典创建建议对象"""
    operations = []
    for op_data in data.get('operations', []):
        operations.append(GraphOperation(
            id=op_data.get('id', str(uuid.uuid4())),
            type=op_data.get('type', 'add_node'),
            data=op_data.get('data', {}),
            reasoning=op_data.get('reasoning', '无说明')
        ))

    return GraphSuggestion(
        id=data.get('id', str(uuid.uuid4())),
        name=data.get('name', '未命名建议'),
        description=data.get('description', ''),
        operations=operations,
        confidence=data.get('confidence', 0.5),
        reasoning=data.get('reasoning', ''),
        preview=None
    )


def _create_default_start_suggestion() -> GraphSuggestion:
    """创建默认的开始节点建议"""
    return GraphSuggestion(
        id='default_start',
        name='添加开始节点',
        description='为空白工作流添加开始节点',
        operations=[
            GraphOperation(
                id='op_start',
                type='add_node',
                data={
                    'node': {
                        'id': f'start_{uuid.uuid4().hex[:8]}',
                        'type': 'start',
                        'name': '开始',
                        'description': '工作流开始节点',
                        'position': {'x': 100, 'y': 100}
                    }
                },
                reasoning='空白工作流需要开始节点'
            )
        ],
        confidence=0.9,
        reasoning='空白工作流的基础结构需求',
        preview=None
    )


def _create_default_processor_suggestion() -> GraphSuggestion:
    """创建默认的处理节点建议"""
    return GraphSuggestion(
        id='default_processor',
        name='添加处理节点',
        description='添加一个处理节点来执行具体任务',
        operations=[
            GraphOperation(
                id='op_processor',
                type='add_node',
                data={
                    'node': {
                        'id': f'processor_{uuid.uuid4().hex[:8]}',
                        'type': 'processor',
                        'name': '处理任务',
                        'description': '执行具体的处理任务',
                        'processor_type': 'human',
                        'position': {'x': 300, 'y': 200}
                    }
                },
                reasoning='工作流需要处理节点来执行任务'
            )
        ],
        confidence=0.8,
        reasoning='工作流通常需要处理节点',
        preview=None
    )


def _create_default_end_suggestion() -> GraphSuggestion:
    """创建默认的结束节点建议"""
    return GraphSuggestion(
        id='default_end',
        name='添加结束节点',
        description='添加结束节点完成工作流',
        operations=[
            GraphOperation(
                id='op_end',
                type='add_node',
                data={
                    'node': {
                        'id': f'end_{uuid.uuid4().hex[:8]}',
                        'type': 'end',
                        'name': '结束',
                        'description': '工作流结束节点',
                        'position': {'x': 500, 'y': 300}
                    }
                },
                reasoning='工作流需要明确的结束节点'
            )
        ],
        confidence=0.7,
        reasoning='完善工作流结构',
        preview=None
    )


def _convert_parsed_data_to_suggestions(parsed_data: dict, context: WorkflowContext) -> List[GraphSuggestion]:
    """转换解析的数据为建议对象"""
    suggestions = []
    for suggestion_data in parsed_data.get('suggestions', []):
        operations = []
        for op_data in suggestion_data.get('operations', []):
            operation = GraphOperation(
                id=op_data.get('id', str(uuid.uuid4())),
                type=op_data.get('type', 'add_node'),
                data=op_data.get('data', {}),
                reasoning=op_data.get('reasoning', '无说明')
            )
            operations.append(operation)

        suggestion = GraphSuggestion(
            id=suggestion_data.get('id', str(uuid.uuid4())),
            name=suggestion_data.get('name', '未命名建议'),
            description=suggestion_data.get('description', ''),
            operations=operations,
            confidence=suggestion_data.get('confidence', 0.5),
            reasoning=suggestion_data.get('reasoning', ''),
            preview=suggestion_data.get('preview')
        )
        suggestions.append(suggestion)
    return suggestions


def _extract_and_clean_json(text: str) -> str:
    """从AI响应中提取并清理JSON内容"""
    try:
        # 尝试找到JSON块的开始和结束
        json_start = text.find('{')
        json_end = text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return ""

        json_content = text[json_start:json_end]

        # 清理常见的JSON格式问题
        # 1. 移除注释行
        lines = json_content.split('\n')
        cleaned_lines = []
        for line in lines:
            # 跳过注释行
            stripped_line = line.strip()
            if not stripped_line.startswith('//') and not stripped_line.startswith('#'):
                cleaned_lines.append(line)

        json_content = '\n'.join(cleaned_lines)

        # 2. 修复常见的JSON语法问题
        # 移除尾随逗号
        json_content = re.sub(r',(\s*[}\]])', r'\1', json_content)

        # 3. 尝试解析以验证JSON有效性
        json.loads(json_content)
        return json_content

    except json.JSONDecodeError as e:
        logger.warning(f"JSON清理后仍然无效: {e}")
        # 尝试更激进的清理
        try:
            # 如果标准清理失败，尝试提取最外层的{}内容
            brace_count = 0
            start_pos = -1
            end_pos = -1

            for i, char in enumerate(text):
                if char == '{':
                    if start_pos == -1:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_pos != -1:
                        end_pos = i + 1
                        break

            if start_pos != -1 and end_pos != -1:
                fallback_json = text[start_pos:end_pos]
                # 再次清理
                fallback_json = re.sub(r',(\s*[}\]])', r'\1', fallback_json)
                json.loads(fallback_json)  # 验证
                return fallback_json

        except Exception:
            pass

        return ""
    except Exception as e:
        logger.warning(f"JSON提取失败: {e}")
        return ""


def parse_ai_graph_suggestions(ai_response: str, context: WorkflowContext) -> List[GraphSuggestion]:
    """解析AI响应为图建议对象"""
    try:
        # 清理和提取JSON内容
        json_content = _extract_and_clean_json(ai_response)

        if not json_content:
            logger.warning("AI响应中未找到有效的JSON格式")
            return []

        parsed_data = json.loads(json_content)

        suggestions = []
        for suggestion_data in parsed_data.get('suggestions', []):
            # 转换操作
            operations = []
            for op_data in suggestion_data.get('operations', []):
                operation = GraphOperation(
                    id=op_data.get('id', str(uuid.uuid4())),
                    type=op_data.get('type', 'add_node'),
                    data=op_data.get('data', {}),
                    reasoning=op_data.get('reasoning', '无说明')
                )
                operations.append(operation)

            # 创建建议对象
            suggestion = GraphSuggestion(
                id=suggestion_data.get('id', str(uuid.uuid4())),
                name=suggestion_data.get('name', '未命名建议'),
                description=suggestion_data.get('description', ''),
                operations=operations,
                confidence=suggestion_data.get('confidence', 0.5),
                reasoning=suggestion_data.get('reasoning', ''),
                preview=suggestion_data.get('preview')
            )

            suggestions.append(suggestion)

        return suggestions

    except Exception as e:
        logger.error(f"解析AI图建议响应失败: {str(e)}")
        logger.debug(f"AI响应内容: {ai_response}")
        return []