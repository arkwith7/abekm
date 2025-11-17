// 대시보드 API 서비스

import axios from 'axios';
import {
  ActivityStatsResponse,
  ChatHistoryResponse,
  ContainerSummaryResponse,
  DashboardSummaryResponse,
  RecentActivitiesResponse,
  RecentDocumentsResponse
} from '../types/dashboard.types';

const API_BASE_URL = '/api/v1/dashboard';

/**
 * 대시보드 요약 정보 조회
 */
export const getDashboardSummary = async (): Promise<DashboardSummaryResponse> => {
  const response = await axios.get<DashboardSummaryResponse>(`${API_BASE_URL}/summary`);
  return response.data;
};

/**
 * 최근 활동 내역 조회
 */
export const getRecentActivities = async (limit: number = 10): Promise<RecentActivitiesResponse> => {
  const response = await axios.get<RecentActivitiesResponse>(`${API_BASE_URL}/recent-activities`, {
    params: { limit }
  });
  return response.data;
};

/**
 * 최근 문서 목록 조회
 */
export const getRecentDocuments = async (limit: number = 5): Promise<RecentDocumentsResponse> => {
  const response = await axios.get<RecentDocumentsResponse>(`${API_BASE_URL}/recent-documents`, {
    params: { limit }
  });
  return response.data;
};

/**
 * 내 컨테이너 요약 정보 조회
 */
export const getContainerSummary = async (): Promise<ContainerSummaryResponse> => {
  const response = await axios.get<ContainerSummaryResponse>(`${API_BASE_URL}/container-summary`);
  return response.data;
};

/**
 * 최근 AI 대화 히스토리 조회
 */
export const getRecentChatSessions = async (limit: number = 5, cursor?: string): Promise<ChatHistoryResponse> => {
  // 서버 검증: 1 <= limit <= 20
  const safeLimit = Math.max(1, Math.min(Number.isFinite(limit) ? limit : 5, 20));
  const response = await axios.get<ChatHistoryResponse>(`${API_BASE_URL}/recent-chat-sessions`, {
    params: { limit: safeLimit, ...(cursor ? { cursor } : {}) }
  });
  return response.data;
};

/**
 * 활동 통계 조회
 */
export const getActivityStats = async (period: '7d' | '30d' | '90d' = '7d'): Promise<ActivityStatsResponse> => {
  const response = await axios.get<ActivityStatsResponse>(`${API_BASE_URL}/activity-stats`, {
    params: { period }
  });
  return response.data;
};
