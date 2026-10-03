"""Telegram notification adapter architecture without a live network transport."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import json
import re
from typing import Protocol

from .dispatch import (
    DisabledNotificationProvider,
    NotificationProvider,
    NotificationProviderKind,
    ProviderAttemptResult,
    ProviderAttemptStatus,
)
from .event_domain import NotificationEvent, safe_payload


class TelegramMode(str, Enum):
    DISABLED = "DISABLED"
    TEST = "TEST"


_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class TelegramConfiguration:
    mode: TelegramMode = TelegramMode.DISABLED
    channel_alias: str | None = None
    maximum_message_characters: int = 3500

    def __post_init__(self) -> None:
        if not isinstance(self.mode, TelegramMode):
            raise ValueError("invalid Telegram mode")
        if (
            type(self.maximum_message_characters) is not int
            or not 256 <= self.maximum_message_characters <= 4096
        ):
            raise ValueError("maximum Telegram message size must be between 256 and 4096")
        if self.mode == TelegramMode.DISABLED:
            if self.channel_alias is not None:
                raise ValueError("disabled Telegram configuration cannot select a channel")
            return
        if (
            not isinstance(self.channel_alias, str)
            or _ALIAS.fullmatch(self.channel_alias) is None
        ):
            raise ValueError("test Telegram mode requires a safe channel alias")


@dataclass(frozen=True)
class TelegramMessage:
    channel_alias: str
    text: str
    event_id: str
    dedupe_identity: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.channel_alias, str)
            or _ALIAS.fullmatch(self.channel_alias) is None
        ):
            raise ValueError("Telegram message channel alias is invalid")
        for name in ("text", "event_id", "dedupe_identity"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Telegram message {name} is required")


class TelegramTransport(Protocol):
    def submit(self, message: TelegramMessage) -> ProviderAttemptResult: ...


def _render_value(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


class TelegramEventFormatter:
    def __init__(self, maximum_characters: int = 3500) -> None:
        if type(maximum_characters) is not int or not 256 <= maximum_characters <= 4096:
            raise ValueError("maximum formatter size must be between 256 and 4096")
        self._maximum_characters = maximum_characters

    @property
    def maximum_characters(self) -> int:
        return self._maximum_characters

    def format(self, event: NotificationEvent, channel_alias: str) -> TelegramMessage:
        if not isinstance(event, NotificationEvent):
            raise ValueError("formatter requires a NotificationEvent")
        if not isinstance(channel_alias, str) or _ALIAS.fullmatch(channel_alias) is None:
            raise ValueError("Telegram channel alias is invalid")
        if safe_payload(dict(event.payload), event.redaction_policy) != event.payload:
            raise ValueError("notification event payload is not safe")

        identity = event.identity
        lines = [
            "ARMS AI notification",
            f"type={event.event_type.value}",
            f"severity={event.severity.value}",
            f"occurred_at={event.occurred_at.isoformat()}",
            f"event_id={event.event_id}",
        ]
        if identity.account_id is not None:
            lines.append(f"account_id={_render_value(identity.account_id)}")
        if identity.firm_id is not None:
            lines.extend((
                f"firm_id={_render_value(identity.firm_id)}",
                f"program_id={_render_value(identity.program_id)}",
                f"profile_version={_render_value(identity.profile_version)}",
            ))
        lines.extend(
            f"payload.{key}={_render_value(value)}"
            for key, value in event.payload
        )
        text = "\n".join(lines)
        if len(text) > self._maximum_characters:
            raise ValueError("formatted Telegram message exceeds configured limit")
        return TelegramMessage(
            channel_alias=channel_alias,
            text=text,
            event_id=event.event_id,
            dedupe_identity=event.dedupe_identity,
        )


class FakeTelegramTransport:
    """Deterministic test transport that records messages and performs no I/O."""

    def __init__(
        self,
        outcomes: tuple[ProviderAttemptResult, ...] | None = None,
    ) -> None:
        self._outcomes = (
            outcomes
            if outcomes is not None
            else (ProviderAttemptResult(ProviderAttemptStatus.DELIVERED),)
        )
        if not self._outcomes:
            raise ValueError("fake Telegram transport requires an outcome")
        if any(not isinstance(item, ProviderAttemptResult) for item in self._outcomes):
            raise ValueError("fake Telegram outcomes are invalid")
        self.messages: list[TelegramMessage] = []

    def submit(self, message: TelegramMessage) -> ProviderAttemptResult:
        if not isinstance(message, TelegramMessage):
            raise ValueError("fake Telegram transport requires a TelegramMessage")
        self.messages.append(message)
        index = min(len(self.messages) - 1, len(self._outcomes) - 1)
        return self._outcomes[index]


class TelegramNotificationProvider:
    kind = NotificationProviderKind.TELEGRAM

    def __init__(
        self,
        configuration: TelegramConfiguration,
        transport: TelegramTransport,
        formatter: TelegramEventFormatter | None = None,
    ) -> None:
        if not isinstance(configuration, TelegramConfiguration):
            raise ValueError("Telegram configuration is required")
        if configuration.mode != TelegramMode.TEST:
            raise ValueError("Telegram provider supports test mode only")
        if transport is None or not callable(getattr(transport, "submit", None)):
            raise ValueError("Telegram transport is invalid")
        self._configuration = configuration
        self._transport = transport
        if formatter is not None and not isinstance(formatter, TelegramEventFormatter):
            raise ValueError("Telegram formatter is invalid")
        self._formatter = formatter or TelegramEventFormatter(
            configuration.maximum_message_characters
        )
        if self._formatter.maximum_characters > configuration.maximum_message_characters:
            raise ValueError("Telegram formatter exceeds configured message limit")

    def deliver(self, event: NotificationEvent) -> ProviderAttemptResult:
        try:
            message = self._formatter.format(
                event,
                self._configuration.channel_alias,
            )
        except (TypeError, ValueError):
            return ProviderAttemptResult(
                ProviderAttemptStatus.PERMANENT_FAILURE,
                "TELEGRAM_FORMAT_REJECTED",
            )
        try:
            result = self._transport.submit(message)
        except Exception:
            return ProviderAttemptResult(
                ProviderAttemptStatus.RETRYABLE_FAILURE,
                "TELEGRAM_TRANSPORT_EXCEPTION",
            )
        if not isinstance(result, ProviderAttemptResult):
            return ProviderAttemptResult(
                ProviderAttemptStatus.PERMANENT_FAILURE,
                "TELEGRAM_TRANSPORT_INVALID_RESULT",
            )
        return result


def build_telegram_provider(
    configuration: TelegramConfiguration,
    *,
    transport: TelegramTransport | None = None,
    formatter: TelegramEventFormatter | None = None,
) -> NotificationProvider:
    if not isinstance(configuration, TelegramConfiguration):
        raise ValueError("Telegram configuration is required")
    if configuration.mode == TelegramMode.DISABLED:
        return DisabledNotificationProvider()
    if transport is None:
        raise ValueError("test Telegram mode requires an explicit transport")
    return TelegramNotificationProvider(configuration, transport, formatter)
