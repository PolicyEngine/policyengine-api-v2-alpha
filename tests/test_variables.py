"""Tests for variable endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion, Variable


def test_list_variables(client):
    """List variables returns a list."""
    response = client.get("/variables")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_variable_not_found(client):
    """Get non-existent variable returns 404."""
    fake_id = uuid4()
    response = client.get(f"/variables/{fake_id}")
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# Version Filtering Tests
# -----------------------------------------------------------------------------


def _create_var(session, version, name):
    """Create and persist a Variable."""
    var = Variable(
        name=name,
        entity="person",
        tax_benefit_model_version_id=version.id,
    )
    session.add(var)
    session.commit()
    session.refresh(var)
    return var


def test__given_model_name__then_returns_only_latest_version_variables(
    client, session
):
    """GET /variables?tax_benefit_model_name=X returns only latest version's vars."""
    model = TaxBenefitModel(name="policyengine-us", description="US")
    session.add(model)
    session.commit()
    session.refresh(model)

    v1 = TaxBenefitModelVersion(
        model_id=model.id,
        version="1.0",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    v2 = TaxBenefitModelVersion(
        model_id=model.id,
        version="2.0",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    session.add(v1)
    session.add(v2)
    session.commit()
    session.refresh(v1)
    session.refresh(v2)

    _create_var(session, v1, "old_variable")
    _create_var(session, v2, "new_variable")

    response = client.get("/variables?tax_benefit_model_name=policyengine-us")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "new_variable"


def test__given_explicit_version_id__then_returns_that_versions_variables(
    client, session
):
    """GET /variables?tax_benefit_model_version_id=X returns that version's vars."""
    model = TaxBenefitModel(name="policyengine-us", description="US")
    session.add(model)
    session.commit()
    session.refresh(model)

    v1 = TaxBenefitModelVersion(
        model_id=model.id,
        version="1.0",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    v2 = TaxBenefitModelVersion(
        model_id=model.id,
        version="2.0",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    session.add(v1)
    session.add(v2)
    session.commit()
    session.refresh(v1)
    session.refresh(v2)

    _create_var(session, v1, "old_variable")
    _create_var(session, v2, "new_variable")

    response = client.get(f"/variables?tax_benefit_model_version_id={v1.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "old_variable"


def test__given_version_id_overrides_model_name(client, session):
    """Version ID takes precedence over model name when both are provided."""
    model = TaxBenefitModel(name="policyengine-us", description="US")
    session.add(model)
    session.commit()
    session.refresh(model)

    v1 = TaxBenefitModelVersion(
        model_id=model.id,
        version="1.0",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    v2 = TaxBenefitModelVersion(
        model_id=model.id,
        version="2.0",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    session.add(v1)
    session.add(v2)
    session.commit()
    session.refresh(v1)
    session.refresh(v2)

    _create_var(session, v1, "old_variable")
    _create_var(session, v2, "new_variable")

    response = client.get(
        f"/variables?tax_benefit_model_name=policyengine-us&tax_benefit_model_version_id={v1.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "old_variable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
