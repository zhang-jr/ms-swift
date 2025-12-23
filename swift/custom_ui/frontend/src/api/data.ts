/**
 * 数据管理 API
 */
import { apiClient } from './client'

export interface DatasetInfo {
  name: string
  path: string
  is_directory: boolean
  file_count?: number
  total_size: number
  size_mb: number
  created_at: string
  modified_at: string
  // 兼容旧的文件模式
  filename?: string
  format?: string
  rows?: number
}

export interface UploadResponse {
  filename: string
  filepath: string
  size_mb: number
  message: string
}

export interface UploadFolderResponse {
  folder_name: string
  file_count: number
  total_size_mb: number
  files: string[]
  message: string
}

export interface PreviewResponse {
  filename: string
  format: string
  num_samples?: number
  preview: string[]
  total_lines?: number
}

export interface FolderPreview {
  folder_name: string
  files: {
    name: string
    size: number
    size_mb: number
    type: string
    modified_at: string
  }[]
  total_files: number
  total_size_mb: number
}

/**
 * 获取数据集列表（默认只返回文件夹）
 */
export const listDatasets = async (includeFiles: boolean = false): Promise<DatasetInfo[]> => {
  const response = await apiClient.get('/data/list', {
    params: { include_files: includeFiles },
  })
  // 注意：apiClient 的响应拦截器已经返回了 response.data
  // 所以这里直接返回 response 即可
  return response as any
}

/**
 * 上传单个文件
 */
export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post('/data/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response as any
}

/**
 * 上传文件夹（批量上传）
 *
 * 保留完整的目录结构：
 * - 使用 file.webkitRelativePath 获取文件的相对路径
 * - 通过 FormData 的第三个参数传递相对路径
 * - 后端根据相对路径重建目录结构
 */
export const uploadFolder = async (files: File[], folderName: string): Promise<UploadFolderResponse> => {
  const formData = new FormData()

  files.forEach((file) => {
    // 使用 webkitRelativePath 或 name 作为文件名
    // webkitRelativePath 包含完整的相对路径（如 "project/subdir/file.txt"）
    const relativePath = (file as any).webkitRelativePath || file.name

    // FormData.append(name, blob, filename) 的第三个参数会被后端识别为文件名
    formData.append('files', file, relativePath)
  })
  formData.append('folder_name', folderName)

  const response = await apiClient.post('/data/upload-folder', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response as any
}

/**
 * 删除数据集（文件或文件夹）
 */
export const deleteDataset = async (name: string): Promise<{ message: string }> => {
  const response = await apiClient.delete(`/data/delete/${name}`)
  return response as any
}

/**
 * 获取数据集详细信息
 */
export const getDatasetInfo = async (name: string): Promise<DatasetInfo> => {
  const response = await apiClient.get(`/data/info/${name}`)
  return response as any
}

/**
 * 下载数据集
 */
export const downloadDataset = (name: string): string => {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${baseURL}/api/data/download/${name}`
}

/**
 * 预览文件夹内容（文件列表）
 */
export const previewFolder = async (folderName: string): Promise<FolderPreview> => {
  const response = await apiClient.get(`/data/preview-folder/${folderName}`)
  return response as any
}

/**
 * 预览数据集文件
 */
export const previewDataset = async (filename: string, lines: number = 10): Promise<PreviewResponse> => {
  const response = await apiClient.get(`/data/preview/${filename}`, {
    params: { lines }
  })
  return response as any
}

// ============ 数据转换 API ============

export interface ConvertRequest {
  project_name: string
  output_format?: 'parquet' | 'jsonl'
  shard_size_mb?: number
  output_name?: string
}

export interface ConvertResponse {
  status: string
  output_folder: string
  output_files: string[]
  summary: {
    total_samples: number
    media_types: {
      image: number
      pdf: number
      video: number
    }
    total_images: number
    providers: Record<string, number>
    models: Record<string, number>
  }
}

export interface ValidationResponse {
  valid: boolean
  project_name?: string
  instruction_count?: number
  type_counts?: {
    image: number
    pdf: number
    video: number
    unknown: number
  }
  structure?: {
    instructions: boolean
    uploads: boolean
  }
  error?: string
}

/**
 * 验证标注项目结构
 */
export const validateAnnotationProject = async (
  projectName: string
): Promise<ValidationResponse> => {
  const response = await apiClient.post('/data/validate-annotation-project', null, {
    params: { project_name: projectName },
  })
  return response as any
}

/**
 * 转换标注数据集为 HuggingFace Datasets 格式
 */
export const convertAnnotationDataset = async (
  request: ConvertRequest
): Promise<ConvertResponse> => {
  const response = await apiClient.post('/data/convert', request)
  return response as any
}

/**
 * 获取支持的转换格式
 */
export const getConvertFormats = async (): Promise<{
  formats: Array<{
    name: string
    description: string
    supports_sharding: boolean
  }>
  media_types: string[]
}> => {
  const response = await apiClient.get('/data/convert-formats')
  return response as any
}

export const dataAPI = {
  listDatasets,
  uploadFile,
  uploadFolder,
  deleteDataset,
  getDatasetInfo,
  downloadDataset,
  previewFolder,
  previewDataset,
  // 数据转换
  validateAnnotationProject,
  convertAnnotationDataset,
  getConvertFormats,
}
