"""pa_cli.gateway — M6 Public-OA pilot and zero-retention safe gateway.

Per ROADMAP [P3-34]:
  Implements the public-OA pilot with per-run consent, mandatory token/cost hard ceilings
  ($0.01/run), anti-prompt injection validation, and strict zero-retention attestations.

Core Security & Privacy Pillars:
  1. Source Rights Gate: Only CC-BY/CC-0 Open Access articles with verified DOIs
     from allowlisted hosts may proceed. Non-OA, paywalled, private, or restricted
     sources (Sci-Hub, Anna's Archive, CNKI) are strictly blocked.
  2. Anti-Prompt Injection Gate: Rigorous scanning and neutralization of adversarial
     prompt injection attempts, system prompt overrides, and delimiter jailbreaks.
  3. Zero-Retention & PII Scrubbing: Sanitizes all author emails, phone numbers,
     and credentials. Restricts payloads strictly to bounded evidence passages.
  4. Hard Ceilings & Explicit Consent: Enforces hard ceilings of max $0.01 USD spend,
     max 100,000 input tokens, and max 25 papers per run. Requires explicit per-run
     operator consent attestations.
  5. Immutable Audit Trail: Records tamper-evident gateway receipts with SHA-256
     payload signatures and operator timestamps.

Global Rule audit:
  Mandatory operator confirmation, immutable audit log, and strict budget caps.
  100% offline-first execution; zero unexpected outbound connections.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .doi import canonicalize_doi
from .evidence import _hash
from .provenance import inspect_artifact

log = logging.getLogger(__name__)

_GATEWAY_LOCK = threading.Lock()
_ACTIVE_RESERVATIONS: dict[str, dict[str, tuple[int, Decimal]]] = {}

# Hard limits for M6 pilot (Strict ceilings)
MAX_COST_USD_CEILING = Decimal("0.01")
MAX_INPUT_TOKENS_CEILING = 100_000
MAX_PAPERS_CEILING = 25
PRICE_PER_M_INPUT_TOKENS = Decimal("0.042")  # $0.042 per million input tokens

DEFAULT_AUDIT_LOG_PATH = Path.home() / ".paper-agent" / "gateway_audit.jsonl"


@contextmanager
def _gateway_file_lock(lock_path: Path, timeout: float = 10.0):
    """Advisory file lock for multi-process budget coordination across OS boundaries."""
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    fd = None
    start = time.monotonic()
    acquired = False
    while not acquired:
        try:
            if os.name == "nt":
                import msvcrt
                fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (BlockingIOError, PermissionError, OSError) as lock_exc:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass
                fd = None
            if time.monotonic() - start >= timeout:
                raise TimeoutError(f"Could not acquire gateway lock {lock_path}: {lock_exc}")
            time.sleep(0.01)
    if not acquired:
        raise TimeoutError(f"Could not acquire gateway lock {lock_path}")
    try:
        yield
    finally:
        if fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                try:
                    os.close(fd)
                except Exception:
                    pass


def _get_resv_path(audit_path: Path) -> Path:
    return audit_path.parent / f".{audit_path.name}.reservations.json"


def _is_pid_alive(pid: int) -> Optional[bool]:
    """Return True/False only for confirmed liveness/death, None if unknown."""
    if not pid or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_proc:
                # ERROR_INVALID_PARAMETER identifies a nonexistent PID. Access
                # denial and other query errors cannot establish process death.
                return False if ctypes.get_last_error() == 87 else None
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code)):
                    return None
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(h_proc)
        except Exception:
            return None
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except OSError:
            # EPERM, namespace restrictions and transient errors are unknown.
            return None


def _read_reservation_data(resv_path: Path) -> dict[str, Any]:
    """Missing ledger is new; an existing empty/corrupt ledger is not healthy."""
    try:
        raw = resv_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Reservation ledger must be an object")
    for run_resvs in data.values():
        if not isinstance(run_resvs, dict):
            raise ValueError("Invalid reservation group")
        for info in run_resvs.values():
            if not isinstance(info, dict):
                raise ValueError("Invalid reservation record")
            tokens = info.get("tokens")
            cost = Decimal(str(info.get("cost", "NaN")))
            timestamp = float(info.get("timestamp", 0))
            pid = info.get("pid", 0)
            if (not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0
                    or not cost.is_finite() or cost < 0 or not math.isfinite(timestamp)
                    or not isinstance(pid, int) or isinstance(pid, bool) or pid < 0):
                raise ValueError("Invalid reservation amounts or process metadata")
    return data


def _retain_reservation(info: dict[str, Any], now: float) -> bool:
    """Only a confirmed dead owner can expire an older reservation."""
    if now - float(info.get("timestamp", 0)) <= 300:
        return True
    pid = info.get("pid", 0)
    # Legacy records without process identity require explicit recovery.
    return not pid or _is_pid_alive(pid) is not False


def _atomic_write_reservations(resv_path: Path, data: dict[str, Any]) -> None:
    """Publish a complete, synced ledger under the caller's budget lock.

    A failed temporary write or replace leaves the original file untouched.
    No compensating overwrite of the shared ledger is necessary.
    """
    content = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=f".{resv_path.name}.", suffix=".tmp", dir=resv_path.parent)
    temp_path = Path(name)
    try:
        with os.fdopen(fd, "wb") as file:
            fd = -1
            if file.write(content) != len(content):
                raise OSError("Short reservation ledger write")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, resv_path)
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            log.warning("Unable to remove reservation temporary file %s", temp_path)


def _load_all_reservations(audit_path: Path) -> dict[str, dict[str, tuple[int, Decimal]]]:
    """Load combined active reservations from disk and in-memory tracker. Raises on read error."""
    combined: dict[str, dict[str, tuple[int, Decimal]]] = {}

    # 1. Start with in-memory reservations
    for run_k, r_dict in _ACTIVE_RESERVATIONS.items():
        for resv_k, val in r_dict.items():
            combined.setdefault(run_k, {})[resv_k] = val

    # 2. Read persistent reservation file for cross-process coordination
    resv_path = _get_resv_path(audit_path)
    data = _read_reservation_data(resv_path)
    now = time.time()
    for run_k, run_resvs in data.items():
        for resv_k, info in run_resvs.items():
            if _retain_reservation(info, now):
                combined.setdefault(run_k, {})[resv_k] = (info["tokens"], Decimal(str(info["cost"])))

    return combined


def _save_reservation(audit_path: Path, run_id: str, resv_id: str, tokens: int, cost: Decimal) -> None:
    """Save an in-flight reservation in memory and on disk. Raises on read/write failure."""
    resv_path = _get_resv_path(audit_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_reservation_data(resv_path)
    now = time.time()
    cleaned: dict[str, Any] = {}
    for r_id, r_dict in data.items():
        sub = {k: v for k, v in r_dict.items() if _retain_reservation(v, now)}
        if sub:
            cleaned[r_id] = sub
    cleaned.setdefault(run_id, {})[resv_id] = {
        "tokens": tokens,
        "cost": str(cost),
        "timestamp": now,
        "pid": os.getpid(),
    }
    _atomic_write_reservations(resv_path, cleaned)
    _ACTIVE_RESERVATIONS.setdefault(run_id, {})[resv_id] = (tokens, cost)


def _remove_reservation(audit_path: Path, run_id: str, resv_id: str) -> None:
    """Release memory only after durable disk removal; propagate write errors."""
    resv_path = _get_resv_path(audit_path)
    data = _read_reservation_data(resv_path)
    now = time.time()
    cleaned: dict[str, Any] = {}
    for r_id, r_dict in data.items():
        sub = {k: v for k, v in r_dict.items()
               if not (r_id == run_id and k == resv_id) and _retain_reservation(v, now)}
        if sub:
            cleaned[r_id] = sub
    _atomic_write_reservations(resv_path, cleaned)
    if run_id in _ACTIVE_RESERVATIONS:
        _ACTIVE_RESERVATIONS[run_id].pop(resv_id, None)
        if not _ACTIVE_RESERVATIONS[run_id]:
            _ACTIVE_RESERVATIONS.pop(run_id, None)


# ==============================================================================
# Anti-Prompt Injection & Adversarial Sanitization Patterns
# ==============================================================================

# Common prompt injection triggers and delimiter breakouts
INJECTION_PATTERNS = [
    (re.compile(r"\bignore\s+(?:all\s+)?previous\s+instructions\b", re.I), "ignore_previous_instructions"),
    (re.compile(r"\bdisregard\s+(?:all\s+)?prior\s+(?:prompts?|instructions?|rules?)\b", re.I), "disregard_prior_rules"),
    (re.compile(r"\byou\s+are\s+now\s+(?:a|an)?\s*(?:DAN|unrestricted|jailbroken|developer\s+mode)\b", re.I), "persona_jailbreak"),
    (re.compile(r"<\|(?:im_start|im_end|system|user|assistant)\|>", re.I), "chat_template_injection"),
    (re.compile(r"\[/?(?:INST|SYS)\]", re.I), "llama_delimiter_injection"),
    (re.compile(r"\boutput\s+only\s+(?:the\s+following|this\s+phrase|yes|no)\s*:\b", re.I), "output_hijacking"),
    (re.compile(r"\boverride\s+(?:the\s+)?(?:rubric|evaluation|system\s+prompt)\b", re.I), "rubric_override"),
    (re.compile(r"\b(?:bash\s+-c|eval\s*\(|exec\s*\(|subprocess\.Popen)\b", re.I), "code_execution_attempt"),
]

# PII patterns
EMAIL_PAT = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PAT = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
API_KEY_PAT = re.compile(r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,})\b", re.I)


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class PaperEvaluationCandidate:
    """A paper candidate submitted to the safe gateway."""
    paper_id: str
    artifact_path: Optional[str]
    doi: str
    source: str = ""
    url: str = ""
    title: str = ""
    data_class: str = "public"  # 'public', 'private', 'confidential', 'unpublished'


@dataclass
class PaperVerificationResult:
    """Security and rights verification result for a candidate paper."""
    paper_id: str
    doi: str
    is_public_oa: bool
    status: str  # 'VERIFIED_PUBLIC_OA', 'BLOCKED_RESTRICTED_SOURCE', 'BLOCKED_NON_OA', 'BLOCKED_PRIVATE', 'BLOCKED_UNVERIFIED_DOI'
    rights_class: str
    blocking_reasons: list[str] = field(default_factory=list)
    license_urls: list[str] = field(default_factory=list)
    artifact_sha256: str = ""
    raw_bytes: bytes = field(default=b"", repr=False)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("raw_bytes", None)
        return d


@dataclass
class SanitizationResult:
    """Results of prompt-injection and PII scrubbing on an evidence snippet."""
    original_length: int
    sanitized_text: str
    injections_detected: list[str] = field(default_factory=list)
    pii_redacted: list[str] = field(default_factory=list)
    is_safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_length": self.original_length,
            "sanitized_length": len(self.sanitized_text),
            "injections_detected": self.injections_detected,
            "pii_redacted_count": len(self.pii_redacted),
            "is_safe": self.is_safe,
        }


@dataclass
class GatewayReceipt:
    """Cryptographic, tamper-evident receipt of a safe gateway verification run."""
    receipt_id: str
    run_id: str
    timestamp_utc: str
    operator: str
    total_candidates: int
    verified_oa_count: int
    blocked_count: int
    injections_intercepted_count: int
    pii_scrubbed_count: int
    estimated_tokens: int
    estimated_cost_usd: str
    ceiling_compliant: bool
    zero_retention_attested: bool
    payload_sha256: str
    gateway_decision: str  # 'AUTHORIZED', 'REJECTED'
    rejection_reasons: list[str] = field(default_factory=list)
    provenance_verified: bool = False
    request_id: str = ""
    recovery: Optional[dict[str, str]] = None
    legacy_pending: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Security & Privacy Gateway Engine
# ==============================================================================

def verify_paper_rights(candidate: PaperEvaluationCandidate) -> PaperVerificationResult:
    """Evaluate whether candidate paper meets strict Public-OA criteria."""
    # 1. Non-public data classes are immediately blocked
    if candidate.data_class in ("private", "confidential", "unpublished"):
        return PaperVerificationResult(
            paper_id=candidate.paper_id,
            doi=candidate.doi,
            is_public_oa=False,
            status="BLOCKED_PRIVATE",
            rights_class=candidate.data_class,
            blocking_reasons=[f"Data classification '{candidate.data_class}' is prohibited from external transit."],
        )

    # 2. Restricted sources are immediately blocked
    if candidate.source.lower() in ("scihub", "annas", "cnki", "pirate"):
        return PaperVerificationResult(
            paper_id=candidate.paper_id,
            doi=candidate.doi,
            is_public_oa=False,
            status="BLOCKED_RESTRICTED_SOURCE",
            rights_class="restricted_source",
            blocking_reasons=[f"Source '{candidate.source}' is on the restricted gateway blocklist."],
        )

    # 3. Artifact inspection if file path is provided
    if candidate.artifact_path:
        artifact_p = Path(candidate.artifact_path)
        if not artifact_p.is_file():
            return PaperVerificationResult(
                paper_id=candidate.paper_id,
                doi=candidate.doi,
                is_public_oa=False,
                status="BLOCKED_NON_OA",
                rights_class="missing_artifact",
                blocking_reasons=[f"Artifact file not found: {candidate.artifact_path}"],
            )
        try:
            raw_bytes = artifact_p.read_bytes()
            art_sha = hashlib.sha256(raw_bytes).hexdigest()
        except Exception:
            raw_bytes = b""
            art_sha = ""
        p_res = inspect_artifact(
            path=artifact_p,
            requested_doi=candidate.doi,
            source=candidate.source,
            url=candidate.url,
            expected_title=candidate.title or None,
            data_class=candidate.data_class,
            raw_bytes=raw_bytes,
        )
        rights_cls = p_res.get("rights", {}).get("class", "unknown")
        lic_urls = p_res.get("rights", {}).get("license_urls", [])
        is_candidate = p_res.get("external_evaluation_candidate", False)
        blocking = p_res.get("blocking_reasons", [])

        if is_candidate and rights_cls == "public_oa":
            return PaperVerificationResult(
                paper_id=candidate.paper_id,
                doi=candidate.doi,
                is_public_oa=True,
                status="VERIFIED_PUBLIC_OA",
                rights_class="public_oa",
                license_urls=lic_urls,
                artifact_sha256=art_sha,
                raw_bytes=raw_bytes,
            )
        else:
            return PaperVerificationResult(
                paper_id=candidate.paper_id,
                doi=candidate.doi,
                is_public_oa=False,
                status="BLOCKED_NON_OA" if rights_cls != "public_oa" else "BLOCKED_UNVERIFIED_DOI",
                rights_class=rights_cls,
                blocking_reasons=blocking or ["Artifact fails public-OA metadata verification."],
                license_urls=lic_urls,
                artifact_sha256=art_sha,
                raw_bytes=raw_bytes,
            )

    # 4. Strict rejection if artifact_path is omitted / not provided
    # Per F2: No presumed OA or CC-BY grant without physical artifact inspection
    return PaperVerificationResult(
        paper_id=candidate.paper_id,
        doi=candidate.doi,
        is_public_oa=False,
        status="BLOCKED_NON_OA",
        rights_class="unverified_no_artifact",
        blocking_reasons=[
            "Verification strictly requires an inspected artifact file (PDF/XML) with validated open-access license metadata."
        ],
    )


def sanitize_evidence_text(text: str) -> SanitizationResult:
    """Scan and sanitize evidence text for prompt injections, jailbreaks, and PII."""
    orig_len = len(text)
    sanitized = text
    injections_detected: list[str] = []
    pii_redacted: list[str] = []

    # 1. Anti-prompt injection scanning and neutralization
    for pat, rule_name in INJECTION_PATTERNS:
        matches = pat.findall(sanitized)
        if matches:
            injections_detected.append(rule_name)
            # Redact the adversarial instruction to safe quoted string
            sanitized = pat.sub(f"[INJECTION_REDACTED:{rule_name}]", sanitized)

    # 2. PII Scrubbing: Emails
    emails = EMAIL_PAT.findall(sanitized)
    if emails:
        pii_redacted.extend([f"email:{e}" for e in emails])
        sanitized = EMAIL_PAT.sub("[EMAIL_REDACTED]", sanitized)

    # 3. PII Scrubbing: Phone numbers
    phones = PHONE_PAT.findall(sanitized)
    if phones:
        pii_redacted.extend([f"phone:{p.strip()}" for p in phones])
        sanitized = PHONE_PAT.sub("[PHONE_REDACTED]", sanitized)

    # 4. PII Scrubbing: API Keys / Credentials
    keys = API_KEY_PAT.findall(sanitized)
    if keys:
        pii_redacted.extend([f"key:{k[:8]}..." for k in keys])
        sanitized = API_KEY_PAT.sub("[CREDENTIAL_REDACTED]", sanitized)

    is_safe = (len(injections_detected) == 0)

    return SanitizationResult(
        original_length=orig_len,
        sanitized_text=sanitized,
        injections_detected=injections_detected,
        pii_redacted=pii_redacted,
        is_safe=is_safe,
    )


def estimate_tokens_and_cost(text_payload: str) -> tuple[int, Decimal]:
    """Estimate token volume and USD cost under JEV pricing ($0.042 / M tokens)."""
    # Standard rule of thumb: ~4 characters per token for English text
    estimated_tokens = max(1, len(text_payload) // 4)
    cost = (Decimal(estimated_tokens) / Decimal(1_000_000)) * PRICE_PER_M_INPUT_TOKENS
    # Round to 6 decimal places
    return estimated_tokens, cost.quantize(Decimal("0.000001"))


def _prepare_gateway_request(run_id, operator, candidates, passages, consent_public_oa,
                             consent_zero_retention, verify_passage_provenance):
    """Shared frozen-artifact/content checks for both accounting backends."""
    rejection_reasons: list[str] = []

    # 1. Mandatory Operator Consent Checks
    if not consent_public_oa:
        rejection_reasons.append("Missing mandatory operator consent: --consent-public-oa.")
    if not consent_zero_retention:
        rejection_reasons.append("Missing mandatory operator consent: --consent-zero-retention.")

    # 2. Candidate Volume Ceiling Check
    if not candidates:
        rejection_reasons.append("Missing candidate papers: candidates list must not be empty.")
    elif len(candidates) > MAX_PAPERS_CEILING:
        rejection_reasons.append(
            f"Paper count ({len(candidates)}) exceeds hard ceiling of {MAX_PAPERS_CEILING} papers/run."
        )

    # 3. Paper Source & Rights Evaluation
    verified_oa_count = 0
    blocked_count = 0
    cand_rights_hashes: dict[str, str] = {}
    cand_rights_bytes: dict[str, bytes] = {}
    for cand in candidates:
        v_res = verify_paper_rights(cand)
        if v_res.is_public_oa:
            verified_oa_count += 1
            if cand.artifact_path and v_res.artifact_sha256:
                cand_rights_hashes[cand.artifact_path] = v_res.artifact_sha256
                cand_rights_bytes[cand.artifact_path] = v_res.raw_bytes
        else:
            blocked_count += 1
            rejection_reasons.append(f"Paper '{cand.paper_id}' ({cand.doi}): {v_res.status} - {'; '.join(v_res.blocking_reasons)}")

    # 4. Anti-Prompt-Injection & PII Scrubbing on Passages
    sanitized_passages: list[str] = []
    total_injections = 0
    total_pii = 0
    for p in passages:
        s_res = sanitize_evidence_text(p)
        sanitized_passages.append(s_res.sanitized_text)
        total_injections += len(s_res.injections_detected)
        total_pii += len(s_res.pii_redacted)
        if not s_res.is_safe:
            log.warning("Gateway intercepted prompt injection attempt: %s", s_res.injections_detected)
            rejection_reasons.append(
                f"Adversarial prompt injection attempt intercepted in passage payload: {', '.join(s_res.injections_detected)}."
            )

    # 4b. Passage Payload Provenance Verification (S3)
    provenance_verified = False
    if verify_passage_provenance and passages:
        candidate_texts: list[str] = []
        artifact_mutated = False
        if blocked_count > 0:
            all_found = False
        else:
            for cand in candidates:
                if cand.artifact_path and Path(cand.artifact_path).is_file():
                    cpath = Path(cand.artifact_path)
                    try:
                        current_bytes = cpath.read_bytes()
                        current_hash = hashlib.sha256(current_bytes).hexdigest()
                        expected_hash = cand_rights_hashes.get(cand.artifact_path)
                        expected_bytes = cand_rights_bytes.get(cand.artifact_path)
                        if (expected_hash and current_hash != expected_hash) or (expected_bytes is not None and current_bytes != expected_bytes):
                            artifact_mutated = True
                            rejection_reasons.append(
                                f"Artifact security violation: file '{cand.artifact_path}' was mutated after rights verification (hash mismatch)."
                            )
                            continue

                        parse_bytes = expected_bytes if expected_bytes is not None else current_bytes
                        if cpath.suffix.lower() == ".pdf":
                            import pymupdf as fitz
                            with fitz.open(stream=parse_bytes, filetype="pdf") as doc:
                                candidate_texts.append("\n".join(page.get_text("text") for page in doc))
                        else:
                            candidate_texts.append(parse_bytes.decode("utf-8", errors="ignore"))
                    except Exception:
                        pass
        if artifact_mutated:
            all_found = False
        elif blocked_count == 0:
            combined_candidate_text = "\n".join(candidate_texts)
            all_found = True
            for p in passages:
                p_strip = p.strip()
                if p_strip and p_strip not in combined_candidate_text:
                    all_found = False
                    rejection_reasons.append(
                        f"Passage payload provenance violation: text snippet '{p_strip[:50]}...' is not anchored in verified candidate artifact."
                    )
        if all_found and candidate_texts and not artifact_mutated and blocked_count == 0:
            provenance_verified = True
    elif not passages and candidates and blocked_count == 0:
        provenance_verified = True

    # 5. Token & Cost Hard Ceiling Checks (including cumulative tracking per run_id)
    combined_payload = "\n".join(sanitized_passages)
    est_tokens, est_cost = estimate_tokens_and_cost(combined_payload)

    payload_hash = hashlib.sha256(combined_payload.encode("utf-8")).hexdigest()
    receipt = GatewayReceipt(
        receipt_id=f"rcpt_{run_id}_{payload_hash[:10]}", run_id=run_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(), operator=operator,
        total_candidates=len(candidates), verified_oa_count=verified_oa_count,
        blocked_count=blocked_count, injections_intercepted_count=total_injections,
        pii_scrubbed_count=total_pii, estimated_tokens=est_tokens,
        estimated_cost_usd=str(est_cost), ceiling_compliant=True,
        zero_retention_attested=consent_zero_retention, payload_sha256=payload_hash,
        gateway_decision="REJECTED" if rejection_reasons else "AUTHORIZED",
        rejection_reasons=rejection_reasons, provenance_verified=provenance_verified,
    )
    return receipt, sanitized_passages


def gateway_store_path(audit_file: Optional[Path] = None) -> Path:
    """Deterministic sibling journal; the JSONL path remains a legacy locator."""
    audit = Path(audit_file or DEFAULT_AUDIT_LOG_PATH)
    return audit.parent / f".{audit.name}.gateway.sqlite3"


def evaluate_gateway_request(
    run_id: str, operator: str, candidates: list[PaperEvaluationCandidate], passages: list[str],
    consent_public_oa: bool, consent_zero_retention: bool,
    max_cost_usd_limit: Optional[str] = None, audit_file: Optional[Path] = None,
    verify_passage_provenance: bool = False, *, ledger_file: Optional[Path] = None,
    storage_backend: str = "transactional",
) -> tuple[GatewayReceipt, list[str]]:
    """Validate offline and durably authorize with the v4 transactional journal.

    ``audit_file`` locates a legacy epoch and its sibling journal; it is never
    silently imported. ``legacy-json`` is a deprecated compatibility adapter.
    A new request ID is generated per evaluation; Store.finalize is idempotent.
    """
    from .gateway_store import GatewayStore
    from .process_identity import current_owner

    audit = Path(audit_file or DEFAULT_AUDIT_LOG_PATH)
    ledger = Path(ledger_file) if ledger_file is not None else gateway_store_path(audit)
    if storage_backend == "legacy-json" and not ledger.exists() and not gateway_store_path(audit).exists():
        return _evaluate_legacy_gateway_request(run_id, operator, candidates, passages,
            consent_public_oa, consent_zero_retention, max_cost_usd_limit, audit,
            verify_passage_provenance)

    receipt, sanitized = _prepare_gateway_request(run_id, operator, candidates, passages,
        consent_public_oa, consent_zero_retention, verify_passage_provenance)
    receipt.request_id = f"req_{uuid.uuid4().hex}"
    store = None
    try:
        if storage_backend != "transactional":
            raise ValueError("Cannot use legacy/unknown backend in a transactional epoch")
        if not ledger.exists() and (audit.exists() or _get_resv_path(audit).exists()):
            raise ValueError("Legacy gateway data requires explicit migration with all v3 writers stopped")
        configured = Decimal(max_cost_usd_limit) if max_cost_usd_limit is not None else MAX_COST_USD_CEILING
        if not configured.is_finite() or configured < 0:
            raise ValueError("Cost ceiling must be finite and nonnegative")
        cap = min(configured, MAX_COST_USD_CEILING)
        store = GatewayStore(ledger)
        if audit.exists() or _get_resv_path(audit).exists():
            sidecar = _get_resv_path(audit)
            digests = {"audit": hashlib.sha256(audit.read_bytes()).hexdigest() if audit.exists() else None,
                       "reservations": hashlib.sha256(sidecar.read_bytes()).hexdigest() if sidecar.exists() else None}
            if not any(event.get("kind") == "migration" and event.get("source_digests") == digests
                       for event in store.status()["events"]):
                raise ValueError("Legacy gateway data requires a completed explicit migration with unchanged sources")
        if receipt.gateway_decision == "AUTHORIZED":
            accepted = store.reserve(receipt.request_id, run_id, receipt.estimated_tokens,
                Decimal(receipt.estimated_cost_usd), MAX_INPUT_TOKENS_CEILING, cap,
                current_owner(), receipt.to_dict())
            if not accepted:
                receipt.gateway_decision = "REJECTED"
                receipt.ceiling_compliant = False
                receipt.rejection_reasons.append("Cumulative token or cost budget ceiling exceeded")
                store.record_rejection(receipt.to_dict())
            else:
                store.finalize(receipt.request_id, receipt.to_dict())
        else:
            store.record_rejection(receipt.to_dict())
    except Exception as exc:
        # Never release a reservation on ambiguous persistence failure. Recovery
        # uses the immutable request snapshot and preserves accounting exactly once.
        receipt.gateway_decision = "REJECTED"
        receipt.ceiling_compliant = False
        receipt.rejection_reasons.append(f"Gateway journal unavailable or conflicting state: {exc}")
    finally:
        if store is not None:
            store.close()
    return receipt, sanitized


def _evaluate_legacy_gateway_request(
    run_id: str,
    operator: str,
    candidates: list[PaperEvaluationCandidate],
    passages: list[str],
    consent_public_oa: bool,
    consent_zero_retention: bool,
    max_cost_usd_limit: Optional[str] = None,
    audit_file: Optional[Path] = None,
    verify_passage_provenance: bool = False,
) -> tuple[GatewayReceipt, list[str]]:
    """Execute the complete M6 Safe Gateway security & privacy verification pipeline."""
    receipt, sanitized_passages = _prepare_gateway_request(run_id, operator, candidates, passages,
        consent_public_oa, consent_zero_retention, verify_passage_provenance)
    rejection_reasons = receipt.rejection_reasons
    est_tokens = receipt.estimated_tokens
    est_cost = Decimal(receipt.estimated_cost_usd)
    combined_payload = "\n".join(sanitized_passages)
    resv_id = f"resv_{run_id}_{uuid.uuid4().hex}"
    acquired_reservation = False
    configured_max_cost = Decimal(max_cost_usd_limit) if max_cost_usd_limit else MAX_COST_USD_CEILING
    effective_max_cost = min(MAX_COST_USD_CEILING, configured_max_cost)
    target_audit_path = audit_file or DEFAULT_AUDIT_LOG_PATH
    lock_path = target_audit_path.parent / f".{target_audit_path.name}.lock"

    try:
        with _GATEWAY_LOCK, _gateway_file_lock(lock_path):
            prior_tokens = 0
            prior_cost = Decimal("0.0")
            audit_read_error: Optional[str] = None
            if target_audit_path.exists():
                try:
                    for line_num, line in enumerate(target_audit_path.read_text(encoding="utf-8").splitlines(), start=1):
                        line_s = line.strip()
                        if not line_s:
                            continue
                        try:
                            rec = json.loads(line_s)
                            if rec.get("run_id") == run_id and rec.get("gateway_decision") == "AUTHORIZED":
                                prior_tokens += int(rec.get("estimated_tokens", 0))
                                prior_cost += Decimal(str(rec.get("estimated_cost_usd", "0.0")))
                        except Exception as json_err:
                            audit_read_error = f"Corrupted audit record on line {line_num}: {json_err}"
                            break
                except Exception as exc:
                    audit_read_error = f"Audit ledger read failure: {exc}"

            if audit_read_error:
                rejection_reasons.append(
                    f"Security gateway fail-closed: cannot verify historical spend against ceiling: {audit_read_error}"
                )

            # Add active in-flight reservations across all processes
            try:
                active_resvs = _load_all_reservations(target_audit_path)
                for (r_tok, r_cst) in active_resvs.get(run_id, {}).values():
                    prior_tokens += r_tok
                    prior_cost += r_cst
            except Exception as resv_read_err:
                rejection_reasons.append(
                    f"Reservation ledger read failure: cannot verify active budget reservations: {resv_read_err}"
                )

            cum_tokens = prior_tokens + est_tokens
            cum_cost = prior_cost + est_cost

            ceiling_ok = (cum_tokens <= MAX_INPUT_TOKENS_CEILING) and (cum_cost <= effective_max_cost)

            if cum_tokens > MAX_INPUT_TOKENS_CEILING:
                rejection_reasons.append(
                    f"Estimated input tokens ({cum_tokens} cumulative for run '{run_id}') exceed hard ceiling of {MAX_INPUT_TOKENS_CEILING} tokens."
                )

            if cum_cost > effective_max_cost:
                rejection_reasons.append(
                    f"Estimated cost (${cum_cost} cumulative for run '{run_id}') exceeds budget ceiling (${effective_max_cost})."
                )

            # 6. Payload Fingerprint
            payload_hash = hashlib.sha256(combined_payload.encode("utf-8")).hexdigest()

            # 7. Final Decision & Receipt Generation
            passed = len(rejection_reasons) == 0
            receipt_id = f"rcpt_{run_id}_{payload_hash[:10]}"
            timestamp = datetime.now(timezone.utc).isoformat()

            if passed:
                try:
                    _save_reservation(target_audit_path, run_id, resv_id, est_tokens, est_cost)
                    acquired_reservation = True
                except Exception as resv_write_err:
                    passed = False
                    if run_id in _ACTIVE_RESERVATIONS:
                        _ACTIVE_RESERVATIONS[run_id].pop(resv_id, None)
                        if not _ACTIVE_RESERVATIONS[run_id]:
                            _ACTIVE_RESERVATIONS.pop(run_id, None)
                    rejection_reasons.append(
                        f"Reservation ledger write failure: cannot persist in-flight budget reservation: {resv_write_err}"
                    )
    except Exception as lock_err:
        passed = False
        ceiling_ok = False
        rejection_reasons.append(
            f"Gateway concurrency lock failure: unable to acquire exclusive budget lock: {lock_err}"
        )
        payload_hash = hashlib.sha256(combined_payload.encode("utf-8")).hexdigest()
        receipt_id = f"rcpt_{run_id}_{payload_hash[:10]}"
        timestamp = datetime.now(timezone.utc).isoformat()

    receipt.receipt_id = receipt_id
    receipt.timestamp_utc = timestamp
    receipt.ceiling_compliant = ceiling_ok
    receipt.gateway_decision = "AUTHORIZED" if passed else "REJECTED"

    try:
        # Append to local audit log (fail-closed if writing fails)
        write_ok = record_gateway_audit_event(receipt, audit_file=target_audit_path)
        if write_ok is False:
            receipt.gateway_decision = "REJECTED"
            if not any("Audit log write failure" in r for r in receipt.rejection_reasons):
                receipt.rejection_reasons.append("Audit log write failure: security gateway requires durable audit trail.")
    finally:
        if acquired_reservation:
            try:
                with _GATEWAY_LOCK, _gateway_file_lock(lock_path):
                    _remove_reservation(target_audit_path, run_id, resv_id)
            except Exception as cleanup_err:
                log.warning("Reservation cleanup failed; retaining budget reservation: %s", cleanup_err)

    return receipt, sanitized_passages


def record_gateway_audit_event(receipt: GatewayReceipt, audit_file: Optional[Path] = None) -> bool:
    """Append immutable gateway verification receipt to local audit log."""
    path = audit_file or DEFAULT_AUDIT_LOG_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt.to_dict(), ensure_ascii=False) + "\n")
        return True
    except Exception as exc:
        log.error("Failed to write gateway audit log: %s", exc)
        return False


def read_gateway_audit_events(audit_file: Optional[Path] = None, *, ledger_file: Optional[Path] = None,
                              storage_backend: str = "transactional") -> list[GatewayReceipt]:
    """Read all recorded gateway verification receipts."""
    if storage_backend == "transactional":
        from .gateway_store import GatewayStore
        from dataclasses import fields
        keys = {item.name for item in fields(GatewayReceipt)}
        # Legacy pending rows lacked content/rights metadata. Keep that unknown
        # rather than manufacturing attestation during operator reconciliation.
        defaults = dict(timestamp_utc="legacy", operator="legacy", total_candidates=0,
                        verified_oa_count=0, blocked_count=0, injections_intercepted_count=0,
                        pii_scrubbed_count=0, ceiling_compliant=False,
                        zero_retention_attested=False, payload_sha256="")
        with GatewayStore(ledger_file or gateway_store_path(audit_file), read_only=True, create=False) as store:
            return [GatewayReceipt(**{key: value for key, value in (defaults | rec).items() if key in keys})
                    for rec in store.receipts()]
    if storage_backend != "legacy-json":
        raise ValueError("Unknown gateway backend")
    path = audit_file or DEFAULT_AUDIT_LOG_PATH
    if not path.is_file():
        return []
    receipts: list[GatewayReceipt] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    receipts.append(GatewayReceipt(**data))
                except Exception:
                    continue
    return receipts


# ==============================================================================
# Formatters
# ==============================================================================

def format_receipt_table(receipt: GatewayReceipt) -> str:
    """Format gateway receipt as high-density ASCII table."""
    lines: list[str] = [
        "=" * 86,
        " M6 PUBLIC-OA & ZERO-RETENTION SAFE GATEWAY RECEIPT [P3-34]",
        "=" * 86,
        f" Receipt ID:             {receipt.receipt_id}",
        f" Run ID:                 {receipt.run_id}",
        f" Timestamp (UTC):        {receipt.timestamp_utc}",
        f" Accountable Operator:   {receipt.operator}",
        "-" * 86,
        f" Gateway Decision:       {receipt.gateway_decision}",
        f" Zero-Retention Signed:  {receipt.zero_retention_attested}",
        f" Verified Public-OA:     {receipt.verified_oa_count} / {receipt.total_candidates} candidates",
        f" Blocked Non-OA/Private: {receipt.blocked_count} candidates",
        f" Injections Neutralized: {receipt.injections_intercepted_count}",
        f" PII Fields Scrubbed:    {receipt.pii_scrubbed_count}",
        "-" * 86,
        f" Estimated Input Tokens: {receipt.estimated_tokens:,} (Ceiling: {MAX_INPUT_TOKENS_CEILING:,})",
        f" Estimated Cost:         ${receipt.estimated_cost_usd} USD (Ceiling: ${MAX_COST_USD_CEILING})",
        f" Ceiling Compliant:      {receipt.ceiling_compliant}",
        f" Payload SHA-256:        {receipt.payload_sha256}",
    ]
    if receipt.rejection_reasons:
        lines.append("-" * 86)
        lines.append(" GATEWAY BLOCKING REASONS:")
        for idx, r in enumerate(receipt.rejection_reasons, 1):
            lines.append(f"  {idx}. {r}")
    lines.append("=" * 86)
    return "\n".join(lines)


def format_receipt_markdown(receipt: GatewayReceipt) -> str:
    """Format gateway receipt as clean Markdown report."""
    status_emoji = "[AUTHORIZED]" if receipt.gateway_decision == "AUTHORIZED" else "[REJECTED]"
    lines: list[str] = [
        f"# M6 Public-OA Safe Gateway Attestation Receipt\n",
        f"**Decision**: `{status_emoji}`\n",
        f"- **Receipt ID**: `{receipt.receipt_id}`",
        f"- **Run ID**: `{receipt.run_id}`",
        f"- **Timestamp (UTC)**: `{receipt.timestamp_utc}`",
        f"- **Accountable Operator**: `{receipt.operator}`",
        f"- **Payload SHA-256**: `{receipt.payload_sha256}`\n",
        "## Security, Rights & Privacy Verification\n",
        f"- **Public-OA Verified**: `{receipt.verified_oa_count}` / `{receipt.total_candidates}` candidates",
        f"- **Blocked Non-OA / Confidential**: `{receipt.blocked_count}` candidates",
        f"- **Prompt Injections Intercepted**: `{receipt.injections_intercepted_count}`",
        f"- **PII Fields Scrubbed**: `{receipt.pii_scrubbed_count}`",
        f"- **Zero-Retention Attestation**: `{receipt.zero_retention_attested}`\n",
        "## Hard Ceiling Compliance\n",
        f"- **Estimated Tokens**: `{receipt.estimated_tokens:,}` (Ceiling: `{MAX_INPUT_TOKENS_CEILING:,}`)",
        f"- **Estimated Cost**: `${receipt.estimated_cost_usd}` USD (Hard Ceiling: `${MAX_COST_USD_CEILING}`)",
        f"- **Ceiling Compliant**: `{receipt.ceiling_compliant}`\n",
    ]
    if receipt.rejection_reasons:
        lines.append("## Blocking Reasons\n")
        for r in receipt.rejection_reasons:
            lines.append(f"- {r}")
        lines.append("")
    lines.append("---\n*Paper Agent M6 Safe Gateway — 100% Offline Pre-Flight Verification.*")
    return "\n".join(lines)
