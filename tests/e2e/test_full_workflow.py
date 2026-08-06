"""End-to-end test of the critical workflow through the real HTTP/API layer:
create portfolio -> set positions -> create model config -> trigger risk run -> fetch result
-> trigger backtest -> fetch result -> create scenario -> trigger stress run -> fetch result.

Asset/price/return data is seeded directly (assets are managed by the ingestion pipeline, not
created via the API -- out of scope per the blueprint's API surface), everything else goes
through real HTTP requests against the FastAPI app.
"""

from __future__ import annotations

import datetime as dt

import pytest

from tests.seed_helpers import seed_synthetic_portfolio

pytestmark = pytest.mark.e2e


def test_full_risk_workflow_through_api(client, api_key_headers, db_session):
    _portfolio, _config, as_of_date, tickers = seed_synthetic_portfolio(db_session, n_days=350)
    db_session.commit()

    # 1. Create a fresh portfolio via the API (separate from the seeded one).
    resp = client.post("/portfolios", json={"name": "E2E Portfolio", "base_currency": "USD"}, headers=api_key_headers)
    assert resp.status_code == 201, resp.text
    portfolio_id = resp.json()["portfolio_id"]

    # 2. Set positions using the seeded synthetic tickers.
    resp = client.post(
        f"/portfolios/{portfolio_id}/positions",
        json={"as_of_date": as_of_date.isoformat(), "positions": [{"ticker": t, "quantity": 100} for t in tickers]},
        headers=api_key_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["positions"]) == 3

    # 3. Fetch the portfolio back -- including the computed valuation fields (dashboard redesign
    # addition: weight/market_value per position, portfolio_value, concentration_hhi).
    resp = client.get(f"/portfolios/{portfolio_id}")
    assert resp.status_code == 200
    portfolio_body = resp.json()
    assert portfolio_body["name"] == "E2E Portfolio"
    assert portfolio_body["portfolio_value"] > 0
    # HHI = sum(w_i^2) for 3 positive weights summing to 1 is minimised (exactly 1/3) only at
    # equal weights and is always < 1; equal quantities with differing prices won't land exactly
    # on 1/3, so assert the mathematically-required bounds rather than an exact value.
    assert 1 / 3 - 1e-9 <= portfolio_body["concentration_hhi"] < 1.0
    for position in portfolio_body["positions"]:
        assert position["market_value"] > 0
        assert 0 < position["weight"] < 1
    assert sum(p["weight"] for p in portfolio_body["positions"]) == pytest.approx(1.0, abs=1e-9)

    # 4. Create a model config.
    resp = client.post(
        "/model-configs",
        json={"lookback_window_days": 250, "mc_num_simulations": 5000, "mc_random_seed": 1, "confidence_levels": [0.95, 0.99]},
        headers=api_key_headers,
    )
    assert resp.status_code == 201, resp.text
    config_id = resp.json()["config_id"]

    # 5. Trigger a risk run.
    resp = client.post(
        "/risk/runs", json={"portfolio_id": portfolio_id, "config_id": config_id, "as_of_date": as_of_date.isoformat()},
        headers=api_key_headers,
    )
    assert resp.status_code == 202, resp.text
    risk_run_id = resp.json()["risk_run_id"]

    # 6. Fetch the risk run result -- internally consistent VaR/CVaR (CVaR >= VaR always).
    resp = client.get(f"/risk/runs/{risk_run_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for method in ("historical", "parametric", "monte_carlo"):
        for conf_key, var_val in body["var"][method].items():
            cvar_val = body["cvar"][method][conf_key]
            assert cvar_val >= var_val - 1e-9, f"{method}/{conf_key}: CVaR < VaR"
    assert len(body["decomposition"]) == 3
    assert body["data_snapshot_hash"]
    # Volatility/max_drawdown (dashboard redesign addition, same logic as the HTML report).
    assert body["volatility"] > 0
    assert 0 <= body["max_drawdown"] < 1

    # 7. Trigger + fetch a backtest.
    window_start = (as_of_date - dt.timedelta(days=90)).isoformat()
    resp = client.post(
        "/risk/backtest",
        json={"portfolio_id": portfolio_id, "config_id": config_id, "method": "historical", "confidence": 0.95, "window_start": window_start, "window_end": as_of_date.isoformat()},
        headers=api_key_headers,
    )
    assert resp.status_code == 202, resp.text
    backtest_id = resp.json()["backtest_id"]

    resp = client.get(f"/risk/backtest/{backtest_id}")
    assert resp.status_code == 200
    backtest_body = resp.json()
    assert backtest_body["num_observations"] > 0
    assert backtest_body["traffic_light_zone"] in {"green", "amber", "red"}
    assert len(backtest_body["exceptions"]) == backtest_body["num_observations"]

    # 8. Create a scenario + trigger + fetch a stress run.
    resp = client.post(
        "/scenarios",
        json={
            "name": "E2E Test Scenario", "scenario_type": "HISTORICAL_REPLAY",
            "historical_start": "2023-01-10", "historical_end": "2023-01-20",
        },
        headers=api_key_headers,
    )
    assert resp.status_code == 201, resp.text
    scenario_id = resp.json()["scenario_id"]

    resp = client.post(
        "/stress/runs", json={"portfolio_id": portfolio_id, "scenario_id": scenario_id, "as_of_date": as_of_date.isoformat()},
        headers=api_key_headers,
    )
    assert resp.status_code == 201, resp.text
    stress_result_id = resp.json()["stress_result_id"]

    resp = client.get(f"/stress/runs/{stress_result_id}")
    assert resp.status_code == 200
    assert "portfolio_pnl" in resp.json()

    # 9. Historical risk view.
    resp = client.get(f"/risk/history/{portfolio_id}")
    assert resp.status_code == 200
    assert len(resp.json()["points"]) == 1


def test_write_endpoints_require_api_key(client):
    resp = client.post("/portfolios", json={"name": "No Auth"})
    assert resp.status_code == 401


def test_get_unknown_portfolio_returns_404(client):
    resp = client.get("/portfolios/999999")
    assert resp.status_code == 404


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
