import { Outlet, Link, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, theme } from 'antd'
import {
  ExperimentOutlined,
  MessageOutlined,
  CloudServerOutlined,
  GithubOutlined,
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
      icon: <ExperimentOutlined />,
      label: <Link to="/train">模型训练</Link>,
    },
    {
      key: '/infer',
      icon: <MessageOutlined />,
      label: <Link to="/infer">模型推理</Link>,
    },
    {
      key: '/deploy',
      icon: <CloudServerOutlined />,
      label: <Link to="/deploy">模型部署</Link>,
    },
  ]

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
        <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold', marginRight: '40px' }}>
          MS-SWIFT Web UI
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{ flex: 1, minWidth: 0 }}
        />
      </Header>
      <Content style={{ padding: '24px', minHeight: 'calc(100vh - 134px)' }}>
        <div
          style={{
            background: colorBgContainer,
            padding: 24,
            minHeight: '100%',
            borderRadius: 8,
          }}
        >
          <Outlet />
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        MS-SWIFT Custom UI ©{new Date().getFullYear()} |{' '}
        <a
          href="https://github.com/modelscope/ms-swift"
          target="_blank"
          rel="noopener noreferrer"
        >
          <GithubOutlined /> GitHub
        </a>
      </Footer>
    </AntLayout>
  )
}

export default Layout
