import { apiRequest } from './client';

export interface ForecastPoint {
  step: number;
  value: number;
}

export interface ForecastRequest {
  symbol: string;
  historical_values: number[];
  horizon: number;
}

export interface ForecastResponse {
  symbol: string;
  horizon: number;
  points: ForecastPoint[];
}

export function createForecast(payload: ForecastRequest) {
  return apiRequest<ForecastResponse>('/forecast', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
