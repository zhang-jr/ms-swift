import React, { Component, ReactNode } from 'react'
import { Result, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] 捕获到错误:', error, errorInfo)
    this.setState({
      error,
      errorInfo,
    })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            background: '#0a0a0a',
          }}
        >
          <Result
            status="error"
            title="页面渲染出错"
            subTitle={
              <div>
                <div style={{ marginBottom: 16 }}>
                  抱歉，页面遇到了一些问题。请尝试刷新页面或联系技术支持。
                </div>
                {this.state.error && (
                  <div
                    style={{
                      background: 'rgba(0, 0, 0, 0.5)',
                      padding: 16,
                      borderRadius: 8,
                      textAlign: 'left',
                      fontSize: 12,
                      fontFamily: 'monospace',
                      color: '#f5222d',
                      maxWidth: 600,
                      overflow: 'auto',
                    }}
                  >
                    <div style={{ marginBottom: 8, fontWeight: 'bold' }}>错误信息:</div>
                    <div>{this.state.error.toString()}</div>
                    {this.state.errorInfo && (
                      <>
                        <div style={{ marginTop: 16, marginBottom: 8, fontWeight: 'bold' }}>
                          堆栈跟踪:
                        </div>
                        <div style={{ whiteSpace: 'pre-wrap' }}>
                          {this.state.errorInfo.componentStack}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            }
            extra={[
              <Button type="primary" key="reload" icon={<ReloadOutlined />} onClick={this.handleReload}>
                刷新页面
              </Button>,
              <Button key="reset" onClick={this.handleReset}>
                尝试恢复
              </Button>,
            ]}
          />
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
