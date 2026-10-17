"""Guard for audit item A7: non-causal patient loci stay out of tracked files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import redact  # noqa: E402


def test_scrub_generic_rules():
    # literals are assembled at runtime so this file is itself clean
    a, b, hla = 32_584_639, 30_000_000, "HL" + "A-DQB1"
    s = redact.scrub(f"chr6:{a} C>A 6:{b} {hla}_AD")
    assert str(a) not in s and str(b) not in s
    assert "HL" + "A-" not in s


def test_scrub_leaves_mask_window_and_causal_loci():
    keep = "mask 6:28500000-33500000 ; chr15:40209701 T>G + chr15:40220612 T>G"
    assert redact.scrub(keep) == keep


def test_scrub_idempotent():
    once = redact.scrub(f"chr6:{32_588_969} T>G " + "HL" + "A-DRB1")
    assert redact.scrub(once) == once


def test_private_site_scrubbed_when_configured(tmp_path, monkeypatch):
    p = tmp_path / "w.json"
    p.write_text('{"sites": {"15:12345678": {"ref": "A", "alt": "G"}}}')
    monkeypatch.setattr(redact, "PRIVATE", p)
    s = redact.scrub("site 15:12345678 A>G and bare 12345678")
    assert "12345678" not in s


def test_hash_guard_detects_withheld_token(monkeypatch):
    import hashlib
    tok = "12345678"
    monkeypatch.setattr(redact, "WITHHELD_HASHES",
                        frozenset({hashlib.sha256(tok.encode()).hexdigest()}))
    assert redact.leaks_by_hash("x " + tok + " y")
    assert not redact.leaks_by_hash("x 40209701 y")


def test_hash_set_is_wellformed():
    assert redact.WITHHELD_HASHES
    assert all(len(h) == 64 for h in redact.WITHHELD_HASHES)


def test_no_tracked_file_leaks():
    bad = [str(p.relative_to(redact.ROOT)) for p in redact.offenders()]
    assert not bad, f"withheld loci present in tracked files: {bad}"
