import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "./lib/api";
import type { Site } from "./lib/types";
import { CortisolView } from "./modules/cortisol/CortisolView";
import { ImportPanel } from "./modules/measurements/ImportPanel";import { ProfilePanel } from "./modules/measurements/ProfilePanel";
import { RegisterPanel } from "./modules/measurements/RegisterPanel";
import { HistoryTable } from "./modules/monitoring/HistoryTable";
import { MentalView } from "./modules/mental/MentalView";
import { RecommendationsPanel } from "./modules/monitoring/RecommendationsPanel";
import { RadiationView } from "./modules/radiation/RadiationView";
import { StatusPanel } from "./modules/monitoring/StatusPanel";
import { TrendChart } from "./modules/monitoring/TrendChart";
import { Header } from "./modules/shell/Header";
import { useToast } from "./modules/shell/Toast";

export default function App() {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage ?? "es";
  const queryClient = useQueryClient();
  const { message, show } = useToast();

  const [astronaut, setAstronaut] = useState("");
  const [site, setSite] = useState<Site>("calcaneus");
  const [view, setView] = useState<"bone" | "cortisol" | "radiation" | "mental">(() => {
    const stored = localStorage.getItem("nasa-space-view");
    return stored === "cortisol" || stored === "radiation" || stored === "mental"
      ? stored
      : "bone";
  });

  useEffect(() => {
    localStorage.setItem("nasa-space-view", view);
  }, [view]);

  const metaQuery = useQuery({
    queryKey: ["meta", lang],
    queryFn: () => api.meta(lang),
  });

  const astronautsQuery = useQuery({
    queryKey: ["astronauts", lang],
    queryFn: () => api.astronauts(lang),
  });

  const astronauts = astronautsQuery.data ?? [];
  const active = astronaut || astronauts[0]?.code || "";

  const assessmentQuery = useQuery({
    queryKey: ["monitoring", active, site, lang],
    queryFn: () => api.monitoring(active, site, lang),
    enabled: active !== "",
  });

  useEffect(() => {
    if (!astronaut && astronauts.length > 0) {
      setAstronaut(astronauts[0].code);
    }
  }, [astronaut, astronauts]);

  const meta = metaQuery.data;
  const assessment = assessmentQuery.data;
  const profile = astronauts.find((item) => item.code === active) ?? null;
  const loadError = metaQuery.isError || astronautsQuery.isError || assessmentQuery.isError;

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["monitoring"] });
  }

  return (
    <div className="app">
      <Header
        astronauts={astronauts}
        astronaut={active}
        onAstronaut={setAstronaut}
        site={site}
        onSite={setSite}
        lang={lang}
        onLang={(next) => void i18n.changeLanguage(next)}
        modelVersion={meta?.model.version}
        view={view}
        onView={setView}
      />

      {view === "cortisol" ? (
        active ? (
          <CortisolView astronaut={active} lang={lang} onToast={show} />
        ) : (
          <section className="panel">
            <div className="empty">{t("common.loading")}</div>
          </section>
        )
      ) : view === "radiation" ? (
        active ? (
          <RadiationView astronaut={active} lang={lang} onToast={show} />
        ) : (
          <section className="panel">
            <div className="empty">{t("common.loading")}</div>
          </section>
        )
      ) : view === "mental" ? (
        active ? (
          <MentalView astronaut={active} lang={lang} onToast={show} />
        ) : (
          <section className="panel">
            <div className="empty">{t("common.loading")}</div>
          </section>
        )
      ) : loadError ? (
        <section className="panel">
          <p className="err">{t("common.error")}</p>
          <button
            type="button"
            onClick={() => {
              void metaQuery.refetch();
              void astronautsQuery.refetch();
              void assessmentQuery.refetch();
            }}
          >
            {t("common.retry")}
          </button>
        </section>
      ) : (
        <div className="shell">
          <div className="column">
            {meta && (
              <RegisterPanel
                key={`${active}-${site}`}
                astronaut={active}
                site={site}
                meta={meta}
                baselineDate={assessment?.baseline?.measured_on ?? null}
                lastDate={assessment?.points.at(-1)?.measured_on ?? null}
                onSaved={() => {
                  void refresh();
                  show(t("register.saved"));
                }}
              />
            )}
            {meta && (
              <ImportPanel
                astronaut={active}
                lang={lang}
                onImported={() => void refresh()}
                onToast={show}
              />
            )}
            {profile && (
              <ProfilePanel
                key={`profile-${profile.code}`}
                astronaut={profile}
                lang={lang}
                onToast={show}
                onSaved={() => {
                  void queryClient.invalidateQueries({ queryKey: ["astronauts"] });
                  void refresh();
                }}
              />
            )}
          </div>

          <section className="panel main" aria-labelledby="monitoring-title">
            <div>
              <h2 id="monitoring-title">{t("monitoring.title")}</h2>
              <StatusPanel
                current={assessment?.current ?? null}
                reference={assessment?.reference ?? null}
                warnings={assessment?.warnings ?? []}
                lang={lang}
              />
              {assessment && (
                <RecommendationsPanel recommendation={assessment.recommendations} />
              )}
            </div>

            <div>
              <h2>{t("chart.title")}</h2>
              {meta && (
                <div className="legend">
                  <span>
                    <i className="swatch ok" />
                    {t("monitoring.legend.normal", { value: meta.thresholds.risk_rate })}
                  </span>
                  <span>
                    <i className="swatch warn" />
                    {t("monitoring.legend.risk", {
                      min: meta.thresholds.risk_rate,
                      max: meta.thresholds.alert_rate,
                    })}
                  </span>
                  <span>
                    <i className="swatch bad" />
                    {t("monitoring.legend.alert", {
                      rate: meta.thresholds.alert_rate,
                      cumulative: meta.thresholds.alert_cumulative,
                    })}
                  </span>
                </div>
              )}
              <TrendChart
                points={assessment?.points ?? []}
                thresholds={meta?.thresholds}
                lang={lang}
              />
            </div>

            <div>
              <h2>{t("table.title")}</h2>
              <HistoryTable points={assessment?.points ?? []} lang={lang} />
            </div>
          </section>
        </div>
      )}

      {view === "bone" && (
        <footer className="footer">
          <span>{meta?.model.formula ?? ""}</span>
          {assessment?.model.references.map((reference) => (
            <a key={reference} href={reference} target="_blank" rel="noreferrer">
              {reference.replace("https://doi.org/", "DOI ")}
            </a>
          ))}
        </footer>
      )}

      <div className={`toast ${message ? "show" : ""}`} role="status">
        {message}
      </div>
    </div>
  );
}
