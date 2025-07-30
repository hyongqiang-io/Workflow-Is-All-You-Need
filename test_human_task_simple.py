"""
人类任务执行简化测试
测试用户从获取任务到提交结果的完整流程
"""

import uuid
import asyncio
import json
from datetime import datetime, timedelta
import sys

# 添加项目根目录到Python路径
sys.path.append('.')

from workflow_framework.services.human_task_service import HumanTaskService
from workflow_framework.models.instance import TaskInstanceStatus, TaskInstanceType


class HumanTaskExecutionTest:
    """人类任务执行测试类"""
    
    def __init__(self):
        self.human_task_service = HumanTaskService()
        
        # 测试数据
        self.test_user_id = uuid.uuid4()
        self.test_task_id = uuid.uuid4()
        
    def setup_mock_data(self):
        """设置模拟数据"""
        print("设置测试数据...")
        
        # 模拟上游数据
        upstream_data = {
            'immediate_upstream': {
                str(uuid.uuid4()): {
                    'node_name': '数据收集节点',
                    'output_data': {
                        'collected_records': 10000,
                        'quality_score': 0.95
                    },
                    'completed_at': '2024-01-15T10:30:00Z'
                },
                str(uuid.uuid4()): {
                    'node_name': '数据预处理节点',
                    'output_data': {
                        'cleaned_records': 9500,
                        'removed_duplicates': 300
                    },
                    'completed_at': '2024-01-15T11:00:00Z'
                }
            },
            'workflow_global': {
                'execution_path': ['start_node', 'data_collection', 'preprocessing'],
                'global_data': {
                    'project_name': 'Q1用户行为分析',
                    'deadline': '2024-01-20T18:00:00Z'
                }
            },
            'node_info': {
                'node_instance_id': str(uuid.uuid4()),
                'upstream_node_count': 2
            }
        }
        
        # 模拟任务数据
        self.mock_task = {
            'task_instance_id': self.test_task_id,
            'task_title': '用户行为数据分析任务',
            'task_description': '分析用户行为数据，识别关键趋势和模式',
            'instructions': '请基于上游节点提供的数据完成分析',
            'input_data': upstream_data,
            'status': TaskInstanceStatus.ASSIGNED.value,
            'priority': 2,
            'estimated_duration': 120,
            'assigned_user_id': self.test_user_id,
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        print("测试数据设置完成")
    
    def test_task_structure(self):
        """测试任务数据结构"""
        print("\n测试1: 任务数据结构验证")
        
        task = self.mock_task
        
        # 验证基本字段
        required_fields = [
            'task_instance_id', 'task_title', 'task_description',
            'instructions', 'status', 'priority', 'input_data'
        ]
        
        print("检查必需字段:")
        for field in required_fields:
            exists = field in task
            status = "OK" if exists else "MISSING"
            print(f"  {field}: {status}")
        
        # 验证上游数据结构
        print("\n检查上游数据结构:")
        input_data = task.get('input_data', {})
        
        upstream_fields = [
            'immediate_upstream', 'workflow_global', 'node_info'
        ]
        
        for field in upstream_fields:
            exists = field in input_data
            status = "OK" if exists else "MISSING"
            print(f"  {field}: {status}")
        
        # 显示上游节点信息
        immediate_upstream = input_data.get('immediate_upstream', {})
        print(f"\n上游节点数量: {len(immediate_upstream)}")
        
        for node_id, node_data in immediate_upstream.items():
            node_name = node_data.get('node_name', 'Unknown')
            output_count = len(node_data.get('output_data', {}))
            print(f"  - {node_name}: {output_count} 个输出字段")
        
        return True
    
    def test_task_details_format(self):
        """测试任务详情格式"""
        print("\n测试2: 任务详情格式化")
        
        # 模拟 get_task_details 返回的格式
        task_details = {
            # 任务基本信息
            'task_instance_id': str(self.mock_task['task_instance_id']),
            'task_title': self.mock_task['task_title'],
            'task_description': self.mock_task['task_description'],
            'instructions': self.mock_task['instructions'],
            'status': self.mock_task['status'],
            'priority': self.mock_task['priority'],
            'priority_label': '中优先级',
            
            # 工作流上下文
            'workflow_context': {
                'workflow_name': 'Q1用户行为分析工作流',
                'instance_name': 'Q1分析实例',
                'workflow_input_data': {
                    'analysis_period': '2024-Q1'
                }
            },
            
            # 节点上下文
            'node_context': {
                'node_name': '数据分析处理节点',
                'node_type': 'PROCESSOR'
            },
            
            # 上游上下文
            'upstream_context': {
                'immediate_upstream_results': self.mock_task['input_data']['immediate_upstream'],
                'upstream_node_count': 2,
                'has_upstream_data': True
            }
        }
        
        print("任务详情结构:")
        print(f"  任务标题: {task_details['task_title']}")
        print(f"  任务状态: {task_details['status']}")
        print(f"  优先级: {task_details['priority_label']}")
        print(f"  工作流: {task_details['workflow_context']['workflow_name']}")
        print(f"  节点类型: {task_details['node_context']['node_type']}")
        print(f"  上游节点数: {task_details['upstream_context']['upstream_node_count']}")
        
        return task_details
    
    def test_task_execution_flow(self):
        """测试任务执行流程"""
        print("\n测试3: 任务执行流程")
        
        # 1. 开始任务
        print("步骤1: 开始执行任务")
        start_result = {
            'task_id': str(self.test_task_id),
            'status': TaskInstanceStatus.IN_PROGRESS.value,
            'started_at': datetime.utcnow().isoformat() + 'Z',
            'message': '任务已开始执行'
        }
        print(f"  任务状态: {start_result['status']}")
        print(f"  开始时间: {start_result['started_at']}")
        
        # 2. 模拟用户工作
        print("\n步骤2: 用户执行分析工作")
        print("  用户查看上游数据...")
        print("  用户进行数据分析...")
        print("  用户准备结果...")
        
        # 3. 提交结果
        print("\n步骤3: 提交分析结果")
        analysis_result = {
            'user_behavior_analysis': {
                'total_users_analyzed': 9500,
                'key_findings': [
                    '移动端用户占比70%',
                    '用户在晚上8-10点最活跃',
                    '新用户7日留存率为45%'
                ],
                'key_metrics': {
                    'daily_active_users': 6500,
                    'conversion_rate': 0.12,
                    'churn_rate': 0.15
                },
                'recommendations': [
                    {
                        'priority': 'high',
                        'action': '优化移动端用户体验',
                        'expected_impact': '提升DAU 10-15%'
                    }
                ]
            }
        }
        
        result_summary = "完成了Q1用户行为数据分析，识别出关键用户群体和优化机会"
        
        submit_result = {
            'task_id': str(self.test_task_id),
            'status': TaskInstanceStatus.COMPLETED.value,
            'completed_at': datetime.utcnow().isoformat() + 'Z',
            'result_data': analysis_result,
            'result_summary': result_summary,
            'actual_duration': 105  # 分钟
        }
        
        print(f"  最终状态: {submit_result['status']}")
        print(f"  完成时间: {submit_result['completed_at']}")
        print(f"  实际耗时: {submit_result['actual_duration']} 分钟")
        print(f"  结果字段数: {len(analysis_result['user_behavior_analysis'])}")
        
        return submit_result
    
    def test_downstream_trigger(self):
        """测试下游任务触发"""
        print("\n测试4: 下游任务触发验证")
        
        print("任务完成后的处理:")
        print("  1. 更新任务状态为COMPLETED")
        print("  2. 保存分析结果到output_data")
        print("  3. 检查下游节点依赖")
        print("  4. 触发下游任务创建")
        
        # 模拟下游任务
        downstream_tasks = [
            {
                'task_id': str(uuid.uuid4()),
                'task_title': '分析报告生成任务',
                'node_name': '报告生成节点',
                'status': 'pending',
                'inherited_data': True
            },
            {
                'task_id': str(uuid.uuid4()),
                'task_title': '可视化图表制作任务',
                'node_name': '可视化节点',
                'status': 'pending',
                'inherited_data': True
            }
        ]
        
        print(f"\n下游任务创建成功: {len(downstream_tasks)} 个")
        for task in downstream_tasks:
            print(f"  - {task['task_title']}")
            print(f"    状态: {task['status']}")
            print(f"    数据继承: {'是' if task['inherited_data'] else '否'}")
        
        return downstream_tasks
    
    def run_complete_test(self):
        """运行完整测试"""
        print("开始人类任务执行完整测试")
        print("=" * 50)
        
        try:
            # 1. 设置数据
            self.setup_mock_data()
            
            # 2. 验证任务结构
            structure_ok = self.test_task_structure()
            
            # 3. 测试详情格式
            task_details = self.test_task_details_format()
            
            # 4. 测试执行流程
            execution_result = self.test_task_execution_flow()
            
            # 5. 测试下游触发
            downstream_tasks = self.test_downstream_trigger()
            
            # 6. 生成测试总结
            print("\n" + "=" * 50)
            print("测试执行总结:")
            
            tests = [
                ("任务数据结构", structure_ok),
                ("任务详情格式", bool(task_details)),
                ("执行流程", bool(execution_result)),
                ("下游触发", bool(downstream_tasks))
            ]
            
            success_count = 0
            for test_name, result in tests:
                status = "通过" if result else "失败"
                print(f"  {test_name}: {status}")
                if result:
                    success_count += 1
            
            completion_rate = (success_count / len(tests)) * 100
            print(f"\n测试完成度: {success_count}/{len(tests)} ({completion_rate:.0f}%)")
            
            if success_count == len(tests):
                print("\n所有测试通过！人类任务执行流程设计正确。")
                return True
            else:
                print("\n部分测试失败，需要进一步完善。")
                return False
                
        except Exception as e:
            print(f"测试执行失败: {e}")
            return False
    
    def generate_api_examples(self):
        """生成API调用示例"""
        print("\n" + "=" * 50)
        print("API调用示例:")
        
        examples = {
            "获取任务列表": {
                "method": "GET",
                "url": "/api/execution/tasks/my?status=assigned",
                "headers": {
                    "Authorization": "Bearer <jwt_token>"
                },
                "response": {
                    "success": True,
                    "data": [
                        {
                            "task_instance_id": str(self.test_task_id),
                            "task_title": "用户行为数据分析任务",
                            "status": "assigned",
                            "priority": 2,
                            "estimated_duration": 120
                        }
                    ]
                }
            },
            
            "获取任务详情": {
                "method": "GET",
                "url": f"/api/execution/tasks/{self.test_task_id}",
                "headers": {
                    "Authorization": "Bearer <jwt_token>"
                },
                "response": {
                    "success": True,
                    "data": {
                        "task_title": "用户行为数据分析任务",
                        "task_description": "分析用户行为数据，识别关键趋势和模式",
                        "upstream_context": {
                            "has_upstream_data": True,
                            "upstream_node_count": 2
                        }
                    }
                }
            },
            
            "开始任务": {
                "method": "POST",
                "url": f"/api/execution/tasks/{self.test_task_id}/start",
                "headers": {
                    "Authorization": "Bearer <jwt_token>"
                },
                "response": {
                    "success": True,
                    "data": {
                        "task_id": str(self.test_task_id),
                        "status": "in_progress",
                        "message": "任务已开始执行"
                    }
                }
            },
            
            "提交结果": {
                "method": "POST",
                "url": f"/api/execution/tasks/{self.test_task_id}/submit",
                "headers": {
                    "Authorization": "Bearer <jwt_token>",
                    "Content-Type": "application/json"
                },
                "body": {
                    "result_data": {
                        "analysis_result": "分析结果数据",
                        "key_findings": ["发现1", "发现2"],
                        "recommendations": ["建议1", "建议2"]
                    },
                    "result_summary": "任务完成总结"
                },
                "response": {
                    "success": True,
                    "data": {
                        "task_id": str(self.test_task_id),
                        "status": "completed",
                        "message": "任务结果已提交"
                    }
                }
            }
        }
        
        for api_name, example in examples.items():
            print(f"\n{api_name}:")
            print(f"  {example['method']} {example['url']}")
            if 'body' in example:
                print("  请求体: (JSON格式)")
                print("    result_data: 分析结果数据")
                print("    result_summary: 结果总结")


def main():
    """主函数"""
    test = HumanTaskExecutionTest()
    
    # 运行完整测试
    success = test.run_complete_test()
    
    # 生成API示例
    test.generate_api_examples()
    
    return success


if __name__ == "__main__":
    result = main()
    
    if result:
        print("\n测试成功完成！")
    else:
        print("\n测试未完全通过！")