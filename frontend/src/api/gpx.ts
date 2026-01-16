/**
 * GPX API
 */

import { api } from './client'

interface GPXInfo {
  filename: string
  name: string | null
  distance_km: number
  elevation_gain_m: number
  elevation_loss_m: number
  max_elevation_m: number
  min_elevation_m: number
}

interface GPXUploadResponse {
  success: boolean
  gpx_id: string
  info: GPXInfo
}

export async function uploadGPX(file: File): Promise<GPXUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return api.postForm<GPXUploadResponse>('/gpx/upload', formData)
}

export async function getGPX(gpxId: string): Promise<GPXInfo> {
  return api.get<GPXInfo>(`/gpx/${gpxId}`)
}
