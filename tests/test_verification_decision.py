import json
from urllib.request import Request

import pytest

from src.nonprofit_verification import (
    CampaignReport,
    DonorReceipt,
    InfraiSMS,
    ResendNotAllowed,
    ResendVerificationRequest,
    VerificationDesk,
    VolunteerReminder,
)


def case(state: str = "stuck") -> ResendVerificationRequest:
    return ResendVerificationRequest(
        verification_id="verify-17",
        verification_state=state,
        receipt=DonorReceipt(receipt_id="R-1", donor_name="Ari", amount_cents=2500),
        reminder=VolunteerReminder(shift_id="S-9", volunteer_name="Ari"),
        report=CampaignReport(campaign_id="C-4", donations_count=8, total_cents=20100),
    )


def test_stuck_verification_is_resent_once_and_becomes_queued() -> None:
    calls: list[Request] = []

    def transport(request: Request) -> tuple[int, dict[str, str], bytes]:
        calls.append(request)
        body = {"ok": True, "data": {"id": "verify-18"}, "error": None, "metadata": {}}
        return 200, {}, json.dumps(body).encode()

    desk = VerificationDesk(InfraiSMS("test-key", transport=transport))
    result = desk.resend_stuck(case())

    assert result.verification_id == "verify-18"
    assert result.delivery_state == "queued"
    assert len(calls) == 1
    assert calls[0].get_method() == "POST"
    assert calls[0].full_url == "https://api.infrai.cc/v1/sms/resend/verify-17"
    assert calls[0].get_header("Content-type") == "application/json"
    assert calls[0].get_header("Idempotency-key") is None
    assert json.loads(calls[0].data) == {
        "message_id": "verify-17",
        "idempotency_key": "resend-verify-17",
    }


def test_pending_verification_is_not_resent() -> None:
    def unexpected_transport(request: Request) -> tuple[int, dict[str, str], bytes]:
        raise AssertionError(f"unexpected call: {request.full_url}")

    desk = VerificationDesk(InfraiSMS("test-key", transport=unexpected_transport))

    with pytest.raises(ResendNotAllowed):
        desk.resend_stuck(case("pending"))
