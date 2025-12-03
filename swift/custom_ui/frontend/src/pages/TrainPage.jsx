/**
 * 训练页面
 */
import React, { useState, useEffect } from 'react'
import {
  Card,
  Form,
  Input,
  Select,
  InputNumber,
  Button,
  Space,
  Table,
  message,
  Divider
} from 'antd'
import { RocketOutlined } from '@ant-design/icons'
import { trainAPI } from '../api/train'

const TrainPage = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState([])
  const [datasets, setDatasets] = useState([])
  const [tasks, setTasks] = useState([])

  // 加载模型和数据集列表
  useEffect(() => {
    loadModels()
    loadDatasets()
    loadTasks()
  }, [])

  const loadModels = async () => {
    try {
      const data = await trainAPI.listModels()
      setModels(data.models || [])
    } catch (error) {
      message.error('加载模型列表失败: ' + error.message)
    }
  }

  const loadDatasets = async () => {
    try {
      const data = await trainAPI.listDatasets()
      setDatasets(data.datasets || [])
    } catch (error) {
      message.error('加载数据集列表失败: ' + error.message)
    }
  }

  const loadTasks = async () => {
    try {
      const data = await trainAPI.listTasks()
      setTasks(data.tasks || [])
    } catch (error) {
      console.error('加载任务列表失败:', error)
    }
  }

  const handleSubmit = async (values) => {
    setLoading(true)
    try {
      const result = await trainAPI.startTraining(values)
      message.success('训练任务已启动: ' + result.task_id)
      form.resetFields()
      loadTasks()
    } catch (error) {
      message.error('启动训练失败: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: '任务 ID',
      dataIndex: 'task_id',
      key: 'task_id',
    },
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button size="small">查看日志</Button>
          <Button size="small" danger>停止</Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card title="模型训练" bordered={false}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            train_type: 'lora',
            num_train_epochs: 1,
            batch_size: 1,
            learning_rate: 0.0001,
            max_length: 2048,
            gpu_id: ['0']
          }}
        >
          <Form.Item
            name="model"
            label="模型"
            rules={[{ required: true, message: '请选择模型' }]}
          >
            <Select
              showSearch
              placeholder="选择模型"
              optionFilterProp="children"
              options={models.map(m => ({
                label: m.model_id || m,
                value: m.model_id || m
              }))}
            />
          </Form.Item>

          <Form.Item
            name="dataset"
            label="数据集"
            rules={[{ required: true, message: '请选择数据集' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择数据集"
              options={datasets.map(d => ({
                label: d,
                value: d
              }))}
            />
          </Form.Item>

          <Space style={{ width: '100%' }} direction="horizontal">
            <Form.Item name="train_type" label="训练类型">
              <Select style={{ width: 120 }}>
                <Select.Option value="full">Full</Select.Option>
                <Select.Option value="lora">LoRA</Select.Option>
                <Select.Option value="qlora">QLoRA</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item name="num_train_epochs" label="训练轮数">
              <InputNumber min={1} max={100} />
            </Form.Item>

            <Form.Item name="batch_size" label="批次大小">
              <InputNumber min={1} max={128} />
            </Form.Item>

            <Form.Item name="learning_rate" label="学习率">
              <InputNumber min={0} max={1} step={0.0001} />
            </Form.Item>
          </Space>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              icon={<RocketOutlined />}
              loading={loading}
            >
              开始训练
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Divider />

      <Card title="训练任务列表" bordered={false}>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="task_id"
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  )
}

export default TrainPage
