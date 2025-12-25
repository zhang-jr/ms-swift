import { useState, useEffect } from 'react'
import {
  Card,
  Form,
  Input,
  Select,
  InputNumber,
  Button,
  Table,
  Typography,
  Space,
  message,
  Divider,
  Tag,
  Modal,
  Row,
  Col,
  Checkbox,
  Radio,
} from 'antd'
import {
  RocketOutlined,
  StopOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CloudServerOutlined,
  CopyOutlined,
  CodeOutlined,
} from '@ant-design/icons'
import { deployAPI } from '@/api/deploy'
import { modelAPI } from '@/api/model'
import type { DeployRequest, ModelInfo } from '@/types'

const { Title, Text, Paragraph } = Typography

const DeployPage = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [deployments, setDeployments] = useState<any[]>([])
  const [baseModels, setBaseModels] = useState<ModelInfo[]>([])
  const [trainedModels, setTrainedModels] = useState<ModelInfo[]>([])
  const [modelSource, setModelSource] = useState<'base' | 'trained'>('base')
  const [gpuStatus, setGpuStatus] = useState<any>(null)
  const [exampleModalVisible, setExampleModalVisible] = useState(false)
  const [selectedDeployment, setSelectedDeployment] = useState<any>(null)

  useEffect(() => {
    loadBaseModels()
    loadTrainedModels()
    loadDeployments()
    loadGpuStatus()

    // 每 10 秒自动刷新部署列表和 GPU 状态
    const interval = setInterval(() => {
      loadDeployments()
      loadGpuStatus()
    }, 10000)

    return () => clearInterval(interval)
  }, [])

  const loadBaseModels = async () => {
    try {
      const data = await modelAPI.getModels()
      console.log('[DeployPage] 加载的基础模型列表:', data)
      setBaseModels(data)
    } catch (error) {
      message.error('加载基础模型列表失败')
    }
  }

  const loadTrainedModels = async () => {
    try {
      const data = await modelAPI.getTrainedModels()
      console.log('[DeployPage] 加载的训练输出模型列表:', data)
      setTrainedModels(data)
    } catch (error) {
      message.error('加载训练输出模型列表失败')
    }
  }

  const loadDeployments = async () => {
    try {
      const { deployments: deps } = await deployAPI.listDeployments()
      setDeployments(deps)
    } catch (error) {
      message.error('加载部署列表失败')
    }
  }

  const loadGpuStatus = async () => {
    try {
      const data = await deployAPI.getGpuStatus()
      setGpuStatus(data)
    } catch (error) {
      console.error('加载 GPU 状态失败:', error)
    }
  }

  // 启动部署
  const handleStartDeployment = async (values: DeployRequest) => {
    console.log('[DeployPage] 表单提交的值:', values)
    console.log('[DeployPage] model_id_or_path:', values.model_id_or_path)
    setLoading(true)
    try {
      await deployAPI.startDeployment(values)
      message.success('部署服务已启动')
      form.resetFields()
      loadDeployments()
    } catch (error: any) {
      console.error('[DeployPage] 部署失败:', error)
      message.error(error.message || '启动部署失败')
    } finally {
      setLoading(false)
    }
  }

  // 停止部署
  const handleStopDeployment = async (deploymentId: string) => {
    try {
      await deployAPI.stopDeployment(deploymentId)
      message.success('部署服务已停止')
      loadDeployments()
    } catch (error: any) {
      message.error(error.message || '停止部署失败')
    }
  }

  // 删除部署
  const handleDeleteDeployment = (deploymentId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除此部署记录吗?',
      onOk: async () => {
        try {
          await deployAPI.deleteDeployment(deploymentId)
          message.success('部署记录已删除')
          loadDeployments()
        } catch (error: any) {
          message.error(error.message || '删除失败')
        }
      },
    })
  }

  // 显示使用示例
  const handleShowExample = (deployment: any) => {
    setSelectedDeployment(deployment)
    setExampleModalVisible(true)
  }

  // 复制示例代码
  const handleCopyExample = (code: string) => {
    navigator.clipboard.writeText(code)
    message.success('示例代码已复制')
  }

  const columns = [
    {
      title: '部署 ID',
      dataIndex: 'deployment_id',
      key: 'deployment_id',
      width: 100,
      render: (text: string) => <Text code>{text.substring(0, 8)}</Text>,
    },
    {
      title: '模型',
      dataIndex: 'served_model_name',
      key: 'served_model_name',
      ellipsis: true,
      render: (text: string, record: any) => {
        // 显示 served_model_name，tooltip 显示完整路径
        return (
          <Text ellipsis={{ tooltip: record.model_path }} style={{ maxWidth: 200 }}>
            {text}
          </Text>
        )
      },
    },
    {
      title: 'GPU',
      dataIndex: 'gpu_id',
      key: 'gpu_id',
      width: 80,
      align: 'center' as const,
      render: (gpu_id: string) => (
        <Tag color="cyan">GPU {gpu_id}</Tag>
      ),
    },
    {
      title: '端口',
      dataIndex: 'port',
      key: 'port',
      width: 80,
      align: 'center' as const,
      render: (port: number) => <Text code>{port}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      align: 'center' as const,
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          starting: 'processing',  // 蓝色动画
          running: 'success',      // 绿色
          unhealthy: 'warning',    // 橙色
          stopped: 'default',      // 灰色
          failed: 'error',         // 红色
          timeout: 'error',        // 红色
        }
        const textMap: Record<string, string> = {
          starting: '启动中',
          running: '运行中',
          unhealthy: '不健康',
          stopped: '已停止',
          failed: '失败',
          timeout: '超时',
        }
        return <Tag color={colorMap[status] || 'default'}>{textMap[status] || status}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (text: string) => {
        const date = new Date(text)
        // 格式：12-24 19:50
        return date.toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Space size="small">
          {record.status === 'running' ? (
            <>
              <Button
                size="small"
                icon={<CodeOutlined />}
                onClick={() => handleShowExample(record)}
              >
                示例
              </Button>
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                onClick={() => handleStopDeployment(record.deployment_id)}
              >
                停止
              </Button>
            </>
          ) : null}
          {record.status !== 'running' ? (
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeleteDeployment(record.deployment_id)}
            >
              删除
            </Button>
          ) : null}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={2} style={{ color: '#fff', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <RocketOutlined style={{ color: '#667eea' }} /> 模型部署
      </Title>
      <Paragraph type="secondary" style={{ fontSize: '15px', marginBottom: '24px' }}>
        <CloudServerOutlined /> 将模型部署为高性能 API 服务，支持 OpenAI 兼容接口
      </Paragraph>

      {/* GPU 状态卡片 */}
      {gpuStatus && (
        <Card
          title={`GPU 状态 (${gpuStatus.used_gpus}/${gpuStatus.total_gpus} 使用中)`}
          bordered={false}
          style={{ marginBottom: '24px' }}
          extra={
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={loadGpuStatus}
            >
              刷新
            </Button>
          }
        >
          <Row gutter={[16, 16]}>
            {gpuStatus.gpus.map((gpu: any) => (
              <Col xs={24} sm={12} md={8} lg={6} key={gpu.gpu_id}>
                <Card
                  size="small"
                  bordered
                  style={{
                    borderColor: gpu.status === 'available' ? '#52c41a' : '#ff7875',
                  }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong>GPU {gpu.gpu_id}</Text>
                      <Tag color={gpu.status === 'available' ? 'success' : 'error'}>
                        {gpu.status === 'available' ? '空闲' : '使用中'}
                      </Tag>
                    </div>
                    {gpu.deployments.length > 0 && (
                      <div>
                        {gpu.deployments.map((dep: any) => (
                          <div key={dep.deployment_id} style={{ fontSize: '12px', color: '#8c8c8c' }}>
                            <Text code style={{ fontSize: '11px' }}>
                              {dep.deployment_id.substring(0, 8)}
                            </Text>
                            <br />
                            <Text style={{ fontSize: '11px' }}>{dep.model.split('/').pop()}</Text>
                          </div>
                        ))}
                      </div>
                    )}
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      <Row gutter={24}>
        <Col xs={24} lg={10}>
          <Card title="部署配置" bordered={false}>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleStartDeployment}
              initialValues={{
                host: '0.0.0.0',
                port: 8080,
                max_length: 2048,
                temperature: 0.7,
                top_p: 0.9,
                use_vllm: true,  // 默认启用 vLLM
                gpu_memory_utilization: 0.9,
              }}
            >
              <Form.Item label="模型来源">
                <Radio.Group
                  value={modelSource}
                  onChange={(e) => {
                    setModelSource(e.target.value)
                    // 切换来源时清空已选择的模型
                    form.setFieldsValue({ model_id_or_path: undefined })
                  }}
                  buttonStyle="solid"
                >
                  <Radio.Button value="base">
                    <CloudServerOutlined /> 基础模型 (/app/models)
                  </Radio.Button>
                  <Radio.Button value="trained">
                    <RocketOutlined /> 训练输出 (/app/output)
                  </Radio.Button>
                </Radio.Group>
              </Form.Item>

              <Form.Item
                label="模型"
                name="model_id_or_path"
                rules={[{ required: true, message: '请选择模型' }]}
                tooltip={
                  modelSource === 'base'
                    ? '从 /app/models 目录选择预训练模型'
                    : '从 /app/output 目录选择训练输出的模型（checkpoint）'
                }
              >
                <Select
                  placeholder={
                    modelSource === 'base'
                      ? '选择基础模型'
                      : '选择训练输出模型'
                  }
                  showSearch
                  onChange={(value) => {
                    // 选中模型时，自动设置 served_model_name
                    const selectedModel = (modelSource === 'base' ? baseModels : trainedModels).find(
                      (m) => m.model_id === value
                    )
                    if (selectedModel) {
                      form.setFieldsValue({ served_model_name: selectedModel.model_name })
                    }
                  }}
                  filterOption={(input, option) => {
                    const searchText = input.toLowerCase()
                    const modelData = option?.data as { model?: ModelInfo }
                    // 搜索 model_name 和 model_id
                    if (modelData?.model) {
                      const m = modelData.model
                      return (
                        m.model_name.toLowerCase().includes(searchText) ||
                        m.model_id.toLowerCase().includes(searchText)
                      )
                    }
                    return false
                  }}
                  options={
                    (modelSource === 'base' ? baseModels : trainedModels).map((m) => ({
                      label: m.model_name,  // 选中后显示简短的 model_name
                      value: m.model_id,    // 实际传递的值（绝对路径）
                      data: { model: m },   // 附加数据供 optionRender 使用
                    }))
                  }
                  optionRender={(option) => {
                    // 下拉列表中的自定义渲染
                    const modelData = option?.data as { model?: ModelInfo } | undefined

                    // 降级方案：如果没有 model 数据，只显示 label
                    if (!modelData?.model) {
                      return <div>{option.label}</div>
                    }

                    const m = modelData.model
                    return (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ flex: 1, overflow: 'hidden' }}>
                          <div style={{ fontWeight: 500 }}>{m.model_name}</div>
                          <div
                            style={{
                              fontSize: '12px',
                              color: '#888',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                            title={m.model_id}
                          >
                            {m.model_id}
                          </div>
                        </div>
                        <Space>
                          {m.model_type === 'adapter' ? (
                            <Tag color="blue">Adapter</Tag>
                          ) : (
                            <Tag color="green">Base</Tag>
                          )}
                          {m.size && <Tag>{m.size}</Tag>}
                        </Space>
                      </div>
                    )
                  }}
                />
              </Form.Item>

              {/* 隐藏字段：自动设置 served_model_name */}
              <Form.Item name="served_model_name" hidden>
                <Input />
              </Form.Item>

              <Form.Item label="Adapter 路径 (可选)" name="adapter_path">
                <Input placeholder="/path/to/adapter" />
              </Form.Item>

              <Divider>服务配置</Divider>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="Host" name="host">
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Port" name="port">
                    <InputNumber min={1024} max={65535} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

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

              <Form.Item name="use_vllm" valuePropName="checked">
                <Checkbox>使用 vLLM (推荐)</Checkbox>
              </Form.Item>

              <Form.Item label="GPU 内存利用率" name="gpu_memory_utilization">
                <InputNumber min={0.1} max={1} step={0.1} style={{ width: '100%' }} />
              </Form.Item>

              <Form.Item label="量化位数 (可选)" name="quantization_bit">
                <Select placeholder="不量化" allowClear>
                  <Select.Option value={4}>4-bit</Select.Option>
                  <Select.Option value={8}>8-bit</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<RocketOutlined />}
                    loading={loading}
                  >
                    启动部署
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={loadDeployments}>
                    刷新列表
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card title="部署列表" bordered={false}>
            <Table
              dataSource={deployments}
              columns={columns}
              rowKey="deployment_id"
              pagination={{ pageSize: 10, size: 'small' }}
              size="small"
              scroll={{ x: 'max-content' }}
            />
          </Card>

        </Col>
      </Row>

      {/* 使用示例 Modal */}
      <Modal
        title="使用示例 - OpenAI 兼容接口"
        open={exampleModalVisible}
        onCancel={() => setExampleModalVisible(false)}
        width={800}
        footer={null}
      >
        {selectedDeployment && (
          <div>
            <Paragraph type="secondary">
              部署 ID: <Text code>{selectedDeployment.deployment_id}</Text>
              <br />
              模型: <Text strong>{selectedDeployment.model_id}</Text>
              <br />
              端点: <Text code>{selectedDeployment.endpoint}</Text>
            </Paragraph>

            <Divider />

            {/* Python 示例 */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Text strong style={{ fontSize: 16 }}>Python (OpenAI SDK)</Text>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => handleCopyExample(
`from openai import OpenAI

# 创建客户端
client = OpenAI(
    api_key="EMPTY",  # vLLM 不需要 API key
    base_url="${selectedDeployment.base_url}/v1",
)

# 发送对话请求
response = client.chat.completions.create(
    model="${selectedDeployment.served_model_name}",  # 使用部署时指定的模型名称
    messages=[
        {"role": "system", "content": "你是一个有用的助手。"},
        {"role": "user", "content": "你好，请介绍一下自己。"}
    ],
    temperature=0.7,
    max_tokens=2048,
)

print(response.choices[0].message.content)`
                  )}
                >
                  复制
                </Button>
              </div>
              <pre style={{
                background: '#1f1f1f',
                color: '#d4d4d4',
                padding: '16px',
                borderRadius: '6px',
                overflow: 'auto',
                fontSize: '13px',
                lineHeight: '1.6'
              }}>
{`from openai import OpenAI

# 创建客户端
client = OpenAI(
    api_key="EMPTY",  # vLLM 不需要 API key
    base_url="${selectedDeployment.base_url}/v1",
)

# 发送对话请求
response = client.chat.completions.create(
    model="${selectedDeployment.served_model_name}",  # 使用部署时指定的模型名称
    messages=[
        {"role": "system", "content": "你是一个有用的助手。"},
        {"role": "user", "content": "你好，请介绍一下自己。"}
    ],
    temperature=0.7,
    max_tokens=2048,
)

print(response.choices[0].message.content)`}
              </pre>
            </div>

            {/* curl 示例 */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Text strong style={{ fontSize: 16 }}>curl</Text>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => handleCopyExample(
`curl ${selectedDeployment.endpoint} \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${selectedDeployment.served_model_name}",
    "messages": [
      {"role": "system", "content": "你是一个有用的助手。"},
      {"role": "user", "content": "你好，请介绍一下自己。"}
    ],
    "temperature": 0.7,
    "max_tokens": 2048
  }'`
                  )}
                >
                  复制
                </Button>
              </div>
              <pre style={{
                background: '#1f1f1f',
                color: '#d4d4d4',
                padding: '16px',
                borderRadius: '6px',
                overflow: 'auto',
                fontSize: '13px',
                lineHeight: '1.6'
              }}>
{`curl ${selectedDeployment.endpoint} \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${selectedDeployment.served_model_name}",
    "messages": [
      {"role": "system", "content": "你是一个有用的助手。"},
      {"role": "user", "content": "你好，请介绍一下自己。"}
    ],
    "temperature": 0.7,
    "max_tokens": 2048
  }'`}
              </pre>
            </div>

            <Divider />

            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              <Text strong>注意事项:</Text>
              <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                <li>部署服务使用 OpenAI 兼容接口，可直接使用 OpenAI SDK</li>
                <li>模型名称 (model) 应为部署时指定的 served_model_name</li>
                <li>vLLM 不需要 API key，可设置为 "EMPTY"</li>
                <li>支持流式输出，设置 <Text code>stream=True</Text></li>
              </ul>
            </Paragraph>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default DeployPage
