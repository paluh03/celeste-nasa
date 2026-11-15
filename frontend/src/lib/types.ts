export type Site = "calcaneus" | "femoral_neck";
export type Sex = "male" | "female";
export type BoneStatus = "normal" | "osteopenia" | "osteoporosis" | "unknown";

export interface Astronaut {
  code: string;
  name: string;
  sex: Sex | null;
  birth_date: string | null;
  age: number | null;
}

export interface ReferenceMetric {
  mean: number;
  sd: number;
  z: number | null;
  t: number | null;
  status: BoneStatus;
}

export interface Reference {
  sex: Sex;
  age: number;
  age_band: string;
  n: number;
  clamped: boolean;
  source: string;
  population: string;
  bua: ReferenceMetric;
  sos: ReferenceMetric;
  status: BoneStatus;
}

export interface Recommendation {
  level: number;
  title: string;
  items: string[];
  disclaimer: string;
}

export interface Point {
  measured_on: string;
  day: number;
  month: number;
  bua: number;
  uv: number;
  att: number | null;
  bv_tv: number;
  cumulative_loss_pct: number;
  rate_pct_month: number | null;
  bv_tv_cumulative_loss_pct: number;
  level: 1 | 2 | 3;
  level_name: string;
  level_tip: string;
  bua_z: number | null;
  sos_z: number | null;
  bua_t: number | null;
  sos_t: number | null;
  bone_status: BoneStatus;
}

export interface ModelInfo {
  version: string;
  formula: string;
  references: string[];
}

export interface Assessment {
  astronaut: Astronaut;
  site: Site;
  baseline: Point | null;
  points: Point[];
  current: Point | null;
  reference: Reference | null;
  recommendations: Recommendation;
  warnings: string[];
  model: ModelInfo;
}

export interface ReferenceInfo {
  source: string;
  population: string;
  bua_unit: string;
  sos_unit: string;
  age_bands: string[];
  t_thresholds: { osteopenia: number; osteoporosis: number };
}

export interface Meta {
  app_name: string;
  model: ModelInfo;
  sites: Site[];
  languages: string[];
  thresholds: {
    risk_rate: number;
    alert_rate: number;
    alert_cumulative: number;
    bua_min: number;
    bua_max: number;
    uv_min: number;
    uv_max: number;
    att_min: number;
    att_max: number;
  };
  units: { bua: string; uv: string; att: string };
  reference: ReferenceInfo;
  cortisol: CortisolReference;
  radiation: RadiationReference;
}

export interface MeasurementInput {
  measured_on: string;
  site: Site;
  bua: number;
  uv: number;
  att: number | null;
}

export interface Measurement {
  id: number;
  measured_on: string;
  site: Site;
  bua: number;
  uv: number;
  att: number | null;
  source: string;
}

export interface AstronautPatch {
  name?: string;
  sex?: Sex;
  birth_date?: string;
}

export interface ImportRowError {
  line: number;
  message: string;
}

export interface ImportReport {
  created: number;
  skipped: number;
  errors: ImportRowError[];
}

// --- Cortisol (modulo independiente) ---

export type CortisolUnit = "ug_dl" | "nmol_l";
export type MissionPhase = "preflight" | "inflight" | "postflight" | "analog";
export type CortisolReading = "normal" | "watch" | "elevated" | "flat";

export interface CortisolSample {
  id: number;
  measured_at: string;
  value_ug_dl: number;
  value_nmol_l: number;
  hour: number;
  band: string;
  z: number;
  percentile: number;
  color: 1 | 2 | 3;
  expected_median_ug_dl: number;
  expected_median_nmol_l: number;
  direction: "high" | "low";
  sex_color: number;
  discordant: boolean;
  above_manufacturer_p95: boolean;
  flags: string[];
  wake_time: string | null;
  mission_phase: MissionPhase | null;
  notes: string | null;
}

export interface CortisolRatio {
  date: string;
  ratio: number;
  reading: CortisolReading;
  afternoon_ug_dl: number;
  night_ug_dl: number;
}

export interface CortisolBaseline {
  band: string;
  n: number;
  median_ug_dl: number;
  delta_pct: number | null;
}

export interface CortisolCurvePoint {
  hour: number;
  median_ug_dl: number;
  p10_ug_dl: number;
  p90_ug_dl: number;
}

export interface CortisolReference {
  method: string;
  source: string;
  sigma_ln: number;
  green_z: number;
  yellow_z: number;
  conversion_nmol_per_ug: number;
  age_range: number[];
  curve: CortisolCurvePoint[];
}

export interface CortisolAssessment {
  astronaut: Astronaut;
  samples: CortisolSample[];
  current: CortisolSample | null;
  ratio: CortisolRatio | null;
  personal_baseline: CortisolBaseline | null;
  bone_cross_risk: boolean;
  warnings: string[];
  reference: CortisolReference;
}

export interface CortisolSampleInput {
  measured_at: string;
  value: number;
  unit: CortisolUnit;
  wake_time?: string | null;
  mission_phase?: MissionPhase | null;
  notes?: string | null;
}

// --- Radiacion (TEPC) ---

export type Region = "gcr" | "saa" | "unknown";

export interface RadiationLayer {
  color: number | null;
  status: string;
  value: number | null;
  p95: number | null;
  p99: number | null;
  fraction: number | null;
  detail: string;
}

export interface RadiationReading {
  id: number;
  measured_at: string;
  eq_rate_usv_min: number;
  dose_rate_ugy_min: number | null;
  region: Region;
  module: string | null;
  mission_day: number | null;
  planned_days: number | null;
  prior_career_msv: number | null;
  notes: string | null;
  source: string;
  q_factor: number | null;
}

export interface RadiationCumulative {
  h_30d_msv: number | null;
  f30: number | null;
  h_total_msv: number | null;
  projection_msv: number | null;
  f_career: number | null;
}

export interface RadiationStratum {
  region: string;
  hour: number | null;
  module: string | null;
  epoch: string | null;
}

export interface RadiationReference {
  source: string;
  product: string;
  period: Record<string, unknown>;
  metric: string;
  unit: string;
  stratum: RadiationStratum | null;
  used_fallback: boolean;
  daily_available: boolean;
  min_cell_n: number;
  limits: Record<string, number>;
  thresholds: Record<string, number>;
  notes: string;
}

export interface RadiationAssessment {
  astronaut: Astronaut;
  readings: RadiationReading[];
  current: RadiationReading | null;
  layers: { a: RadiationLayer; b: RadiationLayer; c: RadiationLayer };
  color: number | null;
  cumulative: RadiationCumulative;
  reference: RadiationReference;
  warnings: string[];
}

export interface RadiationReadingInput {
  measured_at: string;
  eq_rate: number;
  dose_rate?: number | null;
  region: Region;
  module?: string | null;
  mission_day?: number | null;
  planned_days?: number | null;
  prior_career_msv?: number | null;
  notes?: string | null;
}

// --- Salud mental (NASA-TLX + DMRS + ALI) ---

export type TlxMode = "WEIGHTED_FULL" | "RAW_FAST";
export type MentalZone = "green" | "yellow" | "orange" | "red";

export interface Mood {
  m1_sleep: number;
  m2_vigor: number;
  m3_calm: number;
  m4_cohesion: number;
  m5_tension: number;
  m6_irrit: number;
  m7_dysphoria: number;
  m8_somatic: number;
}

export interface TlxTaskInput {
  task_ref?: string | null;
  category?: string | null;
  name?: string | null;
  duration_min: number;
  eval_mode: TlxMode;
  ratings: Record<string, number>;
  tallies?: Record<string, number> | null;
}

export interface TlxTask {
  id: number;
  task_ref: string | null;
  category: string | null;
  name: string | null;
  duration_min: number;
  eval_mode: TlxMode;
  ratings: Record<string, number>;
  weights: Record<string, number>;
  overall: number;
}

export interface MentalDay {
  day: string;
  mission_day: number | null;
  wl_day: number;
  dmrs: number;
  pa: number;
  na: number;
  z_wl: number;
  z_dmrs: number;
  ewma_wl: number;
  ewma_mood: number;
  ali: number;
  sleep_debt: boolean;
  burnout: boolean;
  acute_radiation: boolean;
  zone: MentalZone;
  color: number;
  reasons: string[];
  mood: Mood;
  tasks: TlxTask[];
}

export interface MentalAssessment {
  astronaut: Astronaut;
  days: MentalDay[];
  current: MentalDay | null;
  thresholds: Record<string, number>;
  warnings: string[];
}

export interface MentalDayInput {
  mission_day?: number | null;
  mood: Mood;
  tasks: TlxTaskInput[];
  acute_24h_dose_mgy?: number | null;
  notes?: string | null;
}
