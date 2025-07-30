"""
AI处理器测试
测试AI处理器接收与人类任务一致的内容并整理成AI可接受的形式
"""

import uuid
import asyncio
import json
import sys

# 添加项目根目录到Python路径
sys.path.append('.')

from workflow_framework.services.agent_task_service import AgentTaskService
from workflow_framework.models.instance import TaskInstanceType


class AIProcessorTest:
    """AI处理器测试类"""
    
    def __init__(self):
        self.agent_service = AgentTaskService()
        self.test_task_id = uuid.uuid4()
        
    def setup_test_data(self):
        """设置测试数据（与人类任务完全一致的结构）"""
        print("设置AI处理器测试数据...")
        
        # 模拟与人类任务完全相同的上游数据
        upstream_data = {
            'immediate_upstream': {
                str(uuid.uuid4()): {
                    'node_name': '数据收集节点',
                    'output_data': {
                        'collected_records': 10000,
                        'data_source': 'user_behavior_logs',
                        'quality_score': 0.95,
                        'collection_time': '2024-01-15T10:00:00Z',
                        'data_categories': ['user_actions', 'page_views', 'clicks']
                    },
                    'completed_at': '2024-01-15T10:30:00Z'
                },
                str(uuid.uuid4()): {
                    'node_name': '数据预处理节点',
                    'output_data': {
                        'cleaned_records': 9500,
                        'removed_duplicates': 300,
                        'filled_nulls': 200,
                        'outliers_removed': 150,
                        'preprocessing_summary': '数据清洗完成，质量良好',
                        'quality_metrics': {
                            'completeness': 0.98,
                            'accuracy': 0.94,
                            'consistency': 0.92
                        }
                    },
                    'completed_at': '2024-01-15T11:00:00Z'
                }
            },
            'workflow_global': {
                'execution_path': ['start_node', 'data_collection', 'preprocessing'],
                'global_data': {
                    'project_name': 'Q1用户行为分析',
                    'analyst_team': '数据科学团队',
                    'deadline': '2024-01-20T18:00:00Z',
                    'budget': 50000,
                    'stakeholders': ['产品经理', '运营团队', 'CEO']
                },
                'execution_start_time': '2024-01-15T09:00:00Z'
            },
            'node_info': {
                'node_instance_id': str(uuid.uuid4()),
                'upstream_node_count': 2
            }
        }
        
        # 模拟任务数据（与人类任务结构完全一致）
        self.mock_task = {
            'task_instance_id': self.test_task_id,
            'task_title': '用户行为数据智能分析任务',
            'task_description': '基于预处理后的用户行为数据进行深度分析，识别用户模式、行为趋势和业务机会',
            'instructions': '''
请完成以下分析任务：
1. 分析用户行为模式和趋势
2. 识别关键用户群体特征
3. 发现潜在的业务优化机会
4. 计算核心业务指标
5. 提供数据驱动的决策建议
6. 生成可执行的行动计划
            '''.strip(),
            'input_data': upstream_data,
            'status': 'assigned',
            'priority': 3,  # 高优先级
            'estimated_duration': 45,  # 45分钟
            'assigned_agent_id': uuid.uuid4(),
            'task_type': TaskInstanceType.AGENT.value,
            'workflow_context': {
                'workflow_name': 'Q1用户行为分析工作流',
                'instance_name': '2024年Q1数据分析'
            }
        }
        
        print("AI处理器测试数据设置完成")
    
    def test_system_prompt_generation(self):
        """测试系统Prompt生成"""
        print("\n测试1: 系统Prompt生成")
        
        system_prompt = self.agent_service._build_system_prompt(self.mock_task)
        
        print("生成的系统Prompt:")
        print("-" * 50)
        print(system_prompt)
        print("-" * 50)
        print(f"Prompt长度: {len(system_prompt)} 字符")
        
        # 验证关键内容是否包含
        required_elements = [
            self.mock_task['task_title'],
            self.mock_task['task_description'], 
            self.mock_task['instructions']
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in system_prompt:
                missing_elements.append(element)
        
        if not missing_elements:
            print("[OK] 系统Prompt包含所有必需元素")
            return True
        else:
            print(f"[ERROR] 缺少元素: {missing_elements}")
            return False
    
    def test_upstream_context_preprocessing(self):
        """测试上游上下文预处理"""
        print("\n测试2: 上游上下文预处理")
        
        input_data = self.mock_task['input_data']
        context_info = self.agent_service._preprocess_upstream_context(input_data)
        
        print("预处理的上下文信息:")
        print("-" * 50)
        print(context_info)
        print("-" * 50)
        print(f"上下文长度: {len(context_info)} 字符")
        
        # 验证关键信息是否正确处理
        required_sections = [
            "上游节点提供的数据",
            "工作流全局信息",
            "当前节点信息"
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in context_info:
                missing_sections.append(section)
        
        if not missing_sections:
            print("[OK] 上下文信息包含所有必需部分")
            return True
        else:
            print(f"[ERROR] 缺少部分: {missing_sections}")
            return False
    
    def test_user_message_construction(self):
        """测试用户消息构建"""
        print("\n测试3: 用户消息构建")
        
        # 首先获取上下文信息
        input_data = self.mock_task['input_data']
        context_info = self.agent_service._preprocess_upstream_context(input_data)
        
        # 构建用户消息
        user_message = self.agent_service._build_user_message(self.mock_task, context_info)
        
        print("构建的用户消息:")
        print("-" * 50)
        print(user_message)
        print("-" * 50)
        print(f"消息长度: {len(user_message)} 字符")
        
        # 验证消息格式
        required_elements = [
            "请帮我完成以下任务",
            "以下是可用的上下文信息",
            "JSON格式返回结果",
            "高优先级任务"  # 因为priority=3
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in user_message:
                missing_elements.append(element)
        
        if not missing_elements:
            print("[OK] 用户消息包含所有必需元素")
            return True
        else:
            print(f"[ERROR] 缺少元素: {missing_elements}")
            return False
    
    def test_ai_client_data_structure(self):
        """测试AI Client数据结构"""
        print("\n测试4: AI Client数据结构")
        
        # 模拟process_agent_task中的数据处理流程
        input_data = self.mock_task.get('input_data', {})
        
        # 构建系统Prompt
        system_prompt = self.agent_service._build_system_prompt(self.mock_task)
        
        # 预处理上游上下文
        context_info = self.agent_service._preprocess_upstream_context(input_data)
        
        # 构建用户消息
        user_message = self.agent_service._build_user_message(self.mock_task, context_info)
        
        # 整理成AI Client可接收的数据结构
        ai_client_data = {
            'task_id': str(self.test_task_id),
            'system_prompt': system_prompt,
            'user_message': user_message,
            'task_metadata': {
                'task_title': self.mock_task['task_title'],
                'priority': self.mock_task.get('priority', 1),
                'estimated_duration': self.mock_task.get('estimated_duration', 30)
            }
        }
        
        print("AI Client数据结构:")
        print("-" * 50)
        print(f"Task ID: {ai_client_data['task_id']}")
        print(f"System Prompt: {len(ai_client_data['system_prompt'])} 字符")
        print(f"User Message: {len(ai_client_data['user_message'])} 字符")
        print(f"Task Metadata: {ai_client_data['task_metadata']}")
        print("-" * 50)
        
        # 验证数据结构完整性
        required_fields = ['task_id', 'system_prompt', 'user_message', 'task_metadata']
        missing_fields = []
        
        for field in required_fields:
            if field not in ai_client_data or not ai_client_data[field]:
                missing_fields.append(field)
        
        if not missing_fields:
            print("[OK] AI Client数据结构完整")
            return True, ai_client_data
        else:
            print(f"[ERROR] 缺少字段: {missing_fields}")
            return False, None
    
    async def test_mock_ai_processing(self):
        """测试模拟AI处理流程"""
        print("\n测试5: 模拟AI处理流程")
        
        # 获取AI Client数据结构
        success, ai_client_data = self.test_ai_client_data_structure()
        if not success:
            return False
        
        # 模拟Agent配置
        mock_agent = {
            'agent_id': str(uuid.uuid4()),
            'agent_name': 'claude-test',
            'model': 'claude-3-sonnet',
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        print(f"使用模拟Agent: {mock_agent['agent_name']}")
        
        try:
            # 调用OpenAI格式处理方法
            result = await self.agent_service._process_with_openai_format(mock_agent, ai_client_data)
            
            print("AI处理结果:")
            print("-" * 50)
            print(f"分析结果: {result.get('analysis_result', 'N/A')}")
            print(f"关键发现: {result.get('key_findings', [])}")
            print(f"建议: {result.get('recommendations', [])}")
            print(f"置信度: {result.get('confidence_score', 0)}")
            print(f"总结: {result.get('summary', 'N/A')}")
            print(f"使用模型: {result.get('model_used', 'N/A')}")
            print("-" * 50)
            
            # 验证结果格式
            required_fields = ['analysis_result', 'key_findings', 'recommendations', 'confidence_score', 'summary']
            missing_fields = []
            
            for field in required_fields:
                if field not in result:
                    missing_fields.append(field)
            
            if not missing_fields:
                print("[OK] AI处理结果格式正确")
                return True
            else:
                print(f"[ERROR] 结果缺少字段: {missing_fields}")
                return False
                
        except Exception as e:
            print(f"[ERROR] AI处理失败: {e}")
            return False
    
    def test_data_consistency_with_human_tasks(self):
        """测试与人类任务的数据一致性"""
        print("\n测试6: 与人类任务数据一致性验证")
        
        # 比较AI任务和人类任务的输入数据结构
        ai_input_data = self.mock_task['input_data']
        
        # 验证关键字段存在
        consistency_checks = [
            ('immediate_upstream', 'immediate_upstream' in ai_input_data),
            ('workflow_global', 'workflow_global' in ai_input_data),
            ('node_info', 'node_info' in ai_input_data),
            ('task_title', bool(self.mock_task.get('task_title'))),
            ('task_description', bool(self.mock_task.get('task_description'))),
            ('instructions', bool(self.mock_task.get('instructions')))
        ]
        
        print("数据一致性检查:")
        all_passed = True
        for check_name, passed in consistency_checks:
            status = "[OK] 通过" if passed else "[ERROR] 失败"
            print(f"  {check_name}: {status}")
            if not passed:
                all_passed = False
        
        # 验证上游数据结构
        immediate_upstream = ai_input_data.get('immediate_upstream', {})
        if immediate_upstream:
            sample_node = next(iter(immediate_upstream.values()))
            upstream_structure_checks = [
                ('node_name', 'node_name' in sample_node),
                ('output_data', 'output_data' in sample_node),
                ('completed_at', 'completed_at' in sample_node)
            ]
            
            print("上游数据结构检查:")
            for check_name, passed in upstream_structure_checks:
                status = "[OK] 通过" if passed else "[ERROR] 失败"
                print(f"  {check_name}: {status}")
                if not passed:
                    all_passed = False
        
        if all_passed:
            print("[OK] AI任务与人类任务数据结构完全一致")
            return True
        else:
            print("[ERROR] 数据结构存在不一致")
            return False
    
    async def run_complete_test(self):
        """运行完整测试"""
        print("开始AI处理器完整测试")
        print("=" * 60)
        
        try:
            # 1. 设置数据
            self.setup_test_data()
            
            # 2. 执行各项测试
            tests = [
                ("系统Prompt生成", self.test_system_prompt_generation()),
                ("上游上下文预处理", self.test_upstream_context_preprocessing()),
                ("用户消息构建", self.test_user_message_construction()),
                ("AI Client数据结构", self.test_ai_client_data_structure()[0]),
                ("模拟AI处理", await self.test_mock_ai_processing()),
                ("数据一致性验证", self.test_data_consistency_with_human_tasks())
            ]
            
            # 3. 统计结果
            print("\n" + "=" * 60)
            print("测试结果总结:")
            
            passed_count = 0
            for test_name, result in tests:
                status = "[OK] 通过" if result else "[ERROR] 失败"
                print(f"  {test_name}: {status}")
                if result:
                    passed_count += 1
            
            success_rate = (passed_count / len(tests)) * 100
            print(f"\n测试通过率: {passed_count}/{len(tests)} ({success_rate:.0f}%)")
            
            if passed_count == len(tests):
                print("\n[SUCCESS] 所有测试通过！AI处理器已成功适配人类任务数据结构。")
                return True
            else:
                print("\n[WARNING] 部分测试失败，需要进一步调整。")
                return False
                
        except Exception as e:
            print(f"[ERROR] 测试执行失败: {e}")
            return False


async def main():
    """主函数"""
    test = AIProcessorTest()
    success = await test.run_complete_test()
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    
    if result:
        print("\n[SUCCESS] AI处理器测试成功完成！")
    else:
        print("\n[ERROR] AI处理器测试未完全通过！")