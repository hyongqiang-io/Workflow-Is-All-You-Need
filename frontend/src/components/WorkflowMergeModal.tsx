/**
 * 工作流合并模态框组件 - Linus式简化版本
 * 
 * 移除了复杂的合并逻辑，subdivision树应该专注于展示，不是合并
 * "简单的解决方案通常是正确的" - Linus
 */

import React from 'react';
import './WorkflowMergeModal.css';

interface Props {
  visible: boolean;
  onClose: () => void;
  workflowInstanceId?: string;
}

/**
 * 简化的合并模态框 - 暂时禁用复杂功能
 * 
 * 合并功能是个复杂的特性，应该单独设计
 * subdivision树只负责展示层级关系
 */
export const WorkflowMergeModal: React.FC<Props> = ({
  visible,
  onClose,
  workflowInstanceId
}) => {
  if (!visible) return null;

  return (
    <div className="workflow-merge-modal">
      <div className="modal-content">
        <div className="modal-header">
          <h3>🚧 工作流合并功能</h3>
          <button onClick={onClose} className="close-button">✕</button>
        </div>
        
        <div className="modal-body">
          <div className="feature-notice">
            <h4>📋 功能重构中</h4>
            <p>工作流合并功能正在重构中，采用更简单的设计方案。</p>
            <p>当前版本专注于subdivision树的展示功能。</p>
            
            {workflowInstanceId && (
              <div className="workflow-info">
                <strong>工作流实例ID:</strong> {workflowInstanceId}
              </div>
            )}
          </div>
          
          <div className="action-buttons">
            <button onClick={onClose} className="cancel-button">
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkflowMergeModal;