import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  RocketOutlined,
  MessageOutlined,
  CloudUploadOutlined,
  DatabaseOutlined
} from '@ant-design/icons'

// 页面组件
import TrainPage from './pages/TrainPage'
import InferPage from './pages/InferPage'
import DeployPage from './pages/DeployPage'
import ModelsPage from './pages/ModelsPage'

const { Header, Content, Footer } = Layout

const menuItems = [
  {
    key: 'train',
    icon: <RocketOutlined />,
    label: '模型训练',
    path: '/train'
  },
  {
    key: 'infer',
    icon: <MessageOutlined />,
    label: '模型推理',
    path: '/infer'
  },
  {
    key: 'deploy',
    icon: <CloudUploadOutlined />,
    label: '模型部署',
    path: '/deploy'
  },
  {
    key: 'models',
    icon: <DatabaseOutlined />,
    label: '模型管理',
    path: '/models'
  }
]

function App() {
  const [selectedKey, setSelectedKey] = React.useState('train')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        background: '#001529',
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px'
      }}>
        <div style={{
          color: 'white',
          fontSize: '20px',
          fontWeight: 'bold',
          marginRight: '48px'
        }}>
          MS-SWIFT Custom UI
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems.map(item => ({
            key: item.key,
            icon: item.icon,
            label: item.label,
            onClick: () => {
              setSelectedKey(item.key)
              window.location.hash = item.path
            }
          }))}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>

      <Content style={{ padding: '24px', background: '#f0f2f5' }}>
        <div style={{
          background: 'white',
          padding: '24px',
          minHeight: 'calc(100vh - 134px)',
          borderRadius: '8px'
        }}>
          <Routes>
            <Route path="/" element={<TrainPage />} />
            <Route path="/train" element={<TrainPage />} />
            <Route path="/infer" element={<InferPage />} />
            <Route path="/deploy" element={<DeployPage />} />
            <Route path="/models" element={<ModelsPage />} />
          </Routes>
        </div>
      </Content>

      <Footer style={{ textAlign: 'center', background: '#f0f2f5' }}>
        MS-SWIFT Custom UI ©2024 | 基于 MS-SWIFT 框架开发
      </Footer>
    </Layout>
  )
}

export default App
