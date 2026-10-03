from typing import Any

from fastapi import FastAPI, HTTPException

from .nonprofit_verification import (
    InfraiError,
    InfraiSMS,
    ResendNotAllowed,
    ResendVerificationRequest,
    VerificationDesk,
    VerificationResult,
)

app = FastAPI(title="Nonprofit verification desk")


def _desk() -> VerificationDesk:
    return VerificationDesk(InfraiSMS.from_environment())


@app.post("/verifications/resend", response_model=VerificationResult)
def resend_verification(request: ResendVerificationRequest) -> VerificationResult:
    try:
        return _desk().resend_stuck(request)
    except ResendNotAllowed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "message": exc.detail.get("message", "Request rejected")},
        ) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/verifications/{verification_id}/delivery")
def delivery_state(verification_id: str) -> dict[str, Any]:
    try:
        return {"verification_id": verification_id, "events": _desk().delivery_events(verification_id)}
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code}) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

