"""Tests for standalone simulation endpoints (/simulations/household, /simulations/economy)."""

from uuid import uuid4

from test_fixtures.fixtures_simulations_standalone import (
    create_dataset,
    create_economy_simulation,
    create_household,
    create_household_simulation,
    create_policy,
    create_region,
    create_us_model_and_version,
)

# ===========================================================================
# POST /simulations/household
# ===========================================================================


def test_create_household_simulation(client, session):
    """Create a household simulation returns 200 with pending status."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)

    payload = {"household_id": str(household.id)}
    response = client.post("/simulations/household", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["household_id"] == str(household.id)
    assert data["household_result"] is None
    assert data["policy_id"] is None


def test_create_household_simulation_with_policy(client, session):
    """Create a household simulation with a reform policy."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)
    policy = create_policy(session, model)

    payload = {
        "household_id": str(household.id),
        "policy_id": str(policy.id),
    }
    response = client.post("/simulations/household", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["policy_id"] == str(policy.id)


def test_create_household_simulation_not_found(client, session):
    """Creating with a non-existent household returns 404."""
    model, version = create_us_model_and_version(session)
    payload = {"household_id": str(uuid4())}
    response = client.post("/simulations/household", json=payload)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_create_household_simulation_policy_not_found(client, session):
    """Creating with a non-existent policy returns 404."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)

    payload = {
        "household_id": str(household.id),
        "policy_id": str(uuid4()),
    }
    response = client.post("/simulations/household", json=payload)

    assert response.status_code == 404
    assert "Policy" in response.json()["detail"]


def test_household_simulation_deduplication(client, session):
    """Same inputs produce the same simulation (deterministic UUID)."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)

    payload = {"household_id": str(household.id)}
    response1 = client.post("/simulations/household", json=payload)
    response2 = client.post("/simulations/household", json=payload)

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["id"] == response2.json()["id"]


# ===========================================================================
# GET /simulations/household/{id}
# ===========================================================================


def test_get_household_simulation(client, session):
    """Get a household simulation by ID."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)
    simulation = create_household_simulation(session, version, household)

    response = client.get(f"/simulations/household/{simulation.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(simulation.id)
    assert data["status"] == "completed"
    assert data["household_result"] is not None


def test_get_household_simulation_not_found(client, session):
    """Get a non-existent household simulation returns 404."""
    response = client.get(f"/simulations/household/{uuid4()}")
    assert response.status_code == 404


def test_get_household_simulation_wrong_type(client, session):
    """Get an economy simulation via the household endpoint returns 400."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)
    economy_sim = create_economy_simulation(session, version, dataset)

    response = client.get(f"/simulations/household/{economy_sim.id}")
    assert response.status_code == 400
    assert "not a household simulation" in response.json()["detail"]


# ===========================================================================
# POST /simulations/economy
# ===========================================================================


def test_create_economy_simulation_with_region(client, session):
    """Create an economy simulation using a region code."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)
    region = create_region(session, model, dataset, code="us", label="United States")

    payload = {
        "tax_benefit_model_name": "policyengine_us",
        "region": "us",
    }
    response = client.post("/simulations/economy", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["dataset_id"] == str(dataset.id)
    assert data["region"]["code"] == "us"
    assert data["region"]["label"] == "United States"


def test_create_economy_simulation_with_dataset(client, session):
    """Create an economy simulation using a dataset_id directly."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)

    payload = {
        "tax_benefit_model_name": "policyengine_us",
        "dataset_id": str(dataset.id),
    }
    response = client.post("/simulations/economy", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["dataset_id"] == str(dataset.id)
    assert data["region"] is None


def test_create_economy_simulation_with_region_filter(client, session):
    """Create an economy simulation with a region that requires filtering."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)
    region = create_region(
        session,
        model,
        dataset,
        code="state/ca",
        label="California",
        region_type="state",
        requires_filter=True,
        filter_field="state_code",
        filter_value="CA",
    )

    payload = {
        "tax_benefit_model_name": "policyengine_us",
        "region": "state/ca",
    }
    response = client.post("/simulations/economy", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["filter_field"] == "state_code"
    assert data["filter_value"] == "CA"
    assert data["region"]["requires_filter"] is True


def test_create_economy_simulation_invalid_region(client, session):
    """Creating with a non-existent region returns 404."""
    model, version = create_us_model_and_version(session)

    payload = {
        "tax_benefit_model_name": "policyengine_us",
        "region": "nonexistent/region",
    }
    response = client.post("/simulations/economy", json=payload)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_create_economy_simulation_no_region_or_dataset(client, session):
    """Creating without region or dataset_id returns 422 (Pydantic validation)."""
    model, version = create_us_model_and_version(session)

    payload = {"tax_benefit_model_name": "policyengine_us"}
    response = client.post("/simulations/economy", json=payload)

    assert response.status_code == 422


def test_create_economy_simulation_policy_not_found(client, session):
    """Creating with a non-existent policy returns 404."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)

    payload = {
        "tax_benefit_model_name": "policyengine_us",
        "dataset_id": str(dataset.id),
        "policy_id": str(uuid4()),
    }
    response = client.post("/simulations/economy", json=payload)

    assert response.status_code == 404
    assert "Policy" in response.json()["detail"]


def test_economy_simulation_deduplication(client, session):
    """Same inputs produce the same simulation (deterministic UUID)."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)

    payload = {
        "tax_benefit_model_name": "policyengine_us",
        "dataset_id": str(dataset.id),
    }
    response1 = client.post("/simulations/economy", json=payload)
    response2 = client.post("/simulations/economy", json=payload)

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["id"] == response2.json()["id"]


# ===========================================================================
# GET /simulations/economy/{id}
# ===========================================================================


def test_get_economy_simulation(client, session):
    """Get an economy simulation by ID."""
    model, version = create_us_model_and_version(session)
    dataset = create_dataset(session, model)
    simulation = create_economy_simulation(session, version, dataset)

    response = client.get(f"/simulations/economy/{simulation.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(simulation.id)
    assert data["status"] == "completed"


def test_get_economy_simulation_not_found(client, session):
    """Get a non-existent economy simulation returns 404."""
    response = client.get(f"/simulations/economy/{uuid4()}")
    assert response.status_code == 404


def test_get_economy_simulation_wrong_type(client, session):
    """Get a household simulation via the economy endpoint returns 400."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)
    household_sim = create_household_simulation(session, version, household)

    response = client.get(f"/simulations/economy/{household_sim.id}")
    assert response.status_code == 400
    assert "not an economy simulation" in response.json()["detail"]


# ===========================================================================
# Generic GET /simulations/{id} still works
# ===========================================================================


def test_get_simulation_generic(client, session):
    """The generic GET /simulations/{id} endpoint still works for any type."""
    model, version = create_us_model_and_version(session)
    household = create_household(session)
    simulation = create_household_simulation(session, version, household)

    response = client.get(f"/simulations/{simulation.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(simulation.id)
