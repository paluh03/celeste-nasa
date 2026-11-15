import { useTranslation } from "react-i18next";

import type { Recommendation } from "../../lib/types";

interface Props {
  recommendation: Recommendation;
}

export function RecommendationsPanel({ recommendation }: Props) {
  const { t } = useTranslation();

  return (
    <div className={`recommendations l${recommendation.level}`}>
      <h3>
        {t("exercise.section")} · {recommendation.title}
      </h3>
      <ul>
        {recommendation.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="hint">{recommendation.disclaimer}</p>
    </div>
  );
}
