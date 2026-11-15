import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "../../lib/api";
import type { Astronaut, Sex } from "../../lib/types";

interface Props {
  astronaut: Astronaut;
  lang: string;
  onSaved: () => void;
  onToast: (message: string) => void;
}

export function ProfilePanel({ astronaut, lang, onSaved, onToast }: Props) {
  const { t } = useTranslation();
  const [sex, setSex] = useState<Sex>(astronaut.sex ?? "male");
  const [birthDate, setBirthDate] = useState(astronaut.birth_date ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateAstronaut(astronaut.code, { sex, birth_date: birthDate }, lang),
    onSuccess: () => {
      setError(null);
      onSaved();
      onToast(t("profile.saved"));
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.message : t("profile.error"));
    },
  });

  return (
    <details className="panel collapsible">
      <summary>
        <h2>{t("profile.title")}</h2>
      </summary>

      <div className="row2">
        <div className="field">
          <label htmlFor="profile-sex">{t("profile.sex")}</label>
          <select
            id="profile-sex"
            value={sex}
            onChange={(event) => setSex(event.target.value as Sex)}
          >
            <option value="male">{t("sex.male")}</option>
            <option value="female">{t("sex.female")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="profile-birth">{t("profile.birth_date")}</label>
          <input
            id="profile-birth"
            type="date"
            value={birthDate}
            onChange={(event) => setBirthDate(event.target.value)}
          />
        </div>
      </div>

      {astronaut.age !== null && (
        <p className="hint">{t("profile.age", { age: astronaut.age })}</p>
      )}

      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={mutation.isPending || birthDate === ""}
          onClick={() => {
            setError(null);
            if (!birthDate) {
              setError(t("register.error.date_required"));
              return;
            }
            mutation.mutate();
          }}
        >
          {mutation.isPending ? t("profile.saving") : t("profile.save")}
        </button>
      </div>

      <p className="err" role="alert">
        {error ?? ""}
      </p>
    </details>
  );
}
