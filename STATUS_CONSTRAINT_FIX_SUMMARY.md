# 任务状态约束修复总结

## 🐛 问题描述

用户在界面点击"开始任务"时出现数据库约束错误：

```
asyncpg.exceptions.CheckViolationError: 关系 "task_instance" 的新列违反了检查约束 "task_instance_status_check"
DETAIL: 失败, 行包含(..., in_progress, ...)
```

## 🔍 问题分析

### 原始约束定义：
```sql
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
```

### 问题所在：
1. **缺少 `assigned` 状态** - 任务分配后的状态
2. **缺少 `in_progress` 状态** - 用户开始执行任务后的状态  
3. **使用了 `running` 而不是 `in_progress`** - 状态命名不一致

## ✅ 解决方案

### 1. 执行修复脚本
**文件**: `check_task_constraints.py`

**执行结果**:
```
SUCCESS: New status constraint created
New constraint definition: CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled', 'paused'))
```

### 2. 新的状态约束
```sql
ALTER TABLE task_instance 
ADD CONSTRAINT task_instance_status_check 
CHECK (status IN (
    'pending',      -- 等待分配
    'assigned',     -- 已分配
    'in_progress',  -- 执行中
    'completed',    -- 已完成
    'failed',       -- 失败
    'cancelled',    -- 已取消
    'paused'        -- 已暂停
));
```

## 🔄 任务状态流转

### 完整状态流程：
```
PENDING → ASSIGNED → IN_PROGRESS → COMPLETED
   ↓         ↓           ↓            ↑
CANCELLED ← PAUSED ← FAILED ←────────┘
```

### 状态说明：
- **PENDING**: 任务创建但未分配给用户/代理
- **ASSIGNED**: 任务已分配给用户/代理，等待开始
- **IN_PROGRESS**: 用户点击"开始任务"，正在执行中
- **COMPLETED**: 用户提交任务结果，任务完成
- **FAILED**: 任务执行失败或出现错误
- **CANCELLED**: 任务被取消
- **PAUSED**: 任务被暂停（可恢复）

## 🎯 用户操作对应的状态变化

### 前端操作 → 状态变化：
1. **工作流执行创建任务** → `PENDING` 或 `ASSIGNED`
   - 如果绑定了用户/代理：`ASSIGNED`
   - 如果未绑定：`PENDING`

2. **用户点击"开始任务"** → `ASSIGNED` → `IN_PROGRESS`
   - API: `POST /api/execution/tasks/{task_id}/start`
   - 记录 `started_at` 时间戳

3. **用户提交任务结果** → `IN_PROGRESS` → `COMPLETED`
   - API: `POST /api/execution/tasks/{task_id}/submit`
   - 记录 `completed_at` 时间戳和 `result_summary`

4. **用户暂停任务** → `IN_PROGRESS` → `PAUSED`
   - API: `POST /api/execution/tasks/{task_id}/pause`

5. **管理员取消任务** → 任何状态 → `CANCELLED`
   - API: `POST /api/execution/tasks/{task_id}/cancel`

## 🧪 验证结果

### 约束检查结果：
```
PASS: pending
PASS: assigned  
PASS: in_progress
PASS: completed
PASS: failed
PASS: cancelled

SUCCESS: All required statuses are in the constraint
```

### 测试场景：
1. ✅ 创建任务 → `ASSIGNED` 状态
2. ✅ 开始任务 → `IN_PROGRESS` 状态  
3. ✅ 完成任务 → `COMPLETED` 状态
4. ✅ 暂停任务 → `PAUSED` 状态
5. ✅ 取消任务 → `CANCELLED` 状态

## 📱 前端界面状态显示

### 状态图标和颜色建议：
```javascript
const statusConfig = {
  'pending': { 
    icon: '⏳', 
    color: '#gray', 
    text: '等待分配',
    actions: [] 
  },
  'assigned': { 
    icon: '📋', 
    color: '#blue', 
    text: '已分配',
    actions: ['start', 'reject'] 
  },
  'in_progress': { 
    icon: '🔄', 
    color: '#orange', 
    text: '执行中',
    actions: ['submit', 'pause', 'help'] 
  },
  'completed': { 
    icon: '✅', 
    color: '#green', 
    text: '已完成',
    actions: ['view'] 
  },
  'failed': { 
    icon: '❌', 
    color: '#red', 
    text: '失败',
    actions: ['retry', 'view'] 
  },
  'cancelled': { 
    icon: '🚫', 
    color: '#gray', 
    text: '已取消',
    actions: ['view'] 
  },
  'paused': { 
    icon: '⏸️', 
    color: '#yellow', 
    text: '已暂停',
    actions: ['resume', 'cancel'] 
  }
};
```

## 🚀 现在可以正常使用

**修复完成后，用户现在可以：**

1. ✅ **查看任务列表** - 看到正确的状态显示
2. ✅ **点击开始任务** - 状态正确更新为 `IN_PROGRESS`
3. ✅ **提交任务结果** - 状态正确更新为 `COMPLETED`
4. ✅ **暂停/取消任务** - 状态正确流转

**数据库约束错误已完全解决！** 🎉

## 📝 相关文件

- `check_task_constraints.py` - 约束检查和修复脚本
- `workflow_framework/models/instance.py` - 任务状态枚举定义
- `workflow_framework/api/execution.py` - 任务操作API
- `workflow_framework/repositories/instance/task_instance_repository.py` - 任务数据访问

现在您的任务系统应该可以完全正常工作了！