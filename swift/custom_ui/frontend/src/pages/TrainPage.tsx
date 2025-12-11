import { useState, useEffect, useRef } from 'react'
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
  Statistic,
  Checkbox,
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
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

const TrainPage = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [training, setTraining] = useState(false)
  const [currentTask, setCurrentTask] = useState<TrainStatus | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [models, setModels] = useState<ModelInfo[]>([])
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])

  // 选中的数据集配置（支持多选 + 采样）
  const [selectedDatasets, setSelectedDatasets] = useState<Record<string, number | undefined>>({})

  // 使用 useRef 存储 WebSocket 和轮询引用（不会触发重新渲染）
  const wsRef = useRef<{ close: () => void; readyState: number } | null>(null)
  const pollIntervalRef = useRef<number | null>(null)

  // 组件挂载时：加载数据 + 检查正在运行的任务
  useEffect(() => {
    const initialize = async () => {
      console.log('[TrainPage] 开始初始化...')
      setInitialLoading(true)
      try {
        // 并行加载数据和检查任务
        await Promise.allSettled([
          loadModelsAndDatasets(),
          checkRunningTasks()
        ])
        console.log('[TrainPage] 初始化完成')
      } catch (error) {
        console.error('[TrainPage] 初始化失败:', error)
      } finally {
        console.log('[TrainPage] 设置 initialLoading = false')
        setInitialLoading(false)
      }
    }

    initialize()

    // 组件卸载时清理
    return () => {
      console.log('[TrainPage] 组件卸载，清理资源')
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [])

  const loadModelsAndDatasets = async () => {
    try {
      console.log('开始加载模型和数据集...')
      const [modelsData, datasetsData] = await Promise.all([
        modelAPI.getModels(),
        dataAPI.listDatasets(true), // 传入 true 同时显示文件和文件夹
      ])
      console.log('模型数据:', modelsData)
      console.log('数据集数据:', datasetsData)

      // 防御性编程：确保返回的是数组
      setModels(Array.isArray(modelsData) ? modelsData : [])
      setDatasets(Array.isArray(datasetsData) ? datasetsData : [])
      console.log('数据加载完成')
    } catch (error: any) {
      console.error('加载失败:', error)
      message.error(`加载模型和数据集列表失败: ${error.message}`)
      // 错误时也设置为空数组，避免 undefined
      setModels([])
      setDatasets([])
    }
  }

  // 检查是否有正在运行的任务（页面刷新/路由切换后恢复状态）
  const checkRunningTasks = async () => {
    try {
      console.log('[checkRunningTasks] 开始检查正在运行的任务...')
      const response = await trainAPI.listTasks()
      console.log('[checkRunningTasks] 收到任务列表响应:', response)

      // 防御性检查：确保 response 有效
      if (!response || typeof response !== 'object') {
        console.warn('[checkRunningTasks] 响应无效:', response)
        return
      }

      const tasks = (response as any).tasks || []
      console.log('[checkRunningTasks] 任务数组:', tasks)

      // 防御性检查：确保 tasks 是数组
      if (!Array.isArray(tasks)) {
        console.warn('[checkRunningTasks] tasks 不是数组:', tasks)
        return
      }

      // 查找正在运行的任务
      const runningTask = tasks.find((task: TrainStatus) =>
        task.status === 'running' || task.status === 'pending'
      )

      if (runningTask && runningTask.task_id) {
        console.log('[checkRunningTasks] 发现正在运行的任务:', runningTask.task_id)

        // 防御性检查：确保任务数据完整
        const safeTask = {
          ...runningTask,
          progress: runningTask.progress ?? 0,
          current_epoch: runningTask.current_epoch ?? 0,
          total_epochs: runningTask.total_epochs ?? 1,
          loss: runningTask.loss ?? null,
        }

        setCurrentTask(safeTask)
        setTraining(true)

        // 恢复轮询
        startPolling(runningTask.task_id)

        // 重新连接 WebSocket
        reconnectWebSocket(runningTask.task_id)

        message.info(`已恢复训练任务: ${runningTask.task_id.slice(0, 8)}...`)
      } else {
        console.log('[checkRunningTasks] 没有正在运行的任务')
      }
    } catch (error: any) {
      console.error('[checkRunningTasks] 检查运行任务失败:', error)
      // 不显示错误消息，静默失败
    }
  }

  // 重新连接 WebSocket（先加载历史日志，再建立 WebSocket）
  const reconnectWebSocket = async (taskId: string) => {
    console.log('[reconnectWebSocket] 重新连接 WebSocket, taskId:', taskId)

    // 关闭旧连接
    if (wsRef.current) {
      console.log('[reconnectWebSocket] 关闭旧的 WebSocket 连接')
      try {
        wsRef.current.close()
      } catch (e) {
        console.error('[reconnectWebSocket] 关闭 WebSocket 失败:', e)
      }
      wsRef.current = null
    }

    // 步骤 1：先加载历史日志
    try {
      console.log('[reconnectWebSocket] 加载历史日志...')
      const logsData = await trainAPI.getLogs(taskId)
      console.log(`[reconnectWebSocket] 加载了 ${logsData.total_logs} 条历史日志`)

      // 设置历史日志到状态
      setLogs(logsData.logs || [])
    } catch (error) {
      console.error('[reconnectWebSocket] 加载历史日志失败:', error)
      // 即使加载历史日志失败，也继续建立 WebSocket 连接
      setLogs([])
    }

    // 步骤 2：延迟建立新 WebSocket 连接，接收实时日志
    setTimeout(() => {
      try {
        console.log('[reconnectWebSocket] 建立新的 WebSocket 连接')
        const ws = connectTrainLogs(taskId, (log) => {
          try {
            // 过滤心跳消息
            if (log.includes('"type": "ping"')) {
              return
            }

            // 安全截取日志前100字符用于调试
            const logPreview = typeof log === 'string' ? log.substring(0, 100) : String(log).substring(0, 100)
            console.log('[reconnectWebSocket] 收到新日志:', logPreview)

            // 确保 log 是字符串
            const safeLog = typeof log === 'string' ? log : String(log)
            setLogs((prev) => {
              try {
                return [...prev, safeLog]
              } catch (e) {
                console.error('[reconnectWebSocket] 添加日志到状态失败:', e)
                return prev
              }
            })
          } catch (e) {
            console.error('[reconnectWebSocket] 处理日志消息失败:', e)
          }
        })
        wsRef.current = ws
      } catch (e) {
        console.error('[reconnectWebSocket] 建立 WebSocket 连接失败:', e)
      }
    }, 100)
  }

  // 启动训练
  const handleStartTraining = async (values: any) => {
    // 验证数据集选择
    if (Object.keys(selectedDatasets).length === 0) {
      message.error('请至少选择一个数据集')
      return
    }

    // 转换数据集配置为后端格式
    const datasets = Object.entries(selectedDatasets).map(([name, sample_count]) => ({
      name,
      sample_count: sample_count || undefined
    }))

    setLoading(true)
    try {
      const requestData: TrainRequest = {
        ...values,
        datasets  // 替换为多数据集配置
      }

      const response = await trainAPI.startTraining(requestData)
      message.success('训练任务已启动')
      setTraining(true)
      setLogs([])

      // 开始轮询任务状态
      startPolling(response.task_id)

      // 连接 WebSocket 接收实时日志
      const ws = connectTrainLogs(response.task_id, (log) => {
        // 过滤心跳消息
        if (log.includes('"type": "ping"')) {
          return
        }
        setLogs((prev) => [...prev, log])
      })
      wsRef.current = ws
    } catch (error: any) {
      message.error(error.message || '启动训练失败')
    } finally {
      setLoading(false)
    }
  }

  // 开始轮询任务状态
  const startPolling = (taskId: string) => {
    // 清理旧的轮询
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    const interval = setInterval(async () => {
      try {
        const status = await trainAPI.getStatus(taskId)
        setCurrentTask(status)

        if (status.status === 'completed' || status.status === 'failed' || status.status === 'stopped') {
          clearInterval(interval)
          pollIntervalRef.current = null
          setTraining(false)

          if (status.status === 'completed') {
            message.success('训练完成!')
          } else if (status.status === 'failed') {
            message.error('训练失败')
          }

          // 关闭 WebSocket
          if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
          }
        }
      } catch (error) {
        clearInterval(interval)
        pollIntervalRef.current = null
      }
    }, 2000)

    // 保存 interval 引用
    pollIntervalRef.current = interval
  }

  // 停止训练
  const handleStopTraining = async () => {
    if (!currentTask) return

    try {
      await trainAPI.stopTraining(currentTask.task_id)
      message.success('训练已停止')
      setTraining(false)

      // 清理轮询
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }

      // 关闭 WebSocket
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    } catch (error: any) {
      message.error(error.message || '停止训练失败')
    }
  }

  // 加载状态
  console.log('[TrainPage] 渲染状态:', {
    initialLoading,
    training,
    hasCurrentTask: !!currentTask,
    modelsCount: models.length,
    datasetsCount: datasets.length,
    logsCount: logs.length
  })

  if (initialLoading) {
    console.log('[TrainPage] 显示加载中...')
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <SyncOutlined spin style={{ fontSize: '48px', color: '#667eea', marginBottom: '16px' }} />
        <div style={{ color: 'rgba(255, 255, 255, 0.65)', fontSize: '16px' }}>
          加载训练配置中...
        </div>
      </div>
    )
  }

  console.log('[TrainPage] 显示正常页面, currentTask:', currentTask?.task_id)
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
                <Tag color="purple">{(datasets || []).length} 个文件夹</Tag>
                <Button type="link" size="small">
                  <Link to="/data">管理数据集</Link>
                </Button>
              </Space>
            }
          >
            {(datasets || []).length === 0 ? (
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
                description={`已有 ${(datasets || []).length} 个数据集文件夹可用于训练`}
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
                label="数据集配置"
                tooltip="支持多个数据集混合训练，可为每个数据集设置采样数量（例如 #500 表示采样 500 条）"
                required
              >
                {(datasets || []).filter((d) => d.is_directory).length === 0 ? (
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
                    type="warning"
                    showIcon
                    icon={<FolderOutlined />}
                  />
                ) : (
                  <div
                    style={{
                      border: '1px solid rgba(102, 126, 234, 0.3)',
                      borderRadius: '8px',
                      padding: '12px',
                      background: 'rgba(102, 126, 234, 0.05)',
                      maxHeight: '200px',
                      overflow: 'auto',
                      // 自定义滚动条样式
                      scrollbarWidth: 'thin',
                      scrollbarColor: 'rgba(102, 126, 234, 0.5) rgba(102, 126, 234, 0.1)'
                    }}
                    className="custom-scrollbar"
                  >
                    {(datasets || [])
                      .filter((d) => d.is_directory)
                      .map((dataset) => {
                        const isSelected = dataset.name in selectedDatasets
                        return (
                          <div
                            key={dataset.name}
                            style={{
                              padding: '10px 12px',
                              borderRadius: '6px',
                              background: isSelected ? 'rgba(102, 126, 234, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                              border: `1px solid ${isSelected ? 'rgba(102, 126, 234, 0.4)' : 'transparent'}`,
                              marginBottom: '8px',
                              transition: 'all 0.2s ease',
                              cursor: 'pointer'
                            }}
                            onMouseEnter={(e) => {
                              if (!isSelected) {
                                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (!isSelected) {
                                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)'
                              }
                            }}
                          >
                            <Row gutter={[12, 8]} align="middle">
                              <Col flex="auto">
                                <Checkbox
                                  checked={isSelected}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setSelectedDatasets({ ...selectedDatasets, [dataset.name]: undefined })
                                    } else {
                                      const newSelected = { ...selectedDatasets }
                                      delete newSelected[dataset.name]
                                      setSelectedDatasets(newSelected)
                                    }
                                  }}
                                >
                                  <Space size={8}>
                                    <FolderOutlined style={{ color: isSelected ? '#667eea' : 'rgba(255, 255, 255, 0.65)' }} />
                                    <span style={{
                                      fontWeight: isSelected ? 600 : 400,
                                      color: isSelected ? '#fff' : 'rgba(255, 255, 255, 0.85)'
                                    }}>
                                      {dataset.name}
                                    </span>
                                    <Tag color="blue" style={{ margin: 0 }}>
                                      {dataset.file_count || 0} 个文件
                                    </Tag>
                                    <span style={{ color: 'rgba(255, 255, 255, 0.45)', fontSize: '12px' }}>
                                      {dataset.size_mb.toFixed(2)} MB
                                    </span>
                                  </Space>
                                </Checkbox>
                              </Col>
                              {isSelected && (
                                <Col flex="180px">
                                  <InputNumber
                                    placeholder="采样数量"
                                    min={1}
                                    value={selectedDatasets[dataset.name]}
                                    onChange={(value) => {
                                      setSelectedDatasets({
                                        ...selectedDatasets,
                                        [dataset.name]: value || undefined
                                      })
                                    }}
                                    style={{ width: '100%' }}
                                    size="small"
                                    addonAfter="条"
                                  />
                                </Col>
                              )}
                            </Row>
                          </div>
                        )
                      })}
                    {Object.keys(selectedDatasets).length === 0 && (
                      <div style={{ textAlign: 'center', padding: '20px', color: 'rgba(255, 255, 255, 0.45)' }}>
                        请至少选择一个数据集
                      </div>
                    )}
                  </div>
                )}
                <div style={{ marginTop: '8px', color: 'rgba(255, 255, 255, 0.65)', fontSize: '12px' }}>
                  已选择 {Object.keys(selectedDatasets).length} 个数据集
                  {Object.keys(selectedDatasets).length > 0 && (
                    <>
                      {' · '}
                      <Text style={{ color: '#667eea', fontSize: '12px' }}>
                        {Object.entries(selectedDatasets).map(([name, count]) =>
                          count ? `${name}#${count}` : name
                        ).join(', ')}
                      </Text>
                    </>
                  )}
                </div>
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
                    }}>{currentTask.task_id || 'Unknown'}</Text>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Statistic
                      title="训练状态"
                      value={currentTask.status || 'unknown'}
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
                      value={currentTask.current_epoch ?? 0}
                      suffix={`/ ${currentTask.total_epochs ?? 1}`}
                      valueStyle={{ fontSize: '16px', color: '#667eea' }}
                    />
                  </Col>
                </Row>
                <div>
                  <Text type="secondary" style={{ fontSize: '12px' }}>训练进度</Text>
                  <Progress
                    percent={Math.round(currentTask.progress ?? 0)}
                    strokeColor={{
                      '0%': '#667eea',
                      '100%': '#764ba2',
                    }}
                    trailColor="rgba(255, 255, 255, 0.1)"
                    strokeWidth={12}
                  />
                </div>
                {currentTask.loss !== null && currentTask.loss !== undefined && typeof currentTask.loss === 'number' && (
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

          {/* Loss 曲线图 */}
          {currentTask && currentTask.loss_history && currentTask.loss_history.length > 0 && (
            <Card
              title={<span><ThunderboltOutlined /> Loss 曲线</span>}
              bordered={false}
              style={{
                background: 'linear-gradient(135deg, rgba(118, 75, 162, 0.1) 0%, rgba(102, 126, 234, 0.1) 100%)',
                marginBottom: 16
              }}
            >
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={currentTask.loss_history}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(102, 126, 234, 0.2)" />
                  <XAxis
                    dataKey="step"
                    stroke="rgba(255, 255, 255, 0.6)"
                    label={{ value: 'Step', position: 'insideBottom', offset: -5, fill: 'rgba(255, 255, 255, 0.6)' }}
                  />
                  <YAxis
                    stroke="rgba(255, 255, 255, 0.6)"
                    label={{ value: 'Loss', angle: -90, position: 'insideLeft', fill: 'rgba(255, 255, 255, 0.6)' }}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(10, 14, 39, 0.95)',
                      border: '1px solid rgba(102, 126, 234, 0.5)',
                      borderRadius: '8px',
                      color: '#fff'
                    }}
                    formatter={(value: any) => [value.toFixed(4), 'Loss']}
                    labelFormatter={(label) => `Step: ${label}`}
                  />
                  <Legend
                    wrapperStyle={{ color: 'rgba(255, 255, 255, 0.8)' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="loss"
                    stroke="#667eea"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 6, fill: '#667eea' }}
                    name="Training Loss"
                  />
                </LineChart>
              </ResponsiveContainer>
              <div style={{ textAlign: 'center', marginTop: '8px' }}>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  总共 {currentTask.loss_history.length} 个数据点
                  {currentTask.loss_history.length > 0 && (
                    <> · 最新 Loss: <Text strong style={{ color: '#667eea' }}>
                      {currentTask.loss_history[currentTask.loss_history.length - 1].loss.toFixed(4)}
                    </Text></>
                  )}
                </Text>
              </div>
            </Card>
          )}

          {/* 实时日志 */}
          <Card
            title={
              <span>
                {'>'} 实时日志 {logs.length > 0 && <Tag color="blue">{logs.length} 行</Tag>}
              </span>
            }
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
              className="custom-scrollbar"
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
