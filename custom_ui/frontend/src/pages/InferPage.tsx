import { useState, useEffect, useRef } from 'react'
import {
  Card,
  Form,
  Input,
  Select,
  InputNumber,
  Button,
  List,
  Typography,
  Space,
  message,
  Divider,
  Row,
  Col,
  Spin,
  Tag,
} from 'antd'
import {
  SendOutlined,
  ClearOutlined,
  UploadOutlined,
  DownloadOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { inferAPI } from '@/api/infer'
import { modelAPI } from '@/api/model'
import type { LoadModelRequest, ChatRequest, ModelInfo } from '@/types'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

const InferPage = () => {
  const [loadForm] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [modelLoaded, setModelLoaded] = useState(false)
  const [currentModel, setCurrentModel] = useState<any>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [chatHistory, setChatHistory] = useState<Array<[string, string]>>([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 加载模型列表
  useEffect(() => {
    loadModels()
    checkCurrentModel()
  }, [])

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  const loadModels = async () => {
    try {
      const data = await modelAPI.getModels()
      setModels(data)
    } catch (error) {
      message.error('加载模型列表失败')
    }
  }

  const checkCurrentModel = async () => {
    try {
      const { current_model } = await inferAPI.getCurrentModel()
      if (current_model) {
        setCurrentModel(current_model)
        setModelLoaded(true)
      }
    } catch (error) {
      // 没有加载的模型
    }
  }

  // 加载模型
  const handleLoadModel = async (values: LoadModelRequest) => {
    setLoading(true)
    try {
      const response = await inferAPI.loadModel(values)
      message.success('模型加载成功')
      setModelLoaded(true)
      setCurrentModel(response)
      setChatHistory([])
    } catch (error: any) {
      message.error(error.message || '模型加载失败')
    } finally {
      setLoading(false)
    }
  }

  // 卸载模型
  const handleUnloadModel = async () => {
    try {
      await inferAPI.unloadModel()
      message.success('模型已卸载')
      setModelLoaded(false)
      setCurrentModel(null)
      setChatHistory([])
    } catch (error: any) {
      message.error(error.message || '卸载模型失败')
    }
  }

  // 发送消息
  const handleSendMessage = async () => {
    if (!input.trim()) {
      message.warning('请输入消息')
      return
    }

    if (!modelLoaded) {
      message.warning('请先加载模型')
      return
    }

    setChatLoading(true)
    const userMessage = input
    setInput('')

    try {
      const request: ChatRequest = {
        query: userMessage,
        history: chatHistory,
      }

      const response = await inferAPI.chat(request)
      setChatHistory(response.history)
    } catch (error: any) {
      message.error(error.message || '推理失败')
      // 恢复输入
      setInput(userMessage)
    } finally {
      setChatLoading(false)
    }
  }

  // 清空对话
  const handleClearChat = () => {
    setChatHistory([])
    message.success('对话已清空')
  }

  return (
    <div>
      <Title level={2}>
        <MessageOutlined /> 模型推理
      </Title>
      <Paragraph type="secondary">
        加载模型并进行对话推理
      </Paragraph>

      <Row gutter={24}>
        <Col xs={24} lg={10}>
          <Card title="模型配置" bordered={false}>
            {currentModel && modelLoaded ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text strong>当前模型:</Text>
                  <div style={{ marginTop: 8 }}>
                    <Tag color="green">{currentModel.model_id}</Tag>
                  </div>
                </div>
                {currentModel.adapter_path && (
                  <div>
                    <Text strong>Adapter:</Text>
                    <div style={{ marginTop: 8 }}>
                      <Tag color="blue">{currentModel.adapter_path}</Tag>
                    </div>
                  </div>
                )}
                <Button danger icon={<DownloadOutlined />} onClick={handleUnloadModel}>
                  卸载模型
                </Button>
              </Space>
            ) : (
              <Form
                form={loadForm}
                layout="vertical"
                onFinish={handleLoadModel}
                initialValues={{
                  max_length: 2048,
                  temperature: 0.7,
                  top_p: 0.9,
                  top_k: 50,
                  repetition_penalty: 1.0,
                }}
              >
                <Form.Item
                  label="模型"
                  name="model_id_or_path"
                  rules={[{ required: true, message: '请选择或输入模型路径' }]}
                >
                  <Select
                    showSearch
                    placeholder="选择模型或输入路径"
                    optionFilterProp="children"
                    filterOption={(input, option) =>
                      (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                    }
                    options={models.map((m) => ({
                      label: m.model_name,
                      value: m.model_id,
                    }))}
                  />
                </Form.Item>

                <Form.Item label="Adapter 路径 (可选)" name="adapter_path">
                  <Input placeholder="/path/to/adapter" />
                </Form.Item>

                <Divider>推理参数</Divider>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="Max Length" name="max_length">
                      <InputNumber min={128} step={128} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="Temperature" name="temperature">
                      <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="Top P" name="top_p">
                      <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="Top K" name="top_k">
                      <InputNumber min={0} step={10} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item label="量化位数 (可选)" name="quantization_bit">
                  <Select placeholder="不量化" allowClear>
                    <Select.Option value={4}>4-bit</Select.Option>
                    <Select.Option value={8}>8-bit</Select.Option>
                  </Select>
                </Form.Item>

                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<UploadOutlined />}
                    loading={loading}
                    block
                  >
                    加载模型
                  </Button>
                </Form.Item>
              </Form>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            title="对话界面"
            bordered={false}
            extra={
              <Button
                size="small"
                icon={<ClearOutlined />}
                onClick={handleClearChat}
                disabled={chatHistory.length === 0}
              >
                清空对话
              </Button>
            }
          >
            <div
              style={{
                height: '500px',
                overflow: 'auto',
                marginBottom: '16px',
                padding: '16px',
                background: '#f5f5f5',
                borderRadius: '8px',
              }}
            >
              {chatHistory.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 0' }}>
                  <Text type="secondary">开始对话吧...</Text>
                </div>
              ) : (
                <List
                  dataSource={chatHistory}
                  renderItem={([query, response], index) => (
                    <div key={index} style={{ marginBottom: '16px' }}>
                      {/* 用户消息 */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
                        <div
                          style={{
                            maxWidth: '70%',
                            padding: '12px 16px',
                            background: '#1890ff',
                            color: 'white',
                            borderRadius: '12px',
                            wordWrap: 'break-word',
                          }}
                        >
                          {query}
                        </div>
                      </div>
                      {/* AI 回复 */}
                      <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                        <div
                          style={{
                            maxWidth: '70%',
                            padding: '12px 16px',
                            background: 'white',
                            borderRadius: '12px',
                            wordWrap: 'break-word',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                          }}
                        >
                          {response}
                        </div>
                      </div>
                    </div>
                  )}
                />
              )}
              <div ref={messagesEndRef} />
            </div>

            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder={modelLoaded ? '输入消息...' : '请先加载模型'}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={handleSendMessage}
                disabled={!modelLoaded || chatLoading}
                size="large"
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSendMessage}
                loading={chatLoading}
                disabled={!modelLoaded}
                size="large"
              >
                发送
              </Button>
            </Space.Compact>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default InferPage
