import { apiClient } from './client'
import type { LoadModelRequest, ChatRequest, ChatResponse } from '@/types'

export const inferAPI = {
  // 加载模型
  loadModel: (params: LoadModelRequest): Promise<{ message: string; model_instance_id: string; model_id: string }> => {
    return apiClient.post('/infer/load-model', params)
  },

  // 对话
  chat: (params: ChatRequest): Promise<ChatResponse> => {
    return apiClient.post('/infer/chat', params)
  },

  // 卸载模型
  unloadModel: (modelInstanceId?: string): Promise<{ message: string; model_instance_id: string }> => {
    return apiClient.post('/infer/unload-model', { model_instance_id: modelInstanceId })
  },

  // 获取已加载模型列表
  getLoadedModels: (): Promise<{ models: Array<any> }> => {
    return apiClient.get('/infer/loaded-models')
  },

  // 获取当前模型
  getCurrentModel: (): Promise<{ current_model: any }> => {
    return apiClient.get('/infer/current-model')
  },
}
