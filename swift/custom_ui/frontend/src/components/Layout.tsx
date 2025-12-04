import { Outlet, Link, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, theme } from 'antd'
import {
  ExperimentOutlined,
  MessageOutlined,
  CloudServerOutlined,
  GithubOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  ApiOutlined,
} from '@ant-design/icons'

const { Header, Content, Footer } = AntLayout

const Layout = () => {
  const location = useLocation()
  const {
    token: { colorBgContainer },
  } = theme.useToken()

  const menuItems = [
    {
      key: '/train',
      icon: <ThunderboltOutlined />,
      label: <Link to="/train">模型训练</Link>,
    },
    {
      key: '/infer',
      icon: <ApiOutlined />,
      label: <Link to="/infer">模型推理</Link>,
    },
    {
      key: '/deploy',
      icon: <RocketOutlined />,
      label: <Link to="/deploy">模型部署</Link>,
    },
  ]

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
        }}
      >
        <div style={{
          color: 'white',
          fontSize: '24px',
          fontWeight: 'bold',
          marginRight: '40px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontFamily: 'monospace',
          letterSpacing: '1px'
        }}>
          <ExperimentOutlined style={{ fontSize: '28px' }} />
          DocForgery
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{
            flex: 1,
            minWidth: 0,
            background: 'transparent',
            fontSize: '15px'
          }}
        />
      </Header>
      <Content style={{
        padding: '24px',
        minHeight: 'calc(100vh - 134px)',
        background: 'linear-gradient(180deg, #0f0c29 0%, #302b63 50%, #24243e 100%)'
      }}>
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.05)',
            backdropFilter: 'blur(10px)',
            padding: 24,
            minHeight: '100%',
            borderRadius: 12,
            border: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)'
          }}
        >
          <Outlet />
        </div>
      </Content>
      <Footer style={{
        textAlign: 'center',
        background: '#141414',
        color: 'rgba(255, 255, 255, 0.65)'
      }}>
        DocForgery Training Platform ©{new Date().getFullYear()} |{' '}
        <a
          href="https://github.com/modelscope/ms-swift"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: '#667eea' }}
        >
          <GithubOutlined /> GitHub
        </a>
      </Footer>
    </AntLayout>
  )
}

export default Layout
