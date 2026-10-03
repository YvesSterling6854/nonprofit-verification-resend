import json

from src.nonprofit_verification import (
    CampaignReport,
    DonorReceipt,
    InfraiSMS,
    ResendVerificationRequest,
    VerificationDesk,
    VolunteerReminder,
)


def main() -> None:
    request = ResendVerificationRequest(
        verification_id="verification-from-your-stuck-record",
        verification_state="stuck",
        receipt=DonorReceipt(receipt_id="R-1042", donor_name="Mina", amount_cents=7500),
        reminder=VolunteerReminder(shift_id="SHIFT-18", volunteer_name="Mina"),
        report=CampaignReport(campaign_id="WINTER-KITS", donations_count=31, total_cents=189500),
    )
    result = VerificationDesk(InfraiSMS.from_environment()).resend_stuck(request)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

