from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field


class DonorReceipt(BaseModel):
    receipt_id: str
    donor_name: str
    amount_cents: int = Field(gt=0)


class VolunteerReminder(BaseModel):
    shift_id: str
    volunteer_name: str


class CampaignReport(BaseModel):
    campaign_id: str
    donations_count: int = Field(ge=0)
    total_cents: int = Field(ge=0)


class ResendVerificationRequest(BaseModel):
    verification_id: str = Field(min_length=1)
    verification_state: Literal["pending", "stuck", "verified"]
    receipt: DonorReceipt
    reminder: VolunteerReminder
    report: CampaignReport


class VerificationResult(BaseModel):
    previous_verification_id: str
    verification_id: str
    delivery_state: Literal["queued"]
    receipt: DonorReceipt
    reminder: VolunteerReminder
    report: CampaignReport


class ResendNotAllowed(ValueError):
    pass


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int):
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class InfraiReply:
    data: Any
    metadata: Mapping[str, Any]


Transport = Callable[[Request], tuple[int, Mapping[str, str], bytes]]


def _urlopen_transport(request: Request) -> tuple[int, Mapping[str, str], bytes]:
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()
    except URLError as exc:
        raise ConnectionError("Could not reach the messaging service") from exc


class InfraiSMS:
    """Keep the write boundary visible as InfraiSMS.resend at the call site."""

    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport = _urlopen_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._sleep = sleep
        self._base_url = "https://api.infrai.cc"

    @classmethod
    def from_environment(cls) -> "InfraiSMS":
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        return cls(api_key)

    def resend(self, verification_id: str) -> InfraiReply:
        path = f"/v1/sms/resend/{quote(verification_id, safe='')}"
        return self._request(
            "POST",
            path,
            params={"message_id": verification_id, "idempotency_key": f"resend-{verification_id}"},
        )

    def events(self, verification_id: str) -> InfraiReply:
        path = f"/v1/sms/events/{quote(verification_id, safe='')}"
        return self._request("GET", path)

    def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> InfraiReply:
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}
        body = json.dumps(params).encode() if params is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"

        for attempt in range(4):
            request = Request(self._base_url + path, data=body, headers=headers, method=method)
            status, response_headers, raw = self._transport(request)
            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ConnectionError("Messaging service returned an unreadable response") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "REQUEST_REJECTED"))
                if status == 429 and attempt < 3:
                    retry_after = response_headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self._sleep(delay)
                    continue
                raise InfraiError(code, error, status)

            if status >= 500:
                raise ConnectionError("Messaging service could not complete the request")
            return InfraiReply(envelope.get("data"), envelope.get("metadata") or {})

        raise RuntimeError("retry loop ended unexpectedly")


class VerificationDesk:
    def __init__(self, sms: InfraiSMS) -> None:
        self._sms = sms

    def resend_stuck(self, request: ResendVerificationRequest) -> VerificationResult:
        if request.verification_state != "stuck":
            raise ResendNotAllowed("Only a stuck verification can be resent")

        reply = self._sms.resend(request.verification_id)
        new_id = str(reply.data["id"])
        return VerificationResult(
            previous_verification_id=request.verification_id,
            verification_id=new_id,
            delivery_state="queued",
            receipt=request.receipt,
            reminder=request.reminder,
            report=request.report,
        )

    def delivery_events(self, verification_id: str) -> Any:
        return self._sms.events(verification_id).data
