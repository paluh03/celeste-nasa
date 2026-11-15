import type {
  Assessment,
  Astronaut,
  AstronautPatch,
  CortisolAssessment,
  CortisolSample,
  CortisolSampleInput,
  ImportReport,
  Measurement,
  MeasurementInput,
  MentalAssessment,
  MentalDayInput,
  Meta,
  Point,
  RadiationAssessment,
  RadiationReading,
  RadiationReadingInput,
  Site,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function withLang(path: string, lang?: string): string {
  if (!lang) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}lang=${encodeURIComponent(lang)}`;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  lang?: string,
): Promise<T> {
  const response = await fetch(withLang(path, lang), {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    let code: string | undefined;
    try {
      const body = (await response.json()) as { detail?: string; code?: string };
      detail = body.detail ?? detail;
      code = body.code;
    } catch {
      // respuesta sin JSON: se conserva el statusText
    }
    throw new ApiError(detail, response.status, code);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  meta: (lang: string) => request<Meta>(`${BASE}/meta`, {}, lang),

  astronauts: (lang: string) => request<Astronaut[]>(`${BASE}/astronauts`, {}, lang),

  updateAstronaut: (code: string, patch: AstronautPatch, lang: string) =>
    request<Astronaut>(
      `${BASE}/astronauts/${encodeURIComponent(code)}`,
      { method: "PATCH", body: JSON.stringify(patch) },
      lang,
    ),

  monitoring: (code: string, site: Site, lang: string) =>
    request<Assessment>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/monitoring?site=${site}`,
      {},
      lang,
    ),

  preview: (code: string, input: MeasurementInput, lang: string) =>
    request<Point>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/preview`,
      { method: "POST", body: JSON.stringify(input) },
      lang,
    ),

  createMeasurement: (code: string, input: MeasurementInput, lang: string) =>
    request<Measurement>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/measurements`,
      { method: "POST", body: JSON.stringify(input) },
      lang,
    ),

  importFile: (code: string, file: File, lang: string) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportReport>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/measurements/import`,
      { method: "POST", body: form },
      lang,
    );
  },

  cortisol: (code: string, lang: string) =>
    request<CortisolAssessment>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/cortisol`,
      {},
      lang,
    ),

  createCortisol: (code: string, input: CortisolSampleInput, lang: string) =>
    request<CortisolSample>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/cortisol`,
      { method: "POST", body: JSON.stringify(input) },
      lang,
    ),

  importCortisol: (code: string, file: File, lang: string) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportReport>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/cortisol/import`,
      { method: "POST", body: form },
      lang,
    );
  },

  radiation: (code: string, lang: string) =>
    request<RadiationAssessment>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/radiation`,
      {},
      lang,
    ),

  createRadiation: (code: string, input: RadiationReadingInput, lang: string) =>
    request<RadiationReading>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/radiation`,
      { method: "POST", body: JSON.stringify(input) },
      lang,
    ),

  mental: (code: string, lang: string) =>
    request<MentalAssessment>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/mental`,
      {},
      lang,
    ),

  saveMental: (code: string, day: string, input: MentalDayInput, lang: string) =>
    request<MentalAssessment>(
      `${BASE}/astronauts/${encodeURIComponent(code)}/mental/${day}`,
      { method: "PUT", body: JSON.stringify(input) },
      lang,
    ),
};
