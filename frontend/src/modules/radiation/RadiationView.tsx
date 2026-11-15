import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";
import { fmt, formatDateTime } from "../../lib/format";
import type { RadiationAssessment, RadiationLayer, Region } from "../../lib/types";

interface Props {
  astronaut: string;
  lang: string;
  onToast: (message: string) => void;
}

function nowUtcInput(): string {
  const now = new Date();
  const pad = (value: number) => `${value}`.padStart(2, "0");
  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(
    now.getUTCDate(),
  )}T${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}`;
}

export function RadiationView({ astronaut, lang, onToast }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["radiation", astronaut, lang],
    queryFn: () => api.radiation(astronaut, lang),
    enabled: Boolean(astronaut),
  });

  const [measuredAt, setMeasuredAt] = useState(nowUtcInput);
  const [eq, setEq] = useState("");
  const [dose, setDose] = useState("");
  const [region, setRegion] = useState<Region>("unknown");
  const [module, setModule] = useState("");
  const [missionDay, setMissionDay] = useState("");
  const [plannedDays, setPlannedDays] = useState("");
  const [prior, setPrior] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const eqValue = Number(eq.replace(",", "."));
      if (!Number.isFinite(eqValue) || eqValue <= 0) {
        throw new Error(t("radiation.form.error"));
      }
      return api.createRadiation(
        astronaut,
        {
          measured_at: measuredAt.length === 16 ? `${measuredAt}:00` : measuredAt,
          eq_rate: eqValue,
          dose_rate: dose.trim() ? Number(dose.replace(",", ".")) : null,
          region,
          module: module.trim() || null,
          mission_day: missionDay.trim() ? Number(missionDay) : null,
          planned_days: plannedDays.trim() ? Number(plannedDays) : null,
          prior_career_msv: prior.trim() ? Number(prior.replace(",", ".")) : null,
          notes: notes.trim() || null,
        },
        lang,
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["radiation"] });
      setEq("");
      setDose("");
      setNotes("");
      setError(null);
      onToast(t("radiation.form.saved"));
    },
    onError: (reason) => {
      setError(
        reason instanceof ApiError || reason instanceof Error
          ? reason.message
          : t("radiation.form.error"),
      );
    },
  });

  const data = query.data;
  const layers = data ? (["a", "b", "c"] as const) : [];

  return (
    <div className="shell">
      <section className="panel" aria-labelledby="radiation-form-title">
        <h2 id="radiation-form-title">{t("radiation.form.title")}</h2>

        <div className="field">
          <label htmlFor="rad-datetime">{t("radiation.form.datetime")}</label>
          <input
            id="rad-datetime"
            type="datetime-local"
            value={measuredAt}
            onChange={(event) => setMeasuredAt(event.target.value)}
          />
        </div>

        <div className="row2">
          <div className="field">
            <label htmlFor="rad-eq">{t("radiation.form.eq")}</label>
            <div className="unit">
              <input
                id="rad-eq"
                type="number"
                step="0.001"
                inputMode="decimal"
                placeholder="0.50"
                value={eq}
                onChange={(event) => setEq(event.target.value)}
              />
              <span>{t("radiation.unit.eq")}</span>
            </div>
          </div>
          <div className="field">
            <label htmlFor="rad-dose">
              {t("radiation.form.dose")}{" "}
              <span className="optional">({t("cortisol.optional")})</span>
            </label>
            <div className="unit">
              <input
                id="rad-dose"
                type="number"
                step="0.001"
                inputMode="decimal"
                value={dose}
                onChange={(event) => setDose(event.target.value)}
              />
              <span>{t("radiation.unit.dose")}</span>
            </div>
          </div>
        </div>

        <div className="row2">
          <div className="field">
            <label htmlFor="rad-region">{t("radiation.form.region")}</label>
            <select
              id="rad-region"
              value={region}
              onChange={(event) => setRegion(event.target.value as Region)}
            >
              <option value="unknown">{t("radiation.region.unknown")}</option>
              <option value="gcr">{t("radiation.region.gcr")}</option>
              <option value="saa">{t("radiation.region.saa")}</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="rad-module">
              {t("radiation.form.module")}{" "}
              <span className="optional">({t("cortisol.optional")})</span>
            </label>
            <input
              id="rad-module"
              type="text"
              maxLength={64}
              value={module}
              onChange={(event) => setModule(event.target.value)}
            />
          </div>
        </div>

        <div className="row2">
          <div className="field">
            <label htmlFor="rad-mission">
              {t("radiation.form.mission_day")}{" "}
              <span className="optional">({t("cortisol.optional")})</span>
            </label>
            <input
              id="rad-mission"
              type="number"
              min="0"
              value={missionDay}
              onChange={(event) => setMissionDay(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="rad-planned">
              {t("radiation.form.planned_days")}{" "}
              <span className="optional">({t("cortisol.optional")})</span>
            </label>
            <input
              id="rad-planned"
              type="number"
              min="1"
              value={plannedDays}
              onChange={(event) => setPlannedDays(event.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="rad-prior">
            {t("radiation.form.prior")}{" "}
            <span className="optional">({t("cortisol.optional")})</span>
          </label>
          <input
            id="rad-prior"
            type="number"
            step="0.1"
            min="0"
            value={prior}
            onChange={(event) => setPrior(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="rad-notes">
            {t("radiation.form.notes")}{" "}
            <span className="optional">({t("cortisol.optional")})</span>
          </label>
          <input
            id="rad-notes"
            type="text"
            maxLength={500}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>

        <p className="err" role="alert">
          {error ?? ""}
        </p>

        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={mutation.isPending}
            onClick={() => {
              setError(null);
              mutation.mutate();
            }}
          >
            {mutation.isPending ? t("radiation.form.saving") : t("radiation.form.submit")}
          </button>
        </div>
      </section>

      <section className="panel main" aria-labelledby="radiation-title">
        <div>
          <h2 id="radiation-title">
            {t("radiation.title")}{" "}
            <small className="subtitle">{t("radiation.subtitle")}</small>
          </h2>

          {query.isLoading && <div className="empty">{t("common.loading")}</div>}
          {query.isError && (
            <>
              <p className="err">{t("common.error")}</p>
              <button type="button" onClick={() => void query.refetch()}>
                {t("common.retry")}
              </button>
            </>
          )}

          {data && !data.current && <div className="empty">{t("radiation.empty")}</div>}

          {data?.current && (
            <div className={`radiation-banner c${data.color ?? 0}`}>
              <span className="badge">
                {data.color ? t(`radiation.color.${data.color}`) : t("radiation.color.none")}
              </span>
              <span>
                {fmt(data.current.eq_rate_usv_min, lang, 2)} µSv/min ·{" "}
                {data.current.region.toUpperCase()}
              </span>
            </div>
          )}

          {data && (
            <div className="cortisol-cards">
              {layers.map((key) => (
                <LayerCard key={key} title={t(`radiation.layer.${key}.title`)} layer={data.layers[key]} lang={lang} />
              ))}
            </div>
          )}

          {data && (
            <div className="cortisol-cards">
              <div className="cortisol-card">
                <h3>{t("radiation.cumulative.h30")}</h3>
                <b>{fmt(data.cumulative.h_30d_msv, lang, 3)} mSv</b>
                <span>
                  {t("radiation.cumulative.f30")}: {fmt(data.cumulative.f30, lang, 2)}
                </span>
              </div>
              <div className="cortisol-card">
                <h3>{t("radiation.cumulative.total")}</h3>
                <b>{fmt(data.cumulative.h_total_msv, lang, 3)} mSv</b>
                <span>
                  {t("radiation.cumulative.projection")}:{" "}
                  {fmt(data.cumulative.projection_msv, lang, 3)} mSv
                </span>
              </div>
              <div className="cortisol-card">
                <h3>{t("radiation.cumulative.fcareer")}</h3>
                <b>{fmt(data.cumulative.f_career, lang, 2)}</b>
                <span>
                  {data.reference.limits.career_msv} mSv · {t("radiation.cumulative.f30")}{" "}
                  {data.reference.limits.window_30d_msv} mSv
                </span>
              </div>
            </div>
          )}

          {data && data.warnings.length > 0 && (
            <div className="warnings" role="status">
              <ul>
                {data.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {data && <RadiationChart data={data} lang={lang} />}

          <p className="hint">{t("radiation.disclaimer")}</p>
          {data && (
            <p className="hint">
              {t("radiation.reference", {
                product: data.reference.product,
                source: data.reference.source,
              })}
              {" · "}
              {t("radiation.period", {
                start: String(data.reference.period.start ?? ""),
                end: String(data.reference.period.end ?? ""),
                days: String(data.reference.period.days ?? ""),
              })}
            </p>
          )}
          {data?.reference.used_fallback && <p className="hint">{t("radiation.fallback")}</p>}
        </div>

        {data && (
          <div>
            <h2>{t("radiation.history.title")}</h2>
            <div className="tbl">
              <table>
                <thead>
                  <tr>
                    <th>{t("radiation.table.datetime")}</th>
                    <th>{t("radiation.table.region")}</th>
                    <th>{t("radiation.table.eq")}</th>
                    <th>{t("radiation.table.dose")}</th>
                    <th>{t("radiation.table.q")}</th>
                    <th>{t("radiation.table.color")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.readings].reverse().slice(0, 20).map((reading) => {
                    const p95 = data.layers.a.p95;
                    const p99 = data.layers.a.p99;
                    const color =
                      p95 === null || p99 === null
                        ? 0
                        : reading.eq_rate_usv_min <= p95
                          ? 1
                          : reading.eq_rate_usv_min <= p99
                            ? 2
                            : 3;
                    return (
                      <tr key={reading.id}>
                        <td>{formatDateTime(reading.measured_at, lang)}</td>
                        <td>{t(`radiation.region.${reading.region}`)}</td>
                        <td>{fmt(reading.eq_rate_usv_min, lang, 2)}</td>
                        <td>
                          {reading.dose_rate_ugy_min === null
                            ? "—"
                            : fmt(reading.dose_rate_ugy_min, lang, 2)}
                        </td>
                        <td>{fmt(reading.q_factor, lang, 2)}</td>
                        <td className={`c${color}`}>
                          {color ? (
                            <span className="badge">{t(`radiation.color.${color}`)}</span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function LayerCard({
  title,
  layer,
  lang,
}: {
  title: string;
  layer: RadiationLayer;
  lang: string;
}) {
  const { t } = useTranslation();
  const colorClass = layer.color ? `c${layer.color}` : "";
  return (
    <div className={`cortisol-card ${colorClass}`}>
      <h3>{title}</h3>
      <b>{t(`radiation.layer.status.${layer.status}`)}</b>
      <span>
        {t("radiation.layer.value")}:{" "}
        {layer.value === null
          ? "—"
          : layer.fraction !== null
            ? `${fmt(layer.fraction, lang, 2)}`
            : `${fmt(layer.value, lang, 2)}`}
      </span>
      <span>
        {t("radiation.layer.p95")}: {fmt(layer.p95, lang, 2)} · {t("radiation.layer.p99")}:{" "}
        {fmt(layer.p99, lang, 2)}
      </span>
    </div>
  );
}

function RadiationChart({ data, lang }: { data: RadiationAssessment; lang: string }) {
  const readings = data.readings.slice(-30);
  const p95 = data.layers.a.p95;
  const p99 = data.layers.a.p99;
  if (!readings.length) return null;

  const W = 720;
  const H = 260;
  const L = 48;
  const R = 16;
  const T = 14;
  const B = 34;
  const maxValue = Math.max(
    0.5,
    ...readings.map((reading) => reading.eq_rate_usv_min),
    p99 ?? 0,
  );
  const X = (index: number) => L + (index / Math.max(1, readings.length - 1)) * (W - L - R);
  const Y = (value: number) => H - B - (value / maxValue) * (H - T - B);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="radiation-chart" role="img">
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
        <g key={ratio}>
          <line
            x1={L}
            x2={W - R}
            y1={Y(maxValue * ratio)}
            y2={Y(maxValue * ratio)}
            className="grid"
          />
          <text x={L - 8} y={Y(maxValue * ratio) + 4} textAnchor="end">
            {fmt(maxValue * ratio, lang, 1)}
          </text>
        </g>
      ))}

      {p95 !== null && (
        <line x1={L} x2={W - R} y1={Y(p95)} y2={Y(p95)} className="limit-p95" />
      )}
      {p99 !== null && (
        <line x1={L} x2={W - R} y1={Y(p99)} y2={Y(p99)} className="limit-p99" />
      )}

      <polyline
        className="radiation-series"
        points={readings
          .map((reading, index) => `${X(index)},${Y(reading.eq_rate_usv_min)}`)
          .join(" ")}
      />

      {readings.map((reading, index) => {
        const color =
          p95 === null || p99 === null
            ? 1
            : reading.eq_rate_usv_min <= p95
              ? 1
              : reading.eq_rate_usv_min <= p99
                ? 2
                : 3;
        return (
          <circle
            key={reading.id}
            cx={X(index)}
            cy={Y(reading.eq_rate_usv_min)}
            r={5}
            className={`c${color}`}
          >
            <title>
              {`${reading.measured_at} · ${reading.eq_rate_usv_min} µSv/min`}
            </title>
          </circle>
        );
      })}
    </svg>
  );
}
