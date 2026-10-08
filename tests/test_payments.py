"""Unit tests for submission-payment persistence and R2 backfill behavior."""
from __future__ import annotations

import pytest

import app.d1 as d1
import scripts.backfill_submissions as backfill_module


def test_create_submission_writes_an_unpaid_record(monkeypatch):
    calls = []
    monkeypatch.setattr(d1, "_query", lambda sql, params: calls.append((sql, params)) or [])

    d1.db_create_submission("alice", "12345")

    assert "INSERT OR IGNORE INTO submissions" in calls[0][0]
    assert calls[0][1] == ["alice", "12345"]


def test_get_submission_returns_d1_row(monkeypatch):
    expected = [{"id": 1, "username": "alice", "consumer_number": "12345"}]
    monkeypatch.setattr(d1, "_query", lambda sql, params: expected)

    assert d1.db_get_submission("alice", "12345") == expected[0]


def test_count_unpaid_submissions_returns_count(monkeypatch):
    monkeypatch.setattr(d1, "_query", lambda sql, params: [{"cnt": 2}])

    assert d1.db_count_unpaid_submissions("alice") == 2


def test_count_unpaid_submissions_returns_zero_for_no_row(monkeypatch):
    monkeypatch.setattr(d1, "_query", lambda sql, params: [])

    assert d1.db_count_unpaid_submissions("alice") == 0


def test_get_submission_by_id_returns_matching_row(monkeypatch):
    expected = {"id": 9, "payment_status": "UNPAID"}
    monkeypatch.setattr(d1, "_query", lambda sql, params: [expected])

    assert d1.db_get_submission_by_id(9) == expected


def test_get_submission_by_id_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(d1, "_query", lambda sql, params: [])

    assert d1.db_get_submission_by_id(999) is None


def test_update_payment_status_writes_new_status(monkeypatch):
    calls = []
    monkeypatch.setattr(d1, "_query", lambda sql, params: calls.append((sql, params)) or [])

    d1.db_update_payment_status(3, "PAID")

    assert "updated_at" in calls[0][0]
    assert calls[0][1] == ["PAID", 3]


def test_update_payment_status_rejects_invalid_status(monkeypatch):
    monkeypatch.setattr(d1, "_query", lambda *args: pytest.fail("D1 should not be called"))

    with pytest.raises(ValueError, match="PAID or UNPAID"):
        d1.db_update_payment_status(3, "PENDING")


def test_upsert_submission_inserts_when_absent(monkeypatch):
    calls = []
    monkeypatch.setattr(d1, "_query", lambda sql, params: calls.append((sql, params)) or [])

    assert d1.db_upsert_submission("alice", "12345") == "inserted"
    assert len(calls) == 2
    assert "INSERT INTO submissions" in calls[1][0]


def test_upsert_submission_skips_when_already_present(monkeypatch):
    calls = []
    monkeypatch.setattr(
        d1, "_query", lambda sql, params: calls.append((sql, params)) or [{"id": 1}]
    )

    assert d1.db_upsert_submission("alice", "12345") == "skipped"
    assert len(calls) == 1


def test_iter_submissions_uses_metadata_consumer_numbers(monkeypatch):
    monkeypatch.setattr(backfill_module, "list_consumer_users", lambda: [{"username": "alice"}])
    monkeypatch.setattr(
        backfill_module,
        "get_consumer_details",
        lambda username: [{"consumer_number": "123"}, {"consumer_number": "  "}, {"consumer_number": 456}],
    )

    assert list(backfill_module._iter_submissions()) == [("alice", "123"), ("alice", "456")]


def test_backfill_tracks_inserted_and_skipped_rows(monkeypatch):
    monkeypatch.setattr(backfill_module, "_iter_submissions", lambda: iter([("alice", "1"), ("bob", "2")]))
    monkeypatch.setattr(backfill_module, "db_upsert_submission", lambda user, consumer: "inserted" if user == "alice" else "skipped")

    assert backfill_module.backfill() == (1, 1)


def test_backfill_dry_run_does_not_write_d1(monkeypatch):
    monkeypatch.setattr(backfill_module, "_iter_submissions", lambda: iter([("alice", "1")]))
    monkeypatch.setattr(backfill_module, "db_upsert_submission", lambda *args: pytest.fail("D1 should not be called"))

    assert backfill_module.backfill(dry_run=True) == (1, 0)


def test_backfill_main_reports_success(monkeypatch, capsys):
    monkeypatch.setattr(backfill_module, "backfill", lambda dry_run: (2, 4))

    assert backfill_module.main([]) == 0
    assert "inserted 2; skipped 4" in capsys.readouterr().out


def test_backfill_main_returns_failure_on_error(monkeypatch, capsys):
    def fail(*, dry_run):
        raise RuntimeError("R2 unavailable")

    monkeypatch.setattr(backfill_module, "backfill", fail)

    assert backfill_module.main([]) == 1
    assert "Backfill failed: R2 unavailable" in capsys.readouterr().err
