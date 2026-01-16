/**
 * Prediction API
 */

import { api } from './client'

interface HikePredictRequest {
  gpx_id: string
  experience: string
  backpack: string
  group_size: number
  has_children: boolean
  has_elderly: boolean
  is_round_trip: boolean
}

interface Warning {
  level: 'info' | 'warning' | 'danger'
  code: string
  message: string
}

interface HikePrediction {
  estimated_time_hours: number
  safe_time_hours: number
  recommended_start: string
  warnings: Warning[]
  experience_multiplier: number
  backpack_multiplier: number
  group_multiplier: number
  altitude_multiplier: number
  total_multiplier: number
}

export async function predictHike(
  data: HikePredictRequest
): Promise<HikePrediction> {
  return api.post<HikePrediction>('/predict/hike', data)
}
