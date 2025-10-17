"""
用户交互跟踪服务
记录和分析用户在Tab补全过程中的行为模式
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger
from enum import Enum

from ..utils.database import get_database


class InteractionEventType(str, Enum):
    """交互事件类型"""
    SUGGESTION_SHOWN = "suggestion_shown"
    SUGGESTION_ACCEPTED = "suggestion_accepted"
    SUGGESTION_REJECTED = "suggestion_rejected"
    SUGGESTION_IGNORED = "suggestion_ignored"
    TRIGGER_ACTIVATED = "trigger_activated"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"


class SuggestionType(str, Enum):
    """建议类型"""
    NODE = "node"
    EDGE = "edge"
    WORKFLOW_COMPLETION = "workflow_completion"


class UserInteractionTracker:
    """用户交互跟踪器"""

    def __init__(self):
        self.db = get_database()
        logger.info("🔍 用户交互跟踪器初始化完成")

    async def track_interaction(
        self,
        user_id: uuid.UUID,
        workflow_id: Optional[str],
        event_type: InteractionEventType,
        suggestion_type: Optional[SuggestionType] = None,
        suggestion_data: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        记录用户交互事件

        Args:
            user_id: 用户ID
            workflow_id: 工作流ID
            event_type: 事件类型
            suggestion_type: 建议类型
            suggestion_data: 建议数据
            context_data: 上下文数据
            session_id: 会话ID

        Returns:
            str: 交互记录ID
        """
        try:
            interaction_id = str(uuid.uuid4())

            # 准备数据
            insert_data = {
                'interaction_id': interaction_id,
                'user_id': str(user_id),
                'workflow_id': workflow_id,
                'session_id': session_id or str(uuid.uuid4()),
                'event_type': event_type.value,
                'suggestion_type': suggestion_type.value if suggestion_type else None,
                'suggestion_data': json.dumps(suggestion_data) if suggestion_data else None,
                'context_data': json.dumps(context_data) if context_data else None,
                'created_at': datetime.utcnow(),
                'metadata': json.dumps({
                    'client_timestamp': datetime.utcnow().isoformat(),
                    'tracking_version': '1.0'
                })
            }

            # 插入数据库
            query = """
                INSERT INTO user_interaction_logs (
                    interaction_id, user_id, workflow_id, session_id, event_type,
                    suggestion_type, suggestion_data, context_data, created_at, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """

            # 构建参数列表
            params = (
                insert_data['interaction_id'],
                insert_data['user_id'],
                insert_data['workflow_id'],
                insert_data['session_id'],
                insert_data['event_type'],
                insert_data['suggestion_type'],
                insert_data['suggestion_data'],
                insert_data['context_data'],
                insert_data['created_at'],
                insert_data['metadata']
            )

            async with self.db.transaction() as conn:
                await conn.execute(query, params)

            logger.info(f"🔍 [TRACK] 用户交互已记录: {event_type.value} - 用户:{user_id}")
            return interaction_id

        except Exception as e:
            logger.error(f"🔍 [TRACK] ❌ 交互记录失败: {str(e)}")
            raise

    async def track_suggestion_shown(
        self,
        user_id: uuid.UUID,
        workflow_id: str,
        suggestions: List[Dict[str, Any]],
        trigger_context: Dict[str, Any],
        session_id: str
    ) -> str:
        """记录建议显示事件"""
        return await self.track_interaction(
            user_id=user_id,
            workflow_id=workflow_id,
            event_type=InteractionEventType.SUGGESTION_SHOWN,
            suggestion_type=SuggestionType.NODE if any(s.get('type') for s in suggestions) else SuggestionType.EDGE,
            suggestion_data={
                'suggestions': suggestions,
                'count': len(suggestions),
                'max_confidence': max(s.get('confidence', 0) for s in suggestions) if suggestions else 0,
                'avg_confidence': sum(s.get('confidence', 0) for s in suggestions) / len(suggestions) if suggestions else 0
            },
            context_data=trigger_context,
            session_id=session_id
        )

    async def track_suggestion_accepted(
        self,
        user_id: uuid.UUID,
        workflow_id: str,
        accepted_suggestion: Dict[str, Any],
        suggestion_index: int,
        total_suggestions: int,
        session_id: str
    ) -> str:
        """记录建议接受事件"""
        return await self.track_interaction(
            user_id=user_id,
            workflow_id=workflow_id,
            event_type=InteractionEventType.SUGGESTION_ACCEPTED,
            suggestion_type=SuggestionType.NODE if 'type' in accepted_suggestion else SuggestionType.EDGE,
            suggestion_data={
                'accepted_suggestion': accepted_suggestion,
                'suggestion_index': suggestion_index,
                'total_suggestions': total_suggestions,
                'confidence': accepted_suggestion.get('confidence', 0),
                'reasoning': accepted_suggestion.get('reasoning', ''),
                'selection_method': 'tab_key'  # 假设通过Tab键接受
            },
            session_id=session_id
        )

    async def track_suggestion_rejected(
        self,
        user_id: uuid.UUID,
        workflow_id: str,
        rejected_suggestions: List[Dict[str, Any]],
        rejection_method: str,
        session_id: str
    ) -> str:
        """记录建议拒绝事件"""
        return await self.track_interaction(
            user_id=user_id,
            workflow_id=workflow_id,
            event_type=InteractionEventType.SUGGESTION_REJECTED,
            suggestion_data={
                'rejected_suggestions': rejected_suggestions,
                'rejection_method': rejection_method,  # 'escape_key', 'click_outside', etc.
                'count': len(rejected_suggestions)
            },
            session_id=session_id
        )

    async def get_user_behavior_patterns(
        self,
        user_id: uuid.UUID,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        分析用户行为模式

        Args:
            user_id: 用户ID
            days_back: 分析天数

        Returns:
            Dict: 行为模式分析结果
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days_back)

            # 查询用户交互数据
            query = """
                SELECT event_type, suggestion_type, suggestion_data, context_data, created_at
                FROM user_interaction_logs
                WHERE user_id = %s AND created_at >= %s
                ORDER BY created_at DESC
            """

            async with self.db.transaction() as conn:
                rows = await conn.fetch(query, str(user_id), since_date)

            if not rows:
                return self._empty_behavior_pattern()

            # 分析数据
            total_events = len(rows)
            accepted_count = len([r for r in rows if r['event_type'] == InteractionEventType.SUGGESTION_ACCEPTED.value])
            rejected_count = len([r for r in rows if r['event_type'] == InteractionEventType.SUGGESTION_REJECTED.value])
            shown_count = len([r for r in rows if r['event_type'] == InteractionEventType.SUGGESTION_SHOWN.value])

            # 计算接受率
            acceptance_rate = accepted_count / shown_count if shown_count > 0 else 0

            # 分析建议类型偏好
            node_events = [r for r in rows if r['suggestion_type'] == SuggestionType.NODE.value]
            edge_events = [r for r in rows if r['suggestion_type'] == SuggestionType.EDGE.value]

            # 分析置信度偏好
            confidence_analysis = self._analyze_confidence_preferences(rows)

            # 分析时间模式
            time_analysis = self._analyze_time_patterns(rows)

            # 分析工作流模式
            workflow_patterns = self._analyze_workflow_patterns(rows)

            return {
                'user_id': str(user_id),
                'analysis_period': f'{days_back} days',
                'total_events': total_events,
                'acceptance_rate': round(acceptance_rate, 3),
                'statistics': {
                    'suggestions_shown': shown_count,
                    'suggestions_accepted': accepted_count,
                    'suggestions_rejected': rejected_count,
                    'node_suggestions': len(node_events),
                    'edge_suggestions': len(edge_events)
                },
                'preferences': {
                    'preferred_suggestion_type': 'node' if len(node_events) > len(edge_events) else 'edge',
                    'confidence_threshold': confidence_analysis['preferred_threshold'],
                    'confidence_sensitivity': confidence_analysis['sensitivity']
                },
                'patterns': {
                    'most_active_hour': time_analysis['peak_hour'],
                    'avg_session_length': time_analysis['avg_session_length'],
                    'workflow_complexity_preference': workflow_patterns['complexity_preference']
                },
                'recommendations': self._generate_user_recommendations(
                    acceptance_rate, confidence_analysis, workflow_patterns
                )
            }

        except Exception as e:
            logger.error(f"🔍 [ANALYZE] 行为模式分析失败: {str(e)}")
            return self._empty_behavior_pattern()

    def _analyze_confidence_preferences(self, rows: List[Dict]) -> Dict[str, Any]:
        """分析用户对置信度的偏好"""
        accepted_rows = [r for r in rows if r['event_type'] == InteractionEventType.SUGGESTION_ACCEPTED.value]

        if not accepted_rows:
            return {'preferred_threshold': 0.5, 'sensitivity': 'medium'}

        confidences = []
        for row in accepted_rows:
            try:
                suggestion_data = json.loads(row['suggestion_data']) if row['suggestion_data'] else {}
                confidence = suggestion_data.get('confidence', 0)
                if confidence > 0:
                    confidences.append(confidence)
            except:
                continue

        if not confidences:
            return {'preferred_threshold': 0.5, 'sensitivity': 'medium'}

        avg_confidence = sum(confidences) / len(confidences)
        min_confidence = min(confidences)

        # 判断敏感度
        if min_confidence >= 0.8:
            sensitivity = 'low'  # 只接受高置信度建议
        elif min_confidence >= 0.5:
            sensitivity = 'medium'
        else:
            sensitivity = 'high'  # 愿意接受低置信度建议

        return {
            'preferred_threshold': round(avg_confidence, 2),
            'sensitivity': sensitivity,
            'confidence_range': {
                'min': round(min_confidence, 2),
                'max': round(max(confidences), 2),
                'avg': round(avg_confidence, 2)
            }
        }

    def _analyze_time_patterns(self, rows: List[Dict]) -> Dict[str, Any]:
        """分析时间使用模式"""
        if not rows:
            return {'peak_hour': 10, 'avg_session_length': 0}

        # 分析活跃时间
        hours = [r['created_at'].hour for r in rows]
        peak_hour = max(set(hours), key=hours.count) if hours else 10

        # 简单的会话长度估算（基于事件间隔）
        timestamps = [r['created_at'] for r in rows]
        timestamps.sort()

        session_lengths = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i-1] - timestamps[i]).total_seconds()
            if diff < 3600:  # 1小时内认为是同一会话
                session_lengths.append(diff)

        avg_session_length = sum(session_lengths) / len(session_lengths) if session_lengths else 0

        return {
            'peak_hour': peak_hour,
            'avg_session_length': round(avg_session_length / 60, 1),  # 转换为分钟
            'total_sessions': len(session_lengths) + 1
        }

    def _analyze_workflow_patterns(self, rows: List[Dict]) -> Dict[str, Any]:
        """分析工作流使用模式"""
        # 简化分析：基于上下文数据推断用户偏好的工作流复杂度
        complexity_scores = []

        for row in rows:
            try:
                if row['context_data']:
                    context = json.loads(row['context_data'])
                    node_count = context.get('nodeCount', 0)
                    edge_count = context.get('edgeCount', 0)

                    # 计算复杂度分数
                    complexity = min(1.0, (node_count * 0.1) + (edge_count * 0.05))
                    complexity_scores.append(complexity)
            except:
                continue

        if not complexity_scores:
            return {'complexity_preference': 'medium'}

        avg_complexity = sum(complexity_scores) / len(complexity_scores)

        if avg_complexity < 0.3:
            preference = 'simple'
        elif avg_complexity < 0.7:
            preference = 'medium'
        else:
            preference = 'complex'

        return {
            'complexity_preference': preference,
            'avg_complexity_score': round(avg_complexity, 2)
        }

    def _generate_user_recommendations(
        self,
        acceptance_rate: float,
        confidence_analysis: Dict[str, Any],
        workflow_patterns: Dict[str, Any]
    ) -> List[str]:
        """生成个性化推荐"""
        recommendations = []

        if acceptance_rate < 0.3:
            recommendations.append("建议提高AI预测模型的准确性，当前接受率较低")

        if confidence_analysis['sensitivity'] == 'low':
            recommendations.append("用户偏好高置信度建议，可以提高置信度阈值")
        elif confidence_analysis['sensitivity'] == 'high':
            recommendations.append("用户愿意尝试低置信度建议，可以提供更多创新性建议")

        if workflow_patterns['complexity_preference'] == 'simple':
            recommendations.append("用户偏好简单工作流，建议优先推荐基础节点类型")
        elif workflow_patterns['complexity_preference'] == 'complex':
            recommendations.append("用户偏好复杂工作流，可以推荐高级功能和并行结构")

        return recommendations

    def _empty_behavior_pattern(self) -> Dict[str, Any]:
        """返回空的行为模式（新用户）"""
        return {
            'user_id': '',
            'analysis_period': '0 days',
            'total_events': 0,
            'acceptance_rate': 0,
            'statistics': {
                'suggestions_shown': 0,
                'suggestions_accepted': 0,
                'suggestions_rejected': 0,
                'node_suggestions': 0,
                'edge_suggestions': 0
            },
            'preferences': {
                'preferred_suggestion_type': 'node',
                'confidence_threshold': 0.5,
                'confidence_sensitivity': 'medium'
            },
            'patterns': {
                'most_active_hour': 10,
                'avg_session_length': 0,
                'workflow_complexity_preference': 'medium'
            },
            'recommendations': [
                "新用户，建议从简单的节点建议开始",
                "收集更多交互数据以提供个性化建议"
            ]
        }

    async def get_global_statistics(self, days_back: int = 7) -> Dict[str, Any]:
        """获取全局统计信息"""
        try:
            since_date = datetime.utcnow() - timedelta(days=days_back)

            query = """
                SELECT
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT workflow_id) as unique_workflows,
                    AVG(CASE WHEN event_type = 'suggestion_accepted' THEN 1.0 ELSE 0.0 END) as global_acceptance_rate
                FROM user_interaction_logs
                WHERE created_at >= %s
            """

            async with self.db.transaction() as conn:
                result = await conn.fetchrow(query, since_date)

            return {
                'period': f'{days_back} days',
                'total_interactions': result['total_interactions'] or 0,
                'unique_users': result['unique_users'] or 0,
                'unique_workflows': result['unique_workflows'] or 0,
                'global_acceptance_rate': round(result['global_acceptance_rate'] or 0, 3),
                'generated_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"🔍 [STATS] 全局统计查询失败: {str(e)}")
            return {}


# 全局实例
interaction_tracker = UserInteractionTracker()