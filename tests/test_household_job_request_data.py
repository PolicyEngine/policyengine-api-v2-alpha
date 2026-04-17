"""Regression test for the HouseholdJob.request_data JSON mutation bug (#270).

SQLAlchemy does not track in-place mutations on columns backed by the JSON
type unless ``flag_modified`` (or an equivalent whole-object replacement) is
used. The household impact endpoint re-assigns the dict after updating the
``baseline_job_id`` key so the change is actually persisted.
"""

from sqlmodel import Session

from policyengine_api.models import HouseholdJob, HouseholdJobStatus


def test_request_data_update_round_trips(session: Session):
    """Re-reading a HouseholdJob after updating request_data must show the key."""
    job = HouseholdJob(
        country_id="us",
        request_data={"people": [{"age": 40}], "year": 2024},
        status=HouseholdJobStatus.PENDING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Mirror the pattern used in api/household.py: rebuild the dict so
    # SQLAlchemy sees a new value on the JSON column.
    job.request_data = {**job.request_data, "baseline_job_id": "deadbeef"}
    session.add(job)
    session.commit()

    # Expire + refetch from the database to catch any "only updated in
    # memory" regressions.
    session.expire_all()
    refetched = session.get(HouseholdJob, job.id)
    assert refetched is not None
    assert refetched.request_data.get("baseline_job_id") == "deadbeef"
    assert refetched.request_data.get("year") == 2024
