import axios from 'axios';
import { authService } from './authService';

// axios 인스턴스 생성 (JWT 토큰 자동 포함)
const api = axios.create({
  baseURL: '', // 프록시 사용으로 빈 문자열
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터: JWT 토큰 자동 추가
api.interceptors.request.use((config) => {
  const token = authService.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터: 401 에러 처리
authService.setupResponseInterceptor(api);

export const chatService = {
  async getContainers() {
    try {
      const response = await api.get('/api/v1/containers');
      const containers = response.data || [];

      // 재귀적으로 컨테이너 변환하는 함수
      const transformContainer = (container: any): any => ({
        id: container.container_id,
        name: container.container_name,
        type: this.mapContainerType(container.container_type),
        level: container.org_level,
        path: container.org_path,
        description: container.description,
        permission_level: container.permission_level,
        children: container.children ? container.children.map(transformContainer) : [],
        expanded: false // 기본값으로 닫힌 상태
      });

      // 백엔드 응답을 프론트엔드 형식으로 변환
      const transformedContainers = containers.map(transformContainer);

      console.log('Original containers:', containers);
      console.log('Transformed containers:', transformedContainers);

      return {
        data: transformedContainers,
        status: 'success'
      };
    } catch (error) {
      console.error('Get containers error:', error);
      throw error;
    }
  },

  // 컨테이너 타입 매핑 함수
  mapContainerType(backendType: string): string {
    const typeMap: { [key: string]: string } = {
      'COMPANY': 'organization',
      'DIVISION': 'department',
      'DEPARTMENT': 'department',
      'TEAM': 'team',
      'folder': 'folder'
    };
    return typeMap[backendType] || 'folder';
  },

  async getUserPermissions() {
    try {
      const response = await api.get('/api/v1/permissions/user');
      return response.data;
    } catch (error) {
      console.error('Get user permissions error:', error);
      throw error;
    }
  }
};
