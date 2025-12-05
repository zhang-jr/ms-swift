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
  return response.data
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
  return response.data
}

/**
 * 上传文件夹（批量上传）
 */
export const uploadFolder = async (files: File[], folderName: string): Promise<UploadFolderResponse> => {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  formData.append('folder_name', folderName)

  const response = await apiClient.post('/data/upload-folder', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

/**
 * 删除数据集（文件或文件夹）
 */
export const deleteDataset = async (name: string): Promise<{ message: string }> => {
  const response = await apiClient.delete(`/data/delete/${name}`)
  return response.data
}

/**
 * 获取数据集详细信息
 */
export const getDatasetInfo = async (name: string): Promise<DatasetInfo> => {
  const response = await apiClient.get(`/data/info/${name}`)
  return response.data
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
  return response.data
}

/**
 * 预览数据集文件
 */
export const previewDataset = async (filename: string, lines: number = 10): Promise<PreviewResponse> => {
  const response = await apiClient.get(`/data/preview/${filename}`, {
    params: { lines }
  })
  return response.data
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
}
