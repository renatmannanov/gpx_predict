import { api } from './client';
import type { Race, DistanceResults, SearchResult, RunnerProfileResponse, RunnerSearchResult } from '../types/races';

export function fetchRaces(): Promise<Race[]> {
  return api.get<Race[]>('/races');
}

export function fetchRace(raceId: string): Promise<Race> {
  return api.get<Race>(`/races/${raceId}`);
}

export function fetchResults(raceId: string, year: number): Promise<DistanceResults[]> {
  return api.get<DistanceResults[]>(`/races/${raceId}/${year}/results`);
}

export function searchParticipant(raceId: string, name: string): Promise<SearchResult[]> {
  return api.get<SearchResult[]>(`/races/${raceId}/search?name=${encodeURIComponent(name)}`);
}

export function fetchRunnerProfile(runnerId: number): Promise<RunnerProfileResponse> {
  return api.get<RunnerProfileResponse>(`/runners/${runnerId}`);
}

export function searchRunners(name: string): Promise<RunnerSearchResult[]> {
  return api.get<RunnerSearchResult[]>(`/runners/search?name=${encodeURIComponent(name)}`);
}
