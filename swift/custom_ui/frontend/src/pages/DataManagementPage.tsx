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
  InputNumber,
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
  SwapOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { dataAPI } from '../api/data'
import type { DatasetInfo, FolderPreview, ConvertRequest, ConvertResponse } from '../api/data'

const DataManagementPage = () => {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const [folderName, setFolderName] = useState('')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [previewModalVisible, setPreviewModalVisible] = useState(false)
  const [previewData, setPreviewData] = useState<FolderPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  // 数据转换相关状态
  const [convertModalVisible, setConvertModalVisible] = useState(false)
  const [convertLoading, setConvertLoading] = useState(false)
  const [convertConfig, setConvertConfig] = useState<ConvertRequest>({
    project_name: '',
    output_format: 'parquet',
    shard_size_mb: 500,  // 默认 500MB
    output_name: '',
  })
  const [convertResultVisible, setConvertResultVisible] = useState(false)
  const [convertResult, setConvertResult] = useState<ConvertResponse | null>(null)

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

  // 打开转换模态框
  const handleOpenConvert = (projectName: string) => {
    setConvertConfig({
      project_name: projectName,
      output_format: 'parquet',
      shard_size_mb: 500,  // 默认 500MB
      output_name: '',  // 输出到项目内 data/ 目录，不需要用户自定义名称
    })
    setConvertModalVisible(true)
  }

  // 执行转换
  const handleConvert = async () => {
    setConvertLoading(true)
    try {
      // 先验证项目结构
      const validation = await dataAPI.validateAnnotationProject(convertConfig.project_name)

      if (!validation.valid) {
        message.error(`项目验证失败: ${validation.error}`)
        setConvertLoading(false)
        return
      }

      message.info(`找到 ${validation.instruction_count} 个标注文件，开始转换...`)

      // 执行转换
      const result = await dataAPI.convertAnnotationDataset(convertConfig)

      setConvertResult(result)
      setConvertModalVisible(false)
      setConvertResultVisible(true)
      message.success('数据转换成功！')

      // 刷新数据集列表
      loadDatasets()
    } catch (error: any) {
      message.error(`转换失败: ${error.message}`)
    } finally {
      setConvertLoading(false)
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
          {record.is_directory && (
            <Button
              type="link"
              size="small"
              icon={<SwapOutlined />}
              onClick={() => handleOpenConvert(record.name)}
              style={{ color: '#52c41a' }}
            >
              转换
            </Button>
          )}
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

      {/* 数据转换模态框 */}
      <Modal
        title={
          <Space>
            <SwapOutlined style={{ color: '#52c41a' }} />
            <span>转换标注数据</span>
          </Space>
        }
        open={convertModalVisible}
        onOk={handleConvert}
        onCancel={() => setConvertModalVisible(false)}
        okText="开始转换"
        cancelText="取消"
        confirmLoading={convertLoading}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>项目名称:</div>
            <Input value={convertConfig.project_name} disabled />
            <div style={{ marginTop: 4, fontSize: 12, color: 'rgba(255, 255, 255, 0.45)' }}>
              转换后的数据将保存到: {convertConfig.project_name}/data/
            </div>
          </div>

          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>输出格式:</div>
            <Space>
              <Button
                type={convertConfig.output_format === 'parquet' ? 'primary' : 'default'}
                onClick={() =>
                  setConvertConfig({ ...convertConfig, output_format: 'parquet' })
                }
              >
                Parquet (推荐)
              </Button>
              <Button
                type={convertConfig.output_format === 'jsonl' ? 'primary' : 'default'}
                onClick={() =>
                  setConvertConfig({ ...convertConfig, output_format: 'jsonl' })
                }
              >
                JSONL
              </Button>
            </Space>
          </div>

          {convertConfig.output_format === 'parquet' && (
            <div>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>分片大小 (MB):</div>
              <InputNumber
                min={0}
                max={2000}
                step={100}
                value={convertConfig.shard_size_mb}
                onChange={(value) =>
                  setConvertConfig({
                    ...convertConfig,
                    shard_size_mb: value || 500,
                  })
                }
                style={{ width: '100%' }}
              />
              <div style={{ marginTop: 4, fontSize: 12, color: 'rgba(255, 255, 255, 0.45)' }}>
                0 表示不分片，推荐: 500MB（步进 100MB，点击 +/- 按钮调整）
              </div>
            </div>
          )}

          <div style={{ padding: 12, background: 'rgba(102, 126, 234, 0.1)', borderRadius: 4 }}>
            <div style={{ fontSize: 12, color: 'rgba(255, 255, 255, 0.65)' }}>
              💡 数据源说明：
              <br />
              - 自动从 <strong>uploads</strong> 文件夹读取原始媒体数据
              <br />
              - <strong>instructions</strong> 文件夹提供标注信息（query 和 response）
              <br />
              - 转换为 MS-SWIFT 原生支持的 query-response 格式
            </div>
          </div>
        </Space>
      </Modal>

      {/* 转换结果模态框 */}
      <Modal
        title={
          <Space>
            <SwapOutlined style={{ color: '#52c41a' }} />
            <span>转换成功</span>
          </Space>
        }
        open={convertResultVisible}
        onCancel={() => {
          setConvertResultVisible(false)
          setConvertResult(null)
        }}
        footer={[
          <Button
            key="close"
            type="primary"
            onClick={() => {
              setConvertResultVisible(false)
              setConvertResult(null)
            }}
          >
            关闭
          </Button>,
        ]}
        width={700}
      >
        {convertResult && (
          <>
            <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label="输出文件夹" span={2}>
                <Tag color="green">{convertResult.output_folder}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="总样本数">
                {convertResult.summary.total_samples}
              </Descriptions.Item>
              <Descriptions.Item label="总图片数">
                {convertResult.summary.total_images}
              </Descriptions.Item>
              <Descriptions.Item label="图像样本">
                {convertResult.summary.media_types.image}
              </Descriptions.Item>
              <Descriptions.Item label="PDF 样本">
                {convertResult.summary.media_types.pdf}
              </Descriptions.Item>
              <Descriptions.Item label="视频样本">
                {convertResult.summary.media_types.video}
              </Descriptions.Item>
              <Descriptions.Item label="文件数量" span={2}>
                {convertResult.output_files.length} 个文件
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 16 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>生成的文件:</div>
              <div
                style={{
                  maxHeight: 200,
                  overflow: 'auto',
                  background: 'rgba(0, 0, 0, 0.2)',
                  padding: 12,
                  borderRadius: 4,
                }}
              >
                {convertResult.output_files.map((file, idx) => (
                  <div key={idx} style={{ marginBottom: 4 }}>
                    <FileOutlined /> {file}
                  </div>
                ))}
              </div>
            </div>

            <div
              style={{
                marginTop: 16,
                padding: 12,
                background: 'rgba(82, 196, 26, 0.1)',
                borderRadius: 4,
                border: '1px solid rgba(82, 196, 26, 0.3)',
              }}
            >
              <div style={{ fontWeight: 500, marginBottom: 8 }}>
                ✅ 转换完成！使用 datasets 库加载:
              </div>
              <div style={{ fontSize: 12, color: 'rgba(255, 255, 255, 0.85)' }}>
                1. 在训练页面选择数据集时，输入项目名称: "{convertConfig.project_name}"
                <br />
                2. 系统会自动从 {convertResult.output_folder} 读取 Parquet 文件
                <br />
                3. 支持 HuggingFace datasets.load_dataset() 直接加载
                <br />
                4. 已生成 dataset_infos.json，确保快速加载
              </div>
            </div>
          </>
        )}
      </Modal>
    </div>
  )
}

export default DataManagementPage
