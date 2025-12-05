import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Upload,
  Modal,
  message,
  Tag,
  Input,
  Popconfirm,
  Descriptions,
} from 'antd'
import {
  UploadOutlined,
  FolderOutlined,
  DeleteOutlined,
  EyeOutlined,
  DownloadOutlined,
  ReloadOutlined,
  FileOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { dataAPI } from '../api/data'
import type { DatasetInfo, FolderPreview } from '../api/data'

const DataManagementPage = () => {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [folderName, setFolderName] = useState('')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [previewModalVisible, setPreviewModalVisible] = useState(false)
  const [previewData, setPreviewData] = useState<FolderPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  // 加载数据集列表
  const loadDatasets = async () => {
    setLoading(true)
    try {
      const data = await dataAPI.listDatasets(true) // 传入 true 同时显示文件和文件夹
      setDatasets(data)
    } catch (error: any) {
      message.error(`加载数据集失败: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDatasets()
  }, [])

  // 删除数据集
  const handleDelete = async (name: string) => {
    try {
      await dataAPI.deleteDataset(name)
      message.success('删除成功')
      loadDatasets()
    } catch (error: any) {
      message.error(`删除失败: ${error.message}`)
    }
  }

  // 下载数据集
  const handleDownload = async (name: string) => {
    try {
      const url = `${import.meta.env.VITE_API_URL || ''}/api/data/download/${name}`
      window.open(url, '_blank')
    } catch (error: any) {
      message.error(`下载失败: ${error.message}`)
    }
  }

  // 预览文件夹
  const handlePreview = async (name: string, isDirectory: boolean) => {
    if (!isDirectory) {
      message.info('单个文件预览功能开发中')
      return
    }

    setPreviewLoading(true)
    setPreviewModalVisible(true)
    try {
      const data = await dataAPI.previewFolder(name)
      setPreviewData(data)
    } catch (error: any) {
      message.error(`预览失败: ${error.message}`)
      setPreviewModalVisible(false)
    } finally {
      setPreviewLoading(false)
    }
  }

  // 上传文件夹
  const handleFolderUpload = async () => {
    if (!folderName.trim()) {
      message.error('请输入文件夹名称')
      return
    }

    if (fileList.length === 0) {
      message.error('请选择要上传的文件')
      return
    }

    try {
      const files = fileList.map(f => f.originFileObj as File)
      await dataAPI.uploadFolder(files, folderName)
      message.success('文件夹上传成功')
      setUploadModalVisible(false)
      setFolderName('')
      setFileList([])
      loadDatasets()
    } catch (error: any) {
      message.error(`上传失败: ${error.message}`)
    }
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: DatasetInfo) => (
        <Space>
          {record.is_directory && <FolderOutlined style={{ color: '#667eea' }} />}
          <span style={{ fontWeight: 500 }}>{text}</span>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'is_directory',
      key: 'type',
      render: (isDir: boolean) => (
        <Tag color={isDir ? 'purple' : 'blue'}>
          {isDir ? '文件夹' : '文件'}
        </Tag>
      ),
    },
    {
      title: '文件数量',
      dataIndex: 'file_count',
      key: 'file_count',
      render: (count: number | undefined, record: DatasetInfo) =>
        record.is_directory ? count || 0 : '-',
    },
    {
      title: '大小',
      dataIndex: 'size_mb',
      key: 'size_mb',
      render: (size: number) => `${size.toFixed(2)} MB`,
    },
    {
      title: '修改时间',
      dataIndex: 'modified_at',
      key: 'modified_at',
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: DatasetInfo) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handlePreview(record.name, record.is_directory)}
          >
            预览
          </Button>
          {!record.is_directory && (
            <Button
              type="link"
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(record.name)}
            >
              下载
            </Button>
          )}
          <Popconfirm
            title="确定删除吗？"
            description={`将删除 ${record.is_directory ? '文件夹及其所有内容' : '文件'}: ${record.name}`}
            onConfirm={() => handleDelete(record.name)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card
        title={
          <Space>
            <FolderOutlined style={{ fontSize: '20px', color: '#667eea' }} />
            <span>数据集管理</span>
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadDatasets}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<UploadOutlined />}
              onClick={() => setUploadModalVisible(true)}
            >
              上传文件夹
            </Button>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Table
          columns={columns}
          dataSource={datasets}
          rowKey="path"
          loading={loading}
          pagination={{
            pageSize: 10,
            showTotal: (total) => `共 ${total} 个数据集`,
          }}
        />
      </Card>

      {/* 上传文件夹模态框 */}
      <Modal
        title="上传数据集文件夹"
        open={uploadModalVisible}
        onOk={handleFolderUpload}
        onCancel={() => {
          setUploadModalVisible(false)
          setFolderName('')
          setFileList([])
        }}
        okText="上传"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <div style={{ marginBottom: 8 }}>文件夹名称:</div>
            <Input
              placeholder="例如: project_001"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
            />
          </div>

          <div>
            <div style={{ marginBottom: 8 }}>选择文件:</div>
            <Upload
              multiple
              fileList={fileList}
              onChange={({ fileList: newFileList }) => setFileList(newFileList)}
              beforeUpload={() => false}
              directory
            >
              <Button icon={<UploadOutlined />}>选择文件夹</Button>
            </Upload>
            <div style={{ marginTop: 8, color: 'rgba(255, 255, 255, 0.45)' }}>
              提示: 点击按钮选择整个文件夹上传
            </div>
          </div>
        </Space>
      </Modal>

      {/* 预览文件夹模态框 */}
      <Modal
        title={
          <Space>
            <FolderOutlined />
            {previewData?.folder_name || '文件夹预览'}
          </Space>
        }
        open={previewModalVisible}
        onCancel={() => {
          setPreviewModalVisible(false)
          setPreviewData(null)
        }}
        footer={[
          <Button key="close" onClick={() => setPreviewModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>加载中...</div>
        ) : previewData ? (
          <>
            <Descriptions bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="文件数量">
                {previewData.total_files}
              </Descriptions.Item>
              <Descriptions.Item label="总大小">
                {previewData.total_size_mb.toFixed(2)} MB
              </Descriptions.Item>
            </Descriptions>

            <Table
              dataSource={previewData.files}
              rowKey="name"
              size="small"
              pagination={{ pageSize: 10 }}
              columns={[
                {
                  title: '文件名',
                  dataIndex: 'name',
                  key: 'name',
                  render: (text: string) => (
                    <Space>
                      <FileOutlined />
                      <span>{text}</span>
                    </Space>
                  ),
                },
                {
                  title: '类型',
                  dataIndex: 'type',
                  key: 'type',
                  render: (type: string) => (
                    <Tag color="blue">{type.toUpperCase()}</Tag>
                  ),
                },
                {
                  title: '大小',
                  dataIndex: 'size_mb',
                  key: 'size_mb',
                  render: (size: number) => `${size.toFixed(2)} MB`,
                },
                {
                  title: '修改时间',
                  dataIndex: 'modified_at',
                  key: 'modified_at',
                  render: (time: string) =>
                    new Date(time).toLocaleString('zh-CN'),
                },
              ]}
            />
          </>
        ) : null}
      </Modal>
    </div>
  )
}

export default DataManagementPage
