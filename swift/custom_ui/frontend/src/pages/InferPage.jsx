/**
 * 推理页面
 */
import React, { useState } from 'react'
import { Card, Input, Button, List, Space, message } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { inferAPI } from '../api/infer'

const { TextArea } = Input

const InferPage = () => {
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSend = async () => {
    if (!inputValue.trim()) return

    const userMessage = {
      role: 'user',
      content: inputValue
    }

    setMessages([...messages, userMessage])
    setInputValue('')
    setLoading(true)

    try {
      const result = await inferAPI.chat({
        messages: [...messages, userMessage],
        temperature: 0.7
      })

      setMessages([...messages, userMessage, result.message])
    } catch (error) {
      message.error('推理失败: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card title="模型推理" bordered={false}>
      <div style={{ marginBottom: '16px' }}>
        <Button type="primary" onClick={() => message.info('请先部署模型')}>
          加载模型
        </Button>
      </div>

      <div style={{
        height: '400px',
        overflowY: 'auto',
        border: '1px solid #f0f0f0',
        padding: '16px',
        marginBottom: '16px',
        borderRadius: '4px'
      }}>
        <List
          dataSource={messages}
          renderItem={(item) => (
            <List.Item style={{
              justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start'
            }}>
              <div style={{
                maxWidth: '70%',
                padding: '8px 12px',
                borderRadius: '8px',
                background: item.role === 'user' ? '#1890ff' : '#f0f0f0',
                color: item.role === 'user' ? 'white' : 'black'
              }}>
                {item.content}
              </div>
            </List.Item>
          )}
        />
      </div>

      <Space.Compact style={{ width: '100%' }}>
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="输入消息..."
          autoSize={{ minRows: 2, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={loading}
          onClick={handleSend}
        >
          发送
        </Button>
      </Space.Compact>
    </Card>
  )
}

export default InferPage
