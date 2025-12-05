import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import Layout from './components/Layout'
import DataManagementPage from './pages/DataManagementPage'
import TrainPage from './pages/TrainPage'
import InferPage from './pages/InferPage'
import DeployPage from './pages/DeployPage'

function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#667eea',
          colorSuccess: '#52c41a',
          colorWarning: '#faad14',
          colorError: '#f5222d',
          colorInfo: '#667eea',
          borderRadius: 8,
          fontSize: 14,
          colorBgContainer: 'rgba(255, 255, 255, 0.08)',
          colorBorder: 'rgba(255, 255, 255, 0.15)',
        },
        components: {
          Card: {
            colorBgContainer: 'rgba(255, 255, 255, 0.06)',
            boxShadowTertiary: '0 6px 16px 0 rgba(0, 0, 0, 0.32)',
          },
          Button: {
            primaryShadow: '0 2px 0 rgba(102, 126, 234, 0.1)',
          },
          Input: {
            colorBgContainer: 'rgba(0, 0, 0, 0.25)',
          },
          Select: {
            colorBgContainer: 'rgba(0, 0, 0, 0.25)',
          },
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/data" replace />} />
            <Route path="data" element={<DataManagementPage />} />
            <Route path="train" element={<TrainPage />} />
            <Route path="infer" element={<InferPage />} />
            <Route path="deploy" element={<DeployPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
