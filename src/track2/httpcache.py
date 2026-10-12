"""Cached HTTP layer for the Track 2 engine.

Modes:
    live    - fetch over the network, never touch the cache dir
    record  - fetch over the network AND write every response verbatim to
              the cache dir (raw JSON text, keyed by request hash)
    replay  - never touch the network; return the recorded response for an
              identical request, raise CacheMiss on absence

A cache entry is ``<sha256>.json`` containing::

    {"request": {"method", "url", "body"}, "status": int,
     "fetched_at": iso8601, "body": <raw response text>}

Body is stored as raw text (not re-serialised) so replay returns exactly the
bytes the live API produced.

``--trim-cache`` support: :func:`trim_cache` rewrites recorded bodies in
place keeping only the fields the engine consumes (fixture-size control).
The request hash is untouched, so trimming cannot desynchronise replay.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class CacheMiss(RuntimeError):
    """Replay mode was asked for a request that was never recorded."""


class UpstreamError(RuntimeError):
    """The remote API failed in live/record mode after all retries."""


class CachedHttp:
    """urllib-based JSON client with verbatim record/replay."""

    USER_AGENT = "mva-track2-engine/0.1 (MVA Hackathon 2026; track2 lane L2)"
    TIMEOUT = 60
    RETRIES = 3

    def __init__(self, cache_dir: str | Path | None = None,
                 mode: str = "live"):
        if mode not in ("live", "record", "replay"):
            raise ValueError(f"unknown mode {mode!r}")
        self.mode = mode
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if mode in ("record", "replay"):
            if self.cache_dir is None:
                raise ValueError(f"mode {mode} needs a cache_dir")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.requests = 0          # live fetches performed
        self.hits = 0              # replay hits

    # -- low level ---------------------------------------------------------
    @staticmethod
    def _key(method: str, url: str, body: str | None) -> str:
        h = hashlib.sha256()
        h.update(method.upper().encode())
        h.update(b"\x00")
        h.update(url.encode())
        h.update(b"\x00")
        h.update((body or "").encode())
        return h.hexdigest()

    def _fetch(self, method: str, url: str,
               data: bytes | None, content_type: str) -> tuple[int, str]:
        """One urlopen with bounded retries on 429/5xx. Returns (status, text)."""
        last = None
        for attempt in range(self.RETRIES):
            try:
                req = urllib.request.Request(
                    url, data=data, method=method,
                    headers={"User-Agent": self.USER_AGENT,
                             "Content-Type": content_type,
                             "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as r:
                    self.requests += 1
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                # 4xx (except 429) is a deterministic answer - record it as a
                # real response so replay reproduces the same behaviour
                if e.code == 429 or e.code >= 500:
                    last = UpstreamError(f"HTTP {e.code} for {url}")
                    time.sleep(1.5 * (attempt + 1))
                    continue
                self.requests += 1
                return e.code, e.read().decode("utf-8", "replace")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = UpstreamError(f"{type(e).__name__}: {e} for {url}")
                time.sleep(1.5 * (attempt + 1))
        raise last

    def _roundtrip(self, method: str, url: str, body: str | None,
                   data: bytes | None, content_type: str) -> tuple[int, str]:
        key = self._key(method, url, body)
        cache_file = self.cache_dir / f"{key}.json" if self.cache_dir else None

        if self.mode == "replay":
            if cache_file is None or not cache_file.exists():
                raise CacheMiss(f"no recorded response for {method} {url}")
            self.hits += 1
            entry = json.loads(cache_file.read_text(encoding="utf-8"))
            return entry["status"], entry["body"]

        # record: reuse an existing entry so re-runs/resumes are cheap and
        # identical requests across cases are fetched once
        if self.mode == "record" and cache_file is not None \
                and cache_file.exists():
            self.hits += 1
            entry = json.loads(cache_file.read_text(encoding="utf-8"))
            return entry["status"], entry["body"]

        status, text = self._fetch(method, url, data, content_type)
        if self.mode == "record":
            entry = {
                "request": {"method": method, "url": url, "body": body},
                "status": status,
                "fetched_at": datetime.now(timezone.utc)
                            .replace(microsecond=0).isoformat(),
                "body": text,
            }
            cache_file.write_text(json.dumps(entry, ensure_ascii=False),
                                  encoding="utf-8")
        return status, text

    # -- JSON helpers ------------------------------------------------------
    def get_json(self, url: str) -> tuple[int, object]:
        status, text = self._roundtrip("GET", url, None, None,
                                       "application/json")
        return status, _loads(text)

    def post_json(self, url: str, payload: dict) -> tuple[int, object]:
        body = json.dumps(payload)
        status, text = self._roundtrip("POST", url, body,
                                       body.encode(), "application/json")
        return status, _loads(text)

    def post_form(self, url: str, form: dict) -> tuple[int, object]:
        import urllib.parse
        body = urllib.parse.urlencode(form)
        status, text = self._roundtrip("POST", url, body, body.encode(),
                                       "application/x-www-form-urlencoded")
        return status, _loads(text)


def _loads(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text}


# ------------------------------------------------------------------ trim --
def trim_cache(cache_dir: str | Path) -> dict:
    """Rewrite recorded bodies in ``cache_dir`` keeping only used fields.

    Returns a size report.  Never touches the request hash - the file name
    and request block are byte-identical afterwards.
    """
    cache_dir = Path(cache_dir)
    before = after = 0
    for f in sorted(cache_dir.glob("*.json")):
        before += f.stat().st_size
        entry = json.loads(f.read_text(encoding="utf-8"))
        url = entry["request"]["url"]
        body = entry["body"]
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            after += f.stat().st_size
            continue
        trimmed = _trim_url(url, parsed)
        if trimmed is not None:
            entry["body"] = json.dumps(trimmed, ensure_ascii=False)
            f.write_text(json.dumps(entry, ensure_ascii=False),
                         encoding="utf-8")
        after += f.stat().st_size
    return {"files": len(list(cache_dir.glob("*.json"))),
            "bytes_before": before, "bytes_after": after}


def _trim_url(url: str, parsed):
    """Source-specific field projections.  Returns the trimmed object, or
    None to leave the entry untouched."""
    if "/chembl/api/data/molecule" in url:
        keep = {"molecule_chembl_id", "pref_name", "max_phase",
                "first_approval", "withdrawn_flag", "black_box_warning",
                "cross_references"}
        if isinstance(parsed, dict) and isinstance(parsed.get("molecules"), list):
            out = dict(parsed)
            out["molecules"] = [
                {k: v for k, v in m.items() if k in keep} for m in parsed["molecules"]]
            return out
        if isinstance(parsed, dict):
            return {k: v for k, v in parsed.items() if k in keep}
    if "/chembl/api/data/mechanism" in url:
        keep = {"mec_id", "action_type", "mechanism_of_action",
                "target_chembl_id", "molecule_chembl_id", "max_phase",
                "direct_interaction"}
        return {"mechanisms": [
            {k: v for k, v in m.items() if k in keep}
            for m in parsed.get("mechanisms", [])]}
    if "platform.opentargets.org" in url:
        # GraphQL responses are already field-selected; nothing big to drop.
        return parsed
    if "dgidb.org" in url:
        keep_i = {"drug", "interactionTypes", "sources", "publications"}
        nodes = (parsed.get("data", {}).get("genes", {}) or {}).get("nodes", [])
        for g in nodes:
            g["interactions"] = [
                {k: v for k, v in i.items() if k in keep_i}
                for i in g.get("interactions", [])]
            for i in g["interactions"]:
                if isinstance(i.get("drug"), dict):
                    i["drug"] = {k: v for k, v in i["drug"].items()
                                 if k in ("name", "approved", "conceptId")}
                if isinstance(i.get("sources"), list):
                    i["sources"] = [
                        {k: v for k, v in s.items() if k == "sourceDbName"}
                        for s in i["sources"]]
                if isinstance(i.get("interactionTypes"), list):
                    i["interactionTypes"] = [
                        {k: v for k, v in t.items() if k == "type"}
                        for t in i["interactionTypes"]]
        return parsed
    if "api.fda.gov" in url:
        res = parsed.get("results")
        if not isinstance(res, list):
            return parsed
        keep = {"id", "set_id", "openfda", "pediatric_use", "boxed_warning",
                "indications_and_usage", "dosage_and_administration",
                "effective_time"}
        # L11: the pediatric flag also reads indications/dosage - keep them
        # verbatim like every other evidence field; only pediatric_use is
        # clipped (800, the bound the emitted pediatric_labeling field has
        # always had).
        clip_len = {"pediatric_use": 800}

        def _clip(v, n):
            if isinstance(v, str):
                return v[:n]
            if isinstance(v, list):
                return [x[:n] if isinstance(x, str) else x for x in v]
            return v

        keep_of = {"generic_name", "brand_name", "substance_name",
                   "manufacturer_name", "product_type", "route"}

        def _proj(r):
            o = {k: (_clip(v, clip_len[k]) if k in clip_len else v)
                 for k, v in r.items() if k in keep}
            if isinstance(o.get("openfda"), dict):
                o["openfda"] = {k: v for k, v in o["openfda"].items()
                                if k in keep_of}
            return o

        out = dict(parsed)
        out["results"] = [_proj(r) for r in res]
        return out
    if "mychem.info" in url:
        hits = parsed.get("hits")
        if isinstance(hits, list):
            out = dict(parsed)
            out["hits"] = [_trim_mychem(h) for h in hits]
            return out
        return parsed
    if "string-db.org" in url:
        if isinstance(parsed, list):
            if "/json/network" in url:
                keep = {"preferredName_A", "preferredName_B", "score"}
            elif "/json/interaction_partners" in url:
                keep = {"preferredName_B", "score"}
            elif "get_string_ids" in url:
                keep = {"queryItem", "preferredName", "stringId"}
            elif "/json/version" in url:
                keep = {"string_version"}
            else:
                keep = {"preferredName_A", "preferredName_B",
                    "preferredName", "stringId", "score", "string_version"}
            return [{k: v for k, v in r.items() if k in keep}
                    for r in parsed]
        return parsed
    if "maayanlab.cloud" in url:
        if isinstance(parsed, list):
            trimmed = []
            for s in parsed:
                m = s.get("meta") or {}
                trimmed.append({"id": s.get("id"), "meta": {
                    k: m.get(k) for k in
                    ("symbol", "pert_name", "pert_type", "pert_dose",
                     "cell_line", "local_id")}})
            return trimmed
        if isinstance(parsed, dict) and "results" in parsed:
            rows = parsed["results"]
            keep = {"uuid", "type", "logp-fisher", "logp-avg", "p-up",
                    "p-down", "fdr-up", "fdr-down", "direction-up",
                    "zscore-up", "zscore-down"}
            out = dict(parsed)
            out["results"] = [
                {k: v for k, v in r.items() if k in keep} for r in rows]
            return out
        return parsed
    return None


def _trim_mychem(h):
    """Keep only the fields consumed from a MyChem hit."""
    out = {k: h.get(k) for k in ("inn", "unii") if k in h}
    dc = h.get("drugcentral")
    if isinstance(dc, dict):
        out["drugcentral"] = {k: dc.get(k) for k in ("id", "approval")
                              if k in dc}
    elif isinstance(dc, list):
        out["drugcentral"] = [
            {k: x.get(k) for k in ("id", "approval") if k in x}
            for x in dc if isinstance(x, dict)]
    ch = h.get("chembl")
    if isinstance(ch, dict):
        out["chembl"] = {k: ch.get(k) for k in ("molecule_chembl_id",)
                         if k in ch}
    return out
