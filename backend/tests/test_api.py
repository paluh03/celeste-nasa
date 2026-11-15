from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, delete

from app.domain.models import Measurement
from app.infrastructure.database import get_engine
from app.main import app

API = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_measurements():
    with Session(get_engine()) as session:
        session.exec(delete(Measurement))
        session.commit()
    yield


def _create_astronaut(client: TestClient, code: str) -> None:
    response = client.post(
        f"{API}/astronauts",
        json={
            "code": code,
            "name": "Test",
            "sex": "male",
            "birth_date": "1985-04-12",
        },
    )
    assert response.status_code in (201, 409)


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"].endswith(".db")


def test_meta_exposes_model_and_thresholds(client: TestClient) -> None:
    body = client.get(f"{API}/meta").json()
    assert body["model"]["version"] == "scan-2013-v1"
    assert body["thresholds"]["alert_cumulative"] == 3.0
    assert body["languages"] == ["es", "en"]
    assert body["units"]["bua"] == "dB/MHz"
    assert body["reference"]["source"].startswith("Shin et al.")
    assert body["reference"]["age_bands"][0] == "20-29"
    assert body["reference"]["t_thresholds"]["osteoporosis"] == -2.5


def test_measurement_flow_and_assessment(client: TestClient) -> None:
    _create_astronaut(client, "T-01")

    payload = {
        "measured_on": "2026-07-01",
        "site": "calcaneus",
        "bua": 78.0,
        "uv": 1560.0,
        "att": 52.0,
    }
    created = client.post(f"{API}/astronauts/T-01/measurements", json=payload)
    assert created.status_code == 201, created.text

    second = client.post(
        f"{API}/astronauts/T-01/measurements",
        json={**payload, "measured_on": "2026-07-31", "bua": 77.5},
    )
    assert second.status_code == 201, second.text

    assessment = client.get(
        f"{API}/astronauts/T-01/monitoring", params={"site": "calcaneus", "lang": "es"}
    ).json()

    assert assessment["astronaut"]["code"] == "T-01"
    assert len(assessment["points"]) == 2
    assert assessment["baseline"]["measured_on"] == "2026-07-01"
    assert assessment["current"]["day"] == 30
    assert assessment["current"]["level_name"] == "Normal"
    assert assessment["model"]["references"][0] == "https://doi.org/10.1117/12.810048"

    population = assessment["reference"]
    assert population["age_band"] == "40-49"
    assert population["n"] == 137
    assert population["bua"]["mean"] == pytest.approx(119.2)
    assert population["bua"]["sd"] == pytest.approx(13.9)
    assert population["bua"]["z"] == pytest.approx((77.5 - 119.2) / 13.9, abs=1e-3)
    assert population["bua"]["t"] == pytest.approx((77.5 - 121.4) / 15.6, abs=1e-3)
    assert population["sos"]["mean"] == pytest.approx(1548.7)
    assert population["bua"]["status"] == "osteoporosis"
    assert population["status"] == "osteoporosis"
    assert assessment["current"]["bone_status"] == "osteoporosis"


def test_profile_update_recomputes_reference(client: TestClient) -> None:
    _create_astronaut(client, "T-07")
    payload = {
        "measured_on": "2026-07-01",
        "site": "calcaneus",
        "bua": 114.0,
        "uv": 1548.0,
        "att": 50.0,
    }
    assert client.post(f"{API}/astronauts/T-07/measurements", json=payload).status_code == 201

    before = client.get(f"{API}/astronauts/T-07/monitoring").json()
    assert before["reference"]["age_band"] == "40-49"

    patched = client.patch(
        f"{API}/astronauts/T-07",
        json={"sex": "female", "birth_date": "1991-02-01"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["age"] == 35

    after = client.get(f"{API}/astronauts/T-07/monitoring").json()
    assert after["reference"]["age_band"] == "30-39"
    assert after["reference"]["bua"]["mean"] == pytest.approx(113.9)
    assert after["reference"]["status"] == "normal"


def test_astronaut_table_has_profile_columns() -> None:
    from sqlalchemy import inspect

    from app.infrastructure.database import get_engine

    columns = {column["name"] for column in inspect(get_engine()).get_columns("astronaut")}
    assert {"sex", "birth_date"} <= columns


def test_english_labels_and_errors(client: TestClient) -> None:
    _create_astronaut(client, "T-02")

    bad = client.post(
        f"{API}/astronauts/T-02/measurements",
        params={"lang": "en"},
        json={
            "measured_on": "2026-07-01",
            "site": "calcaneus",
            "bua": 78.0,
            "uv": 1.5,
            "att": 52.0,
        },
    )
    assert bad.status_code == 422
    assert "UV must be between" in bad.json()["detail"]

    client.post(
        f"{API}/astronauts/T-02/measurements",
        json={
            "measured_on": "2026-07-01",
            "site": "calcaneus",
            "bua": 78.0,
            "uv": 1560.0,
            "att": 52.0,
        },
    )
    assessment = client.get(
        f"{API}/astronauts/T-02/monitoring",
        params={"site": "calcaneus", "lang": "en"},
    ).json()
    assert assessment["current"]["level_name"] == "Normal"
    assert "exercise" in assessment["current"]["level_tip"].lower()


def test_date_must_be_after_baseline(client: TestClient) -> None:
    _create_astronaut(client, "T-03")
    payload = {
        "measured_on": "2026-07-10",
        "site": "calcaneus",
        "bua": 78.0,
        "uv": 1560.0,
        "att": 52.0,
    }
    assert client.post(f"{API}/astronauts/T-03/measurements", json=payload).status_code == 201

    earlier = client.post(
        f"{API}/astronauts/T-03/measurements",
        json={**payload, "measured_on": "2026-07-01"},
    )
    assert earlier.status_code == 422
    assert "linea base" in earlier.json()["detail"]


def test_import_csv(client: TestClient) -> None:
    _create_astronaut(client, "T-04")
    csv_body = (
        "date,bua,uv,att,site\n"
        "2026-07-01,78.0,1560,52,calcaneus\n"
        "2026-07-31,77.5,1556,51.6,calcaneus\n"
        "2026-08-15,76.6,1550,50.9,calcaneus\n"
    )
    response = client.post(
        f"{API}/astronauts/T-04/measurements/import",
        files={"file": ("demo.csv", csv_body.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["created"] == 3
    assert report["errors"] == []

    points = client.get(f"{API}/astronauts/T-04/monitoring", params={"site": "calcaneus"}).json()[
        "points"
    ]
    assert len(points) == 3
    assert points[-1]["cumulative_loss_pct"] == pytest.approx(1.7948, abs=1e-3)


def test_import_xlsx_and_report_bad_rows(client: TestClient) -> None:
    _create_astronaut(client, "T-05")

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["date", "bua", "uv", "att"])
    sheet.append(["2026-07-01", 78.0, 1560, 52])
    sheet.append(["2026-07-31", 77.5, 1.5, 51.6])  # UV invalido
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = client.post(
        f"{API}/astronauts/T-05/measurements/import",
        files={
            "file": (
                "demo.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["created"] == 1
    assert report["skipped"] == 1
    assert report["errors"][0]["line"] == 3


def test_unsupported_import_format(client: TestClient) -> None:
    _create_astronaut(client, "T-06")
    response = client.post(
        f"{API}/astronauts/T-06/measurements/import",
        files={"file": ("demo.txt", b"hola", "text/plain")},
    )
    assert response.status_code == 422
    assert "csv" in response.json()["detail"].lower()
