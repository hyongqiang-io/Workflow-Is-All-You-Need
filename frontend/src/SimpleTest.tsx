import React from 'react';

const SimpleTest: React.FC = () => {
  console.log('SimpleTest组件正在渲染');
  
  React.useEffect(() => {
    console.log('SimpleTest组件已挂载');
  }, []);

  return (
    <div style={{ padding: '20px' }}>
      <h1>简单测试页面</h1>
      <p>如果你看到这个页面，说明React应用正在运行</p>
      <button onClick={() => {
        console.log('按钮被点击');
        fetch('http://localhost:8002/api/auth/me')
          .then(res => res.json())
          .then(data => console.log('API响应:', data))
          .catch(err => console.error('API错误:', err));
      }}>
        测试API连接
      </button>
    </div>
  );
};

export default SimpleTest;