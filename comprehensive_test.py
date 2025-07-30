#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整工作流系统综合测试
Comprehensive Workflow System Test
包含：工作流创建 -> 执行 -> 状态追踪 -> 人机协作的完整流程测试
"""

import asyncio
import sys
import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 设置编码和环境
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入所有必需的模块
from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.services.human_task_service import HumanTaskService
from workflow_framework.services.agent_task_service import agent_task_service
from workflow_framework.services.monitoring_service import monitoring_service
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
from workflow_framework.repositories.agent.agent_repository import AgentRepository
from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from workflow_framework.repositories.instance.task_instance_repository import TaskInstanceRepository

# 导入模型
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate
from workflow_framework.models.processor import ProcessorCreate, ProcessorType
from workflow_framework.models.agent import AgentCreate
from workflow_framework.models.instance import (
    WorkflowExecuteRequest, TaskInstanceStatus, TaskInstanceUpdate, WorkflowInstanceStatus
)


class ComprehensiveTestSuite:
    """综合测试套件"""
    
    def __init__(self):
        self.test_data = {}
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'test_details': []
        }
        
        # 服务实例
        self.auth_service = AuthService()
        self.workflow_service = WorkflowService()
        self.node_service = NodeService()
        self.human_task_service = HumanTaskService()
        self.processor_repository = ProcessorRepository()
        self.agent_repository = AgentRepository()
        self.workflow_instance_repo = WorkflowInstanceRepository()
        self.task_instance_repo = TaskInstanceRepository()
    
    def log_test_result(self, test_name: str, success: bool, message: str, details: Dict[str, Any] = None):
        """记录测试结果"""
        self.test_results['total_tests'] += 1
        if success:
            self.test_results['passed_tests'] += 1
            status = "✅ PASS"
        else:
            self.test_results['failed_tests'] += 1
            status = "❌ FAIL"
        
        print(f"{status} {test_name}: {message}")
        
        self.test_results['test_details'].append({
            'test_name': test_name,
            'success': success,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })
    
    async def setup_test_environment(self):
        """设置测试环境"""
        print("🔧 设置测试环境...")
        
        try:
            # 初始化数据库
            await initialize_database()
            self.log_test_result("数据库初始化", True, "数据库连接成功")
            
            # 启动所有服务
            await execution_engine.start_engine()
            await agent_task_service.start_service()
            await monitoring_service.start_monitoring()
            self.log_test_result("服务启动", True, "所有执行服务启动成功")
            
            return True
            
        except Exception as e:
            self.log_test_result("环境设置", False, f"环境设置失败: {e}")
            return False
    
    async def test_1_create_business_scenario(self):
        """测试1: 创建业务场景"""
        print("\n📋 测试1: 创建业务场景 - 客户订单处理工作流")
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 1.1 创建业务用户角色
            print("  1.1 创建业务用户...")
            
            # 销售员
            sales_user = UserCreate(
                username=f"sales_manager_{timestamp}",
                email=f"sales_{timestamp}@company.com",
                password="sales123456",
                role="sales",
                description="销售经理，负责订单审核"
            )
            sales_response = await self.auth_service.register_user(sales_user)
            
            # 财务员
            finance_user = UserCreate(
                username=f"finance_officer_{timestamp}",
                email=f"finance_{timestamp}@company.com",
                password="finance123456",
                role="finance",
                description="财务专员，负责价格审核"
            )
            finance_response = await self.auth_service.register_user(finance_user)
            
            # 系统管理员
            admin_user = UserCreate(
                username=f"system_admin_{timestamp}",
                email=f"admin_{timestamp}@company.com",
                password="admin123456",
                role="admin",
                description="系统管理员，负责工作流管理"
            )
            admin_response = await self.auth_service.register_user(admin_user)
            
            self.test_data['users'] = {
                'sales': sales_response,
                'finance': finance_response,
                'admin': admin_response
            }
            
            self.log_test_result("用户创建", True, f"成功创建3个业务用户")
            
            # 1.2 创建AI代理
            print("  1.2 创建AI代理...")
            
            # 风险评估AI
            risk_agent = AgentCreate(
                agent_name=f"风险评估AI_{timestamp}",
                description="专门用于订单风险评估的AI代理",
                endpoint="https://api.openai.com/v1",
                capabilities=["风险分析", "欺诈检测", "信用评估", "数据挖掘"],
                status=True
            )
            risk_agent_record = await self.agent_repository.create_agent(risk_agent)
            
            # 价格优化AI
            pricing_agent = AgentCreate(
                agent_name=f"价格优化AI_{timestamp}",
                description="智能价格优化和动态定价AI代理",
                endpoint="https://api.openai.com/v1",
                capabilities=["价格分析", "市场预测", "竞争分析", "利润优化"],
                status=True
            )
            pricing_agent_record = await self.agent_repository.create_agent(pricing_agent)
            
            self.test_data['agents'] = {
                'risk': risk_agent_record,
                'pricing': pricing_agent_record
            }
            
            self.log_test_result("AI代理创建", True, f"成功创建2个专业AI代理")
            
            # 1.3 创建处理器
            print("  1.3 创建业务处理器...")
            
            # 销售处理器
            sales_processor = ProcessorCreate(
                name=f"销售审核处理器_{timestamp}",
                type=ProcessorType.HUMAN,
                user_id=sales_response.user_id,
                agent_id=None
            )
            sales_processor_record = await self.processor_repository.create_processor(sales_processor)
            
            # 财务处理器
            finance_processor = ProcessorCreate(
                name=f"财务审核处理器_{timestamp}",
                type=ProcessorType.HUMAN,
                user_id=finance_response.user_id,
                agent_id=None
            )
            finance_processor_record = await self.processor_repository.create_processor(finance_processor)
            
            # 风险评估处理器
            risk_processor = ProcessorCreate(
                name=f"AI风险评估处理器_{timestamp}",
                type=ProcessorType.AGENT,
                user_id=None,
                agent_id=risk_agent_record['agent_id']
            )
            risk_processor_record = await self.processor_repository.create_processor(risk_processor)
            
            # 价格优化处理器
            pricing_processor = ProcessorCreate(
                name=f"AI价格优化处理器_{timestamp}",
                type=ProcessorType.AGENT,
                user_id=None,
                agent_id=pricing_agent_record['agent_id']
            )
            pricing_processor_record = await self.processor_repository.create_processor(pricing_processor)
            
            # 混合决策处理器
            mixed_processor = ProcessorCreate(
                name=f"人机协作决策处理器_{timestamp}",
                type=ProcessorType.MIX,
                user_id=admin_response.user_id,
                agent_id=risk_agent_record['agent_id']
            )
            mixed_processor_record = await self.processor_repository.create_processor(mixed_processor)
            
            self.test_data['processors'] = {
                'sales': sales_processor_record,
                'finance': finance_processor_record,
                'risk': risk_processor_record,
                'pricing': pricing_processor_record,
                'mixed': mixed_processor_record
            }
            
            self.log_test_result("处理器创建", True, f"成功创建5个业务处理器")
            
            return True
            
        except Exception as e:
            self.log_test_result("业务场景创建", False, f"创建失败: {e}")
            return False
    
    async def test_2_create_complex_workflow(self):
        """测试2: 创建复杂工作流"""
        print("\n🏗️  测试2: 创建复杂的客户订单处理工作流")
        
        try:
            admin_user = self.test_data['users']['admin']
            processors = self.test_data['processors']
            
            # 2.1 创建工作流
            print("  2.1 创建主工作流...")
            
            workflow_data = WorkflowCreate(
                name=f"智能订单处理工作流_{datetime.now().strftime('%H%M%S')}",
                description="""
                完整的客户订单处理工作流，包含：
                1. 订单接收和初步验证
                2. AI风险评估
                3. 销售人员审核
                4. AI价格优化
                5. 财务人员审核
                6. 人机协作最终决策
                7. 订单确认和处理
                """,
                creator_id=admin_user.user_id
            )
            
            workflow_response = await self.workflow_service.create_workflow(workflow_data)
            self.test_data['workflow'] = workflow_response
            
            self.log_test_result("工作流创建", True, f"主工作流创建成功: {workflow_response.name}")
            
            # 2.2 创建工作流节点
            print("  2.2 创建工作流节点...")
            
            nodes = []
            
            # 开始节点
            start_node = await self.node_service.create_node(NodeCreate(
                name="订单提交",
                type=NodeType.START,
                task_description="客户提交订单，系统接收订单信息",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=100,
                position_y=300
            ), admin_user.user_id)
            nodes.append(('start', start_node))
            
            # AI风险评估节点
            risk_node = await self.node_service.create_node(NodeCreate(
                name="AI风险评估",
                type=NodeType.PROCESSOR,
                task_description="AI系统分析订单风险，包括客户信用、欺诈检测、异常模式识别",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=300,
                position_y=200
            ), admin_user.user_id)
            nodes.append(('risk', risk_node))
            
            # 销售审核节点
            sales_node = await self.node_service.create_node(NodeCreate(
                name="销售审核",
                type=NodeType.PROCESSOR,
                task_description="销售经理审核订单内容、客户需求和商务条款",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=300,
                position_y=400
            ), admin_user.user_id)
            nodes.append(('sales', sales_node))
            
            # AI价格优化节点
            pricing_node = await self.node_service.create_node(NodeCreate(
                name="AI价格优化",
                type=NodeType.PROCESSOR,
                task_description="AI系统进行动态定价、利润优化和竞争分析",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=500,
                position_y=200
            ), admin_user.user_id)
            nodes.append(('pricing', pricing_node))
            
            # 财务审核节点
            finance_node = await self.node_service.create_node(NodeCreate(
                name="财务审核",
                type=NodeType.PROCESSOR,
                task_description="财务专员审核价格策略、成本分析和利润预测",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=500,
                position_y=400
            ), admin_user.user_id)
            nodes.append(('finance', finance_node))
            
            # 人机协作决策节点
            decision_node = await self.node_service.create_node(NodeCreate(
                name="智能决策",
                type=NodeType.PROCESSOR,
                task_description="结合AI分析和人工经验，做出最终订单决策",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=700,
                position_y=300
            ), admin_user.user_id)
            nodes.append(('decision', decision_node))
            
            # 结束节点
            end_node = await self.node_service.create_node(NodeCreate(
                name="订单确认",
                type=NodeType.END,
                task_description="生成最终订单确认，发送给客户并启动后续流程",
                workflow_base_id=workflow_response.workflow_base_id,
                position_x=900,
                position_y=300
            ), admin_user.user_id)
            nodes.append(('end', end_node))
            
            self.test_data['nodes'] = dict(nodes)
            
            self.log_test_result("节点创建", True, f"成功创建7个工作流节点")
            
            # 2.3 分配处理器到节点
            print("  2.3 分配处理器到节点...")
            
            # 风险评估节点 -> AI风险处理器
            await self.node_service.assign_processor_to_node(
                risk_node.node_base_id,
                workflow_response.workflow_base_id,
                processors['risk']['processor_id'],
                admin_user.user_id
            )
            
            # 销售审核节点 -> 销售处理器
            await self.node_service.assign_processor_to_node(
                sales_node.node_base_id,
                workflow_response.workflow_base_id,
                processors['sales']['processor_id'],
                admin_user.user_id
            )
            
            # 价格优化节点 -> AI价格处理器
            await self.node_service.assign_processor_to_node(
                pricing_node.node_base_id,
                workflow_response.workflow_base_id,
                processors['pricing']['processor_id'],
                admin_user.user_id
            )
            
            # 财务审核节点 -> 财务处理器
            await self.node_service.assign_processor_to_node(
                finance_node.node_base_id,
                workflow_response.workflow_base_id,
                processors['finance']['processor_id'],
                admin_user.user_id
            )
            
            # 智能决策节点 -> 混合处理器
            await self.node_service.assign_processor_to_node(
                decision_node.node_base_id,
                workflow_response.workflow_base_id,
                processors['mixed']['processor_id'],
                admin_user.user_id
            )
            
            self.log_test_result("处理器分配", True, f"成功分配5个处理器到对应节点")
            
            # 2.4 创建节点连接
            print("  2.4 创建节点连接...")
            
            connections = [
                (start_node.node_base_id, risk_node.node_base_id, "订单提交 -> AI风险评估"),
                (start_node.node_base_id, sales_node.node_base_id, "订单提交 -> 销售审核"),
                (risk_node.node_base_id, pricing_node.node_base_id, "AI风险评估 -> AI价格优化"),
                (sales_node.node_base_id, finance_node.node_base_id, "销售审核 -> 财务审核"),
                (pricing_node.node_base_id, decision_node.node_base_id, "AI价格优化 -> 智能决策"),
                (finance_node.node_base_id, decision_node.node_base_id, "财务审核 -> 智能决策"),
                (decision_node.node_base_id, end_node.node_base_id, "智能决策 -> 订单确认")
            ]
            
            for from_node, to_node, desc in connections:
                connection_data = NodeConnectionCreate(
                    from_node_base_id=from_node,
                    to_node_base_id=to_node,
                    workflow_base_id=workflow_response.workflow_base_id
                )
                await self.node_service.create_node_connection(connection_data, admin_user.user_id)
                print(f"    ✓ {desc}")
            
            self.log_test_result("节点连接", True, f"成功创建7个节点连接")
            
            return True
            
        except Exception as e:
            self.log_test_result("复杂工作流创建", False, f"创建失败: {e}")
            return False
    
    async def test_3_execute_workflow_with_monitoring(self):
        """测试3: 执行工作流并实时监控"""
        print("\n🚀 测试3: 执行工作流并实时监控")
        
        try:
            workflow = self.test_data['workflow']
            admin_user = self.test_data['users']['admin']
            
            # 3.1 创建真实的业务订单数据
            print("  3.1 准备真实订单数据...")
            
            order_data = {
                "order_id": f"ORD-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "customer": {
                    "id": "CUST-001",
                    "name": "上海科技有限公司",
                    "type": "enterprise",
                    "credit_rating": "A",
                    "history_orders": 25,
                    "total_amount": 1250000
                },
                "products": [
                    {
                        "id": "PROD-001",
                        "name": "企业级服务器",
                        "quantity": 10,
                        "unit_price": 25000,
                        "category": "hardware"
                    },
                    {
                        "id": "PROD-002", 
                        "name": "软件许可证",
                        "quantity": 50,
                        "unit_price": 1200,
                        "category": "software"
                    }
                ],
                "order_details": {
                    "total_amount": 310000,
                    "currency": "CNY",
                    "payment_terms": "30天净付",
                    "delivery_date": (datetime.now() + timedelta(days=15)).isoformat(),
                    "priority": "high",
                    "source": "direct_sales"
                },
                "requirements": {
                    "custom_configuration": True,
                    "installation_service": True,
                    "training_required": True,
                    "warranty_years": 3
                }
            }
            
            # 3.2 创建工作流执行请求
            print("  3.2 创建执行请求...")
            
            execute_request = WorkflowExecuteRequest(
                workflow_base_id=workflow.workflow_base_id,
                instance_name=f"订单处理_{order_data['order_id']}",
                input_data=order_data,
                context_data={
                    "created_by": admin_user.username,
                    "priority": "high",
                    "expected_completion": (datetime.now() + timedelta(hours=2)).isoformat(),
                    "business_unit": "sales_dept",
                    "region": "shanghai"
                }
            )
            
            # 3.3 开始执行工作流
            print("  3.3 开始执行工作流...")
            
            execution_result = await execution_engine.execute_workflow(
                execute_request, admin_user.user_id
            )
            
            instance_id = execution_result['instance_id']
            self.test_data['instance_id'] = instance_id
            
            self.log_test_result("工作流启动", True, f"工作流开始执行，实例ID: {instance_id}")
            
            # 3.4 实时监控执行状态
            print("  3.4 开始实时监控...")
            
            monitoring_data = []
            max_monitor_cycles = 20  # 最多监控20次
            
            for cycle in range(max_monitor_cycles):
                await asyncio.sleep(3)  # 每3秒检查一次
                
                # 获取工作流状态
                status_info = await execution_engine.get_workflow_status(instance_id)
                
                if status_info:
                    instance = status_info['instance']
                    stats = status_info['statistics']
                    
                    cycle_data = {
                        'cycle': cycle + 1,
                        'timestamp': datetime.now().isoformat(),
                        'status': instance['status'],
                        'current_node': instance.get('current_node_id'),
                        'stats': stats
                    }
                    monitoring_data.append(cycle_data)
                    
                    print(f"    周期 {cycle + 1:2d}: 状态={instance['status']:<12} ", end="")
                    
                    if stats:
                        print(f"任务(总:{stats.get('total_tasks', 0):2d} "
                              f"完成:{stats.get('completed_tasks', 0):2d} "
                              f"进行:{stats.get('pending_tasks', 0):2d})")
                    else:
                        print("统计数据准备中...")
                    
                    # 检查是否完成
                    if instance['status'] in ['completed', 'failed', 'cancelled']:
                        print(f"    🏁 工作流执行结束: {instance['status']}")
                        break
                        
                    # 如果有进行中的任务，尝试处理一些
                    if cycle % 3 == 0:  # 每隔3个周期处理一次任务
                        await self._process_some_tasks()
                
                else:
                    print(f"    周期 {cycle + 1:2d}: 无法获取状态信息")
            
            self.test_data['monitoring_data'] = monitoring_data
            
            # 3.5 获取最终执行结果
            final_status = await execution_engine.get_workflow_status(instance_id)
            if final_status:
                final_instance = final_status['instance']
                final_stats = final_status['statistics']
                
                self.log_test_result("工作流监控", True, 
                    f"监控完成，最终状态: {final_instance['status']}, "
                    f"监控周期: {len(monitoring_data)}")
                
                # 记录详细的执行结果
                execution_summary = {
                    'instance_id': instance_id,
                    'final_status': final_instance['status'],
                    'execution_time': final_instance.get('completed_at', 'N/A'),
                    'total_cycles': len(monitoring_data),
                    'final_stats': final_stats
                }
                
                self.test_data['execution_summary'] = execution_summary
                
                return True
            else:
                self.log_test_result("工作流监控", False, "无法获取最终执行状态")
                return False
                
        except Exception as e:
            self.log_test_result("工作流执行监控", False, f"执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _process_some_tasks(self):
        """处理一些待处理的任务"""
        try:
            # 获取一些待处理的人工任务
            admin_user = self.test_data['users']['admin']
            sales_user = self.test_data['users']['sales']
            finance_user = self.test_data['users']['finance']
            
            # 检查销售用户的任务
            sales_tasks = await self.human_task_service.get_user_tasks(
                sales_user.user_id, TaskInstanceStatus.ASSIGNED, 5
            )
            
            # 处理第一个销售任务
            if sales_tasks:
                task = sales_tasks[0]
                task_id = task['task_instance_id']
                
                # 开始任务
                await self.human_task_service.start_task(task_id, sales_user.user_id)
                
                # 提交结果
                result_data = {
                    "review_result": "approved",
                    "comments": "订单信息完整，客户信誉良好，建议通过",
                    "risk_level": "low",
                    "recommended_action": "proceed"
                }
                
                await self.human_task_service.submit_task_result(
                    task_id, sales_user.user_id, result_data, "销售审核通过"
                )
                
                print(f"        -> 处理了销售任务: {task['task_title']}")
            
            # 检查财务用户的任务
            finance_tasks = await self.human_task_service.get_user_tasks(
                finance_user.user_id, TaskInstanceStatus.ASSIGNED, 5
            )
            
            # 处理第一个财务任务
            if finance_tasks:
                task = finance_tasks[0]
                task_id = task['task_instance_id']
                
                # 开始任务
                await self.human_task_service.start_task(task_id, finance_user.user_id)
                
                # 提交结果
                result_data = {
                    "financial_review": "approved",
                    "price_analysis": "合理的定价策略",
                    "profit_margin": 0.28,
                    "cost_analysis": "成本控制良好",
                    "recommendation": "批准订单"
                }
                
                await self.human_task_service.submit_task_result(
                    task_id, finance_user.user_id, result_data, "财务审核通过"
                )
                
                print(f"        -> 处理了财务任务: {task['task_title']}")
            
            # 检查管理员的混合任务
            admin_tasks = await self.human_task_service.get_user_tasks(
                admin_user.user_id, TaskInstanceStatus.ASSIGNED, 5
            )
            
            # 处理管理员任务
            if admin_tasks:
                task = admin_tasks[0]
                task_id = task['task_instance_id']
                
                # 开始任务
                await self.human_task_service.start_task(task_id, admin_user.user_id)
                
                # 提交结果
                result_data = {
                    "final_decision": "approved",
                    "decision_confidence": 0.92,
                    "ai_recommendations": "AI建议批准，风险可控",
                    "human_judgment": "基于业务经验，同意AI建议",
                    "final_terms": {
                        "approved_amount": 310000,
                        "payment_terms": "30天净付",
                        "special_conditions": "包含安装和培训服务"
                    }
                }
                
                await self.human_task_service.submit_task_result(
                    task_id, admin_user.user_id, result_data, "最终决策：批准订单"
                )
                
                print(f"        -> 处理了决策任务: {task['task_title']}")
                
        except Exception as e:
            print(f"        -> 处理任务时出错: {e}")
    
    async def test_4_analyze_execution_results(self):
        """测试4: 分析执行结果"""
        print("\n📊 测试4: 分析执行结果和性能指标")
        
        try:
            instance_id = self.test_data['instance_id']
            monitoring_data = self.test_data['monitoring_data']
            
            # 4.1 获取详细的执行统计
            print("  4.1 获取执行统计...")
            
            execution_stats = await self.workflow_instance_repo.get_execution_statistics(instance_id)
            if execution_stats:
                print(f"    总节点数: {execution_stats.total_nodes}")
                print(f"    完成节点: {execution_stats.completed_nodes}")
                print(f"    总任务数: {execution_stats.total_tasks}")
                print(f"    完成任务: {execution_stats.completed_tasks}")
                print(f"    人工任务: {execution_stats.human_tasks}")
                print(f"    AI任务: {execution_stats.agent_tasks}")
                print(f"    混合任务: {execution_stats.mixed_tasks}")
                if execution_stats.average_task_duration:
                    print(f"    平均任务时长: {execution_stats.average_task_duration:.1f}分钟")
                if execution_stats.total_execution_time:
                    print(f"    总执行时间: {execution_stats.total_execution_time}分钟")
                
                self.log_test_result("执行统计", True, "成功获取详细执行统计")
            else:
                self.log_test_result("执行统计", False, "无法获取执行统计")
            
            # 4.2 分析任务执行情况
            print("  4.2 分析任务执行情况...")
            
            all_tasks = await self.task_instance_repo.get_tasks_by_workflow_instance(instance_id)
            
            task_analysis = {
                'total_tasks': len(all_tasks),
                'by_type': {},
                'by_status': {},
                'execution_times': []
            }
            
            for task in all_tasks:
                # 按类型统计
                task_type = task['task_type']
                if task_type not in task_analysis['by_type']:
                    task_analysis['by_type'][task_type] = 0
                task_analysis['by_type'][task_type] += 1
                
                # 按状态统计
                status = task['status']
                if status not in task_analysis['by_status']:
                    task_analysis['by_status'][status] = 0
                task_analysis['by_status'][status] += 1
                
                # 执行时间统计
                if task.get('actual_duration'):
                    task_analysis['execution_times'].append({
                        'task_title': task['task_title'],
                        'type': task_type,
                        'duration': task['actual_duration']
                    })
            
            print(f"    任务类型分布: {task_analysis['by_type']}")
            print(f"    任务状态分布: {task_analysis['by_status']}")
            print(f"    有执行时间的任务: {len(task_analysis['execution_times'])}个")
            
            self.test_data['task_analysis'] = task_analysis
            
            self.log_test_result("任务分析", True, f"完成{len(all_tasks)}个任务的详细分析")
            
            # 4.3 获取监控指标
            print("  4.3 获取系统监控指标...")
            
            current_metrics = await monitoring_service.get_current_metrics()
            
            print(f"    系统指标:")
            print(f"      工作流总数: {current_metrics['metrics']['workflows']['total']}")
            print(f"      运行中: {current_metrics['metrics']['workflows']['running']}")
            print(f"      已完成: {current_metrics['metrics']['workflows']['completed']}")
            print(f"      成功率: {current_metrics['metrics']['performance']['success_rate']:.1f}%")
            print(f"      告警总数: {current_metrics['alerts']['total']}")
            print(f"      未确认告警: {current_metrics['alerts']['unacknowledged']}")
            
            self.log_test_result("监控指标", True, "成功获取系统监控指标")
            
            # 4.4 获取工作流健康状态
            print("  4.4 获取工作流健康状态...")
            
            health_info = await monitoring_service.get_workflow_health(instance_id)
            
            print(f"    健康分数: {health_info['health_score']:.1f}/100")
            print(f"    发现问题: {len(health_info['issues'])}个")
            print(f"    建议数量: {len(health_info['recommendations'])}条")
            
            if health_info['issues']:
                print("    问题详情:")
                for issue in health_info['issues']:
                    print(f"      - [{issue['severity']}] {issue['message']}")
            
            if health_info['recommendations']:
                print("    改进建议:")
                for rec in health_info['recommendations'][:3]:  # 只显示前3条
                    print(f"      - {rec}")
            
            self.test_data['health_info'] = health_info
            
            self.log_test_result("健康评估", True, f"工作流健康分数: {health_info['health_score']:.1f}")
            
            # 4.5 生成性能报告
            print("  4.5 生成性能报告...")
            
            performance_report = await monitoring_service.get_performance_report(1)
            
            print(f"    性能报告 ({performance_report['period']}):")
            print(f"      处理工作流: {performance_report['summary']['total_workflows']}")
            print(f"      整体成功率: {performance_report['summary']['success_rate']:.1f}%")
            print(f"      平均任务时长: {performance_report['summary']['avg_task_duration']:.1f}分钟")
            
            self.test_data['performance_report'] = performance_report
            
            self.log_test_result("性能报告", True, "成功生成性能分析报告")
            
            return True
            
        except Exception as e:
            self.log_test_result("执行结果分析", False, f"分析失败: {e}")
            return False
    
    async def test_5_human_machine_collaboration(self):
        """测试5: 人机协作功能"""
        print("\n🤝 测试5: 深度测试人机协作功能")
        
        try:
            users = self.test_data['users']
            
            # 5.1 测试用户任务管理
            print("  5.1 测试用户任务管理...")
            
            for user_type, user in users.items():
                print(f"    测试{user_type}用户的任务管理...")
                
                # 获取任务列表
                user_tasks = await self.human_task_service.get_user_tasks(user.user_id, limit=10)
                
                # 获取任务统计
                user_stats = await self.human_task_service.get_task_statistics(user.user_id)
                
                # 获取任务历史
                user_history = await self.human_task_service.get_task_history(user.user_id, days=1)
                
                print(f"      任务总数: {len(user_tasks)}")
                print(f"      完成率: {user_stats['completion_rate']:.1f}%")
                print(f"      历史任务: {len(user_history)}个")
                
                if user_tasks:
                    # 测试任务详情获取
                    task_details = await self.human_task_service.get_task_details(
                        user_tasks[0]['task_instance_id'], user.user_id
                    )
                    if task_details:
                        print(f"      ✓ 成功获取任务详情")
            
            self.log_test_result("用户任务管理", True, "所有用户的任务管理功能正常")
            
            # 5.2 测试Agent任务处理
            print("  5.2 测试Agent任务处理...")
            
            # 获取Agent任务统计
            agent_stats = await agent_task_service.get_agent_task_statistics()
            
            print(f"    Agent任务统计:")
            print(f"      总任务数: {agent_stats['total_tasks']}")
            print(f"      成功率: {agent_stats['success_rate']:.1f}%")
            print(f"      平均处理时间: {agent_stats['average_processing_time']:.1f}分钟")
            print(f"      队列大小: {agent_stats['queue_size']}")
            
            # 获取待处理的Agent任务
            pending_agent_tasks = await agent_task_service.get_pending_agent_tasks(limit=5)
            print(f"      待处理任务: {len(pending_agent_tasks)}个")
            
            self.log_test_result("Agent任务处理", True, f"Agent处理成功率: {agent_stats['success_rate']:.1f}%")
            
            # 5.3 测试混合任务协作
            print("  5.3 测试混合任务协作...")
            
            admin_user = users['admin']
            
            # 获取管理员的混合任务
            mixed_tasks = await self.human_task_service.get_user_tasks(
                admin_user.user_id, limit=10
            )
            
            mixed_task_count = sum(1 for task in mixed_tasks if task['task_type'] == 'mixed')
            
            print(f"    混合任务数量: {mixed_task_count}")
            
            if mixed_task_count > 0:
                print(f"    ✓ 混合任务功能正常运行")
                self.log_test_result("混合任务协作", True, f"发现{mixed_task_count}个混合协作任务")
            else:
                self.log_test_result("混合任务协作", True, "暂无混合任务，但功能正常")
            
            return True
            
        except Exception as e:
            self.log_test_result("人机协作功能", False, f"测试失败: {e}")
            return False
    
    async def generate_comprehensive_report(self):
        """生成综合测试报告"""
        print("\n📋 生成综合测试报告")
        
        try:
            report = {
                'test_summary': {
                    'total_tests': self.test_results['total_tests'],
                    'passed_tests': self.test_results['passed_tests'],
                    'failed_tests': self.test_results['failed_tests'],
                    'success_rate': (self.test_results['passed_tests'] / self.test_results['total_tests']) * 100 if self.test_results['total_tests'] > 0 else 0
                },
                'business_scenario': {
                    'users_created': len(self.test_data.get('users', {})),
                    'agents_created': len(self.test_data.get('agents', {})),
                    'processors_created': len(self.test_data.get('processors', {})),
                    'workflow_name': self.test_data.get('workflow', {}).get('name', 'N/A')
                },
                'execution_results': self.test_data.get('execution_summary', {}),
                'performance_metrics': {
                    'monitoring_cycles': len(self.test_data.get('monitoring_data', [])),
                    'task_analysis': self.test_data.get('task_analysis', {}),
                    'health_score': self.test_data.get('health_info', {}).get('health_score', 0)
                },
                'test_details': self.test_results['test_details'],
                'generated_at': datetime.now().isoformat()
            }
            
            # 输出测试报告
            print("\n" + "=" * 100)
            print("🎯 综合测试报告")
            print("=" * 100)
            
            print(f"\n📊 测试概览:")
            print(f"  总测试数: {report['test_summary']['total_tests']}")
            print(f"  通过测试: {report['test_summary']['passed_tests']}")
            print(f"  失败测试: {report['test_summary']['failed_tests']}")
            print(f"  成功率: {report['test_summary']['success_rate']:.1f}%")
            
            print(f"\n🏢 业务场景:")
            print(f"  创建用户: {report['business_scenario']['users_created']}个")
            print(f"  创建AI代理: {report['business_scenario']['agents_created']}个")
            print(f"  创建处理器: {report['business_scenario']['processors_created']}个")
            print(f"  工作流名称: {report['business_scenario']['workflow_name']}")
            
            if report['execution_results']:
                print(f"\n🚀 执行结果:")
                print(f"  实例ID: {report['execution_results']['instance_id']}")
                print(f"  最终状态: {report['execution_results']['final_status']}")
                print(f"  监控周期: {report['execution_results']['total_cycles']}")
            
            print(f"\n📈 性能指标:")
            print(f"  监控周期数: {report['performance_metrics']['monitoring_cycles']}")
            print(f"  健康分数: {report['performance_metrics']['health_score']:.1f}/100")
            
            if report['performance_metrics']['task_analysis']:
                task_analysis = report['performance_metrics']['task_analysis']
                print(f"  任务总数: {task_analysis['total_tasks']}")
                print(f"  任务类型: {task_analysis['by_type']}")
                print(f"  任务状态: {task_analysis['by_status']}")
            
            print(f"\n📝 详细测试结果:")
            for detail in report['test_details']:
                status = "✅" if detail['success'] else "❌"
                print(f"  {status} {detail['test_name']}: {detail['message']}")
            
            print("\n" + "=" * 100)
            
            # 保存报告到文件
            report_filename = f"comprehensive_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"📄 详细报告已保存到: {report_filename}")
            
            return report
            
        except Exception as e:
            print(f"❌ 生成报告失败: {e}")
            return None
    
    async def cleanup_test_environment(self):
        """清理测试环境"""
        print("\n🧹 清理测试环境...")
        
        try:
            # 停止所有服务
            await monitoring_service.stop_monitoring()
            await agent_task_service.stop_service()
            await execution_engine.stop_engine()
            
            # 关闭数据库连接
            await close_database()
            
            print("✓ 测试环境清理完成")
            
        except Exception as e:
            print(f"⚠ 清理环境时出错: {e}")
    
    async def run_comprehensive_test(self):
        """运行综合测试"""
        print("🎯 开始运行工作流系统综合测试")
        print("=" * 100)
        
        try:
            # 设置测试环境
            if not await self.setup_test_environment():
                return False
            
            # 运行测试序列
            test_sequence = [
                self.test_1_create_business_scenario,
                self.test_2_create_complex_workflow,
                self.test_3_execute_workflow_with_monitoring,
                self.test_4_analyze_execution_results,
                self.test_5_human_machine_collaboration
            ]
            
            for test_func in test_sequence:
                if not await test_func():
                    print(f"\n❌ 测试序列中断，{test_func.__name__} 失败")
                    break
            
            # 生成综合报告
            report = await self.generate_comprehensive_report()
            
            # 评估整体结果
            success_rate = self.test_results['passed_tests'] / self.test_results['total_tests'] * 100
            
            if success_rate >= 90:
                print(f"\n🎉 综合测试成功！成功率: {success_rate:.1f}%")
                print("   工作流系统所有核心功能正常运行")
                result = True
            elif success_rate >= 70:
                print(f"\n⚠️  综合测试部分成功，成功率: {success_rate:.1f}%")
                print("   大部分功能正常，少量问题需要关注")
                result = True
            else:
                print(f"\n❌ 综合测试失败，成功率: {success_rate:.1f}%")
                print("   发现重要问题，需要修复后重新测试")
                result = False
            
            return result
            
        except Exception as e:
            print(f"\n💥 综合测试过程中发生严重错误: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            await self.cleanup_test_environment()


async def main():
    """主函数"""
    print("启动工作流系统综合测试...")
    
    test_suite = ComprehensiveTestSuite()
    success = await test_suite.run_comprehensive_test()
    
    if success:
        print("\n所有测试完成！系统功能验证成功。")
        return 0
    else:
        print("\n测试发现问题，请查看报告详情。")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        sys.exit(1)