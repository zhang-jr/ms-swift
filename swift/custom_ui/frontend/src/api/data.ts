/**
 * 数据管理 API
 */
import { apiClient } from './client'

export interface DatasetFile {
  filename: string
  size: number
  size_str: string
  num_samples?: number
  format: string
  upload_time: string
}

export interface UploadResponse {
  message: string
  filename: string
  size: number
  path: string
}

export interface PreviewResponse {
  filename: string
  format: string
  num_samples?: number
  preview: string[]
  total_lines?: number
}

/**
 * 上传数据集文件
 */
export const uploadDataset = async (file: File): Promise<UploadResponse> => {
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
 * 获取数据集列表
 */
export const listDatasets = async (): Promise<DatasetFile[]> => {
  const response = await apiClient.get('/data/list')
  return response.data
}

/**
 * 预览数据集
 */
export const previewDataset = async (filename: string, lines: number = 10): Promise<PreviewResponse> => {
  const response = await apiClient.get(`/data/preview/${filename}`, {
    params: { lines }
  })
  return response.data
}

/**
 * 下载数据集
 */
export const downloadDataset = (filename: string): string => {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${baseURL}/api/data/download/${filename}`
}

/**
 * 删除数据集
 */
export const deleteDataset = async (filename: string): Promise<{ message: string }> => {
  const response = await apiClient.delete(`/data/delete/${filename}`)
  return response.data
}

export const dataAPI = {
  uploadDataset,
  listDatasets,
  previewDataset,
  downloadDataset,
  deleteDataset,
}
