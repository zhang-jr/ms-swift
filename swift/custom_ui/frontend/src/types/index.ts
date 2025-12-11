// 数据集配置类型
export interface DatasetConfig {
  name: string  // 数据集名称或路径
  sample_count?: number  // 采样数量（可选，例如 500）
}

// 训练相关类型
export interface TrainRequest {
  model_id: string
  model_type?: string
  datasets: DatasetConfig[]  // 支持多个数据集
  train_type?: string
  lora_rank?: number
  lora_alpha?: number
  lora_dropout?: number
  num_train_epochs?: number
  per_device_train_batch_size?: number
  gradient_accumulation_steps?: number
  learning_rate?: number
  max_length?: number
  output_dir?: string
  logging_steps?: number
  save_steps?: number
  warmup_ratio?: number
  weight_decay?: number
  gradient_checkpointing?: boolean
}

export interface TrainResponse {
  task_id: string
  status: string
  message: string
  created_at: string
}

export interface LossDataPoint {
  step: number
  loss: number
  epoch: number
}

export interface TrainStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_epoch: number
  total_epochs: number
  loss: number | null
  loss_history: LossDataPoint[]
  logs: string[]
  created_at: string
  updated_at: string
}

// 推理相关类型
export interface LoadModelRequest {
  model_id_or_path: string
  adapter_path?: string
  model_type?: string
  max_length?: number
  temperature?: number
  top_p?: number
  top_k?: number
  repetition_penalty?: number
  quantization_bit?: number
}

export interface ChatRequest {
  query: string
  history?: Array<[string, string]>
  system?: string
  max_new_tokens?: number
  temperature?: number
  top_p?: number
  top_k?: number
}

export interface ChatResponse {
  response: string
  history: Array<[string, string]>
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

// 部署相关类型
export interface DeployRequest {
  model_id_or_path: string
  adapter_path?: string
  host?: string
  port?: number
  max_length?: number
  temperature?: number
  top_p?: number
  use_vllm?: boolean
  gpu_memory_utilization?: number
  max_num_batched_tokens?: number
  quantization_bit?: number
}

export interface DeployResponse {
  deployment_id: string
  status: string
  endpoint: string
  message: string
  created_at: string
}

export interface DeploymentStatus {
  deployment_id: string
  status: 'starting' | 'running' | 'stopped' | 'failed'
  endpoint: string
  model_id: string
  created_at: string
  updated_at: string
}

// 模型和数据集类型
export interface ModelInfo {
  model_id: string
  model_name: string
  model_type: string
  size?: string
  description?: string
  tags: string[]
}

export interface DatasetInfo {
  dataset_id: string
  dataset_name: string
  description?: string
  num_samples?: number
  tags: string[]
}
