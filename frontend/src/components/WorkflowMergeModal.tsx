/**
 * 工作流合并配置模态框组件
 * Workflow Merge Configuration Modal Component
 * 
 * 提供合并预览、配置和执行界面
 */

import React, { useState, useCallback, useEffect } from 'react';
import { executionAPI } from '../services/api';
import { MergeCandidate } from '../services/workflowTemplateConnectionManager';
import './WorkflowMergeModal.css';

interface MergePreviewData {
  parent_workflow: {
    workflow_base_id: string;
    name: string;
    current_nodes: number;
    current_connections: number;
  };
  merge_summary: {
    total_merge_candidates: number;
    valid_merges: number;
    invalid_merges: number;
    net_nodes_change: number;
    net_connections_change: number;
  };
  merge_feasibility: {
    can_proceed: boolean;
    complexity_increase: string;
    recommended_approach: string;
  };
  valid_merge_previews: any[];
  invalid_merge_previews: any[];
}

interface MergeConfig {
  new_workflow_name: string;
  new_workflow_description: string;
  preserve_original: boolean;
  execute_immediately: boolean;
  notify_on_completion: boolean;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  mergePreviewData: MergePreviewData | null;
  selectedCandidates: MergeCandidate[];
  allCandidates: MergeCandidate[];
  onCandidateToggle: (candidateId: string) => void;
  onMergeExecuted?: (result: any) => void;
}

const WorkflowMergeModal: React.FC<Props> = ({
  isOpen,
  onClose,
  mergePreviewData,
  selectedCandidates,
  allCandidates,
  onCandidateToggle,
  onMergeExecuted
}) => {
  // 合并配置状态
  const [mergeConfig, setMergeConfig] = useState<MergeConfig>({
    new_workflow_name: '',
    new_workflow_description: '',
    preserve_original: true,
    execute_immediately: false,
    notify_on_completion: true
  });

  // 执行状态
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<'preview' | 'config' | 'executing' | 'result'>('preview');

  // 重置模态框状态
  useEffect(() => {
    if (isOpen && mergePreviewData) {
      // 生成默认的合并工作流名称
      const timestamp = new Date().toLocaleString('zh-CN', { 
        year: '2-digit', 
        month: '2-digit', 
        day: '2-digit', 
        hour: '2-digit', 
        minute: '2-digit' 
      }).replace(/[^\d]/g, '');
      
      const defaultWorkflowName = mergePreviewData?.parent_workflow?.name 
        ? `${mergePreviewData.parent_workflow.name}_merged_${timestamp}`
        : `merged_workflow_${timestamp}`;
      
      const defaultDescription = mergePreviewData?.parent_workflow?.name
        ? `通过模板连接合并生成的工作流，基于 "${mergePreviewData.parent_workflow.name}"`
        : '通过模板连接合并生成的工作流';
      
      setMergeConfig({
        new_workflow_name: defaultWorkflowName,
        new_workflow_description: defaultDescription,
        preserve_original: true,
        execute_immediately: false,
        notify_on_completion: true
      });
      
      setCurrentStep('preview');
      setExecutionResult(null);
      setExecutionError(null);
      setIsExecuting(false);
    }
  }, [isOpen, mergePreviewData]);

  // 处理配置字段变更
  const handleConfigChange = useCallback((field: keyof MergeConfig, value: any) => {
    setMergeConfig(prev => ({
      ...prev,
      [field]: value
    }));
  }, []);

  // 验证配置
  const validateConfig = useCallback(() => {
    const errors: string[] = [];
    
    if (!mergeConfig.new_workflow_name.trim()) {
      errors.push('请输入新工作流名称');
    }
    
    if (mergeConfig.new_workflow_name.length < 2) {
      errors.push('工作流名称至少需要2个字符');
    }
    
    if (mergeConfig.new_workflow_name.length > 100) {
      errors.push('工作流名称不能超过100个字符');
    }

    return errors;
  }, [mergeConfig]);

  // 执行合并操作
  const handleExecuteMerge = useCallback(async () => {
    if (!mergePreviewData || selectedCandidates.length === 0) {
      setExecutionError('缺少合并数据');
      return;
    }

    const validationErrors = validateConfig();
    if (validationErrors.length > 0) {
      setExecutionError(validationErrors.join('; '));
      return;
    }

    setIsExecuting(true);
    setExecutionError(null);
    setCurrentStep('executing');

    try {
      console.log('🔄 执行工作流合并:', {
        parentWorkflowId: mergePreviewData?.parent_workflow?.workflow_base_id,
        candidatesCount: selectedCandidates.length,
        config: mergeConfig
      });

      // 准备合并请求数据
      const mergeRequest = {
        selected_merges: selectedCandidates.map(candidate => ({
          subdivision_id: candidate.subdivision_id,
          target_node_id: candidate.replaceable_node.node_base_id,
          sub_workflow_id: candidate.sub_workflow_id,
          nodes_to_add: 5, // 这里应该从预览数据中获取
          connections_to_add: 3 // 这里应该从预览数据中获取
        })),
        merge_config: mergeConfig
      };

      // 调用合并执行API - 使用已配置的API实例
      const { default: api } = await import('../services/api');
      const parentWorkflowId = mergePreviewData?.parent_workflow?.workflow_base_id;
      
      if (!parentWorkflowId) {
        throw new Error('无法获取父工作流ID，请重新尝试');
      }
      
      const response = await api.post(
        `/workflow-merge/${parentWorkflowId}/execute-merge`,
        mergeRequest
      );

      if (response.data?.success) {
        setExecutionResult(response.data.data);
        setCurrentStep('result');
        
        // 通知父组件
        if (onMergeExecuted) {
          onMergeExecuted(response.data.data);
        }

        console.log('✅ 工作流合并执行成功');
      } else {
        setExecutionError(response.data?.message || '合并执行失败');
        setCurrentStep('config');
      }

    } catch (err: any) {
      console.error('❌ 执行工作流合并失败:', err);
      setExecutionError(err.response?.data?.detail || err.message || '合并执行失败');
      setCurrentStep('config');
    } finally {
      setIsExecuting(false);
    }
  }, [mergePreviewData, selectedCandidates, mergeConfig, validateConfig, onMergeExecuted]);

  // 处理模态框关闭
  const handleClose = useCallback(() => {
    if (isExecuting) {
      return; // 执行中不允许关闭
    }
    onClose();
  }, [isExecuting, onClose]);

  // 渲染预览步骤
  const renderPreviewStep = () => {
    if (!mergePreviewData) return null;

    return (
      <div className="merge-step preview-step">
        {/* 合并候选选择面板 */}
        {allCandidates && allCandidates.length > 0 && (
          <div className="merge-candidates-section">
            <h3>📋 可合并的任务细分 ({allCandidates.length})</h3>
            <p className="candidates-description">
              选择要整合到主工作流中的任务细分。绿色标记表示完全兼容，建议优先选择。
            </p>
            
            <div className="candidates-list-container">
              <div className="candidates-list">
                {allCandidates.map((candidate: MergeCandidate) => (
                  <div 
                    key={candidate.subdivision_id}
                    className={`candidate-item ${selectedCandidates.some(sc => sc.subdivision_id === candidate.subdivision_id) ? 'selected' : ''}`}
                    onClick={() => onCandidateToggle(candidate.subdivision_id)}
                  >
                    <div className="candidate-header">
                      <input
                        type="checkbox"
                        checked={selectedCandidates.some(sc => sc.subdivision_id === candidate.subdivision_id)}
                        onChange={() => onCandidateToggle(candidate.subdivision_id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <span className="candidate-name">{candidate.replaceable_node.name}</span>
                      <span className={`compatibility-badge ${candidate.compatibility.is_compatible ? 'compatible' : 'incompatible'}`}>
                        {candidate.compatibility.is_compatible ? '✓' : '✗'}
                      </span>
                    </div>
                    
                    <div className="candidate-details">
                      <div className="node-info">
                        <span>节点类型: {candidate.replaceable_node.type}</span>
                      </div>
                      
                      {candidate.compatibility.issues.length > 0 && (
                        <div className="compatibility-issues">
                          <span className="issues-label">问题:</span>
                          {candidate.compatibility.issues.map((issue: string, index: number) => (
                            <div key={index} className="issue-item">{issue}</div>
                          ))}
                        </div>
                      )}
                      
                      {candidate.compatibility.recommendations.length > 0 && (
                        <div className="compatibility-recommendations">
                          <span className="recommendations-label">建议:</span>
                          {candidate.compatibility.recommendations.map((rec: string, index: number) => (
                            <div key={index} className="recommendation-item">{rec}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <h3>合并预览</h3>
        
        <div className="preview-summary">
          <div className="source-workflow">
            <h4>源工作流</h4>
            <div className="workflow-info">
              <span className="workflow-name">{mergePreviewData?.parent_workflow?.name || '未知工作流'}</span>
              <div className="workflow-stats">
                <span>{mergePreviewData?.parent_workflow?.current_nodes || 0} 个节点</span>
                <span>{mergePreviewData?.parent_workflow?.current_connections || 0} 个连接</span>
              </div>
            </div>
          </div>

          <div className="merge-arrow">→</div>

          <div className="result-workflow">
            <h4>合并后工作流</h4>
            <div className="workflow-info">
              <span className="workflow-name">新合并工作流</span>
              <div className="workflow-stats">
                <span className="stat-change positive">
                  +{mergePreviewData?.merge_summary?.net_nodes_change || 0} 节点
                </span>
                <span className="stat-change positive">
                  +{mergePreviewData?.merge_summary?.net_connections_change || 0} 连接
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="merge-feasibility">
          <div className={`feasibility-status ${mergePreviewData?.merge_feasibility?.can_proceed ? 'feasible' : 'not-feasible'}`}>
            <span className="status-icon">
              {mergePreviewData?.merge_feasibility?.can_proceed ? '✓' : '✗'}
            </span>
            <span className="status-text">
              {mergePreviewData?.merge_feasibility?.can_proceed ? '可以合并' : '无法合并'}
            </span>
          </div>
          
          <div className="feasibility-details">
            <div className="detail-item">
              <span className="detail-label">复杂度:</span>
              <span className={`detail-value ${mergePreviewData?.merge_feasibility?.complexity_increase || 'unknown'}`}>
                {mergePreviewData?.merge_feasibility?.complexity_increase || '未知'}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">建议方式:</span>
              <span className="detail-value">{mergePreviewData?.merge_feasibility?.recommended_approach || '无建议'}</span>
            </div>
          </div>
        </div>

        {mergePreviewData?.valid_merge_previews && mergePreviewData.valid_merge_previews.length > 0 && (
          <div className="merge-operations">
            <h4>合并操作 ({mergePreviewData.valid_merge_previews.length})</h4>
            <div className="operations-list">
              {mergePreviewData.valid_merge_previews.map((operation: any, index: number) => (
                <div key={index} className="operation-item">
                  <div className="operation-target">
                    <span className="target-node">{operation.target_node?.name || 'Unknown Node'}</span>
                  </div>
                  <div className="operation-arrow">→</div>
                  <div className="operation-replacement">
                    <span className="replacement-workflow">
                      {operation.replacement_info?.sub_workflow_name || 'Unknown Workflow'}
                    </span>
                    <div className="replacement-stats">
                      <span>+{operation.replacement_info?.nodes_to_add || 0} 节点</span>
                      <span>+{operation.replacement_info?.connections_to_add || 0} 连接</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // 渲染配置步骤
  const renderConfigStep = () => (
    <div className="merge-step config-step">
      <h3>合并配置</h3>
      
      <div className="config-form">
        <div className="form-group">
          <label>新工作流名称 *</label>
          <input
            type="text"
            value={mergeConfig.new_workflow_name}
            onChange={(e) => handleConfigChange('new_workflow_name', e.target.value)}
            placeholder="输入新工作流名称"
            disabled={isExecuting}
          />
        </div>

        <div className="form-group">
          <label>工作流描述</label>
          <textarea
            value={mergeConfig.new_workflow_description}
            onChange={(e) => handleConfigChange('new_workflow_description', e.target.value)}
            placeholder="描述合并后的工作流用途和特点"
            rows={3}
            disabled={isExecuting}
          />
        </div>

        <div className="form-group checkbox-group">
          <label>
            <input
              type="checkbox"
              checked={mergeConfig.preserve_original}
              onChange={(e) => handleConfigChange('preserve_original', e.target.checked)}
              disabled={isExecuting}
            />
            保留原始工作流
          </label>
        </div>

        <div className="form-group checkbox-group">
          <label>
            <input
              type="checkbox"
              checked={mergeConfig.execute_immediately}
              onChange={(e) => handleConfigChange('execute_immediately', e.target.checked)}
              disabled={isExecuting}
            />
            创建后立即执行
          </label>
        </div>

        <div className="form-group checkbox-group">
          <label>
            <input
              type="checkbox"
              checked={mergeConfig.notify_on_completion}
              onChange={(e) => handleConfigChange('notify_on_completion', e.target.checked)}
              disabled={isExecuting}
            />
            完成时通知
          </label>
        </div>
      </div>

      {executionError && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {executionError}
        </div>
      )}
    </div>
  );

  // 渲染执行步骤
  const renderExecutingStep = () => (
    <div className="merge-step executing-step">
      <h3>正在合并工作流</h3>
      
      <div className="execution-progress">
        <div className="progress-spinner"></div>
        <div className="progress-text">
          <p>正在执行合并操作，请稍候...</p>
          <div className="progress-details">
            <div>• 创建新工作流结构</div>
            <div>• 复制和替换节点</div>
            <div>• 重建连接关系</div>
            <div>• 验证工作流完整性</div>
          </div>
        </div>
      </div>
    </div>
  );

  // 渲染结果步骤
  const renderResultStep = () => {
    if (!executionResult) return null;

    return (
      <div className="merge-step result-step">
        <h3>合并完成</h3>
        
        <div className="result-summary">
          <div className="success-indicator">
            <span className="success-icon">✅</span>
            <span className="success-text">工作流合并成功！</span>
          </div>

          <div className="result-details">
            <div className="detail-group">
              <h4>新工作流信息</h4>
              <div className="detail-item">
                <span className="label">工作流名称:</span>
                <span className="value">{executionResult.new_workflow_name}</span>
              </div>
              <div className="detail-item">
                <span className="label">工作流ID:</span>
                <span className="value">{executionResult.new_workflow_id}</span>
              </div>
            </div>

            {executionResult.merge_statistics && (
              <div className="detail-group">
                <h4>合并统计</h4>
                <div className="statistics-grid">
                  <div className="stat-item">
                    <span className="stat-value">{executionResult.merge_statistics.nodes_created}</span>
                    <span className="stat-label">创建节点</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-value">{executionResult.merge_statistics.connections_created}</span>
                    <span className="stat-label">创建连接</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-value">{executionResult.merge_statistics.nodes_replaced}</span>
                    <span className="stat-label">替换节点</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-value">{executionResult.merge_statistics.replacement_operations}</span>
                    <span className="stat-label">合并操作</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="result-actions">
            <button 
              className="primary-button"
              onClick={() => {
                // 跳转到新工作流
                window.location.href = `/workflows/${executionResult.new_workflow_id}`;
              }}
            >
              查看新工作流
            </button>
            
            {mergeConfig.execute_immediately && (
              <button 
                className="secondary-button"
                onClick={() => {
                  // 跳转到执行页面
                  window.location.href = `/execution/${executionResult.new_workflow_id}`;
                }}
              >
                查看执行状态
              </button>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (!isOpen) return null;

  return (
    <div className="workflow-merge-modal-overlay" onClick={handleClose}>
      <div className="workflow-merge-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="header-title">
            <h2>工作流合并</h2>
            {mergePreviewData && (
              <span className="source-workflow">{mergePreviewData?.parent_workflow?.name || '工作流'}</span>
            )}
          </div>
          
          <div className="header-steps">
            <div className={`step-indicator ${currentStep === 'preview' ? 'active' : 'completed'}`}>
              <span className="step-number">1</span>
              <span className="step-label">预览</span>
            </div>
            <div className={`step-indicator ${currentStep === 'config' ? 'active' : ['executing', 'result'].includes(currentStep) ? 'completed' : ''}`}>
              <span className="step-number">2</span>
              <span className="step-label">配置</span>
            </div>
            <div className={`step-indicator ${currentStep === 'executing' ? 'active' : currentStep === 'result' ? 'completed' : ''}`}>
              <span className="step-number">3</span>
              <span className="step-label">执行</span>
            </div>
          </div>

          <button 
            className="close-button" 
            onClick={handleClose}
            disabled={isExecuting}
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {currentStep === 'preview' && renderPreviewStep()}
          {currentStep === 'config' && renderConfigStep()}
          {currentStep === 'executing' && renderExecutingStep()}
          {currentStep === 'result' && renderResultStep()}
        </div>

        <div className="modal-footer">
          {currentStep === 'preview' && (
            <div className="footer-actions">
              <button 
                className="secondary-button" 
                onClick={handleClose}
              >
                取消
              </button>
              <button 
                className="primary-button"
                onClick={() => setCurrentStep('config')}
                disabled={!mergePreviewData?.merge_feasibility?.can_proceed}
              >
                继续配置
              </button>
            </div>
          )}

          {currentStep === 'config' && (
            <div className="footer-actions">
              <button 
                className="secondary-button" 
                onClick={() => setCurrentStep('preview')}
                disabled={isExecuting}
              >
                返回预览
              </button>
              <button 
                className="primary-button"
                onClick={handleExecuteMerge}
                disabled={isExecuting || validateConfig().length > 0}
              >
                {isExecuting ? '执行中...' : '开始合并'}
              </button>
            </div>
          )}

          {currentStep === 'result' && (
            <div className="footer-actions">
              <button 
                className="primary-button" 
                onClick={handleClose}
              >
                完成
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WorkflowMergeModal;