import React, { useState } from 'react';
import { Button, Modal, message } from 'antd';
import { BulbOutlined } from '@ant-design/icons';
import AIWorkflowGenerator from '../../components/AIWorkflowGenerator';
import WorkflowImportExport from '../../components/WorkflowImportExport';

const AIWorkflowPage: React.FC = () => {
  const [showImportModal, setShowImportModal] = useState(false);
  const [generatedWorkflowData, setGeneratedWorkflowData] = useState<any>(null);

  const handleWorkflowGenerated = (workflowData: any) => {
    setGeneratedWorkflowData(workflowData);
  };

  const handleImportToEditor = (workflowData: any) => {
    setGeneratedWorkflowData(workflowData);
    setShowImportModal(true);
  };

  const handleImportSuccess = (result: any) => {
    setShowImportModal(false);
    message.success(`工作流导入成功！已创建 ${result.nodes_created} 个节点和 ${result.connections_created} 个连接`);
    
    // 可以在这里跳转到工作流编辑页面
    if (result.workflow_base_id) {
      window.location.href = `/workflow?id=${result.workflow_base_id}`;
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <AIWorkflowGenerator
        onWorkflowGenerated={handleWorkflowGenerated}
        onImportToEditor={handleImportToEditor}
      />

      <Modal
        title="导入AI生成的工作流"
        open={showImportModal}
        onCancel={() => setShowImportModal(false)}
        footer={null}
        width={800}
      >
        {generatedWorkflowData && (
          <WorkflowImportExport
            onImportSuccess={handleImportSuccess}
            preloadedData={generatedWorkflowData}
            hideExportSection={true}
          />
        )}
      </Modal>
    </div>
  );
};

export default AIWorkflowPage;