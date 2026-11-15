import { useId } from "react";
import { useTranslation } from "react-i18next";

import { fmt } from "../../lib/format";
import type { Meta, Point } from "../../lib/types";

interface Props {
  points: Point[];
  thresholds?: Meta["thresholds"];
  lang: string;
}

const DAYS_PER_MONTH = 30.4375;

export function TrendChart({ points, thresholds, lang }: Props) {
  const { t } = useTranslation();
  const clipId = useId().replace(/[:]/g, "");

  if (!points.length || !thresholds) {
    return <div className="empty">{t("chart.empty")}</div>;
  }

  const months = (point: Point) => point.day / DAYS_PER_MONTH;
  const xMax = Math.max(6, Math.ceil(Math.max(...points.map(months)) + 1));
  const maxLoss = Math.max(...points.map((point) => point.cumulative_loss_pct));
  const minLoss = Math.min(0, ...points.map((point) => point.cumulative_loss_pct));
  const yMax = Math.max(5, Math.ceil(maxLoss + 1));
  const yMin = Math.floor(minLoss);

  const W = 680;
  const H = 320;
  const L = 44;
  const R = 16;
  const T = 12;
  const B = 34;

  const X = (month: number) => L + (month / xMax) * (W - L - R);
  const Y = (value: number) =>
    H - B - ((value - yMin) / (yMax - yMin)) * (H - T - B);

  const triangle = (slope: number) =>
    `${X(0)},${Y(0)} ${X(xMax)},${Y(0)} ${X(xMax)},${Y(slope * xMax)}`;

  const yStep = yMax - yMin <= 8 ? 1 : 2;
  const yTicks: number[] = [];
  for (let value = yMin; value <= yMax; value += yStep) yTicks.push(value);

  const xTicks: number[] = [];
  for (let month = 0; month <= xMax; month += 1) xTicks.push(month);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={t("chart.title")}
      className="trend-chart"
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={L} y={T} width={W - L - R} height={H - T - B} />
        </clipPath>
      </defs>

      <g clipPath={`url(#${clipId})`}>
        <polygon points={triangle(thresholds.risk_rate)} className="band-ok" />
        <polygon
          points={`${X(0)},${Y(0)} ${X(xMax)},${Y(thresholds.risk_rate * xMax)} ${X(
            xMax,
          )},${Y(thresholds.alert_rate * xMax)}`}
          className="band-warn"
        />
        <polygon
          points={`${X(0)},${Y(thresholds.alert_rate * xMax)} ${X(xMax)},${Y(
            thresholds.alert_rate * xMax,
          )} ${X(xMax)},${Y(yMax)} ${X(0)},${Y(yMax)}`}
          className="band-bad"
        />

        {yTicks.map((value) => (
          <g key={`y-${value}`}>
            <line
              x1={L}
              x2={W - R}
              y1={Y(value)}
              y2={Y(value)}
              className={value === 0 ? "grid grid-axis" : "grid"}
            />
            <text x={L - 8} y={Y(value) + 4} textAnchor="end">
              {value}
            </text>
          </g>
        ))}

        {xTicks.map((month) => (
          <text key={`x-${month}`} x={X(month)} y={H - B + 16} textAnchor="middle">
            {month}
          </text>
        ))}

        <line
          x1={L}
          x2={W - R}
          y1={Y(thresholds.alert_cumulative)}
          y2={Y(thresholds.alert_cumulative)}
          className="limit-line"
        />
        <text x={W - R - 4} y={Y(thresholds.alert_cumulative) - 5} textAnchor="end" className="limit-text">
          {t("chart.limit", { value: thresholds.alert_cumulative })}
        </text>

        <polyline
          className="series"
          points={points
            .map((point) => `${X(months(point))},${Y(point.cumulative_loss_pct)}`)
            .join(" ")}
        />

        {points.map((point) => (
          <circle
            key={`${point.measured_on}-${point.day}`}
            cx={X(months(point))}
            cy={Y(point.cumulative_loss_pct)}
            r={6}
            className={`dot l${point.level}`}
          >
            <title>
              {`${point.measured_on} · ${point.level_name} · ${fmt(
                point.cumulative_loss_pct,
                lang,
                1,
              )} %`}
              {point.rate_pct_month === null
                ? ""
                : ` · ${fmt(point.rate_pct_month, lang, 2)} %/mes`}
            </title>
          </circle>
        ))}
      </g>

      <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle">
        {t("chart.x")}
      </text>
      <text
        transform={`translate(12 ${(T + H - B) / 2}) rotate(-90)`}
        textAnchor="middle"
      >
        {t("chart.y")}
      </text>
    </svg>
  );
}
