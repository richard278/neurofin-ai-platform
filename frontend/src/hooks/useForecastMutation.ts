import { useMutation } from '@tanstack/react-query';
import { createForecast, ForecastRequest, ForecastResponse } from '../api/forecast';

export function useForecastMutation() {
  return useMutation<ForecastResponse, Error, ForecastRequest>({
    mutationFn: createForecast,
  });
}
