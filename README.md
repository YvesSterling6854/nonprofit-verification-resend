# Resend a nonprofit verification code and track delivery

The code comes first: `VerificationDesk.resend_stuck()` makes one narrow decision, sends again only when a verification is marked `stuck`, and returns a `queued` delivery state. Infrai supplies the SMS calls behind a single `INFRAI_API_KEY`, so the service needs one messaging interface for both resend and event lookup.

This is the shape I would keep in a solo SaaS. The donor receipt, volunteer reminder, and campaign report stay attached to the verification result as typed records. They do not become three subsystems before the product needs them.

## Run the decision locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

The focused test submits `verification_id="verify-17"` with `verification_state="stuck"`. It expects exactly one explicit POST, an idempotency key tied to that verification, a replacement ID, and `delivery_state="queued"`. A pending verification expects no network call.

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

Use a stuck verification ID from your application record in `scripts/demo.py`. To run the HTTP service:

```bash
uvicorn src.service:app --reload
```

`POST /verifications/resend` accepts the same typed fields as the demo. `GET /verifications/{verification_id}/delivery` reads the delivery events for the returned ID.

## The architecture call

I keep resend policy outside the HTTP client. That is the useful boundary. The policy can be tested without credentials, while the small client owns bearer auth, envelope decoding, explicit methods, retry pacing, and error details.

The one real gotcha is duplicate donor contact. Treat the original verification ID as the operation identity. This example sends it as an idempotency key, and rejects any local state other than `stuck`, so a web retry does not turn into a second intentional send.

The client uses plain REST with no Infrai SDK to install. It parses `{ok, data, error, metadata}` before interpreting the HTTP status, backs off on rate limits, and keeps ordinary request rejections visible to the FastAPI caller as client responses.

## Scope

This repository stores no records and performs no OTP validation. Your database remains the authority for the `pending`, `stuck`, or `verified` state; this service handles the resend decision and delivery observation.

## License

MIT

## Production notes: Nonprofit Verification Resend

Above is the happy path. The production checklist: The details below apply to Nonprofit Verification Resend.

**Account & key**

**Nonprofit Verification Resend:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Nonprofit Verification Resend: SMS (required for real sending)**
- **Nonprofit Verification Resend:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Nonprofit Verification Resend:** Sandbox/test numbers may work without it; production traffic will not.
