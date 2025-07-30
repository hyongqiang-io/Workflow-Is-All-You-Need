# 工作流执行顺序与延迟任务实例化设计

## 🎯 目标

确保任务实例只在所有前置节点都执行完成后才创建，实现真正的按需实例化。

## 📊 当前问题分析

### 现状
1. **提前创建**: 工作流启动时就创建所有PROCESSOR节点的任务实例
2. **用户可见**: 用户立即看到所有任务，不管依赖关系
3. **状态混乱**: 任务状态与节点依赖状态不一致

### 问题位置
- `execution_service.py:946` - `_create_tasks_for_nodes()` 提前创建所有任务
- `execution_service.py:1028` - 立即调用 `create_task()` 

## 🔧 新设计方案

### 1. 执行顺序维护机制

```
工作流启动 → 创建节点实例 → 标记节点状态 → 按依赖关系逐步激活节点 → 创建任务实例
```

### 2. 节点状态生命周期

```
CREATED → WAITING → READY → RUNNING → COMPLETED
    ↓        ↓        ↓        ↓         ↓
   创建     等待     就绪     执行      完成
  节点    前置     创建     任务      任务
  实例    完成     任务     实例      结果
```

### 3. 延迟任务创建触发点

**触发条件**:
- 所有前置节点状态为 `COMPLETED`
- 当前节点状态为 `WAITING` 或 `READY`
- 节点类型为 `PROCESSOR`

**触发位置**:
- 在 `_check_downstream_tasks()` 中
- 当前置节点完成时自动检查

## 🏗️ 实现方案

### 步骤1: 修改节点实例创建逻辑
- 只创建节点实例，不创建任务实例
- 设置节点初始状态：START节点为READY，其他为WAITING

### 步骤2: 实现延迟任务创建方法
- `_create_tasks_when_ready()` - 检查并创建就绪节点的任务
- `_check_node_prerequisites()` - 检查前置节点完成情况

### 步骤3: 修改下游触发逻辑
- 在节点完成时触发下游节点检查
- 满足条件时创建任务实例

### 步骤4: 更新状态管理
- 节点状态：WAITING → READY → RUNNING → COMPLETED
- 任务状态：只有READY节点才会有任务实例

## 📋 数据库状态字段

### node_instance表状态值
- `waiting` - 等待前置节点完成
- `ready` - 前置条件满足，准备创建任务  
- `running` - 任务已创建并执行中
- `completed` - 节点执行完成

### task_instance表
- 只有节点状态为`ready`或`running`时才存在记录
- 用户只能看到当前可执行的任务

## 🔍 执行流程示例

### 简单工作流: START → PROCESSOR → END

**1. 初始状态**
```
start: READY (无前置条件)
processor: WAITING (等待start完成)  
end: WAITING (等待processor完成)
```

**2. START节点完成后**
```
start: COMPLETED
processor: READY → 创建processor任务实例
end: WAITING
```

**3. PROCESSOR任务完成后**
```  
start: COMPLETED
processor: COMPLETED
end: READY → 自动执行end节点
```

## 🎯 用户体验改进

### 之前
- 用户看到所有任务（包括不可执行的）
- 任务状态混乱，用户不知道哪些能执行

### 之后  
- 用户只看到当前可执行的任务
- 清晰的执行顺序，任务按依赖关系逐步出现
- 更好的工作流执行体验

## 🔧 技术实现要点

1. **状态同步**: 确保节点状态与任务创建同步
2. **错误处理**: 前置节点失败时的处理逻辑
3. **性能优化**: 避免频繁的依赖检查
4. **并发安全**: 多个节点同时完成时的处理

这个设计确保了工作流的执行顺序严格按照依赖关系进行，用户体验更加清晰。