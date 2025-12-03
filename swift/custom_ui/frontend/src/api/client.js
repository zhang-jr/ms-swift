/**
 * API 客户端
 * 封装所有 API 请求
 */
import axios from 'axios'

// 创建 axios 实例
const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
client.interceptors.request.use(
  config => {
    // 可以在这里添加 token 等
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
client.interceptors.response.use(
  response => {
    // 统一处理响应
    const { data } = response
    if (data.code === 0) {
      return data.data
    } else {
      return Promise.reject(new Error(data.message || 'Request failed'))
    }
  },
  error => {
    // 统一处理错误
    const message = error.response?.data?.message || error.message
    return Promise.reject(new Error(message))
  }
)

export default client
