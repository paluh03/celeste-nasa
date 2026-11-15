import { useTranslation } from "react-i18next";

import { fmt } from "../../lib/format";
import type { Point, Reference } from "../../lib/types";

interface Props {
  current: Point | null;
  reference: Reference | null;
  warnings: string[];
  lang: string;
}

export function StatusPanel({ current, reference, warnings, lang }: Props) {
  const { t } = useTranslation();

  if (!current) {
    return (
      <div className="kpis">
        <div className="empty">{t("common.no_data")}</div>
      </div>
    );
  }

  return (
    <>
      {warnings.length > 0 && (
        <div className="warnings" role="status">
          <strong>{t("monitoring.warning")}:</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="kpis">
        <div className={`kpi status l${current.level}`}>
          <b>{current.level_name}</b>
          <span>{current.level_tip}</span>
        </div>
        <div className="kpi">
          <b>{fmt(current.cumulative_loss_pct, lang, 1)} %</b>
          <span>{t("monitoring.kpi.cumulative")}</span>
        </div>
        <div className="kpi">
          <b>
            {current.rate_pct_month === null ? "—" : fmt(current.rate_pct_month, lang, 2)}
          </b>
          <span>{t("monitoring.kpi.rate")}</span>
        </div>
        <div className="kpi">
          <b>{fmt(current.bv_tv, lang, 3)}</b>
          <span>{t("monitoring.kpi.bvtv")}</span>
        </div>
        <div className="kpi">
          <b>{current.day}</b>
          <span>{t("monitoring.kpi.days")}</span>
        </div>
        <div className="kpi">
          <b>{fmt(current.month, lang, 1)}</b>
          <span>{t("monitoring.kpi.month")}</span>
        </div>
      </div>

      {reference && (
        <div className="reference">
          <div className="reference-head">
            <span className={`badge bone-${reference.status}`}>
              {t(`bone.${reference.status}`)}
            </span>
            <span className="hint">
              {t("reference.group", {
                band: reference.age_band,
                age: reference.age,
                n: reference.n,
              })}
            </span>
          </div>

          <div className="reference-grid">
            <div>
              <strong>BUA</strong>
              <span>
                {t("reference.mean_sd", {
                  mean: fmt(reference.bua.mean, lang, 1),
                  sd: fmt(reference.bua.sd, lang, 1),
                })}
              </span>
              <span>
                {t("reference.score", {
                  z: fmt(reference.bua.z, lang, 2),
                  t: fmt(reference.bua.t, lang, 2),
                })}
              </span>
            </div>
            <div>
              <strong>SOS</strong>
              <span>
                {t("reference.mean_sd", {
                  mean: fmt(reference.sos.mean, lang, 1),
                  sd: fmt(reference.sos.sd, lang, 1),
                })}
              </span>
              <span>
                {t("reference.score", {
                  z: fmt(reference.sos.z, lang, 2),
                  t: fmt(reference.sos.t, lang, 2),
                })}
              </span>
            </div>
          </div>

          {reference.clamped && <p className="hint">{t("reference.clamped")}</p>}
          <p className="hint">
            {t("reference.source", {
              source: reference.source,
              population: reference.population,
            })}
          </p>
        </div>
      )}
    </>
  );
}
