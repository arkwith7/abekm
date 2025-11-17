// 시스템관리자 관련 타입 정의

import { User as BaseUser } from './user.types';

// 시스템 관리자 전용 사용자 인터페이스 (확장된 정보 포함)
export interface User extends BaseUser {
  last_login?: string;
  session_count: number;
  activity_score: number;
  created_by?: string;
  updated_by?: string;
}

export interface UserRole {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface SystemConfig {
  ai_model_settings: {
    model_name: string;
    temperature: number;
    max_tokens: number;
    timeout: number;
  };
  search_settings: {
    max_results: number;
    similarity_threshold: number;
    enable_fuzzy_search: boolean;
  };
  security_settings: {
    session_timeout: number;
    max_login_attempts: number;
    password_policy: {
      min_length: number;
      require_special_chars: boolean;
      require_numbers: boolean;
    };
  };
  storage_settings: {
    max_file_size: number;
    allowed_file_types: string[];
    backup_retention_days: number;
  };
}

export interface SecurityAudit {
  id: string;
  event_type: 'login' | 'logout' | 'failed_login' | 'permission_change' | 'data_access' | 'system_change';
  user_id?: string;
  user_name?: string;
  ip_address: string;
  user_agent?: string;
  resource?: string;
  action: string;
  result: 'success' | 'failure' | 'blocked';
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  details: Record<string, any>;
  timestamp: string;
}

export interface BackupInfo {
  id: string;
  backup_type: 'full' | 'incremental' | 'database' | 'files';
  status: 'pending' | 'running' | 'completed' | 'failed';
  file_path?: string;
  file_size?: number;
  description?: string;
  created_at: string;
  completed_at?: string;
  error_message?: string;
  retention_until: string;
}

export interface ResourceUsage {
  timestamp: string;
  cpu_percentage: number;
  memory_percentage: number;
  disk_percentage: number;
  network_in_mbps: number;
  network_out_mbps: number;
  active_connections: number;
}

export interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_usage: number;
  active_sessions: number;
  api_response_time: number;
  uptime: number;
  last_updated: string;
}

export interface SystemAlert {
  id: string;
  type: 'warning' | 'error' | 'info';
  category: 'performance' | 'security' | 'storage' | 'network';
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'new' | 'acknowledged' | 'resolved';
  created_at: string;
  resolved_at?: string;
}

export interface UserManagement {
  user: User;
  last_login: string;
  session_count: number;
  activity_score: number;
  status: 'active' | 'inactive' | 'suspended';
  permissions: string[];
}

export interface SecurityPolicy {
  id: string;
  name: string;
  category: 'authentication' | 'authorization' | 'data' | 'network';
  description: string;
  rules: SecurityRule[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SecurityRule {
  id: string;
  type: 'password' | 'session' | 'access' | 'encryption';
  setting: string;
  value: string | number | boolean;
  description: string;
}

export interface AuditLog {
  id: string;
  user_id: string;
  user_name: string;
  action: string;
  resource: string;
  resource_id?: string;
  ip_address: string;
  user_agent: string;
  status: 'success' | 'failure';
  details: Record<string, any>;
  timestamp: string;
}

export interface SystemActivity {
  timestamp: string;
  type: 'user_login' | 'document_upload' | 'permission_change' | 'system_event';
  description: string;
  user?: string;
  metadata?: Record<string, any>;
}

export interface PerformanceChart {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    borderColor: string;
    backgroundColor: string;
  }[];
}

export interface UserStatistics {
  total_users: number;
  active_users: number;
  new_users_today: number;
  new_users_week: number;
  user_growth_rate: number;
  role_distribution: {
    USER: number;
    MANAGER: number;
    ADMIN: number;
  };
}

export interface SystemBackup {
  id: string;
  type: 'full' | 'incremental';
  status: 'running' | 'completed' | 'failed';
  file_size: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
}
