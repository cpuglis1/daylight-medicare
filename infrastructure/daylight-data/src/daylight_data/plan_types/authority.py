"""Exact-purpose external receipt replay. This module never enables consumer routes."""
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

from . import SCOPE, PlanTypeError
from .common import digest, file_sha, read_json

CAPABILITIES = {"pdp_reference","medigap_benefits","medigap_discovery","medigap_rate_observation"}
GATES = {"source_use","method","output"}


def instant(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (TypeError,ValueError) as error:
        raise PlanTypeError("TIMEZONE_REQUIRED") from error


def validate_review(receipt, manifest, trusted, *, now=None):
    """Trust assignments are operator-controlled, never supplied by an HTTP request."""
    now = now or datetime.now(timezone.utc)
    actor = receipt.get("reviewer",{}).get("actor")
    gate, capability = receipt.get("gate"), receipt.get("capability")
    assignment = trusted.get(actor,{})
    if (receipt.get("schema")!='daylight-plan-type-review/1' or gate not in GATES
            or capability not in CAPABILITIES or gate not in assignment.get("gates",[])
            or capability not in assignment.get("capabilities",[])
            or receipt.get("scope")!=SCOPE or receipt.get("build_id")!=manifest["build_id"]
            or receipt.get("code_sha256")!=digest(manifest["code"])
            or receipt.get("source_bindings_sha256")!=digest(manifest["sources"])
            or receipt.get("decision") not in {'accepted','held','revoked'}
            or receipt.get("consumer_release_enabled") is not False
            or receipt.get("reviewer",{}).get("qualified_for_scope") is not True
            or receipt.get("reviewer",{}).get("independent_of_sales") is not True
            or not isinstance(receipt.get("dispositions"),list) or not receipt["dispositions"]):
        raise PlanTypeError("EXACT_TRUSTED_REVIEW_REQUIRED")
    reviewed, expires = instant(receipt.get("reviewed_at_utc")), instant(receipt.get("expires_at_utc"))
    deadline = manifest["review_due"]["L04" if capability=='pdp_reference' else "L10"]
    if not reviewed<=now<expires<=instant(deadline):
        raise PlanTypeError("REVIEW_EXPIRED_OR_NOT_CURRENT")
    return receipt


def record_review(connection, receipt_path, original_path, trust_path, *, now=None):
    """Privileged offline operator command; validates the original receipt bytes."""
    receipt = read_json(receipt_path)
    original = read_json(original_path)
    # Both independently stored copies must reproduce the exact human decision.
    if original != receipt or receipt.get("original_receipt_sha256") is not None:
        raise PlanTypeError("ORIGINAL_AUTHORITY_REPLAY_MISMATCH")
    row = connection.execute("SELECT manifest FROM dl_plan_types.build b JOIN dl_plan_types.completion c USING(build_id) WHERE b.build_id=%s",(receipt.get("build_id"),)).fetchone()
    if not row:
        raise PlanTypeError("COMPLETED_EXACT_BUILD_REQUIRED")
    validate_review(receipt,row["manifest"],read_json(trust_path),now=now)
    with connection.transaction():
        connection.execute("SET LOCAL ROLE daylight_plan_reviewer")
        connection.execute("""INSERT INTO dl_plan_types.review_event
          (build_id,capability,gate,decision,receipt_sha256,original_authority,expires_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s)""",
          (receipt["build_id"],receipt["capability"],receipt["gate"],receipt["decision"],file_sha(original_path),
           Jsonb({"receipt":receipt,"original_sha256":file_sha(original_path),
                  "trust_registry_sha256":file_sha(trust_path),"original_replayed":True}),
           receipt["expires_at_utc"]))


def authority_holds(manifest, capability, events, *, stopped=False, now=None):
    now = now or datetime.now(timezone.utc)
    if capability not in CAPABILITIES:
        raise PlanTypeError("UNSUPPORTED_CAPABILITY")
    holds = ["CONSUMER_DISPLAY_DISABLED_PENDING_DATA_APPROVAL"]
    if stopped:
        holds.append("SOURCE_STOP")
    deadline = manifest["review_due"]["L04" if capability=='pdp_reference' else "L10"]
    if now>=instant(deadline):
        holds.append("SOURCE_REVIEW_DUE")
    for gate in sorted(GATES):
        relevant=[e for e in events if e.get("capability")==capability and e.get("gate")==gate]
        latest=max(relevant,key=lambda e:e["event_id"]) if relevant else None
        proof=(latest or {}).get("original_authority",{})
        receipt=proof.get("receipt",{})
        if (not latest or latest.get("decision")!='accepted' or latest.get("build_id")!=manifest["build_id"]
                or proof.get("original_replayed") is not True
                or receipt.get("build_id")!=manifest["build_id"]
                or receipt.get('scope')!=SCOPE or receipt.get('decision')!='accepted'
                or receipt.get('capability')!=capability or receipt.get('gate')!=gate
                or receipt.get('consumer_release_enabled') is not False
                or receipt.get("source_bindings_sha256")!=digest(manifest["sources"])
                or receipt.get("code_sha256")!=digest(manifest["code"])
                or now>=instant(str(latest.get("expires_at")))):
            holds.append(gate.upper()+"_APPROVAL_REQUIRED")
    return holds
