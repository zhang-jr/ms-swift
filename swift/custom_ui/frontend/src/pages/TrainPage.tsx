import { useState, useEffect } from 'react'
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
} from 'antd'
import {
  PlayCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import { trainAPI, connectTrainLogs } from '@/api/train'
import { modelAPI } from '@/api/model'
import type { TrainRequest, TrainStatus, ModelInfo, DatasetInfo } from '@/types'

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
        modelAPI.getDatasets(),
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
      <Title level={2}>
        <ExperimentOutlined /> 模型训练
      </Title>
      <Paragraph type="secondary">
        配置训练参数并启动模型微调任务
      </Paragraph>

      <Row gutter={24}>
        <Col xs={24} lg={12}>
          <Card title="训练配置" bordered={false}>
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
                label="数据集"
                name="dataset"
                rules={[{ required: true, message: '请选择数据集' }]}
              >
                <Select
                  showSearch
                  placeholder="选择或搜索数据集"
                  optionFilterProp="children"
                  filterOption={(input, option) =>
                    (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                  }
                  options={datasets.map((d) => ({
                    label: d.dataset_name,
                    value: d.dataset_id,
                  }))}
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
          <Card title="训练进度" bordered={false}>
            {currentTask ? (
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <div>
                  <Text strong>任务 ID:</Text> <Text code>{currentTask.task_id}</Text>
                </div>
                <div>
                  <Text strong>状态:</Text> <Text>{currentTask.status}</Text>
                </div>
                <div>
                  <Progress percent={Math.round(currentTask.progress)} />
                </div>
                <div>
                  <Text strong>当前轮次:</Text> {currentTask.current_epoch} / {currentTask.total_epochs}
                </div>
                {currentTask.loss !== null && (
                  <div>
                    <Text strong>Loss:</Text> {currentTask.loss.toFixed(4)}
                  </div>
                )}
              </Space>
            ) : (
              <Text type="secondary">暂无训练任务</Text>
            )}
          </Card>

          <Card title="实时日志" bordered={false} style={{ marginTop: 24 }}>
            <div
              style={{
                height: '400px',
                overflow: 'auto',
                background: '#1e1e1e',
                padding: '12px',
                borderRadius: '4px',
                fontFamily: 'monospace',
                fontSize: '12px',
              }}
            >
              {logs.length > 0 ? (
                logs.map((log, index) => (
                  <div key={index} style={{ color: '#d4d4d4', marginBottom: '4px' }}>
                    {log}
                  </div>
                ))
              ) : (
                <Text type="secondary">等待日志...</Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default TrainPage
