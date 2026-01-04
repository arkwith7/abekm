import axios from 'axios';
import { authService } from './authService';
import { getApiUrl } from '../utils/apiConfig';

const api = axios.create({
  baseURL: getApiUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

authService.setupResponseInterceptor(api);

export interface IpcTreeNode {
  code: string;
  level: string;
  description_ko?: string | null;
  description_en?: string | null;
  patent_count?: number;
  children: IpcTreeNode[];
}

export interface PatentCardDto {
  metadata_id: number;
  application_number: string;
  applicant?: string | null;
  patent_status?: string | null;
  legal_status?: string | null;
  main_ipc_code?: string | null;
  primary_ipc_section?: string | null;
  abstract?: string | null;
}

export interface PatentListResponse {
  items: PatentCardDto[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStatsResponse {
  total_patents: number;
  by_patent_status: Array<{ patent_status: string; count: number }>;
  by_ipc_section: Array<{ primary_ipc_section: string; count: number }>;
}

export const ipPortfolioService = {
  async getIpcTree(includePatentCount = false): Promise<IpcTreeNode[]> {
    const { data } = await api.get('/api/v1/ip-portfolio/ipc-tree', {
      params: { include_patent_count: includePatentCount },
    });
    return data?.tree ?? [];
  },

  async getDashboardStats(ipcCode?: string, includeChildren = true): Promise<DashboardStatsResponse> {
    const { data } = await api.get('/api/v1/ip-portfolio/dashboard-stats', {
      params: { ipc_code: ipcCode, include_children: includeChildren },
    });
    return data;
  },

  async listPatents(params: {
    ipcCode?: string;
    includeChildren?: boolean;
    page?: number;
    pageSize?: number;
  }): Promise<PatentListResponse> {
    const { data } = await api.get('/api/v1/ip-portfolio/patents', {
      params: {
        ipc_code: params.ipcCode,
        include_children: params.includeChildren ?? true,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    });
    return data;
  },
};
