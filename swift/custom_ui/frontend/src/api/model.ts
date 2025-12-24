import { apiClient } from './client'
import type { ModelInfo, DatasetInfo } from '@/types'

export const modelAPI = {
  // 获取基础模型列表（/app/models）
  getModels: (params?: { search?: string; model_type?: string; tag?: string }): Promise<ModelInfo[]> => {
    return apiClient.get('/model/models', { params })
  },

  // 获取训练输出模型列表（/app/output）
  getTrainedModels: (params?: { search?: string; model_type?: string; tag?: string }): Promise<ModelInfo[]> => {
    return apiClient.get('/model/trained-models', { params })
  },

  // 获取模型详情
  getModelDetail: (modelId: string): Promise<ModelInfo> => {
    return apiClient.get(`/model/models/${modelId}`)
  },

  // 获取数据集列表
  getDatasets: (params?: { search?: string; tag?: string }): Promise<DatasetInfo[]> => {
    return apiClient.get('/model/datasets', { params })
  },

  // 获取数据集详情
  getDatasetDetail: (datasetId: string): Promise<DatasetInfo> => {
    return apiClient.get(`/model/datasets/${datasetId}`)
  },

  // 获取模型类型列表
  getModelTypes: (): Promise<{ model_types: string[] }> => {
    return apiClient.get('/model/model-types')
  },
}
