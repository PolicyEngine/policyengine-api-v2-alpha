"""Tests for resolving deployed PolicyEngine runtime bundles."""

from types import SimpleNamespace

import pytest

from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion
from policyengine_api.runtime_versions import (
    resolve_runtime_model_version_from_db,
    resolve_shared_runtime_model_version_from_db,
)


def _create_model_version(session, *, model_name: str, version: str):
    model = TaxBenefitModel(name=model_name, description=f"{model_name} model")
    session.add(model)
    session.commit()
    session.refresh(model)

    model_version = TaxBenefitModelVersion(
        model_id=model.id,
        version=version,
        description=f"{model_name}@{version}",
    )
    session.add(model_version)
    session.commit()
    session.refresh(model_version)
    return model_version


def test_resolve_runtime_model_version_from_db_returns_matching_bundle(
    session, monkeypatch
):
    model_version = _create_model_version(
        session, model_name="policyengine-uk", version="2.74.0"
    )
    fake_runtime = SimpleNamespace(version="2.74.0")
    fake_module = SimpleNamespace(uk_latest=fake_runtime)

    monkeypatch.setattr(
        "policyengine_api.runtime_versions.import_module",
        lambda module_name: fake_module,
    )

    resolved = resolve_runtime_model_version_from_db(session, model_version.id)

    assert resolved is fake_runtime


def test_resolve_runtime_model_version_from_db_normalizes_model_name(
    session, monkeypatch
):
    model_version = _create_model_version(
        session, model_name="policyengine_us", version="1.602.0"
    )
    fake_runtime = SimpleNamespace(version="1.602.0")
    fake_module = SimpleNamespace(us_latest=fake_runtime)

    monkeypatch.setattr(
        "policyengine_api.runtime_versions.import_module",
        lambda module_name: fake_module,
    )

    resolved = resolve_runtime_model_version_from_db(session, model_version.id)

    assert resolved is fake_runtime


def test_resolve_runtime_model_version_from_db_rejects_version_mismatch(
    session, monkeypatch
):
    model_version = _create_model_version(
        session, model_name="policyengine-uk", version="2.74.0"
    )
    fake_module = SimpleNamespace(uk_latest=SimpleNamespace(version="2.75.0"))

    monkeypatch.setattr(
        "policyengine_api.runtime_versions.import_module",
        lambda module_name: fake_module,
    )

    with pytest.raises(ValueError, match="does not match the deployed runtime bundle"):
        resolve_runtime_model_version_from_db(session, model_version.id)


def test_resolve_shared_runtime_model_version_from_db_requires_consistent_bundle(
    session, monkeypatch
):
    baseline_version = _create_model_version(
        session, model_name="policyengine-us", version="1.602.0"
    )
    reform_version = _create_model_version(
        session, model_name="policyengine-us", version="1.602.0"
    )
    fake_runtime = SimpleNamespace(version="1.602.0")
    fake_module = SimpleNamespace(us_latest=fake_runtime)

    monkeypatch.setattr(
        "policyengine_api.runtime_versions.import_module",
        lambda module_name: fake_module,
    )

    resolved = resolve_shared_runtime_model_version_from_db(
        session,
        baseline_version.id,
        reform_version.id,
    )

    assert resolved is fake_runtime


def test_resolve_shared_runtime_model_version_from_db_rejects_mixed_models(
    session, monkeypatch
):
    baseline_version = _create_model_version(
        session, model_name="policyengine-us", version="1.602.0"
    )
    reform_version = _create_model_version(
        session, model_name="policyengine-uk", version="1.602.0"
    )

    us_runtime = SimpleNamespace(version="1.602.0")
    uk_runtime = SimpleNamespace(version="1.602.0")

    def _fake_import(module_name: str):
        if module_name.endswith(".us"):
            return SimpleNamespace(us_latest=us_runtime)
        if module_name.endswith(".uk"):
            return SimpleNamespace(uk_latest=uk_runtime)
        raise AssertionError(f"Unexpected module {module_name}")

    monkeypatch.setattr(
        "policyengine_api.runtime_versions.import_module",
        _fake_import,
    )

    with pytest.raises(ValueError, match="same tax-benefit model"):
        resolve_shared_runtime_model_version_from_db(
            session,
            baseline_version.id,
            reform_version.id,
        )
