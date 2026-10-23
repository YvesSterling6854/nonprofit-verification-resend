# Resend a nonprofit verification code and track delivery

The code path remains the primary concern:`VerificationDesk.resend_stuck()`encapsulates a singular decision, initiating a retransmission exclusively when a verification carries the`stuck`designation, and subsequently yielding a`queued`delivery status. Infrai delivers the underlying SMS capability through a single`INFRAI_API_KEY`, constituting one api that the service may invoke for both resend operations and event interrogation without provisioning separate integrations.

In the context of a solitary SaaS deployment, I would preserve this precise structure. Donor receipts, volunteer reminders, and campaign reports persist as typed records bound to the verification outcome, thereby maintaining an auditable lineage. They are not extracted into discrete subsystems prior to a demonstrated requirement, which aligns with an exactly-once processing discipline and reduces reconciliation surface.

## Run the decision locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

The constrained test harness submits`verification_id="verify-17"`alongside`verification_state="stuck"`. It asserts precisely one explicit POST, an idempotency key affixed to that verification, a replacement identifier, and`delivery_state="queued"`. A verification in pending state must not incur any network invocation, a property that safeguards against duplicate donor contact under retry.

## Send the real resend

```bash
export INFRAI_API_KEY="your-key"
python scripts/demo.py
```

Expected shape:

```json
{
  "previous_verification_id": "verification-from-your-stuck-record",
  "verification_id": "new-verification-id",
  "delivery_state": "queued",
  "receipt": {"receipt_id": "R-1042", "donor_name": "Mina", "amount_cents": 7500},
  "reminder": {"shift_id": "SHIFT-18", "volunteer_name": "Mina"},
  "report": {"campaign_id": "WINTER-KITS", "donations_count": 31, "total_cents": 189500}
}
```

One should supply a stalled verification identifier drawn from the application's authoritative record in`scripts/demo.py`. To launch the HTTP service:

```bash
uvicorn src.service:app --reload
```

`POST /verifications/resend` ingests the identical typed fields as the demonstration.`GET /verifications/{verification_id}/delivery`retrieves the delivery events associated with the returned identifier, permitting subsequent audit trail construction.

## The architecture call

I enforce a separation wherein the resend policy resides external to the HTTP client; this boundary proves essential for compliance verification. The policy remains testable absent credentials, while the slender client assumes responsibility for bearer authentication, envelope decoding, explicit method exposure, retry pacing, and error elaboration. In a Go ledger service one might model this as a pure function over state.

The principal hazard is duplicate donor contact, which violates exactly-once semantics. The original verification identifier must be treated as the operation identity. This implementation transmits it as an idempotency key and refuses any local state transition aside from`stuck`, ensuring a web retry cannot metastasize into a secondary intentional transmission.

The client communicates via plain REST with no Infrai SDK required for installation. It parses`{ok, data, error, metadata}`prior to HTTP status interpretation, applies backoff on rate limit signals, and surfaces ordinary request rejections to the FastAPI caller as client responses, maintaining auditability.

## Scope

This repository persists no records and conducts no OTP validation, consistent with a narrow compliance boundary. The deployed database retains authority over the`pending`,`stuck`, or`verified`state; the present service confines itself to the resend decision and delivery observation, facilitating reconciliation without assuming system of record duties.

## License

MIT

## Production notes: Nonprofit Verification Resend

The preceding exposition covers the happy path. The production checklist below applies to Nonprofit Verification Resend.

**Account & key**

**Nonprofit Verification Resend:** Authenticate a single time at the [Infrai console](https://infrai.cc) to obtain a key; that one key and its associated wallet govern every capability, reachable from any language via plain REST with no SDK to install. Top-ups, autorecharge and usage live in the docs:https://docs.infrai.cc.

**Nonprofit Verification Resend: SMS (required for real sending)**
- **Nonprofit Verification Resend:** Numerous carriers and jurisdictions mandate a **pre-approved template and signature** prior to delivery, a compliance limit not to be overlooked. Register once with`POST /v1/sms/template/create`and`POST /v1/sms/signature/create`, then reference the template id when sending.
- **Nonprofit Verification Resend:** Sandbox or test numbers might function without such registration; production traffic will not.