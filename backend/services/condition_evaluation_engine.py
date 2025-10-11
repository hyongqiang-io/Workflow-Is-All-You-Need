"""
条件评估引擎
Condition Evaluation Engine

处理工作流中条件边的评估逻辑，支持多种条件类型：
- 表达式条件
- 用户选择条件
- 输出字段条件
- 复合条件
"""

import re
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from loguru import logger


class ConditionEvaluationEngine:
    """条件评估引擎"""

    def __init__(self):
        # 支持的操作符
        self.operators = {
            'equals': lambda a, b: a == b,
            'not_equals': lambda a, b: a != b,
            'greater_than': lambda a, b: float(a) > float(b),
            'less_than': lambda a, b: float(a) < float(b),
            'greater_equal': lambda a, b: float(a) >= float(b),
            'less_equal': lambda a, b: float(a) <= float(b),
            'contains': lambda a, b: str(b) in str(a),
            'not_contains': lambda a, b: str(b) not in str(a),
            'starts_with': lambda a, b: str(a).startswith(str(b)),
            'ends_with': lambda a, b: str(a).endswith(str(b)),
            'in': lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
            'not_in': lambda a, b: a not in b if isinstance(b, (list, tuple, set)) else True,
            'regex_match': lambda a, b: bool(re.match(str(b), str(a))),
            'is_empty': lambda a, b: not a or a == '' or a is None,
            'is_not_empty': lambda a, b: a and a != '' and a is not None
        }

        # 类型转换函数
        self.type_converters = {
            'string': str,
            'number': float,
            'integer': int,
            'boolean': lambda x: str(x).lower() in ['true', '1', 'yes', 'on'],
            'date': lambda x: datetime.fromisoformat(str(x)) if isinstance(x, str) else x
        }

    async def evaluate_condition(self, condition_config: Dict[str, Any],
                               context: Dict[str, Any]) -> bool:
        """
        统一的条件评估入口 - 消除special cases

        Linus原则: "好代码没有特殊情况"
        所有边都是条件边，固定边的条件就是 True

        Args:
            condition_config: 条件配置，None或空表示永远为true
            context: 评估上下文，包含节点输出、路径数据等

        Returns:
            bool: 条件评估结果
        """
        try:
            # 🔧 消除特殊情况：空条件 = 永远为true的条件
            if not condition_config:
                return True  # 这就是"固定边"的本质

            condition_type = condition_config.get('type', 'expression')

            if condition_type == 'simple':
                return await self._evaluate_simple_condition(condition_config, context)
            elif condition_type == 'expression':
                return await self._evaluate_expression_condition(condition_config, context)
            elif condition_type == 'user_choice':
                return await self._evaluate_user_choice_condition(condition_config, context)
            elif condition_type == 'compound':
                return await self._evaluate_compound_condition(condition_config, context)
            elif condition_type == 'script':
                return await self._evaluate_script_condition(condition_config, context)
            else:
                logger.warning(f"未知的条件类型: {condition_type}")
                return False

        except Exception as e:
            logger.error(f"条件评估失败: {e}, 条件配置: {condition_config}")
            return False

    async def _evaluate_simple_condition(self, condition_config: Dict[str, Any],
                                       context: Dict[str, Any]) -> bool:
        """评估简单条件（字段比较）"""
        field_path = condition_config.get('field_path')  # 支持嵌套字段，如 "output.result.status"
        operator = condition_config.get('operator', 'equals')
        expected_value = condition_config.get('expected_value')
        value_type = condition_config.get('value_type', 'string')

        if not field_path:
            logger.error("简单条件缺少field_path")
            return False

        # 获取字段值
        actual_value = self._get_nested_value(context, field_path)

        if actual_value is None and operator not in ['is_empty', 'is_not_empty']:
            logger.debug(f"字段值为空: {field_path}")
            return False

        # 类型转换
        try:
            if value_type in self.type_converters and actual_value is not None:
                actual_value = self.type_converters[value_type](actual_value)
            if value_type in self.type_converters and expected_value is not None:
                expected_value = self.type_converters[value_type](expected_value)
        except (ValueError, TypeError) as e:
            logger.warning(f"类型转换失败: {e}")
            return False

        # 执行比较
        if operator in self.operators:
            result = self.operators[operator](actual_value, expected_value)
            logger.debug(f"简单条件评估: {actual_value} {operator} {expected_value} = {result}")
            return result
        else:
            logger.error(f"不支持的操作符: {operator}")
            return False

    async def _evaluate_expression_condition(self, condition_config: Dict[str, Any],
                                           context: Dict[str, Any]) -> bool:
        """评估表达式条件"""
        expression = condition_config.get('expression', 'true')
        variables = condition_config.get('variables', {})

        # 创建安全的评估环境
        safe_context = self._create_safe_context(context, variables)

        try:
            # 替换变量
            processed_expression = self._process_expression_variables(expression, safe_context)

            # 评估表达式
            result = self._safe_eval(processed_expression)

            logger.debug(f"表达式条件评估: {expression} -> {processed_expression} = {result}")
            return bool(result)

        except Exception as e:
            logger.error(f"表达式评估失败: {expression}, 错误: {e}")
            return False

    async def _evaluate_user_choice_condition(self, condition_config: Dict[str, Any],
                                            context: Dict[str, Any]) -> bool:
        """评估用户选择条件"""
        # 用户选择条件需要等待用户交互
        user_selection = context.get('user_selections', {})
        node_id = context.get('current_node_id')
        choice_key = condition_config.get('choice_key', 'default')

        if node_id and node_id in user_selection:
            selected_choices = user_selection[node_id]
            expected_choice = condition_config.get('expected_choice')

            if isinstance(selected_choices, list):
                result = expected_choice in selected_choices
            else:
                result = selected_choices == expected_choice

            logger.debug(f"用户选择条件评估: {selected_choices} 包含 {expected_choice} = {result}")
            return result

        # 如果没有用户选择，检查是否有默认值
        default_result = condition_config.get('default_result', False)
        logger.debug(f"用户选择条件使用默认值: {default_result}")
        return default_result

    async def _evaluate_compound_condition(self, condition_config: Dict[str, Any],
                                         context: Dict[str, Any]) -> bool:
        """评估复合条件（AND/OR组合）"""
        operator = condition_config.get('operator', 'and').lower()
        conditions = condition_config.get('conditions', [])

        if not conditions:
            return True

        results = []
        for sub_condition in conditions:
            result = await self.evaluate_condition(sub_condition, context)
            results.append(result)

        if operator == 'and':
            final_result = all(results)
        elif operator == 'or':
            final_result = any(results)
        elif operator == 'not':
            # NOT操作符只对第一个条件取反
            final_result = not results[0] if results else True
        else:
            logger.error(f"不支持的复合操作符: {operator}")
            return False

        logger.debug(f"复合条件评估: {operator}({results}) = {final_result}")
        return final_result

    async def _evaluate_script_condition(self, condition_config: Dict[str, Any],
                                       context: Dict[str, Any]) -> bool:
        """评估脚本条件（高级功能，支持Python代码片段）"""
        script = condition_config.get('script', 'return True')
        timeout = condition_config.get('timeout', 5)  # 5秒超时

        # 为了安全，这里应该使用沙箱环境执行脚本
        # 简化实现，只支持基本的Python表达式
        try:
            # 创建受限的执行环境
            safe_globals = {
                '__builtins__': {
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'list': list,
                    'dict': dict,
                    'max': max,
                    'min': min,
                    'sum': sum,
                    'abs': abs,
                    'round': round,
                }
            }

            safe_locals = {
                'context': context,
                'node_output': context.get('node_output', {}),
                'path_data': context.get('path_data', {}),
                'global_data': context.get('global_data', {})
            }

            # 包装脚本为函数
            wrapped_script = f"""
def evaluate_condition():
    {script}

result = evaluate_condition()
"""

            exec(wrapped_script, safe_globals, safe_locals)
            result = safe_locals.get('result', False)

            logger.debug(f"脚本条件评估结果: {result}")
            return bool(result)

        except Exception as e:
            logger.error(f"脚本条件执行失败: {script}, 错误: {e}")
            return False

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """获取嵌套字段的值"""
        keys = path.split('.')
        value = data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _create_safe_context(self, context: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """创建安全的评估上下文"""
        safe_context = {}

        # 添加上下文数据
        if 'node_output' in context:
            safe_context['output'] = context['node_output']
        if 'path_data' in context:
            safe_context['path'] = context['path_data']
        if 'global_data' in context:
            safe_context['global'] = context['global_data']

        # 添加自定义变量
        safe_context.update(variables)

        return safe_context

    def _process_expression_variables(self, expression: str, context: Dict[str, Any]) -> str:
        """处理表达式中的变量引用"""
        # 替换 ${variable} 格式的变量
        def replace_variable(match):
            var_path = match.group(1)
            value = self._get_nested_value(context, var_path)

            if isinstance(value, str):
                return f"'{value}'"
            elif value is None:
                return 'None'
            else:
                return str(value)

        # 使用正则表达式匹配变量引用
        processed = re.sub(r'\$\{([^}]+)\}', replace_variable, expression)

        # 替换 $variable 格式的变量
        def replace_simple_variable(match):
            var_name = match.group(1)
            value = context.get(var_name)

            if isinstance(value, str):
                return f"'{value}'"
            elif value is None:
                return 'None'
            else:
                return str(value)

        processed = re.sub(r'\$(\w+)', replace_simple_variable, processed)

        return processed

    def _safe_eval(self, expression: str) -> Any:
        """安全地评估表达式"""
        # 只允许基本的比较和逻辑运算
        allowed_chars = set('0123456789+-*/().,<>=!&|abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_\'" ')

        if not all(c in allowed_chars for c in expression):
            raise ValueError(f"表达式包含不安全的字符: {expression}")

        # 替换逻辑操作符
        expression = expression.replace(' and ', ' and ')
        expression = expression.replace(' or ', ' or ')
        expression = expression.replace(' not ', ' not ')

        # 基本的true/false评估
        expression = expression.strip()

        if expression.lower() == 'true':
            return True
        elif expression.lower() == 'false':
            return False

        # 对于复杂表达式，使用受限的eval
        try:
            safe_globals = {"__builtins__": {}}
            return eval(expression, safe_globals, {})
        except:
            # 如果eval失败，尝试解析简单的比较表达式
            return self._parse_simple_comparison(expression)

    def _parse_simple_comparison(self, expression: str) -> bool:
        """解析简单的比较表达式"""
        # 匹配 "value1 operator value2" 格式
        comparison_pattern = r"([^<>=!]+)\s*(==|!=|<=|>=|<|>)\s*([^<>=!]+)"
        match = re.match(comparison_pattern, expression.strip())

        if match:
            left, op, right = match.groups()
            left = left.strip().strip("'\"")
            right = right.strip().strip("'\"")

            # 尝试数值比较
            try:
                left_num = float(left)
                right_num = float(right)

                if op == '==':
                    return left_num == right_num
                elif op == '!=':
                    return left_num != right_num
                elif op == '<':
                    return left_num < right_num
                elif op == '>':
                    return left_num > right_num
                elif op == '<=':
                    return left_num <= right_num
                elif op == '>=':
                    return left_num >= right_num

            except ValueError:
                # 字符串比较
                if op == '==':
                    return left == right
                elif op == '!=':
                    return left != right

        return False

    def validate_condition_config(self, condition_config: Dict[str, Any]) -> List[str]:
        """验证条件配置的有效性"""
        errors = []

        if not isinstance(condition_config, dict):
            errors.append("条件配置必须是字典类型")
            return errors

        condition_type = condition_config.get('type', 'expression')

        if condition_type == 'simple':
            if not condition_config.get('field_path'):
                errors.append("简单条件必须指定field_path")

            operator = condition_config.get('operator', 'equals')
            if operator not in self.operators:
                errors.append(f"不支持的操作符: {operator}")

        elif condition_type == 'expression':
            if not condition_config.get('expression'):
                errors.append("表达式条件必须指定expression")

        elif condition_type == 'compound':
            operator = condition_config.get('operator', 'and')
            if operator not in ['and', 'or', 'not']:
                errors.append(f"复合条件操作符必须是and/or/not: {operator}")

            conditions = condition_config.get('conditions', [])
            if not conditions:
                errors.append("复合条件必须包含子条件")

        return errors


# 全局条件评估引擎实例
_condition_engine: Optional[ConditionEvaluationEngine] = None

def get_condition_engine() -> ConditionEvaluationEngine:
    """获取条件评估引擎实例"""
    global _condition_engine
    if _condition_engine is None:
        _condition_engine = ConditionEvaluationEngine()
        logger.debug("初始化条件评估引擎")
    return _condition_engine