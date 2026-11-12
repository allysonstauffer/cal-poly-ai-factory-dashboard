"""Tests for summarize_workloads, using the fake fixture only."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

import summarize_workloads as sw

FIXTURE = Path(__file__).parent / "fixtures" / "workloads_fake.json"
WORKLOADS = json.loads(FIXTURE.read_text())["workloads"]

# Every identifying field in the fixture whose values must never be printed.
IDENTIFYING_FIELDS = (
    "id", "name", "submittedBy", "projectName", "projectId",
    "departmentName", "departmentId", "namespace", "clusterId",
)


def run(capsys, argv, samples_dir=None):
    kwargs = {"samples_dir": samples_dir} if samples_dir else {}
    code = sw.main(argv, **kwargs)
    out, err = capsys.readouterr()
    return code, out, err


def test_counts_match_fixture(capsys):
    code, out, _ = run(capsys, [str(FIXTURE)])
    assert code == 0
    assert "Total workloads: 7" in out
    # Phase: 3 Running, 2 Pending, 1 Completed, 1 Failed
    assert "  Running: 3" in out
    assert "  Pending: 2" in out
    assert "  Completed: 1" in out
    assert "  Failed: 1" in out
    # Type: 3 training, 2 workspace, 2 inference
    assert "  training: 3" in out
    assert "  workspace: 2" in out
    assert "  inference: 2" in out
    assert "Unique submitters: 7" in out


def test_gpu_fields(capsys):
    _, out, _ = run(capsys, [str(FIXTURE)])
    # Fixture has allocatedResources.gpu (Running: 4 + 1 + 1 = 6) but no requested-GPU field.
    assert "Allocated GPUs (total): 6 (field found on 7/7 workloads)" in out
    assert "Requested GPUs: field not found" in out


def test_no_identifying_values_in_output(capsys):
    _, out, err = run(capsys, [str(FIXTURE)])
    combined = (out + err).lower()
    leaked = {
        f"{field}={w[field]}"
        for w in WORKLOADS
        for field in IDENTIFYING_FIELDS
        if w.get(field) and str(w[field]).lower() in combined
    }
    assert not leaked, f"identifying values printed: {leaked}"
    # Belt and braces: no fixture name prefixes or email-ish strings at all.
    assert "fake-" not in combined
    assert "@" not in combined


def test_missing_fields_do_not_crash(tmp_path, capsys):
    sparse = [{}, {"phase": None}, {"type": ""}, {"allocatedResources": "oops"}, {"allocatedResources": {"gpu": "2"}}]
    path = tmp_path / "sparse.json"
    path.write_text(json.dumps(sparse))

    code, out, _ = run(capsys, [str(path)])
    assert code == 0
    assert "Total workloads: 5" in out
    # No record has a usable phase or type (absent, None, or empty string).
    assert out.count(f"  {sw.MISSING}: 5") == 2
    assert "Unique submitters: field not found" in out
    assert "Allocated GPUs (total): 2 (field found on 1/5 workloads)" in out
    assert "Requested GPUs: field not found" in out


def test_empty_and_bare_list_inputs(tmp_path, capsys):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"workloads": []}))
    code, out, _ = run(capsys, [str(path)])
    assert code == 0
    assert "Total workloads: 0" in out

    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps(WORKLOADS[:2]))
    code, out, _ = run(capsys, [str(bare)])
    assert code == 0
    assert "Total workloads: 2" in out


@pytest.mark.parametrize("content", ["not json", json.dumps({"foo": 1}), json.dumps("string")])
def test_bad_file_reports_error(tmp_path, capsys, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    code, out, err = run(capsys, [str(path)])
    assert code == 1
    assert "Could not read bad.json" in err


def test_defaults_to_newest_sample(tmp_path, capsys):
    older = tmp_path / "workloads_old.json"
    older.write_text(json.dumps({"workloads": WORKLOADS[:1]}))
    newer = tmp_path / "workloads_new.json"
    shutil.copy(FIXTURE, newer)
    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))

    code, out, _ = run(capsys, [], samples_dir=tmp_path)
    assert code == 0
    assert "Source: workloads_new.json" in out
    assert "Total workloads: 7" in out


def test_no_samples_found(tmp_path, capsys):
    code, _, err = run(capsys, [], samples_dir=tmp_path / "does-not-exist")
    assert code == 1
    assert "No JSON files found" in err


def test_field_mapping_tries_candidates_in_order(monkeypatch):
    monkeypatch.setitem(sw.FIELDS, "allocated_gpus", ("nope.gpu", "allocatedResources.gpu"))
    assert sw.lookup({"allocatedResources": {"gpu": 3}}, "allocated_gpus") == 3
    assert sw.lookup({}, "allocated_gpus") is sw._ABSENT
