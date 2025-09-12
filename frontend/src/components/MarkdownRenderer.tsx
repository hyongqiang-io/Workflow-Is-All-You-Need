import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Typography, Alert, Divider, Table, Tag } from 'antd';
import { 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  InfoCircleOutlined, 
  WarningOutlined,
  LinkOutlined,
  CopyOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

interface MarkdownRendererProps {
  content: string;
  className?: string;
  style?: React.CSSProperties;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className,
  style
}) => {
  const customComponents = {
    // 标题渲染
    h1: ({ children, ...props }: any) => (
      <Title level={1} style={{ marginTop: '32px', marginBottom: '16px' }} {...props}>
        {children}
      </Title>
    ),
    h2: ({ children, ...props }: any) => (
      <Title level={2} style={{ marginTop: '24px', marginBottom: '12px' }} {...props}>
        {children}
      </Title>
    ),
    h3: ({ children, ...props }: any) => (
      <Title level={3} style={{ marginTop: '20px', marginBottom: '10px' }} {...props}>
        {children}
      </Title>
    ),
    h4: ({ children, ...props }: any) => (
      <Title level={4} style={{ marginTop: '16px', marginBottom: '8px' }} {...props}>
        {children}
      </Title>
    ),
    h5: ({ children, ...props }: any) => (
      <Title level={5} style={{ marginTop: '14px', marginBottom: '6px' }} {...props}>
        {children}
      </Title>
    ),

    // 段落渲染
    p: ({ children, ...props }: any) => (
      <Paragraph style={{ lineHeight: '1.8', marginBottom: '16px' }} {...props}>
        {children}
      </Paragraph>
    ),

    // 代码块渲染
    code: ({ node, inline, className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';
      
      if (!inline && language) {
        return (
          <div style={{ position: 'relative', marginBottom: '16px' }}>
            <div
              style={{
                position: 'absolute',
                top: '8px',
                right: '8px',
                zIndex: 1,
                opacity: 0.7,
                cursor: 'pointer'
              }}
              onClick={() => {
                navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
              }}
              title="复制代码"
            >
              <CopyOutlined style={{ color: '#fff' }} />
            </div>
            <SyntaxHighlighter
              language={language}
              style={oneDark}
              customStyle={{
                borderRadius: '6px',
                fontSize: '14px',
                padding: '16px'
              }}
              {...props}
            >
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          </div>
        );
      }

      return (
        <Text
          code
          style={{
            backgroundColor: '#f5f5f5',
            padding: '2px 4px',
            borderRadius: '3px',
            fontSize: '0.9em'
          }}
          {...props}
        >
          {children}
        </Text>
      );
    },

    // 链接渲染
    a: ({ href, children, ...props }: any) => (
      <Text
        style={{ 
          color: '#1890ff',
          textDecoration: 'none',
          borderBottom: '1px dashed #1890ff',
          cursor: 'pointer'
        }}
        onClick={(e) => {
          e.preventDefault();
          if (href?.startsWith('http')) {
            window.open(href, '_blank', 'noopener,noreferrer');
          } else if (href?.startsWith('#')) {
            // 处理锚点链接
            const element = document.getElementById(href.slice(1));
            if (element) {
              element.scrollIntoView({ behavior: 'smooth' });
            }
          }
        }}
        {...props}
      >
        <LinkOutlined style={{ marginRight: '4px', fontSize: '12px' }} />
        {children}
      </Text>
    ),

    // 列表渲染
    ul: ({ children, ...props }: any) => (
      <ul style={{ marginBottom: '16px', paddingLeft: '24px' }} {...props}>
        {children}
      </ul>
    ),
    ol: ({ children, ...props }: any) => (
      <ol style={{ marginBottom: '16px', paddingLeft: '24px' }} {...props}>
        {children}
      </ol>
    ),
    li: ({ children, ...props }: any) => (
      <li style={{ marginBottom: '4px', lineHeight: '1.6' }} {...props}>
        {children}
      </li>
    ),

    // 引用块渲染
    blockquote: ({ children, ...props }: any) => {
      // 检查是否是特殊提示块
      const content = String(children).toLowerCase();
      
      let alertType: 'success' | 'info' | 'warning' | 'error' = 'info';
      let icon = <InfoCircleOutlined />;
      
      if (content.includes('⚠️') || content.includes('warning') || content.includes('注意')) {
        alertType = 'warning';
        icon = <WarningOutlined />;
      } else if (content.includes('✅') || content.includes('success') || content.includes('成功')) {
        alertType = 'success';
        icon = <CheckCircleOutlined />;
      } else if (content.includes('❌') || content.includes('error') || content.includes('错误')) {
        alertType = 'error';
        icon = <ExclamationCircleOutlined />;
      }

      return (
        <Alert
          type={alertType}
          icon={icon}
          message={children}
          style={{
            marginBottom: '16px',
            borderRadius: '6px'
          }}
          showIcon
          {...props}
        />
      );
    },

    // 表格渲染
    table: ({ children, ...props }: any) => {
      // 提取表格数据
      const rows = React.Children.toArray(children).filter((child: any) => 
        child?.props?.children
      );
      
      if (!rows.length) return null;

      const headerRow = rows[0] as React.ReactElement;
      const bodyRows = rows.slice(1);
      
      // 提取表头
      const headers = React.Children.toArray(headerRow.props.children).map((th: any, index) => ({
        title: th.props.children,
        dataIndex: `col${index}`,
        key: `col${index}`,
        ellipsis: true
      }));

      // 提取表格数据
      const dataSource = bodyRows.map((row: any, rowIndex) => {
        const cells = React.Children.toArray(row.props.children);
        const rowData: any = { key: rowIndex };
        
        cells.forEach((cell: any, cellIndex) => {
          rowData[`col${cellIndex}`] = cell.props.children;
        });
        
        return rowData;
      });

      return (
        <Table
          columns={headers}
          dataSource={dataSource}
          pagination={false}
          size="small"
          style={{ marginBottom: '16px' }}
          bordered
          {...props}
        />
      );
    },

    // 分割线
    hr: () => <Divider style={{ margin: '24px 0' }} />,

    // 强调文本
    strong: ({ children, ...props }: any) => (
      <Text strong {...props}>{children}</Text>
    ),
    em: ({ children, ...props }: any) => (
      <Text italic {...props}>{children}</Text>
    ),

    // 删除线
    del: ({ children, ...props }: any) => (
      <Text delete {...props}>{children}</Text>
    ),

    // 任务列表
    input: ({ checked, ...props }: any) => {
      if (props.type === 'checkbox') {
        return (
          <span style={{ marginRight: '8px' }}>
            {checked ? (
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
            ) : (
              <span style={{ 
                display: 'inline-block',
                width: '14px',
                height: '14px',
                border: '2px solid #d9d9d9',
                borderRadius: '2px'
              }} />
            )}
          </span>
        );
      }
      return <input {...props} />;
    }
  };

  return (
    <div 
      className={className}
      style={{
        fontSize: '14px',
        lineHeight: '1.8',
        color: 'rgba(0, 0, 0, 0.85)',
        ...style
      }}
    >
      <ReactMarkdown
        components={customComponents}
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        skipHtml={false}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;