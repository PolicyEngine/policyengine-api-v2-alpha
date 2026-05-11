from __future__ import annotations

import importlib
import sys
import types

from policyengine_api.services import bundle_metadata


def test_bundle_metadata_endpoint_returns_current_bundle(client, monkeypatch):
    payload = {
        "available": True,
        "bundle_version": "4.4.2",
        "bundle_digest": "sha256:test",
        "policyengine_version": "4.4.2",
        "profiles": {},
        "packages": {},
        "validation_report": "validation-report.json",
    }
    monkeypatch.setattr(
        "policyengine_api.api.metadata.current_bundle_metadata",
        lambda: payload,
    )

    response = client.get("/metadata/bundle")

    assert response.status_code == 200
    assert response.json() == payload


def test_current_bundle_metadata_reads_policyengine_bundle(monkeypatch):
    fake_bundle = types.ModuleType("policyengine.bundle")
    fake_bundle.get_bundle_manifest = lambda: {
        "bundle_version": "4.4.2",
        "bundle_digest": "sha256:test",
        "policyengine": {"version": "4.4.2"},
        "profiles": {
            "us": {
                "packages": ["policyengine", "policyengine-us"],
                "countries": ["us"],
                "install_targets": {},
            }
        },
        "packages": {"policyengine": {"version": "4.4.2"}},
        "validation_report": "validation-report.json",
    }
    fake_bundle.require_bundle = lambda strict=True: None
    fake_policyengine = types.ModuleType("policyengine")
    fake_policyengine.bundle = fake_bundle
    monkeypatch.setitem(sys.modules, "policyengine", fake_policyengine)
    monkeypatch.setitem(sys.modules, "policyengine.bundle", fake_bundle)
    bundle_metadata.reset_bundle_metadata_cache()

    metadata = bundle_metadata.current_bundle_metadata(strict=True)

    assert metadata["available"] is True
    assert metadata["bundle_version"] == "4.4.2"
    assert metadata["profiles"]["us"]["packages"] == [
        "policyengine",
        "policyengine-us",
    ]
    bundle_metadata.reset_bundle_metadata_cache()


def test_simulation_creation_records_bundle_metadata(session, monkeypatch):
    analysis = importlib.import_module("policyengine_api.api.analysis")
    monkeypatch.setattr(
        analysis,
        "current_bundle_metadata",
        lambda: {"available": True, "bundle_version": "4.4.2"},
    )

    from policyengine_api.api.analysis import _get_or_create_simulation
    from policyengine_api.models import (
        SimulationStatus,
        SimulationType,
        TaxBenefitModel,
        TaxBenefitModelVersion,
    )

    model = TaxBenefitModel(name="policyengine-us", description="US model")
    session.add(model)
    session.commit()
    session.refresh(model)
    model_version = TaxBenefitModelVersion(model_id=model.id, version="1.0.0")
    session.add(model_version)
    session.commit()
    session.refresh(model_version)

    simulation = _get_or_create_simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=None,
        session=session,
    )

    assert simulation.status == SimulationStatus.PENDING
    assert simulation.bundle_metadata == {
        "available": True,
        "bundle_version": "4.4.2",
    }
