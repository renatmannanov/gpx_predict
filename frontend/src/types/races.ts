// === Список гонок ===

export interface RaceDistance {
  id: string;
  name: string;
  distance_km: number | null;
  elevation_gain_m: number | null;
  start_altitude_m: number | null;
  finish_altitude_m: number | null;
  grade: string | null;
  has_gpx: boolean;
}

export interface RaceEdition {
  year: number;
  date: string | null;
  has_results: boolean;
  registration_url: string | null;
}

export interface Race {
  id: string;
  name: string;
  type: string | null;
  location: string | null;
  distances: RaceDistance[];
  editions: RaceEdition[];
  next_date: string | null;
}

// === Результаты ===

export interface TimeBucket {
  label: string;
  count: number;
  percent: number;
}

export interface GenderDistribution {
  gender: string;
  count: number;
  percent: number;
}

export interface CategoryDistribution {
  category: string;
  count: number;
  percent: number;
}

export interface ClubStatsData {
  club: string;
  count: number;
  best_time_s: number;
  best_time: string;
  avg_percentile: number;
}

export interface RaceStats {
  finishers: number;
  best_time: string;
  worst_time: string;
  median_time: string;
  p25_time: string;
  p75_time: string;
  time_buckets: TimeBucket[];
  gender_distribution: GenderDistribution[];
  category_distribution: CategoryDistribution[];
  club_stats: ClubStatsData[];
  total_participants?: number;
  dnf_count?: number;
  dns_count?: number;
  dnf_rate?: number | null;
}

export interface RaceResult {
  name: string;
  name_local: string | null;
  time_s: number;
  time_formatted: string;
  place: number;
  category: string | null;
  gender: string | null;
  club: string | null;
  pace: string | null;
  name_normalized?: string;
  runner_id?: number;
  status: string; // "finished" | "dnf" | "dns" | "dsq" | "over_time_limit"
}

export interface DistanceResults {
  distance_name: string;
  distance_km: number | null;
  year: number;
  stats: RaceStats;
  results: RaceResult[];
}

// === Поиск ===

export interface SearchResult {
  year: number;
  result: RaceResult | null;
  percentile?: number | null;
  total_finishers?: number | null;
  gender_percentile?: number | null;
  category_rank?: number | null;
  category_total?: number | null;
}

// === Runner profile ===

export interface RunnerProfile {
  id: number;
  name: string;
  name_normalized: string;
  club: string | null;
  category: string | null;
  gender: string | null;
}

export interface RunnerRaceResult {
  race_id: string;
  race_name: string;
  distance_name: string;
  distance_km: number | null;
  year: number;
  time_s: number;
  time_formatted: string;
  place: number;
  total_finishers: number;
  percentile: number;
  category: string | null;
  club: string | null;
  status: string;
}

export interface RunnerProfileResponse {
  profile: RunnerProfile;
  results: RunnerRaceResult[];
  total_races: number;
  years_active: number;
  median_percentile: number | null;
}

// === Хелперы ===

export type RaceCategory = 'trail' | 'road' | 'other';

// Fallback: type пока NULL в БД, определяем по race.id
// TODO: убрать после заполнения type в catalog.yaml + БД
const RACE_TYPE_BY_ID: Record<string, RaceCategory> = {
  alpine_race_kz: 'trail',
  tengri_ultra_kz: 'trail',
  salomon_trail_kz: 'trail',
  irbis_race_kz: 'trail',
  aqbura_bay_trail_kz: 'trail',
  karkyra_ultra_kz: 'trail',
  backyard_ultra_kz: 'trail',
  monster_of_shymbulak_kz: 'trail',
  amangeldy_race_kz: 'trail',
  ak_bulak_night_race_kz: 'trail',
  mount_fest_skyrunning_kz: 'trail',
  kosmos_uphill_kz: 'trail',
  red_bull_400_kz: 'trail',
  tau_jarys_am_kz: 'trail',
  tun_run_kz: 'trail',
  burabay_ice_kz: 'trail',
  almaty_marathon_am_kz: 'road',
  almaty_half_marathon_am_kz: 'road',
  zerenda_half_marathon_kz: 'road',
  winter_run_am_kz: 'road',
  almaty_copa_run_am_kz: 'road',
  summer_relay_am_kz: 'road',
};

export function getRaceCategory(type: string | null, raceId?: string): RaceCategory {
  // 1. Сначала по type из API (когда заполнят в БД)
  if (type) {
    if (type.includes('trail') || type.includes('sky') || type.includes('ultra'))
      return 'trail';
    if (type.includes('road') || type.includes('marathon'))
      return 'road';
  }
  // 2. Fallback по id
  if (raceId && raceId in RACE_TYPE_BY_ID) {
    return RACE_TYPE_BY_ID[raceId];
  }
  return 'other';
}

export function getRaceCategoryLabel(cat: RaceCategory): string {
  if (cat === 'trail') return 'Трейл';
  if (cat === 'road') return 'Шоссе';
  return 'Другое';
}
