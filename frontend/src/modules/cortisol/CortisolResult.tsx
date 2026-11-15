import { useTranslation } from "react-i18next";

import { fmt } from "../../lib/format";
import type { CortisolSample } from "../../lib/types";

interface Props {
  current: CortisolSample;
  lang: string;
}

const FLAG_LABELS: Record<string, string> = {
  assay_floor: "cortisol.result.assay_floor",
  above_manufacturer_p95: "cortisol.result.manufacturer",
  sex_discordant: "cortisol.result.discordant",
  age_out_of_range: "cortisol.flags.age_out_of_range",
};

export function CortisolResult({ current, lang }: Props) {
  const { t } = useTranslation();
  const flags = current.flags.filter((flag) => flag in FLAG_LABELS);

  return (
    <div className={`cortisol-result c${current.color}`}>
      <div className="cortisol-result-head">
        <div>
          <span className="badge">{t(`cortisol.color.${current.color}`)}</span>
          <p className="cortisol-value">
            {fmt(current.value_ug_dl, lang, 2)} <small>µg/dL</small>
          </p>
          <p className="hint">
            {fmt(current.value_nmol_l, lang, 1)} nmol/L · {t(`cortisol.band.${current.band}`)}
          </p>
        </div>
        <div className="cortisol-metrics">
          <div>
            <span>{t("cortisol.result.expected")}</span>
            <b>{fmt(current.expected_median_ug_dl, lang, 2)} µg/dL</b>
          </div>
          <div>
            <span>{t("cortisol.result.z")}</span>
            <b>{fmt(current.z, lang, 2)}</b>
          </div>
          <div>
            <span>{t("cortisol.result.percentile")}</span>
            <b>{fmt(current.percentile, lang, 1)} %</b>
          </div>
        </div>
      </div>

      <p>
        {t(`cortisol.result.direction.${current.direction}`)}
        {current.color !== 1 ? ` · ${t("cortisol.result.repeat")}` : ""}
      </p>

      {flags.length > 0 && (
        <ul className="cortisol-flags">
          {flags.map((flag) => (
            <li key={flag}>{t(FLAG_LABELS[flag])}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
