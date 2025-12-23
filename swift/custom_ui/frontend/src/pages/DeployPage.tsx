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
} from 'antd'
import {
  RocketOutlined,
  StopOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CloudServerOutlined,
  CopyOutlined,
} from '@ant-design/icons'
import { deployAPI } from '@/api/deploy'
import { modelAPI } from '@/api/model'
import type { DeployRequest, ModelInfo } from '@/types'

const { Title, Text, Paragraph } = Typography

const DeployPage = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [deployments, setDeployments] = useState<any[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])

  useEffect(() => {
    loadModels()
    loadDeployments()
  }, [])

  const loadModels = async () => {
    try {
      const data = await modelAPI.getModels()
      setModels(data)
    } catch (error) {
      message.error('加载模型列表失败')
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

  // 启动部署
  const handleStartDeployment = async (values: DeployRequest) => {
    setLoading(true)
    try {
      await deployAPI.startDeployment(values)
      message.success('部署服务已启动')
      form.resetFields()
      loadDeployments()
    } catch (error: any) {
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

  // 复制端点地址
  const handleCopyEndpoint = (endpoint: string) => {
    navigator.clipboard.writeText(endpoint)
    message.success('端点地址已复制')
  }

  const columns = [
    {
      title: '部署 ID',
      dataIndex: 'deployment_id',
      key: 'deployment_id',
      render: (text: string) => <Text code>{text.substring(0, 8)}</Text>,
    },
    {
      title: '模型',
      dataIndex: 'model_id',
      key: 'model_id',
    },
    {
      title: '端点地址',
      dataIndex: 'endpoint',
      key: 'endpoint',
      render: (text: string) => (
        <Space>
          <Text code>{text}</Text>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={() => handleCopyEndpoint(text)}
          />
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          starting: 'blue',
          running: 'green',
          stopped: 'default',
          failed: 'red',
        }
        return <Tag color={colorMap[status]}>{status}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => new Date(text).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          {record.status === 'running' ? (
            <Button
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => handleStopDeployment(record.deployment_id)}
            >
              停止
            </Button>
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

      <Row gutter={24}>
        <Col xs={24} lg={12}>
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

        <Col xs={24} lg={12}>
          <Card title="部署列表" bordered={false}>
            <Table
              dataSource={deployments}
              columns={columns}
              rowKey="deployment_id"
              pagination={false}
              size="small"
            />
          </Card>

          <Card title="使用示例" bordered={false} style={{ marginTop: 24 }}>
            <Paragraph>
              <Text strong>OpenAI 兼容接口:</Text>
            </Paragraph>
            <pre style={{
              background: '#1f1f1f',
              color: '#d4d4d4',  // 可见的灰色文字
              padding: '12px',
              borderRadius: '4px',
              overflow: 'auto'
            }}>
{`import openai
client = openai.OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8080/v1",
)

response = client.chat.completions.create(
    model="default",
    messages=[
        {"role": "user", "content": "你好"}
    ]
)
print(response.choices[0].message.content)`}
            </pre>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default DeployPage
