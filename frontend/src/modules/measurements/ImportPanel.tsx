import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";
import type { ImportReport } from "../../lib/types";

interface Props {
  astronaut: string;
  lang: string;
  onImported: () => void;
  onToast: (message: string) => void;
}

export function ImportPanel({ astronaut, lang, onImported, onToast }: Props) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (target: File) => api.importFile(astronaut, target, lang),
    onSuccess: (report: ImportReport) => {
      onImported();
      onToast(t("import.result", { created: report.created, skipped: report.skipped }));
      setFile(null);
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.message : t("import.error"));
    },
  });

  return (
    <details className="panel import-panel">
      <summary>
        <h2>{t("import.title")}</h2>
      </summary>

      <p className="hint">{t("import.hint")}</p>

      <div className="field">
        <label htmlFor="import-file">{t("import.file")}</label>
        <input
          id="import-file"
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
              setError(t("import.no_file"));
              return;
            }
            mutation.mutate(file);
          }}
        >
          {mutation.isPending ? t("import.submitting") : t("import.submit")}
        </button>
      </div>

      <p className="err" role="alert">
        {error ?? ""}
      </p>

      {mutation.data && (
        <div className="import-report">
          <p>{t("import.result", { created: mutation.data.created, skipped: mutation.data.skipped })}</p>
          {mutation.data.errors.length > 0 && (
            <>
              <strong>{t("import.errors")}</strong>
              <ul>
                {mutation.data.errors.map((item) => (
                  <li key={`${item.line}-${item.message}`}>
                    {item.line}: {item.message}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </details>
  );
}
