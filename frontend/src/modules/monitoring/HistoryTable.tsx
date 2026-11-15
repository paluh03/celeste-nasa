import { useTranslation } from "react-i18next";

import { fmt, signed } from "../../lib/format";
import type { Point } from "../../lib/types";

interface Props {
  points: Point[];
  lang: string;
}

export function HistoryTable({ points, lang }: Props) {
  const { t } = useTranslation();

  if (!points.length) {
    return <div className="empty">{t("table.empty")}</div>;
  }

  const rows = [...points].reverse();

  return (
    <div className="tbl">
      <table>
        <thead>
          <tr>
            <th>{t("table.date")}</th>
            <th>{t("table.day")}</th>
            <th>{t("table.month")}</th>
            <th>{t("table.bua")}</th>
            <th>{t("table.uv")}</th>
            <th>{t("table.att")}</th>
            <th>{t("table.bvtv")}</th>
            <th>{t("table.zbua")}</th>
            <th>{t("table.zsos")}</th>
            <th>{t("table.cumulative")}</th>
            <th>{t("table.rate")}</th>
            <th>{t("table.level")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((point) => (
            <tr key={`${point.measured_on}-${point.bua}`}>
              <td>{point.measured_on}</td>
              <td>{point.day}</td>
              <td>{fmt(point.month, lang, 1)}</td>
              <td>{fmt(point.bua, lang, 2)}</td>
              <td>{fmt(point.uv, lang, 0)}</td>
              <td>{point.att === null ? "—" : fmt(point.att, lang, 2)}</td>
              <td>{fmt(point.bv_tv, lang, 3)}</td>
              <td>{signed(point.bua_z, lang, 2)}</td>
              <td>{signed(point.sos_z, lang, 2)}</td>
              <td>{fmt(point.cumulative_loss_pct, lang, 1)} %</td>
              <td>
                {point.rate_pct_month === null ? "—" : fmt(point.rate_pct_month, lang, 2)}
              </td>
              <td className={`l${point.level}`}>
                <span className="badge">{point.level_name}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
