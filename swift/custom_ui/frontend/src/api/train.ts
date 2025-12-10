import { apiClient } from './client'
import type { TrainRequest, TrainResponse, TrainStatus } from '@/types'

export const trainAPI = {
  // 启动训练
  startTraining: (params: TrainRequest): Promise<TrainResponse> => {
    return apiClient.post('/train/start', params)
  },

  // 获取训练状态
  getStatus: (taskId: string): Promise<TrainStatus> => {
    return apiClient.get(`/train/status/${taskId}`)
  },

  // 停止训练
  stopTraining: (taskId: string): Promise<{ message: string; task_id: string }> => {
    return apiClient.post(`/train/stop/${taskId}`)
  },

  // 获取训练任务列表
  listTasks: (): Promise<{ tasks: Array<any> }> => {
    return apiClient.get('/train/list')
  },

  // 删除训练任务
  deleteTask: (taskId: string): Promise<{ message: string; task_id: string }> => {
    return apiClient.delete(`/train/delete/${taskId}`)
  },

  // 获取训练任务的历史日志
  getLogs: (taskId: string): Promise<{ task_id: string; logs: string[]; total_logs: number }> => {
    return apiClient.get(`/train/logs/${taskId}`)
  },
}

// WebSocket 连接用于实时日志
export const connectTrainLogs = (taskId: string, onMessage: (message: string) => void) => {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/logs/${taskId}`
  console.log(`[WebSocket] 连接到: ${wsUrl}`)

  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    console.log(`[WebSocket] 连接已建立: ${taskId}`)
  }

  ws.onmessage = (event) => {
    console.log(`[WebSocket] 收到消息:`, event.data)
    onMessage(event.data)
  }

  ws.onerror = (error) => {
    console.error(`[WebSocket] 错误:`, error)
  }

  ws.onclose = (event) => {
    console.log(`[WebSocket] 连接关闭: code=${event.code}, reason=${event.reason}, wasClean=${event.wasClean}`)
  }

  return ws
}
