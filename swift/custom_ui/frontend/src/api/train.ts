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

// WebSocket 连接用于实时日志（带自动重连）
export const connectTrainLogs = (
  taskId: string,
  onMessage: (message: string) => void,
  options: { maxRetries?: number; retryDelay?: number } = {}
) => {
  const { maxRetries = 5, retryDelay = 2000 } = options
  let retryCount = 0
  let ws: WebSocket | null = null
  let shouldReconnect = true

  const connect = () => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/logs/${taskId}`
    console.log(`[WebSocket] 连接到: ${wsUrl} (尝试 ${retryCount + 1})`)

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log(`[WebSocket] 连接已建立: ${taskId}`)
      retryCount = 0 // 重置重试计数
    }

    ws.onmessage = (event) => {
      onMessage(event.data)
    }

    ws.onerror = (error) => {
      console.error(`[WebSocket] 错误:`, error)
    }

    ws.onclose = (event) => {
      console.log(`[WebSocket] 连接关闭: code=${event.code}, wasClean=${event.wasClean}`)

      // 只有非正常关闭且未超过最大重试次数时才重连
      if (shouldReconnect && !event.wasClean && retryCount < maxRetries) {
        retryCount++
        console.log(`[WebSocket] ${retryDelay}ms 后尝试重连... (${retryCount}/${maxRetries})`)
        setTimeout(() => {
          if (shouldReconnect) {
            connect()
          }
        }, retryDelay)
      } else if (retryCount >= maxRetries) {
        console.error(`[WebSocket] 达到最大重试次数 (${maxRetries})，停止重连`)
      }
    }

    return ws
  }

  const initialWs = connect()

  // 返回一个带 close 方法的对象，用于手动关闭连接
  return {
    close: () => {
      shouldReconnect = false // 禁用自动重连
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    },
    get readyState() {
      return ws?.readyState ?? WebSocket.CLOSED
    }
  }
}
