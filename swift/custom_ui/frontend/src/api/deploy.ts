import { apiClient } from './client'
import type { DeployRequest, DeployResponse, DeploymentStatus } from '@/types'

export const deployAPI = {
  // 启动部署
  startDeployment: (params: DeployRequest): Promise<DeployResponse> => {
    return apiClient.post('/deploy/start', params)
  },

  // 获取部署状态
  getStatus: (deploymentId: string): Promise<DeploymentStatus> => {
    return apiClient.get(`/deploy/status/${deploymentId}`)
  },

  // 停止部署
  stopDeployment: (deploymentId: string): Promise<{ message: string; deployment_id: string }> => {
    return apiClient.post(`/deploy/stop/${deploymentId}`)
  },

  // 获取部署列表
  listDeployments: (): Promise<{ deployments: Array<any> }> => {
    return apiClient.get('/deploy/list')
  },

  // 删除部署
  deleteDeployment: (deploymentId: string): Promise<{ message: string; deployment_id: string }> => {
    return apiClient.delete(`/deploy/delete/${deploymentId}`)
  },
}
