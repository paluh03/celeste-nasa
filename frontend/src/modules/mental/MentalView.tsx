import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";
import { fmt, todayISO } from "../../lib/format";
import type { MentalAssessment, MentalDay, Mood, TlxMode } from "../../lib/types";

interface Props {
  astronaut: string;
  lang: string;
  onToast: (message: string) => void;
}

const DIMENSIONS = ["MD", "PD", "TD", "OP", "EF", "FR"] as const;
const MOOD_KEYS = [
  "m1_sleep",
  "m2_vigor",
  "m3_calm",
  "m4_cohesion",
  "m5_tension",
  "m6_irrit",
  "m7_dysphoria",
  "m8_somatic",
] as const;

const DEFAULT_RATINGS = Object.fromEntries(DIMENSIONS.map((dim) => [dim, "50"]));
const DEFAULT_TALLIES = {
  MD: "3",
  PD: "3",
  TD: "3",
  OP: "2",
  EF: "2",
  FR: "2",
};

interface TaskState {
  name: string;
  duration: string;
  mode: TlxMode;
  ratings: Record<string, string>;
  tallies: Record<string, string>;
}

function emptyTask(): TaskState {
  return {
    name: "",
    duration: "60",
    mode: "RAW_FAST",
    ratings: { ...DEFAULT_RATINGS },
    tallies: { ...DEFAULT_TALLIES },
  };
}

function defaultMood(): Mood {
  return {
    m1_sleep: 5,
    m2_vigor: 5,
    m3_calm: 5,
    m4_cohesion: 5,
    m5_tension: 5,
    m6_irrit: 5,
    m7_dysphoria: 5,
    m8_somatic: 5,
  };
}

export function MentalView({ astronaut, lang, onToast }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["mental", astronaut, lang],
    queryFn: () => api.mental(astronaut, lang),
    enabled: Boolean(astronaut),
  });

  const [day, setDay] = useState(todayISO);
  const [missionDay, setMissionDay] = useState("");
  const [tasks, setTasks] = useState<TaskState[]>([emptyTask()]);
  const [mood, setMood] = useState<Mood>(defaultMood);
  const [acute, setAcute] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.saveMental(
        astronaut,
        day,
        {
          mission_day: missionDay.trim() ? Number(missionDay) : null,
          mood,
          tasks: tasks.map((task) => ({
            name: task.name.trim() || null,
            duration_min: Number(task.duration),
            eval_mode: task.mode,
            ratings: Object.fromEntries(
              DIMENSIONS.map((dim) => [dim, Number(task.ratings[dim])]),
            ),
            tallies:
              task.mode === "WEIGHTED_FULL"
                ? Object.fromEntries(
                    DIMENSIONS.map((dim) => [dim, Number(task.tallies[dim])]),
                  )
                : null,
          })),
          acute_24h_dose_mgy: acute.trim() ? Number(acute.replace(",", ".")) : null,
          notes: notes.trim() || null,
        },
        lang,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mental"] });
      setError(null);
      onToast(t("mental.form.saved"));
    },
    onError: (reason) => {
      setError(
        reason instanceof ApiError || reason instanceof Error
          ? reason.message
          : t("mental.form.error"),
      );
    },
  });

  const data = query.data;

  function updateTask(index: number, patch: Partial<TaskState>) {
    setTasks((current) =>
      current.map((task, position) => (position === index ? { ...task, ...patch } : task)),
    );
  }

  return (
    <div className="shell">
      <section className="panel" aria-labelledby="mental-form-title">
        <h2 id="mental-form-title">{t("mental.form.title")}</h2>

        <div className="row2">
          <div className="field">
            <label htmlFor="mental-day">{t("mental.form.day")}</label>
            <input
              id="mental-day"
              type="date"
              value={day}
              max={todayISO()}
              onChange={(event) => setDay(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="mental-mission">{t("mental.form.mission_day")}</label>
            <input
              id="mental-mission"
              type="number"
              min="0"
              value={missionDay}
              onChange={(event) => setMissionDay(event.target.value)}
            />
          </div>
        </div>

        <h3 className="form-section">{t("mental.form.tasks")}</h3>
        {tasks.map((task, index) => (
          <div className="task-card" key={index}>
            <div className="row2">
              <div className="field">
                <label>{t("mental.form.task_name")}</label>
                <input
                  type="text"
                  value={task.name}
                  onChange={(event) => updateTask(index, { name: event.target.value })}
                />
              </div>
              <div className="field">
                <label>{t("mental.form.duration")}</label>
                <input
                  type="number"
                  min="1"
                  max="1440"
                  value={task.duration}
                  onChange={(event) => updateTask(index, { duration: event.target.value })}
                />
              </div>
            </div>

            <div className="field">
              <label>{t("mental.form.mode")}</label>
              <select
                value={task.mode}
                onChange={(event) =>
                  updateTask(index, { mode: event.target.value as TlxMode })
                }
              >
                <option value="RAW_FAST">{t("mental.mode.RAW_FAST")}</option>
                <option value="WEIGHTED_FULL">{t("mental.mode.WEIGHTED_FULL")}</option>
              </select>
            </div>

            <div className="rating-grid">
              {DIMENSIONS.map((dim) => (
                <label key={dim}>
                  <span>{t(`mental.dimension.${dim}`)}</span>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="5"
                    value={task.ratings[dim]}
                    onChange={(event) =>
                      updateTask(index, {
                        ratings: { ...task.ratings, [dim]: event.target.value },
                      })
                    }
                  />
                </label>
              ))}
            </div>

            {task.mode === "WEIGHTED_FULL" && (
              <>
                <p className="hint">{t("mental.form.tallies")}</p>
                <div className="rating-grid">
                  {DIMENSIONS.map((dim) => (
                    <label key={dim}>
                      <span>{t(`mental.dimension.${dim}`)}</span>
                      <input
                        type="number"
                        min="0"
                        max="5"
                        step="1"
                        value={task.tallies[dim]}
                        onChange={(event) =>
                          updateTask(index, {
                            tallies: { ...task.tallies, [dim]: event.target.value },
                          })
                        }
                      />
                    </label>
                  ))}
                </div>
              </>
            )}

            {tasks.length > 1 && (
              <div className="actions">
                <button
                  type="button"
                  onClick={() =>
                    setTasks((current) => current.filter((_, position) => position !== index))
                  }
                >
                  {t("mental.form.remove")}
                </button>
              </div>
            )}
          </div>
        ))}

        <div className="actions">
          <button type="button" onClick={() => setTasks((current) => [...current, emptyTask()])}>
            {t("mental.form.add_task")}
          </button>
        </div>

        <h3 className="form-section">{t("mental.form.mood")}</h3>
        <div className="mood-grid">
          {MOOD_KEYS.map((key) => (
            <label key={key}>
              <span>{t(`mental.mood.${key}`)}</span>
              <input
                type="range"
                min="0"
                max="10"
                step="1"
                value={mood[key]}
                onChange={(event) =>
                  setMood({ ...mood, [key]: Number(event.target.value) })
                }
              />
              <b>{mood[key]}</b>
            </label>
          ))}
        </div>

        <div className="field">
          <label htmlFor="mental-acute">
            {t("mental.form.acute")} <span className="optional">({t("cortisol.optional")})</span>
          </label>
          <input
            id="mental-acute"
            type="number"
            min="0"
            step="0.1"
            value={acute}
            onChange={(event) => setAcute(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="mental-notes">
            {t("mental.form.notes")} <span className="optional">({t("cortisol.optional")})</span>
          </label>
          <input
            id="mental-notes"
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
            {mutation.isPending ? t("mental.form.saving") : t("mental.form.submit")}
          </button>
        </div>
      </section>

      <section className="panel main" aria-labelledby="mental-title">
        <div>
          <h2 id="mental-title">
            {t("mental.title")} <small className="subtitle">{t("mental.subtitle")}</small>
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

          {data && !data.current && <div className="empty">{t("mental.empty")}</div>}
          {data?.current && <MentalResult day={data.current} lang={lang} />}
          {data && <p className="hint">{t("mental.disclaimer")}</p>}
        </div>

        {data && data.days.length > 0 && <MentalChart data={data} lang={lang} />}

        {data && data.days.length > 0 && (
          <div>
            <h2>{t("mental.history.title")}</h2>
            <div className="tbl">
              <table>
                <thead>
                  <tr>
                    <th>{t("mental.table.day")}</th>
                    <th>{t("mental.table.wl")}</th>
                    <th>{t("mental.table.dmrs")}</th>
                    <th>{t("mental.table.ali")}</th>
                    <th>{t("mental.table.zone")}</th>
                    <th>{t("mental.table.reasons")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.days].reverse().map((item) => (
                    <tr key={item.day}>
                      <td>{item.day}</td>
                      <td>{fmt(item.wl_day, lang, 1)}</td>
                      <td>{fmt(item.dmrs, lang, 1)}</td>
                      <td>{fmt(item.ali, lang, 1)}</td>
                      <td className={`z${item.color}`}>
                        <span className="badge">{t(`mental.zone.${item.zone}`)}</span>
                      </td>
                      <td className="flags-cell">
                        {item.reasons.map((reason) => t(`mental.reason.${reason}`)).join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function MentalResult({ day, lang }: { day: MentalDay; lang: string }) {
  const { t } = useTranslation();
  const flags: string[] = [];
  if (day.sleep_debt) flags.push("sleep_debt");
  if (day.burnout) flags.push("burnout");
  if (day.acute_radiation) flags.push("acute_radiation");

  return (
    <div className={`mental-zone z${day.color}`}>
      <div className="mental-zone-head">
        <div>
          <span className="badge">{t(`mental.zone.${day.zone}`)}</span>
          <p className="hint">{t(`mental.zone.${day.zone}.text`)}</p>
        </div>
        <div className="cortisol-metrics">
          <div>
            <span>{t("mental.metrics.ali")}</span>
            <b>{fmt(day.ali, lang, 1)}</b>
          </div>
          <div>
            <span>{t("mental.metrics.dmrs")}</span>
            <b>{fmt(day.dmrs, lang, 1)}</b>
          </div>
          <div>
            <span>{t("mental.metrics.wl")}</span>
            <b>{fmt(day.wl_day, lang, 1)}</b>
          </div>
        </div>
      </div>

      <div className="cortisol-cards">
        <div className="cortisol-card">
          <h3>{t("mental.metrics.ewma_wl")}</h3>
          <b>{fmt(day.ewma_wl, lang, 1)}</b>
          <span>
            {t("mental.metrics.z")}: {fmt(day.z_wl, lang, 2)}
          </span>
        </div>
        <div className="cortisol-card">
          <h3>{t("mental.metrics.ewma_mood")}</h3>
          <b>{fmt(day.ewma_mood, lang, 1)}</b>
          <span>
            {t("mental.metrics.z")}: {fmt(day.z_dmrs, lang, 2)}
          </span>
        </div>
        <div className="cortisol-card">
          <h3>
            {t("mental.metrics.pa")} / {t("mental.metrics.na")}
          </h3>
          <b>
            {fmt(day.pa, lang, 1)} / {fmt(day.na, lang, 1)}
          </b>
          <span>{day.reasons.map((reason) => t(`mental.reason.${reason}`)).join(" · ")}</span>
        </div>
      </div>

      {flags.length > 0 && (
        <ul className="cortisol-flags">
          {flags.map((flag) => (
            <li key={flag}>{t(`mental.flags.${flag}`)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MentalChart({ data, lang }: { data: MentalAssessment; lang: string }) {
  const { t } = useTranslation();
  const days = data.days.slice(-30);
  if (days.length === 0) return null;

  const W = 720;
  const H = 280;
  const L = 44;
  const R = 16;
  const T = 14;
  const B = 34;
  const X = (index: number) => L + (index / Math.max(1, days.length - 1)) * (W - L - R);
  const Y = (value: number) => H - B - (value / 100) * (H - T - B);
  const line = (selector: (item: MentalDay) => number) =>
    days.map((item, index) => `${X(index)},${Y(selector(item))}`).join(" ");

  return (
    <div>
      <h2>{t("mental.chart.title")}</h2>
      <div className="legend">
        <span>
          <i className="swatch accent" />
          {t("mental.chart.legend.wl")}
        </span>
        <span>
          <i className="swatch ok" />
          {t("mental.chart.legend.mood")}
        </span>
        <span>
          <i className="swatch bad" />
          {t("mental.chart.legend.ali")}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mental-chart" role="img">
        <rect x={L} y={Y(65)} width={W - L - R} height={Y(45) - Y(65)} className="zone-orange-band" />
        <rect x={L} y={Y(100)} width={W - L - R} height={Y(65) - Y(100)} className="zone-red-band" />
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line x1={L} x2={W - R} y1={Y(value)} y2={Y(value)} className="grid" />
            <text x={L - 8} y={Y(value) + 4} textAnchor="end">
              {value}
            </text>
          </g>
        ))}
        <polyline points={line((item) => item.ewma_wl)} className="line-wl" />
        <polyline points={line((item) => item.ewma_mood)} className="line-mood" />
        <polyline points={line((item) => item.ali)} className="line-ali" />
        {days.map((item, index) => (
          <text key={item.day} x={X(index)} y={H - B + 16} textAnchor="middle">
            {item.day.slice(5)}
          </text>
        ))}
      </svg>
      <p className="hint">
        {days[0].day} → {days[days.length - 1].day} · {fmt(data.current?.ali ?? 0, lang, 1)}
      </p>
    </div>
  );
}
