# 新工作流上下文管理架构

## 概述

这是一个全新设计的工作流上下文管理架构，旨在解决原有架构中的线程安全、资源管理、依赖关系管理等问题。新架构采用模块化设计，提供了更好的可扩展性、性能和可维护性。

## 架构组件

### 1. WorkflowInstanceContext (工作流实例上下文)
**文件**: `workflow_instance_context.py`

**功能**:
- 为每个工作流实例提供独立的上下文管理空间
- 线程安全的状态管理和数据流控制
- 节点执行状态跟踪和依赖关系管理
- 支持工作流暂停、恢复、取消等操作

**主要特性**:
- 使用 `threading.RLock()` 确保线程安全
- 完整的节点生命周期管理（PENDING → READY → EXECUTING → COMPLETED/FAILED）
- 自动依赖关系解析和下游节点触发
- 丰富的状态查询和统计信息

### 2. WorkflowInstanceManager (工作流实例管理器)
**文件**: `workflow_instance_manager.py`

**功能**:
- 统一管理所有工作流实例的生命周期
- 提供实例创建、查询、销毁等功能
- 自动资源清理和内存管理
- 并发控制和性能优化

**主要特性**:
- 支持最大并发工作流数量限制
- 使用弱引用（WeakRef）防止内存泄漏
- 定时清理已完成的工作流实例
- 提供详细的管理器统计信息

### 3. NodeDependencyTracker (节点依赖跟踪器)
**文件**: `node_dependency_tracker.py`

**功能**:
- 提供线程安全的依赖关系管理
- 支持多种依赖类型（顺序、并行、条件、可选）
- 高性能的依赖状态跟踪和更新
- 依赖图验证和循环检测

**主要特性**:
- 使用读写锁机制保护并发访问
- 支持复杂的依赖规则定义
- 提供依赖图可视化信息
- 自动检测和处理循环依赖

### 4. ResourceCleanupManager (资源清理管理器)
**文件**: `resource_cleanup_manager.py`

**功能**:
- 统一的资源生命周期管理
- 自动内存清理和垃圾回收优化
- 支持多种清理策略
- 内存压力监控和优化

**主要特性**:
- 支持立即、延迟、定期、按需等清理策略
- 使用弱引用跟踪资源生命周期
- 内存使用监控和自动优化
- 可配置的清理参数和策略

### 5. WorkflowContextCompatibilityAdapter (兼容性适配器)
**文件**: `workflow_context_compatibility.py`

**功能**:
- 提供与现有代码的兼容性接口
- 平滑的迁移路径
- 保持原有API不变的情况下使用新架构

**主要特性**:
- 完全兼容现有的 `WorkflowContextManager` 接口
- 内部使用新架构组件实现
- 支持渐进式迁移
- 提供兼容性统计和监控

### 6. WorkflowContextManagerV2 (统一管理器)
**文件**: `workflow_context_manager_v2.py`

**功能**:
- 新架构的统一入口点
- 整合所有组件提供完整功能
- 支持多种工作模式（增强、兼容、混合）
- 性能监控和指标收集

**主要特性**:
- 三种工作模式：ENHANCED、COMPATIBLE、HYBRID
- 全面的性能监控和指标收集
- 统一的回调机制和事件处理
- 完整的生命周期管理

## 架构优势

### 1. 线程安全
- 所有组件都使用适当的锁机制保护共享数据
- 避免了原有架构中的数据竞争问题
- 支持高并发工作流执行

### 2. 资源管理
- 自动资源清理和垃圾回收
- 内存泄漏防护机制
- 可配置的资源使用限制

### 3. 可扩展性
- 模块化设计，各组件职责清晰
- 支持插件式扩展
- 易于添加新功能和优化

### 4. 性能优化
- 高效的依赖关系解析算法
- 缓存机制减少重复计算
- 并行执行和异步处理

### 5. 兼容性
- 完全向后兼容现有接口
- 支持渐进式迁移
- 混合模式允许新旧架构并存

## 使用方式

### 1. 基本使用（增强模式）

```python
from .workflow_context_manager_v2 import get_context_manager_v2, ManagerMode

# 获取管理器实例
manager = get_context_manager_v2(ManagerMode.ENHANCED)

# 创建工作流实例
context = await manager.create_workflow_instance(
    workflow_instance_id=workflow_id,
    workflow_base_id=base_id,
    config={'timeout': 300}
)

# 注册节点依赖
await manager.register_node_with_dependencies(
    workflow_instance_id=workflow_id,
    node_instance_id=node_id,
    node_base_id=node_base_id,
    dependencies=[{
        'upstream_node_id': upstream_id,
        'type': 'SEQUENCE'
    }]
)

# 执行节点
result = await manager.execute_node(
    workflow_instance_id=workflow_id,
    node_instance_id=node_id,
    execution_func=my_execution_function
)
```

### 2. 兼容模式使用

```python
from .workflow_context_compatibility import get_compatible_context_manager

# 获取兼容性管理器
compat_manager = get_compatible_context_manager()

# 使用原有接口
await compat_manager.initialize_workflow_context(workflow_id)
await compat_manager.register_node_dependencies(
    node_instance_id, node_base_id, workflow_id, upstream_nodes
)
await compat_manager.mark_node_completed(
    workflow_id, node_base_id, node_instance_id, output_data
)
```

### 3. 混合模式使用

```python
from .workflow_context_manager_v2 import WorkflowContextManagerV2, ManagerMode

# 创建混合模式管理器
manager = WorkflowContextManagerV2(mode=ManagerMode.HYBRID)

# 可以同时使用新接口和兼容接口
new_context = await manager.create_workflow_instance(...)
compat_interface = manager.get_compatibility_interface()
```

## 迁移指南

### 阶段1：部署新架构
1. 部署所有新架构文件
2. 在测试环境中验证功能
3. 进行性能基准测试

### 阶段2：兼容模式运行
1. 将现有代码切换到兼容模式
2. 验证功能正常性
3. 监控性能改进

### 阶段3：渐进式迁移
1. 逐步将部分代码迁移到新接口
2. 使用混合模式同时支持新旧接口
3. 持续监控和优化

### 阶段4：完全迁移
1. 将所有代码迁移到新接口
2. 切换到增强模式
3. 移除兼容性代码

## 性能对比

### 内存使用
- 新架构：支持自动内存清理，减少内存泄漏
- 旧架构：可能存在内存累积问题

### 并发性能
- 新架构：线程安全设计，支持高并发
- 旧架构：存在潜在的线程安全问题

### 依赖解析
- 新架构：O(1)时间复杂度的依赖查找
- 旧架构：O(n)时间复杂度

### 资源清理
- 新架构：自动化资源清理
- 旧架构：手动清理，容易遗漏

## 监控和调试

### 统计信息
```python
# 获取全局统计
stats = manager.get_global_statistics()

# 获取工作流状态
status = await manager.get_workflow_status(workflow_id)

# 获取性能指标
await manager.optimize_performance()
```

### 日志记录
- 所有组件都提供详细的日志记录
- 支持不同日志级别
- 包含性能指标和错误信息

### 调试功能
- 依赖图可视化
- 执行路径跟踪
- 性能瓶颈识别

## 配置选项

### 实例管理器配置
```python
manager = WorkflowInstanceManager(
    max_concurrent_workflows=100,
    cleanup_interval_seconds=300,
    auto_cleanup_after_hours=24
)
```

### 依赖跟踪器配置
```python
tracker = NodeDependencyTracker(
    max_worker_threads=4
)
```

### 资源清理器配置
```python
cleanup_manager = ResourceCleanupManager(
    cleanup_interval_seconds=60,
    max_cleanup_workers=2,
    enable_gc_optimization=True
)
```

## 故障排除

### 常见问题

1. **内存使用过高**
   - 检查是否启用了自动清理
   - 调整清理间隔和策略
   - 使用 `optimize_performance()` 方法

2. **依赖关系错误**
   - 使用 `validate_dependencies()` 检查循环依赖
   - 检查节点注册顺序
   - 验证依赖规则定义

3. **性能问题**
   - 检查并发限制设置
   - 优化节点执行函数
   - 使用性能监控功能

### 调试工具
- 依赖图导出功能
- 详细的执行日志
- 性能分析报告

## 未来扩展

### 计划功能
1. 分布式工作流支持
2. 持久化状态管理
3. 更多依赖类型支持
4. 可视化管理界面
5. 机器学习优化

### 扩展接口
- 自定义依赖规则
- 插件式节点执行器
- 外部监控系统集成
- 自定义清理策略

## 贡献指南

### 代码规范
- 遵循PEP 8风格指南
- 使用类型提示
- 添加完整的文档字符串
- 编写单元测试

### 测试要求
- 单元测试覆盖率 > 90%
- 集成测试覆盖主要用例
- 性能测试验证改进
- 兼容性测试确保向后兼容

这个新架构为工作流上下文管理提供了一个现代化、高性能、可扩展的解决方案，同时保持了与现有代码的完全兼容性。