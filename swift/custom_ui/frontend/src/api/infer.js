/**
 * 推理相关 API
 */
import client from './client'

export const inferAPI = {
  /**
   * 对话推理
   */
  chat: (params) => {
    return client.post('/infer/chat', params)
  },

  /**
   * 加载模型
   */
  loadModel: (params) => {
    return client.post('/infer/load-model', params)
  },

  /**
   * 卸载模型
   */
  unloadModel: () => {
    return client.post('/infer/unload-model')
  },

  /**
   * 获取推理状态
   */
  getStatus: () => {
    return client.get('/infer/status')
  },

  /**
   * 获取已加载模型
   */
  listLoadedModels: () => {
    return client.get('/infer/models')
  }
}
