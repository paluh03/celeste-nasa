import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";
import type { CortisolUnit, MissionPhase } from "../../lib/types";

interface Props {
  astronaut: string;
  lang: string;
  onSaved: () => void;
  onToast: (message: string) => void;
}

function nowLocalInput(): string {
  const now = new Date();
  const pad = (value: number) => `${value}`.padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(
    now.getHours(),
  )}:${pad(now.getMinutes())}`;
}

const MAX_UG_DL = 10;
const NMOL_PER_UG = 27.59;

export function CortisolForm({ astronaut, lang, onSaved, onToast }: Props) {
  const { t } = useTranslation();
  const [measuredAt, setMeasuredAt] = useState(nowLocalInput);
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState<CortisolUnit>("ug_dl");
  const [wake, setWake] = useState("");
  const [phase, setPhase] = useState<MissionPhase | "">("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const numeric = Number(value.replace(",", "."));
      const max = unit === "ug_dl" ? MAX_UG_DL : MAX_UG_DL * NMOL_PER_UG;
      if (!measuredAt) throw new Error(t("register.error.date_required"));
      if (!Number.isFinite(numeric) || numeric <= 0 || numeric > max) {
        throw new Error(t("error.cortisol_range", { max }));
      }
      if (new Date(measuredAt).getTime() > Date.now() + 5 * 60 * 1000) {
        throw new Error(t("error.measured_at_future"));
      }
      return api.createCortisol(
        astronaut,
        {
          measured_at: measuredAt.length === 16 ? `${measuredAt}:00` : measuredAt,
          value: numeric,
          unit,
          wake_time: wake || null,
          mission_phase: phase || null,
          notes: notes.trim() || null,
        },
        lang,
      );
    },
    onSuccess: () => {
      setValue("");
      setNotes("");
      setError(null);
      onSaved();
      onToast(t("cortisol.form.saved"));
    },
    onError: (reason) => {
      setError(reason instanceof ApiError || reason instanceof Error ? reason.message : t("cortisol.form.error"));
    },
  });

  return (
    <section className="panel" aria-labelledby="cortisol-form-title">
      <h2 id="cortisol-form-title">{t("cortisol.form.title")}</h2>

      <div className="field">
        <label htmlFor="cortisol-datetime">{t("cortisol.form.datetime")}</label>
        <input
          id="cortisol-datetime"
          type="datetime-local"
          value={measuredAt}
          onChange={(event) => setMeasuredAt(event.target.value)}
        />
        <p className="hint">{t("cortisol.form.hint")}</p>
      </div>

      <div className="row2">
        <div className="field">
          <label htmlFor="cortisol-value">{t("cortisol.form.value")}</label>
          <input
            id="cortisol-value"
            type="number"
            step="0.01"
            inputMode="decimal"
            placeholder="0.47"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="cortisol-unit">{t("cortisol.form.unit")}</label>
          <select
            id="cortisol-unit"
            value={unit}
            onChange={(event) => setUnit(event.target.value as CortisolUnit)}
          >
            <option value="ug_dl">{t("cortisol.unit.ug_dl")}</option>
            <option value="nmol_l">{t("cortisol.unit.nmol_l")}</option>
          </select>
        </div>
      </div>

      <div className="row2">
        <div className="field">
          <label htmlFor="cortisol-wake">
            {t("cortisol.form.wake")} <span className="optional">({t("cortisol.optional")})</span>
          </label>
          <input
            id="cortisol-wake"
            type="time"
            value={wake}
            onChange={(event) => setWake(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="cortisol-phase">
            {t("cortisol.form.phase")} <span className="optional">({t("cortisol.optional")})</span>
          </label>
          <select
            id="cortisol-phase"
            value={phase}
            onChange={(event) => setPhase(event.target.value as MissionPhase | "")}
          >
            <option value="">—</option>
            <option value="preflight">{t("cortisol.phase.preflight")}</option>
            <option value="inflight">{t("cortisol.phase.inflight")}</option>
            <option value="postflight">{t("cortisol.phase.postflight")}</option>
            <option value="analog">{t("cortisol.phase.analog")}</option>
          </select>
        </div>
      </div>

      <div className="field">
        <label htmlFor="cortisol-notes">
          {t("cortisol.form.notes")} <span className="optional">({t("cortisol.optional")})</span>
        </label>
        <input
          id="cortisol-notes"
          type="text"
          maxLength={500}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </div>

      <p className="err" role="alert" aria-live="polite">
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
          {mutation.isPending ? t("cortisol.form.saving") : t("cortisol.form.submit")}
        </button>
      </div>
    </section>
  );
}
