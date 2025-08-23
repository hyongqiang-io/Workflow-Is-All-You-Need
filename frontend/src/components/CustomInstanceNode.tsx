import React from 'react';
import { Button, Tag, Badge } from 'antd';
import { Handle, Position } from 'reactflow';
import { 
  BranchesOutlined, 
  ReloadOutlined, 
  ShrinkOutlined, 
  ExpandAltOutlined,
  UserOutlined,
  RobotOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';

// 统一的节点数据接口
interface UnifiedNodeData {
  // 基础属性
  label: string;
  status: string;
  nodeId?: string;
  node_name?: string; // 添加 node_name 属性
  
  // 外观配置
  scale?: 'normal' | 'small' | 'large';
  showTaskActions?: boolean;
  
  // 处理器信息
  processor_name?: string;
  processor_type?: string;
  task_count?: number;
  
  // 扩展相关
  expansionLevel?: number; // 添加 expansionLevel 属性
  
  // 执行详细信息 - 支持子工作流节点显示详细数据
  retry_count?: number;
  execution_duration_seconds?: number;
  input_data?: any;
  output_data?: any;
  error_message?: string;
  start_at?: string;
  completed_at?: string;
  tasks?: any[];
  
  // Subdivision相关
  subWorkflowInfo?: {
    has_subdivision: boolean;
    subdivision_count: number;
    subdivision_status?: 'draft' | 'running' | 'completed' | 'failed' | 'cancelled';
    is_expandable: boolean;
  };
  isExpanded?: boolean;
  isLoading?: boolean;
  
  // 任务相关
  task?: {
    task_instance_id?: string;
    task_title?: string;
    task_type?: string;
    priority?: number;
    estimated_duration?: number;
    isAssignedToMe?: boolean;
    isCreator?: boolean;
  };
  
  // 回调函数
  onNodeClick?: (data: any) => void;
  onNodeDoubleClick?: (data: any) => void;
  onExpandNode?: (nodeId: string) => void;
  onCollapseNode?: (nodeId: string) => void;
  
  // 任务操作回调
  onStartTask?: (taskId: string) => void;
  onCompleteTask?: (taskId: string) => void;
  onPauseTask?: (taskId: string) => void;
  onSubdivideTask?: (taskId: string) => void;
}

interface CustomInstanceNodeProps {
  data: UnifiedNodeData;
  selected?: boolean;
}

/**
 * 统一的工作流节点组件
 * 支持所有场景：主工作流、子工作流、任务流程视图
 */
export const CustomInstanceNode: React.FC<CustomInstanceNodeProps> = ({ data, selected }) => {
  // console.log('🔍 [CustomInstanceNode] 渲染节点，接收数据:', data);
  // console.log('🔍 [CustomInstanceNode] 节点详细字段:', {
  //   label: data.label,
  //   nodeId: data.nodeId,
  //   status: data.status,
  //   processor_name: data.processor_name,
  //   processor_type: data.processor_type,
  //   task_count: data.task_count,
  //   expansionLevel: data.expansionLevel,
  //   has_subWorkflowInfo: !!data.subWorkflowInfo,
  //   isExpanded: data.isExpanded
  // });
  
  // 状态颜色映射
  const getNodeColor = (status?: string) => {
    switch (status) {
      case 'completed': return '#52c41a';
      case 'running': return '#1890ff';
      case 'in_progress': return '#1890ff';
      case 'assigned': return '#1890ff';
      case 'failed': return '#ff4d4f';
      case 'error': return '#ff4d4f';
      case 'pending': return '#faad14';
      case 'waiting': return '#faad14';
      case 'blocked': return '#722ed1';
      case 'paused': return '#fa8c16';
      case 'cancelled': return '#8c8c8c';
      default: return '#d9d9d9';
    }
  };

  const getNodeBackground = (status?: string) => {
    switch (status) {
      case 'completed': return '#f6ffed';
      case 'running': return '#e6f7ff';
      case 'in_progress': return '#e6f7ff';
      case 'assigned': return '#e6f7ff';
      case 'failed': return '#fff2f0';
      case 'error': return '#fff2f0';
      case 'pending': return '#fff7e6';
      case 'waiting': return '#fffbe6';
      case 'blocked': return '#f9f0ff';
      case 'paused': return '#fff2e8';
      case 'cancelled': return '#f5f5f5';
      default: return '#fafafa';
    }
  };

  const getSubWorkflowStatusColor = (status?: string) => {
    switch (status) {
      case 'completed': return '#52c41a';
      case 'running': return '#1890ff';
      case 'failed': return '#ff4d4f';
      case 'draft': return '#faad14';
      case 'cancelled': return '#8c8c8c';
      default: return '#d9d9d9';
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'completed': return '已完成';
      case 'running': return '运行中';
      case 'in_progress': return '进行中';
      case 'assigned': return '已分配';
      case 'failed': return '失败';
      case 'error': return '错误';
      case 'pending': return '等待中';
      case 'waiting': return '等待中';
      case 'blocked': return '阻塞';
      case 'paused': return '暂停';
      case 'cancelled': return '已取消';
      default: return '未知';
    }
  };

  const getNodeTypeIcon = (type?: string) => {
    switch (type) {
      case 'start': return <PlayCircleOutlined />;
      case 'end': return <CheckCircleOutlined />;
      case 'human': return <UserOutlined />;
      case 'ai': 
      case 'agent': return <RobotOutlined />;
      case 'decision': return <BranchesOutlined />;
      default: return <InfoCircleOutlined />;
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'pending': return <ClockCircleOutlined />;
      case 'in_progress': return <PlayCircleOutlined />;
      case 'completed': return <CheckCircleOutlined />;
      case 'failed': return <InfoCircleOutlined />;
      case 'blocked': return <InfoCircleOutlined />;
      default: return <ClockCircleOutlined />;
    }
  };

  // subdivision相关逻辑
  const hasSubWorkflow = data.subWorkflowInfo?.has_subdivision || false;
  const isExpandable = data.subWorkflowInfo?.is_expandable || false;
  const isExpanded = data.isExpanded || false;
  const isLoading = data.isLoading || false;

  // 根据scale调整尺寸
  const scale = data.scale || 'normal';
  const scaleConfig = {
    small: { 
      padding: '8px', 
      fontSize: '12px', 
      minWidth: '120px',
      tagSize: '10px',
      buttonHeight: '20px'
    },
    normal: { 
      padding: '12px', 
      fontSize: '14px', 
      minWidth: hasSubWorkflow ? '200px' : '180px',
      tagSize: '11px',
      buttonHeight: '24px'
    },
    large: { 
      padding: '16px', 
      fontSize: '16px', 
      minWidth: '220px',
      tagSize: '12px',
      buttonHeight: '28px'
    }
  };

  const currentScale = scaleConfig[scale];

  // 事件处理
  const handleNodeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onNodeClick) {
      data.onNodeClick(data);
    }
  };

  const handleNodeDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (data.onNodeDoubleClick) {
      data.onNodeDoubleClick(data);
    } else if (data.onNodeClick) {
      data.onNodeClick(data);
    }
  };

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (isLoading) {
      console.log(`⏳ [CustomInstanceNode] 节点正在加载中，忽略展开操作`);
      return;
    }
    
    const nodeId = data.nodeId || data.label;
    console.log(`🔄 [CustomInstanceNode] 切换展开状态:`, {
      nodeId,
      currentExpanded: isExpanded,
      hasSubWorkflow,
      isExpandable,
      subWorkflowInfo: data.subWorkflowInfo
    });
    
    if (isExpanded) {
      console.log(`📤 [CustomInstanceNode] 收起节点 ${nodeId}`);
      data.onCollapseNode?.(nodeId);
    } else {
      console.log(`📥 [CustomInstanceNode] 展开节点 ${nodeId}`);
      data.onExpandNode?.(nodeId);
    }
  };

  // 任务操作处理
  const handleTaskAction = (action: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    const taskId = data.task?.task_instance_id;
    if (!taskId) return;

    switch (action) {
      case 'start':
        data.onStartTask?.(taskId);
        break;
      case 'complete':
        data.onCompleteTask?.(taskId);
        break;
      case 'pause':
        data.onPauseTask?.(taskId);
        break;
      case 'subdivide':
        data.onSubdivideTask?.(taskId);
        break;
    }
  };

  return (
    <div
      style={{
        padding: currentScale.padding,
        borderRadius: '8px',
        border: hasSubWorkflow 
          ? `2px dashed ${getSubWorkflowStatusColor(data.subWorkflowInfo?.subdivision_status)}`
          : `2px solid ${selected ? '#1890ff' : getNodeColor(data.status)}`,
        backgroundColor: getNodeBackground(data.status),
        minWidth: currentScale.minWidth,
        textAlign: 'center' as const,
        boxShadow: selected ? '0 0 0 2px rgba(24, 144, 255, 0.2)' : '0 2px 8px rgba(0,0,0,0.1)',
        transition: 'all 0.3s ease',
        cursor: 'pointer',
        position: 'relative' as const,
      }}
      onClick={handleNodeClick}
      onDoubleClick={handleNodeDoubleClick}
      className={hasSubWorkflow ? 'has-subdivision' : ''}
    >
      <Handle type="target" position={Position.Top} />
      
      {/* Subdivision计数徽章 */}
      {hasSubWorkflow && (
        <div style={{ position: 'absolute', top: '-8px', right: '-8px' }}>
          <Badge 
            count={data.subWorkflowInfo?.subdivision_count || 0} 
            showZero={false}
            style={{ 
              backgroundColor: getSubWorkflowStatusColor(data.subWorkflowInfo?.subdivision_status),
              color: 'white'
            }}
          />
        </div>
      )}

      {/* 任务高亮指示器 */}
      {data.task?.isAssignedToMe && (
        <div style={{ 
          position: 'absolute', 
          top: '-6px', 
          left: '-6px',
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          backgroundColor: '#52c41a',
          border: '2px solid white',
          boxShadow: '0 0 4px rgba(82, 196, 26, 0.5)'
        }} />
      )}

      {/* 节点名称 - 增强显示逻辑 */}
      <div style={{ 
        fontWeight: 'bold', 
        marginBottom: '6px', 
        fontSize: currentScale.fontSize 
      }}>
        {data.task?.task_type && getNodeTypeIcon(data.task.task_type)}
        {' '}{data.label || data.node_name || '未命名节点'}
      </div>
      
      {/* 状态标签 */}
      <div style={{ marginBottom: '6px' }}>
        <Tag 
          color={getNodeColor(data.status)} 
          style={{ fontSize: currentScale.tagSize }}
          icon={getStatusIcon(data.status)}
        >
          {getStatusText(data.status)}
        </Tag>
      </div>

      {/* 子工作流状态指示器 */}
      {hasSubWorkflow && data.subWorkflowInfo?.subdivision_status && (
        <div style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Tag 
            color={getSubWorkflowStatusColor(data.subWorkflowInfo.subdivision_status)}
            icon={<BranchesOutlined />}
            style={{ fontSize: currentScale.tagSize }}
          >
            子工作流: {
              data.subWorkflowInfo.subdivision_status === 'running' ? '运行中' :
              data.subWorkflowInfo.subdivision_status === 'completed' ? '已完成' :
              data.subWorkflowInfo.subdivision_status === 'failed' ? '失败' :
              data.subWorkflowInfo.subdivision_status === 'draft' ? '草稿' :
              data.subWorkflowInfo.subdivision_status === 'cancelled' ? '已取消' : '未知'
            }
          </Tag>
        </div>
      )}

      {/* 处理器信息 - 增强显示逻辑 */}
      {(data.processor_name || data.processor_type) && (
        <div style={{ 
          fontSize: parseInt(currentScale.tagSize) + 1 + 'px', 
          color: '#666', 
          marginBottom: '4px' 
        }}>
          {data.processor_name || '未指定处理器'} ({data.processor_type || 'unknown'})
        </div>
      )}
      
      {/* 任务数量 - 改进显示 */}
      {data.task_count !== undefined && (
        <div style={{ 
          fontSize: currentScale.tagSize, 
          color: '#999', 
          marginBottom: '4px' 
        }}>
          任务数: {data.task_count}
        </div>
      )}

      {/* 执行详细信息 - 新增支持子工作流节点 */}
      {(data.retry_count !== undefined && data.retry_count > 0) && (
        <div style={{ 
          fontSize: currentScale.tagSize, 
          color: '#ff7a00', 
          marginBottom: '2px' 
        }}>
          重试: {data.retry_count}次
        </div>
      )}

      {data.execution_duration_seconds && data.execution_duration_seconds > 0 && (
        <div style={{ 
          fontSize: currentScale.tagSize, 
          color: '#52c41a', 
          marginBottom: '2px' 
        }}>
          耗时: {Math.round(data.execution_duration_seconds)}s
        </div>
      )}

      {data.error_message && (
        <div style={{ 
          fontSize: currentScale.tagSize, 
          color: '#ff4d4f', 
          marginBottom: '2px',
          maxWidth: '100%',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap'
        }} title={data.error_message}>
          错误: {data.error_message}
        </div>
      )}

      {/* 输入输出数据标识 */}
      {(data.input_data || data.output_data) && (
        <div style={{ marginBottom: '4px' }}>
          {data.input_data && Object.keys(data.input_data).length > 0 && (
            <Tag color="blue" style={{ fontSize: '9px', margin: '0 2px 2px 0' }}>
              输入:{Object.keys(data.input_data).length}
            </Tag>
          )}
          {data.output_data && Object.keys(data.output_data).length > 0 && (
            <Tag color="green" style={{ fontSize: '9px', margin: '0 2px 2px 0' }}>
              输出:{Object.keys(data.output_data).length}
            </Tag>
          )}
        </div>
      )}

      {/* 任务优先级和预估时间 */}
      {data.task && (
        <div style={{ marginBottom: '6px' }}>
          {data.task.priority && (
            <Tag color={data.task.priority > 3 ? 'red' : 'blue'} style={{ fontSize: '10px' }}>
              P{data.task.priority}
            </Tag>
          )}
          {data.task.estimated_duration && (
            <Tag color="orange" style={{ fontSize: '10px' }}>
              {data.task.estimated_duration}min
            </Tag>
          )}
        </div>
      )}

      {/* 任务操作按钮 */}
      {data.showTaskActions && data.task && (
        <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px', justifyContent: 'center' }}>
          {data.status === 'pending' && (
            <Button 
              size="small" 
              type="primary" 
              style={{ height: currentScale.buttonHeight, fontSize: currentScale.tagSize }}
              onClick={(e) => handleTaskAction('start', e)}
            >
              开始
            </Button>
          )}
          {data.status === 'in_progress' && (
            <>
              <Button 
                size="small" 
                type="primary" 
                style={{ height: currentScale.buttonHeight, fontSize: currentScale.tagSize }}
                onClick={(e) => handleTaskAction('complete', e)}
              >
                完成
              </Button>
              <Button 
                size="small" 
                style={{ height: currentScale.buttonHeight, fontSize: currentScale.tagSize }}
                onClick={(e) => handleTaskAction('pause', e)}
              >
                暂停
              </Button>
            </>
          )}
          {(data.status === 'pending' || data.status === 'assigned') && (
            <Button 
              size="small" 
              icon={<BranchesOutlined />}
              style={{ height: currentScale.buttonHeight, fontSize: currentScale.tagSize }}
              onClick={(e) => handleTaskAction('subdivide', e)}
            >
              细分
            </Button>
          )}
        </div>
      )}

      {/* 展开/收起按钮 */}
      {isExpandable && (
        <div style={{ marginTop: '8px' }}>
          <Button
            type="text"
            size="small"
            icon={isLoading ? <ReloadOutlined spin /> : (isExpanded ? <ShrinkOutlined /> : <ExpandAltOutlined />)}
            onClick={handleExpandToggle}
            style={{
              padding: '2px 6px',
              fontSize: currentScale.tagSize,
              height: currentScale.buttonHeight,
              color: getSubWorkflowStatusColor(data.subWorkflowInfo?.subdivision_status)
            }}
          >
            {isLoading ? '加载中' : (isExpanded ? '收起' : '展开')}
          </Button>
        </div>
      )}

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

export default CustomInstanceNode;