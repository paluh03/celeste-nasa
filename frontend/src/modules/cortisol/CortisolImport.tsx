import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";

interface Props {
  astronaut: string;
  lang: string;
  onImported: () => void;
  onToast: (message: string) => void;
}

export function CortisolImport({ astronaut, lang, onImported, onToast }: Props) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (target: File) => api.importCortisol(astronaut, target, lang),
    onSuccess: (report) => {
      onImported();
      onToast(t("cortisol.import.result", { created: report.created, skipped: report.skipped }));
      setFile(null);
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.message : t("cortisol.import.error"));
    },
  });

  return (
    <details className="panel collapsible">
      <summary>
        <h2>{t("cortisol.import.title")}</h2>
      </summary>

      <p className="hint">{t("cortisol.import.hint")}</p>

      <div className="field">
        <input
          type="file"
          accept=".csv,.xlsx,.json"
          onChange={(event) => {
            setError(null);
            setFile(event.target.files?.[0] ?? null);
          }}
        />
      </div>

      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={mutation.isPending}
          onClick={() => {
            setError(null);
            if (!file) {
              setError(t("cortisol.import.no_file"));
              return;
            }
            mutation.mutate(file);
          }}
        >
          {mutation.isPending ? t("common.loading") : t("cortisol.import.submit")}
        </button>
      </div>

      <p className="err" role="alert">
        {error ?? ""}
      </p>

      {mutation.data && (
        <div className="import-report">
          <p>
            {t("cortisol.import.result", {
              created: mutation.data.created,
              skipped: mutation.data.skipped,
            })}
          </p>
          {mutation.data.errors.length > 0 && (
            <ul>
              {mutation.data.errors.map((item) => (
                <li key={`${item.line}-${item.message}`}>
                  {item.line}: {item.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </details>
  );
}
