import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Card,
  Form,
  Select,
  InputNumber,
  Button,
  Progress,
  Typography,
  Space,
  message,
  Divider,
  Row,
  Col,
  Collapse,
  Alert,
  Tag,
} from 'antd'
import {
  PlayCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  RocketOutlined,
  FireOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DatabaseOutlined,
  FolderOutlined,
} from '@ant-design/icons'
import { trainAPI, connectTrainLogs } from '@/api/train'
import { modelAPI } from '@/api/model'
import { dataAPI } from '@/api/data'
import type { TrainRequest, TrainStatus, ModelInfo } from '@/types'
import type { DatasetInfo } from '@/api/data'

const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

const TrainPage = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [training, setTraining] = useState(false)
  const [currentTask, setCurrentTask] = useState<TrainStatus | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])

  // 加载模型和数据集列表
  useEffect(() => {
    loadModelsAndDatasets()
  }, [])

  const loadModelsAndDatasets = async () => {
    try {
      const [modelsData, datasetsData] = await Promise.all([
        modelAPI.getModels(),
        dataAPI.listDatasets(), // 使用文件夹列表
      ])
      setModels(modelsData)
      setDatasets(datasetsData)
    } catch (error) {
      message.error('加载模型和数据集列表失败')
    }
  }

  // 启动训练
  const handleStartTraining = async (values: TrainRequest) => {
    setLoading(true)
    try {
      const response = await trainAPI.startTraining(values)
      message.success('训练任务已启动')
      setTraining(true)
      setLogs([])

      // 开始轮询任务状态
      pollTaskStatus(response.task_id)

      // 连接 WebSocket 接收实时日志
      const ws = connectTrainLogs(response.task_id, (log) => {
        setLogs((prev) => [...prev, log])
      })

      // 保存 WebSocket 连接以便后续关闭
      return () => {
        ws.close()
      }
    } catch (error: any) {
      message.error(error.message || '启动训练失败')
    } finally {
      setLoading(false)
    }
  }

  // 轮询任务状态
  const pollTaskStatus = async (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await trainAPI.getStatus(taskId)
        setCurrentTask(status)

        if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
          clearInterval(interval)
          setTraining(false)

          if (status.status === 'completed') {
            message.success('训练完成!')
          } else if (status.status === 'failed') {
            message.error('训练失败')
          }
        }
      } catch (error) {
        clearInterval(interval)
      }
    }, 2000)
  }

  // 停止训练
  const handleStopTraining = async () => {
    if (!currentTask) return

    try {
      await trainAPI.stopTraining(currentTask.task_id)
      message.success('训练已停止')
      setTraining(false)
    } catch (error: any) {
      message.error(error.message || '停止训练失败')
    }
  }

  return (
    <div>
      <Title level={2} style={{ color: '#fff', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <ThunderboltOutlined style={{ color: '#667eea' }} /> 模型训练
      </Title>
      <Paragraph type="secondary" style={{ fontSize: '15px', marginBottom: '24px' }}>
        <RocketOutlined /> 配置训练参数并启动模型微调任务
      </Paragraph>

      <Row gutter={24}>
        <Col xs={24} lg={12}>
          {/* 数据集提示区域 */}
          <Card
            title={<span><DatabaseOutlined /> 数据集</span>}
            bordered={false}
            style={{ marginBottom: 16 }}
            extra={
              <Space>
                <Tag color="purple">{datasets.length} 个文件夹</Tag>
                <Button type="link" size="small">
                  <Link to="/data">管理数据集</Link>
                </Button>
              </Space>
            }
          >
            {datasets.length === 0 ? (
              <Alert
                message="暂无数据集"
                description={
                  <>
                    请先到{' '}
                    <Link to="/data" style={{ color: '#667eea' }}>
                      <DatabaseOutlined /> 数据管理
                    </Link>{' '}
                    页面上传训练数据集文件夹
                  </>
                }
                type="info"
                showIcon
                icon={<FolderOutlined />}
                style={{
                  background: 'rgba(102, 126, 234, 0.1)',
                  border: '1px solid rgba(102, 126, 234, 0.3)',
                }}
                action={
                  <Link to="/data">
                    <Button type="primary" size="small">
                      去上传
                    </Button>
                  </Link>
                }
              />
            ) : (
              <Alert
                message="数据集已就绪"
                description={`已有 ${datasets.length} 个数据集文件夹可用于训练`}
                type="success"
                showIcon
                style={{
                  background: 'rgba(82, 196, 26, 0.1)',
                  border: '1px solid rgba(82, 196, 26, 0.3)',
                }}
              />
            )}
          </Card>

          {/* 训练配置 */}
          <Card
            title={<span><ThunderboltOutlined /> 训练配置</span>}
            bordered={false}
          >
            <Form
              form={form}
              layout="vertical"
              onFinish={handleStartTraining}
              initialValues={{
                train_type: 'lora',
                lora_rank: 8,
                lora_alpha: 32,
                lora_dropout: 0.05,
                num_train_epochs: 1,
                per_device_train_batch_size: 1,
                gradient_accumulation_steps: 16,
                learning_rate: 0.0001,
                max_length: 2048,
                logging_steps: 10,
                save_steps: 100,
                warmup_ratio: 0.03,
                weight_decay: 0.01,
                gradient_checkpointing: true,
              }}
            >
              <Form.Item
                label="模型"
                name="model_id"
                rules={[{ required: true, message: '请选择模型' }]}
              >
                <Select
                  showSearch
                  placeholder="选择或搜索模型"
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

              <Form.Item
                label="数据集文件夹"
                name="dataset"
                rules={[{ required: true, message: '请选择数据集文件夹' }]}
                tooltip="选择已上传的数据集文件夹，系统会自动从 /app/data/{folder_name} 读取训练数据"
              >
                <Select
                  showSearch
                  placeholder="选择数据集文件夹"
                  optionFilterProp="children"
                  filterOption={(input, option) =>
                    (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                  }
                  options={datasets
                    .filter((d) => d.is_directory) // 只显示文件夹
                    .map((d) => ({
                      label: (
                        <Space>
                          <FolderOutlined />
                          {d.name}
                          <Tag color="blue" style={{ marginLeft: 8 }}>
                            {d.file_count || 0} 个文件
                          </Tag>
                          <span style={{ color: 'rgba(255, 255, 255, 0.45)', fontSize: '12px' }}>
                            {d.size_mb.toFixed(2)} MB
                          </span>
                        </Space>
                      ),
                      value: d.name,
                    }))}
                  notFoundContent={
                    <div style={{ textAlign: 'center', padding: '20px' }}>
                      <FolderOutlined style={{ fontSize: '24px', color: 'rgba(255, 255, 255, 0.25)' }} />
                      <div style={{ marginTop: '8px', color: 'rgba(255, 255, 255, 0.45)' }}>
                        暂无数据集文件夹
                      </div>
                      <Link to="/data">
                        <Button type="link" size="small">
                          去上传
                        </Button>
                      </Link>
                    </div>
                  }
                />
              </Form.Item>

              <Collapse defaultActiveKey={[]} ghost>
                <Panel header="基础参数" key="basic">
                  <Form.Item label="训练类型" name="train_type">
                    <Select>
                      <Select.Option value="lora">LoRA</Select.Option>
                      <Select.Option value="full">Full Fine-tuning</Select.Option>
                    </Select>
                  </Form.Item>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="训练轮数" name="num_train_epochs">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="Batch Size" name="per_device_train_batch_size">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="学习率" name="learning_rate">
                        <InputNumber min={0} step={0.00001} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="最大长度" name="max_length">
                        <InputNumber min={128} step={128} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Panel>

                <Panel header="LoRA 参数" key="lora">
                  <Row gutter={16}>
                    <Col span={8}>
                      <Form.Item label="LoRA Rank" name="lora_rank">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="LoRA Alpha" name="lora_alpha">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item label="LoRA Dropout" name="lora_dropout">
                        <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Panel>

                <Panel header="高级参数" key="advanced">
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="梯度累积步数" name="gradient_accumulation_steps">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="Warmup Ratio" name="warmup_ratio">
                        <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="日志步数" name="logging_steps">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="保存步数" name="save_steps">
                        <InputNumber min={1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Panel>
              </Collapse>

              <Divider />

              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<PlayCircleOutlined />}
                    loading={loading}
                    disabled={training}
                  >
                    开始训练
                  </Button>
                  <Button
                    danger
                    icon={<StopOutlined />}
                    onClick={handleStopTraining}
                    disabled={!training}
                  >
                    停止训练
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={loadModelsAndDatasets}>
                    刷新列表
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          {/* 训练进度 */}
          <Card
            title={<span><FireOutlined /> 训练进度</span>}
            bordered={false}
            style={{
              background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)',
              marginBottom: 16
            }}
          >
            {currentTask ? (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Row gutter={16}>
                  <Col span={24}>
                    <Text strong>任务 ID:</Text> <Text code style={{
                      background: 'rgba(102, 126, 234, 0.2)',
                      padding: '2px 8px',
                      borderRadius: '4px'
                    }}>{currentTask.task_id}</Text>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Statistic
                      title="训练状态"
                      value={currentTask.status}
                      prefix={
                        currentTask.status === 'running' ? <SyncOutlined spin style={{ color: '#667eea' }} /> :
                        currentTask.status === 'completed' ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                        <CloseCircleOutlined style={{ color: '#f5222d' }} />
                      }
                      valueStyle={{ fontSize: '16px' }}
                    />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="当前轮次"
                      value={currentTask.current_epoch}
                      suffix={`/ ${currentTask.total_epochs}`}
                      valueStyle={{ fontSize: '16px', color: '#667eea' }}
                    />
                  </Col>
                </Row>
                <div>
                  <Text type="secondary" style={{ fontSize: '12px' }}>训练进度</Text>
                  <Progress
                    percent={Math.round(currentTask.progress)}
                    strokeColor={{
                      '0%': '#667eea',
                      '100%': '#764ba2',
                    }}
                    trailColor="rgba(255, 255, 255, 0.1)"
                    strokeWidth={12}
                  />
                </div>
                {currentTask.loss !== null && (
                  <Row gutter={16}>
                    <Col span={24}>
                      <Statistic
                        title="Loss 值"
                        value={currentTask.loss.toFixed(4)}
                        valueStyle={{ fontSize: '20px', color: '#667eea', fontWeight: 'bold' }}
                      />
                    </Col>
                  </Row>
                )}
              </Space>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <FireOutlined style={{ fontSize: '48px', color: 'rgba(255, 255, 255, 0.2)', marginBottom: '16px' }} />
                <Text type="secondary" style={{ display: 'block' }}>暂无训练任务</Text>
                <Text type="secondary" style={{ fontSize: '12px' }}>配置参数后点击"开始训练"启动任务</Text>
              </div>
            )}
          </Card>

          {/* 实时日志 */}
          <Card
            title={<span style={{ fontFamily: 'monospace' }}>{'>'} 实时日志</span>}
            bordered={false}
            style={{
              background: 'linear-gradient(135deg, rgba(15, 12, 41, 0.6) 0%, rgba(36, 36, 62, 0.6) 100%)'
            }}
          >
            <div
              style={{
                height: '350px',
                overflow: 'auto',
                background: 'linear-gradient(180deg, #0a0e27 0%, #1a1a2e 100%)',
                padding: '16px',
                borderRadius: '8px',
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                fontSize: '12px',
                border: '1px solid rgba(102, 126, 234, 0.3)',
                boxShadow: 'inset 0 2px 8px rgba(0, 0, 0, 0.6)',
              }}
            >
              {logs.length > 0 ? (
                logs.map((log, index) => (
                  <div
                    key={index}
                    style={{
                      color: '#0f0',
                      marginBottom: '2px',
                      textShadow: '0 0 5px rgba(0, 255, 0, 0.5)',
                      lineHeight: '1.5'
                    }}
                  >
                    <span style={{ color: '#667eea', marginRight: '8px' }}>[{index + 1}]</span>
                    {log}
                  </div>
                ))
              ) : (
                <div style={{ textAlign: 'center', paddingTop: '100px' }}>
                  <Text type="secondary" style={{ fontFamily: 'monospace', display: 'block', marginBottom: '8px' }}>
                    {'>'} 等待日志输出...
                  </Text>
                  <Text type="secondary" style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                    训练开始后将显示实时日志
                  </Text>
                </div>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default TrainPage
