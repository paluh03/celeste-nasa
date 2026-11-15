import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";
import { addDays, daysBetween, fmt, todayISO } from "../../lib/format";
import type { MeasurementInput, Meta, Point, Site } from "../../lib/types";

interface Props {
  astronaut: string;
  site: Site;
  meta: Meta;
  baselineDate: string | null;
  lastDate: string | null;
  onSaved: () => void;
}

export function RegisterPanel({
  astronaut,
  site,
  meta,
  baselineDate,
  lastDate,
  onSaved,
}: Props) {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage ?? "es";

  const [step, setStep] = useState(1);
  const [date, setDate] = useState(() => (lastDate ? addDays(lastDate, 15) : todayISO()));
  const [bua, setBua] = useState("");
  const [uv, setUv] = useState("");
  const [att, setAtt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<MeasurementInput | null>(null);
  const [preview, setPreview] = useState<Point | null>(null);

  const previewMutation = useMutation({
    mutationFn: (input: MeasurementInput) => api.preview(astronaut, input, lang),
  });
  const saveMutation = useMutation({
    mutationFn: (input: MeasurementInput) => api.createMeasurement(astronaut, input, lang),
  });

  const pending = previewMutation.isPending || saveMutation.isPending;
  const limits = meta.thresholds;

  function message(reason: unknown): string {
    return reason instanceof ApiError ? reason.message : t("register.error.save");
  }

  function parseDraft(): MeasurementInput | null {
    const buaValue = Number(bua.replace(",", "."));
    const uvValue = Number(uv.replace(",", "."));
    const attValue = att.trim() === "" ? null : Number(att.replace(",", "."));

    if (!Number.isFinite(buaValue) || !(buaValue > limits.bua_min && buaValue < limits.bua_max)) {
      setError(
        t("register.error.bua", { min: limits.bua_min, max: limits.bua_max }),
      );
      return null;
    }
    if (!Number.isFinite(uvValue) || !(uvValue >= limits.uv_min && uvValue <= limits.uv_max)) {
      setError(t("register.error.uv", { min: limits.uv_min, max: limits.uv_max }));
      return null;
    }
    if (
      attValue !== null &&
      (!Number.isFinite(attValue) || !(attValue > limits.att_min && attValue < limits.att_max))
    ) {
      setError(t("register.error.att", { min: limits.att_min, max: limits.att_max }));
      return null;
    }

    return { measured_on: date, site, bua: buaValue, uv: uvValue, att: attValue };
  }

  function reset() {
    setStep(1);
    setBua("");
    setUv("");
    setAtt("");
    setPreview(null);
    setDraft(null);
    setError(null);
    setDate(draft ? addDays(draft.measured_on, 15) : todayISO());
  }

  function next() {
    setError(null);

    if (step === 1) {
      if (!date) {
        setError(t("register.error.date_required"));
        return;
      }
      if (baselineDate && date <= baselineDate) {
        setError(t("register.error.date_after_baseline", { baseline: baselineDate }));
        return;
      }
      setStep(2);
      return;
    }

    if (step === 2) {
      const input = parseDraft();
      if (!input) return;
      setDraft(input);
      previewMutation.mutate(input, {
        onSuccess: (point) => {
          setPreview(point);
          setStep(3);
        },
        onError: (reason) => setError(message(reason)),
      });
      return;
    }

    if (draft) {
      saveMutation.mutate(draft, {
        onSuccess: () => {
          onSaved();
          reset();
        },
        onError: (reason) => setError(message(reason)),
      });
    }
  }

  const hint =
    baselineDate && date
      ? t("register.hint.day", {
          day: daysBetween(baselineDate, date),
          baseline: baselineDate,
        })
      : t("register.hint.first");

  return (
    <section className="panel" aria-labelledby="register-title">
      <h2 id="register-title">{t("register.title")}</h2>

      <ol className="steps">
        <li className={step === 1 ? "on" : step > 1 ? "done" : ""}>
          {t("register.step.session")}
        </li>
        <li className={step === 2 ? "on" : step > 2 ? "done" : ""}>
          {t("register.step.measures")}
        </li>
        <li className={step === 3 ? "on" : ""}>{t("register.step.confirm")}</li>
      </ol>

      {step === 1 && (
        <div>
          <div className="field">
            <label htmlFor="session-date">{t("register.date")}</label>
            <input
              id="session-date"
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
            <p className="hint">{hint}</p>
          </div>
          <div className="field">
            <span className="label">{t("register.site_label")}</span>
            <p className="static-value">{t(`site.${site}`)}</p>
          </div>
        </div>
      )}

      {step === 2 && (
        <div>
          <div className="field">
            <label htmlFor="bua">{t("register.bua")}</label>
            <div className="unit">
              <input
                id="bua"
                type="number"
                step="0.01"
                inputMode="decimal"
                placeholder="118.00"
                value={bua}
                onChange={(event) => setBua(event.target.value)}
              />
              <span>{meta.units.bua}</span>
            </div>
          </div>
          <div className="field">
            <label htmlFor="uv">{t("register.uv")}</label>
            <div className="unit">
              <input
                id="uv"
                type="number"
                step="1"
                inputMode="decimal"
                placeholder="1560"
                value={uv}
                onChange={(event) => setUv(event.target.value)}
              />
              <span>{meta.units.uv}</span>
            </div>
          </div>
          <div className="field">
            <label htmlFor="att">
              {t("register.att")}{" "}
              <span className="optional">({t("register.optional")})</span>
            </label>
            <div className="unit">
              <input
                id="att"
                type="number"
                step="0.01"
                inputMode="decimal"
                placeholder="52.00"
                value={att}
                onChange={(event) => setAtt(event.target.value)}
              />
              <span>{meta.units.att}</span>
            </div>
          </div>
        </div>
      )}

      {step === 3 && preview && (
        <div>
          <dl className="review">
            <dt>{t("register.review.astronaut")}</dt>
            <dd>{astronaut}</dd>
            <dt>{t("register.review.date")}</dt>
            <dd>
              {preview.measured_on} · {t("register.review.day", { day: preview.day })}
            </dd>
            <dt>{t("register.review.bua")}</dt>
            <dd>
              {fmt(preview.bua, lang, 2)} {meta.units.bua}
            </dd>
            <dt>{t("register.review.uv")}</dt>
            <dd>
              {fmt(preview.uv, lang, 0)} {meta.units.uv}
            </dd>
            <dt>{t("register.review.att")}</dt>
            <dd>
              {preview.att === null ? "—" : `${fmt(preview.att, lang, 2)} ${meta.units.att}`}
            </dd>
            <dt>{t("register.review.bvtv")}</dt>
            <dd>{fmt(preview.bv_tv, lang, 3)}</dd>
            <dt>{t("register.review.cumulative")}</dt>
            <dd>{fmt(preview.cumulative_loss_pct, lang, 1)} %</dd>
            <dt>{t("register.review.rate")}</dt>
            <dd>
              {preview.rate_pct_month === null
                ? "—"
                : `${fmt(preview.rate_pct_month, lang, 2)} %/mes`}
            </dd>
            <dt>{t("register.review.reference")}</dt>
            <dd>
              <span className={`badge bone-${preview.bone_status}`}>
                {t(`bone.${preview.bone_status}`)}
              </span>
            </dd>
          </dl>

          <div className={`verdict l${preview.level}`}>
            {preview.day === 0 ? (
              <>
                <span className="badge">{t("register.baseline.badge")}</span>{" "}
                {t("register.baseline.tip")}
              </>
            ) : (
              <>
                <span className="badge">{preview.level_name}</span> {preview.level_tip}
              </>
            )}
          </div>
        </div>
      )}

      <p className="err" role="alert" aria-live="polite">
        {error ?? ""}
      </p>

      <div className="actions">
        {step > 1 && (
          <button type="button" onClick={() => setStep(step - 1)} disabled={pending}>
            {t("register.action.back")}
          </button>
        )}
        <button type="button" className="primary" onClick={next} disabled={pending}>
          {step === 3
            ? saveMutation.isPending
              ? t("register.action.saving")
              : t("register.action.save")
            : previewMutation.isPending
              ? t("common.loading")
              : t("register.action.next")}
        </button>
      </div>
    </section>
  );
}
