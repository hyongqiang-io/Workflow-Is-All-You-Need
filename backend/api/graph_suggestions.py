"""
统一的图操作建议API端点
替换分离的节点/边建议系统，使用操作序列方式
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
from loguru import logger

from ..services.ai_workflow_generator import AIWorkflowGenerator
from ..models.user import User
from ..utils.auth import get_current_user

router = APIRouter(prefix="/tab-completion", tags=["图操作建议"])

# 图操作类型
class GraphOperationType(str):
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
    current_user: User = Depends(get_current_user)
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

        # 调用AI服务生成图操作建议
        ai_generator = AIWorkflowGenerator()
        ai_response = await ai_generator._call_real_api(
            prompt=prompt,
            temperature=0.7,
            max_tokens=4000
        )

        if not ai_response:
            return GraphSuggestionResponse(
                success=False,
                message="AI服务响应为空"
            )

        # 解析AI响应
        suggestions = parse_ai_graph_suggestions(ai_response, context)

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
    current_user: User = Depends(get_current_user)
):
    """跟踪图操作执行结果"""
    try:
        logger.info(f"🔮 [TRACK] 收到操作执行跟踪")
        logger.info(f"🔮 [TRACK] 建议ID: {request.suggestion_id}")
        logger.info(f"🔮 [TRACK] 操作数量: {len(request.operations)}")
        logger.info(f"🔮 [TRACK] 执行结果: {request.success}")

        # TODO: 这里可以将执行结果保存到数据库进行分析
        # 用于改进AI建议的质量

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
        node_id = node.get('id', 'unknown_id')
        node_name = node.get('name') or node.get('data', {}).get('label', '未命名')
        node_type = node.get('type') or node.get('data', {}).get('type', 'processor')
        current_state += f"- 节点{i+1}: {node_name} ({node_type}) [ID: {node_id}]\n"

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
              "processor_id": "相关处理器ID（可选）"
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
              "target_node_id": "实际的节点UUID（从上面的节点列表中获取）",
              "connection_type": "normal|conditional|parallel",
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
8. **重要**：在创建连接时，必须使用上面节点列表中的实际UUID（[ID: xxx]格式中的ID），不要使用描述性名称

请生成最多1个最佳建议（幽灵编辑模式）："""

    return prompt

def parse_ai_graph_suggestions(ai_response: str, context: WorkflowContext) -> List[GraphSuggestion]:
    """解析AI响应为图建议对象"""
    try:
        # 提取JSON内容
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            logger.warning("🔮 [PARSE] AI响应中未找到JSON格式，跳过处理")
            logger.debug(f"AI响应内容: {ai_response[:200]}...")
            return []

        json_content = ai_response[json_start:json_end]
        parsed_data = json.loads(json_content)

        # 验证根级结构
        if not isinstance(parsed_data, dict) or 'suggestions' not in parsed_data:
            logger.warning("🔮 [PARSE] AI响应缺少'suggestions'字段，跳过处理")
            logger.debug(f"解析的数据结构: {parsed_data}")
            return []

        suggestions_data = parsed_data.get('suggestions', [])
        if not isinstance(suggestions_data, list) or len(suggestions_data) == 0:
            logger.warning("🔮 [PARSE] AI响应的'suggestions'字段为空或格式错误，跳过处理")
            return []

        suggestions = []
        for i, suggestion_data in enumerate(suggestions_data):
            # 严格验证每个建议的必需字段
            if not isinstance(suggestion_data, dict):
                logger.warning(f"🔮 [PARSE] 建议{i+1}不是有效的对象格式，跳过")
                continue

            # 检查必需字段
            required_fields = ['name', 'operations']
            missing_fields = [field for field in required_fields if not suggestion_data.get(field)]
            if missing_fields:
                logger.warning(f"🔮 [PARSE] 建议{i+1}缺少必需字段: {missing_fields}，跳过")
                continue

            # 验证操作列表
            operations_data = suggestion_data.get('operations', [])
            if not isinstance(operations_data, list) or len(operations_data) == 0:
                logger.warning(f"🔮 [PARSE] 建议{i+1}的操作列表为空或格式错误，跳过")
                continue

            # 解析和验证每个操作
            operations = []
            for j, op_data in enumerate(operations_data):
                if not isinstance(op_data, dict):
                    logger.warning(f"🔮 [PARSE] 建议{i+1}的操作{j+1}不是有效对象，跳过")
                    continue

                # 验证操作的必需字段
                op_required_fields = ['type', 'data']
                op_missing_fields = [field for field in op_required_fields if not op_data.get(field)]
                if op_missing_fields:
                    logger.warning(f"🔮 [PARSE] 建议{i+1}的操作{j+1}缺少必需字段: {op_missing_fields}，跳过")
                    continue

                # 验证操作类型
                op_type = op_data.get('type')
                if op_type not in [GraphOperationType.ADD_NODE, GraphOperationType.ADD_EDGE,
                                 GraphOperationType.REMOVE_NODE, GraphOperationType.REMOVE_EDGE,
                                 GraphOperationType.UPDATE_NODE, GraphOperationType.UPDATE_EDGE]:
                    logger.warning(f"🔮 [PARSE] 建议{i+1}的操作{j+1}类型无效: {op_type}，跳过")
                    continue

                # 验证操作数据的完整性
                op_data_content = op_data.get('data', {})
                if not isinstance(op_data_content, dict):
                    logger.warning(f"🔮 [PARSE] 建议{i+1}的操作{j+1}数据格式错误，跳过")
                    continue

                # 根据操作类型验证具体数据
                if op_type == GraphOperationType.ADD_NODE:
                    if 'node' not in op_data_content or not isinstance(op_data_content['node'], dict):
                        logger.warning(f"🔮 [PARSE] 建议{i+1}的添加节点操作{j+1}缺少node数据，跳过")
                        continue
                    node_data = op_data_content['node']
                    if not node_data.get('name') or not node_data.get('type'):
                        logger.warning(f"🔮 [PARSE] 建议{i+1}的添加节点操作{j+1}缺少节点名称或类型，跳过")
                        continue

                elif op_type == GraphOperationType.ADD_EDGE:
                    if 'edge' not in op_data_content or not isinstance(op_data_content['edge'], dict):
                        logger.warning(f"🔮 [PARSE] 建议{i+1}的添加连接操作{j+1}缺少edge数据，跳过")
                        continue
                    edge_data = op_data_content['edge']
                    if not edge_data.get('source_node_id') or not edge_data.get('target_node_id'):
                        logger.warning(f"🔮 [PARSE] 建议{i+1}的添加连接操作{j+1}缺少源或目标节点ID，跳过")
                        continue

                # 通过所有验证，创建操作对象
                operation = GraphOperation(
                    id=op_data.get('id', str(uuid.uuid4())),
                    type=op_type,
                    data=op_data_content,
                    reasoning=op_data.get('reasoning', '无说明')
                )
                operations.append(operation)
                logger.info(f"🔮 [PARSE] ✅ 验证通过: 建议{i+1}的操作{j+1} - {op_type}")

            # 如果没有有效的操作，跳过这个建议
            if len(operations) == 0:
                logger.warning(f"🔮 [PARSE] 建议{i+1}没有有效操作，跳过整个建议")
                continue

            # 创建建议对象
            suggestion = GraphSuggestion(
                id=suggestion_data.get('id', str(uuid.uuid4())),
                name=suggestion_data.get('name', '未命名建议'),
                description=suggestion_data.get('description', ''),
                operations=operations,
                confidence=min(max(suggestion_data.get('confidence', 0.5), 0.0), 1.0),  # 限制在0-1范围
                reasoning=suggestion_data.get('reasoning', ''),
                preview=suggestion_data.get('preview')
            )

            suggestions.append(suggestion)
            logger.info(f"🔮 [PARSE] ✅ 成功解析建议: {suggestion.name} (包含{len(operations)}个操作)")

        if len(suggestions) == 0:
            logger.warning("🔮 [PARSE] 所有建议都未通过验证，返回空列表")
        else:
            logger.info(f"🔮 [PARSE] ✅ 解析完成，共{len(suggestions)}个有效建议")

        return suggestions

    except json.JSONDecodeError as e:
        logger.error(f"🔮 [PARSE] ❌ JSON解析失败: {str(e)}")
        logger.debug(f"AI响应内容: {ai_response}")
        return []
    except Exception as e:
        logger.error(f"🔮 [PARSE] ❌ 解析AI图建议响应失败: {str(e)}")
        logger.debug(f"AI响应内容: {ai_response}")
        return []