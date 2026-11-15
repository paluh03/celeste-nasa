import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { CortisolCurvePoint, CortisolSample } from "../../lib/types";

interface Props {
  curve: CortisolCurvePoint[];
  samples: CortisolSample[];
}

const W = 720;
const H = 300;
const L = 48;
const R = 16;
const T = 14;
const B = 38;

export function CortisolChart({ curve, samples }: Props) {
  const { t } = useTranslation();
  const clipId = useId().replace(/[:]/g, "");

  if (curve.length === 0) {
    return <div className="empty">{t("cortisol.empty")}</div>;
  }

  const lastDate = samples.at(-1)?.measured_at.slice(0, 10);
  const shown = lastDate
    ? samples.filter((sample) => sample.measured_at.slice(0, 10) === lastDate)
    : [];

  const maxValue = Math.max(
    1.2,
    ...curve.map((point) => point.p90_ug_dl),
    ...shown.map((sample) => sample.value_ug_dl),
  );
  const yMax = Math.ceil(maxValue * 1.15 * 10) / 10;

  const X = (hour: number) => L + (hour / 24) * (W - L - R);
  const Y = (value: number) => H - B - (value / yMax) * (H - T - B);

  const bandPoints = [
    ...curve.map((point) => `${X(point.hour)},${Y(point.p90_ug_dl)}`),
    ...[...curve].reverse().map((point) => `${X(point.hour)},${Y(point.p10_ug_dl)}`),
  ].join(" ");

  const medianPoints = curve
    .map((point) => `${X(point.hour)},${Y(point.median_ug_dl)}`)
    .join(" ");

  const xTicks = [0, 3, 6, 9, 12, 15, 18, 21, 24];
  const yTicks = Array.from({ length: 5 }, (_, index) => (yMax / 4) * index);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={t("cortisol.title")}
      className="cortisol-chart"
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={L} y={T} width={W - L - R} height={H - T - B} />
        </clipPath>
      </defs>

      <g clipPath={`url(#${clipId})`}>
        <polygon points={bandPoints} className="cortisol-band" />
        <polyline points={medianPoints} className="cortisol-median" />

        {shown.map((sample) => (
          <circle
            key={sample.id}
            cx={X(sample.hour)}
            cy={Y(sample.value_ug_dl)}
            r={6}
            className={`cortisol-dot c${sample.color}`}
          >
            <title>
              {`${sample.measured_at} · ${sample.value_ug_dl} µg/dL · z ${sample.z}`}
            </title>
          </circle>
        ))}
      </g>

      {yTicks.map((value) => (
        <g key={`y-${value}`}>
          <line x1={L} x2={W - R} y1={Y(value)} y2={Y(value)} className="grid" />
          <text x={L - 8} y={Y(value) + 4} textAnchor="end">
            {value.toFixed(1)}
          </text>
        </g>
      ))}

      {xTicks.map((hour) => (
        <text key={`x-${hour}`} x={X(hour)} y={H - B + 16} textAnchor="middle">
          {hour}:00
        </text>
      ))}

      <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle">
        {t("cortisol.chart.x")}
      </text>
      <text transform={`translate(12 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle">
        µg/dL
      </text>
    </svg>
  );
}
