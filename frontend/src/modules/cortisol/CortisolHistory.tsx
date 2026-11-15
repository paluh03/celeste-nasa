import { useTranslation } from "react-i18next";

import { fmt, formatDateTime } from "../../lib/format";
import type { CortisolSample } from "../../lib/types";

interface Props {
  samples: CortisolSample[];
  lang: string;
}

export function CortisolHistory({ samples, lang }: Props) {
  const { t } = useTranslation();

  if (!samples.length) {
    return <div className="empty">{t("cortisol.empty")}</div>;
  }

  const rows = [...samples].reverse();

  return (
    <div className="tbl">
      <table>
        <thead>
          <tr>
            <th>{t("cortisol.table.datetime")}</th>
            <th>{t("cortisol.table.band")}</th>
            <th>{t("cortisol.table.ug")}</th>
            <th>{t("cortisol.table.nmol")}</th>
            <th>{t("cortisol.table.z")}</th>
            <th>{t("cortisol.table.color")}</th>
            <th>{t("cortisol.table.flags")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((sample) => (
            <tr key={sample.id}>
              <td>{formatDateTime(sample.measured_at, lang)}</td>
              <td>{t(`cortisol.band.${sample.band}`)}</td>
              <td>{fmt(sample.value_ug_dl, lang, 2)}</td>
              <td>{fmt(sample.value_nmol_l, lang, 1)}</td>
              <td>{fmt(sample.z, lang, 2)}</td>
              <td className={`c${sample.color}`}>
                <span className="badge">{t(`cortisol.color.${sample.color}`)}</span>
              </td>
              <td className="flags-cell">
                {sample.flags
                  .map((flag) => t(`cortisol.flag.${flag}`))
                  .filter((text) => !text.startsWith("cortisol.flag."))
                  .join(" · ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
