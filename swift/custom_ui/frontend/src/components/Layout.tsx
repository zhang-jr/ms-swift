import { Outlet, Link, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Avatar, Dropdown } from 'antd'
import {
  ExperimentOutlined,
  HomeOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  RocketOutlined,
  UserOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons'

const { Sider, Content } = AntLayout

const Layout = () => {
  const location = useLocation()

  // 左侧边栏菜单项
  const menuItems = [
    {
      key: '/data',
      icon: <DatabaseOutlined />,
      label: <Link to="/data">数据管理</Link>,
    },
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

  // 用户菜单
  const userMenuItems = [
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出',
    },
  ]

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      {/* 左侧边栏 */}
      <Sider
        width={240}
        style={{
          background: '#1a1a1a',
          borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Logo 区域 */}
        <div
          style={{
            height: '64px',
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            cursor: 'pointer',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginRight: '12px',
            }}
          >
            <ExperimentOutlined style={{ fontSize: '20px', color: 'white' }} />
          </div>
          <span
            style={{
              color: 'white',
              fontSize: '18px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
            }}
          >
            DocForgery
          </span>
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{
            background: 'transparent',
            border: 'none',
            marginTop: '20px',
            color: 'rgba(255, 255, 255, 0.65)',
          }}
          theme="dark"
        />
      </Sider>

      {/* 主内容区 */}
      <AntLayout>
        {/* 顶部栏（可选：面包屑、用户信息等） */}
        <div
          style={{
            height: '64px',
            background: '#141414',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
          }}
        >
          <div style={{ color: 'rgba(255, 255, 255, 0.85)', fontSize: '16px' }}>
            {location.pathname === '/data' && '数据管理'}
            {location.pathname === '/train' && '模型训练'}
            {location.pathname === '/infer' && '模型推理'}
            {location.pathname === '/deploy' && '模型部署'}
          </div>

          {/* 用户头像 */}
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Avatar
              style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                cursor: 'pointer',
              }}
              icon={<UserOutlined />}
            />
          </Dropdown>
        </div>

        {/* 内容区域 */}
        <Content
          style={{
            padding: '24px',
            minHeight: 'calc(100vh - 64px)',
            background: '#0a0a0a',
          }}
        >
          <div
            style={{
              background: '#1a1a1a',
              padding: 24,
              minHeight: '100%',
              borderRadius: 12,
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <Outlet />
          </div>
        </Content>
      </AntLayout>
    </AntLayout>
  )
}

export default Layout
