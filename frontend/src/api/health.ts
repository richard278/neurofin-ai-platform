import { apiRequest } from './client';

export interface HealthResponse {
  status: string;
  app_name?: string;
  version?: string;
  environment?: string;
}

export function getHealth() {
  return apiRequest<HealthResponse>('/health');
}
