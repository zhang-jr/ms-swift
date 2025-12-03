/**
 * 训练相关 API
 */
import client from './client'

export const trainAPI = {
  /**
   * 启动训练任务
   */
  startTraining: (params) => {
    return client.post('/train/start', params)
  },

  /**
   * 获取训练状态
   */
  getStatus: (taskId) => {
    return client.get(`/train/status/${taskId}`)
  },

  /**
   * 停止训练任务
   */
  stopTraining: (taskId) => {
    return client.post(`/train/stop/${taskId}`)
  },

  /**
   * 获取所有训练任务
   */
  listTasks: () => {
    return client.get('/train/tasks')
  },

  /**
   * 获取训练日志
   */
  getLogs: (taskId, lines = 50) => {
    return client.get(`/train/logs/${taskId}`, {
      params: { lines }
    })
  },

  /**
   * 获取可用模型列表
   */
  listModels: () => {
    return client.get('/train/models')
  },

  /**
   * 获取可用数据集列表
   */
  listDatasets: () => {
    return client.get('/train/datasets')
  }
}
