"""Клиент личного кабинета ДомРесурс (domres.ru) для Псковэнергосбыта."""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

_LOGGER = logging.getLogger(__name__)

API = "https://domres.ru/api"
CUSTOMER = "ikus-mes"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


def force_ipv4() -> None:
    socket.getaddrinfo = _ipv4_getaddrinfo


class CabinetError(RuntimeError):
    """Ошибка кабинета."""


class AuthError(CabinetError):
    """Неверный логин или пароль."""


@dataclass
class Scale:
    scale_id: int
    name: str
    last: float | None = None
    last_date: str | None = None
    unit: str = ""


@dataclass
class Meter:
    account: str
    account_id: str
    base_id: str
    counter_id: str
    counter_number: str
    service: str
    counter_name: str = ""
    scales: list[Scale] = field(default_factory=list)
    last: float | None = None
    last_date: str | None = None

    @property
    def scale_id(self) -> int | None:
        return self.scales[0].scale_id if self.scales else None


@dataclass
class CabinetState:
    account: str
    base_id: str
    account_id: str = ""
    owner: str = ""
    address: str = ""
    meters: list[Meter] = field(default_factory=list)
    reading_state: str = ""

    @property
    def meter(self) -> Meter | None:
        return self.meters[0] if self.meters else None


def _request(session: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
    timeout = kwargs.pop("timeout", 45)
    try:
        return session.request(method, url, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise CabinetError(f"сеть: {exc}") from exc


def _error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        message = str(data.get("message") or "").strip()
        if message and message.lower() not in {"неизвестная ошибка сервера"}:
            return message
        cause = str(data.get("cause") or "").strip()
        if cause:
            return cause
    text = response.text.strip()
    return text[:300] or f"HTTP {response.status_code}"


def _parse_float(raw: Any) -> float | None:
    if raw in ("", None):
        return None
    try:
        return float(str(raw).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def _login_type(username: str) -> str:
    return "EMAIL" if "@" in username else "PHONE"


def _owner_name(profile: dict[str, Any]) -> str:
    name = profile.get("name") if isinstance(profile.get("name"), dict) else {}
    parts = [str(name.get("last") or ""), str(name.get("first") or ""), str(name.get("patronymic") or "")]
    return " ".join(part for part in parts if part).strip()


class PskovenergosbitClient:
    def __init__(self, username: str, password: str) -> None:
        self._username = username.strip()
        self._password = password

    def _session(self) -> requests.Session:
        force_ipv4()
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Content-Type": "application/json",
                "Customer": CUSTOMER,
            }
        )
        return session

    def _login(self, session: requests.Session) -> None:
        response = _request(
            session,
            "POST",
            f"{API}/v8/users/auth",
            json={
                "login": self._username,
                "password": self._password,
                "type": _login_type(self._username),
            },
            headers={"withTotp": "true", "Captcha": "none"},
        )
        if response.status_code == 424:
            raise AuthError("кабинет запросил код подтверждения. Войдите один раз на https://domres.ru/")
        if response.status_code == 449:
            raise AuthError("кабинет запросил капчу. Войдите один раз на https://domres.ru/")
        try:
            data = response.json()
        except ValueError:
            data = None
        token = data.get("auth") if isinstance(data, dict) else None
        if response.status_code != 200 or not token:
            message = _error_message(response) if response.status_code else "вход не выполнен"
            if response.status_code in {400, 401, 403} or "парол" in message.lower() or "логин" in message.lower():
                raise AuthError(message or "неверный логин или пароль")
            raise AuthError(message or "неверный логин или пароль")
        session.headers["Authorization"] = f"Bearer {token}"

    def fetch(self) -> CabinetState:
        session = self._session()
        self._login(session)
        return self._load_state(session)

    def _accounts(self, session: requests.Session) -> list[dict[str, Any]]:
        response = _request(session, "GET", f"{API}/v8/accounts/light")
        if response.status_code != 200:
            raise CabinetError(_error_message(response))
        data = response.json()
        if not isinstance(data, list) or not data:
            raise CabinetError(
                "в кабинете ДомРесурс нет привязанного лицевого счёта. "
                "Добавьте его на https://domres.ru/ в разделе адресов"
            )
        return [item for item in data if isinstance(item, dict)]

    def _profile_owner(self, session: requests.Session) -> str:
        response = _request(session, "GET", f"{API}/v6/users/current")
        if response.status_code != 200:
            return ""
        try:
            data = response.json()
        except ValueError:
            return ""
        return _owner_name(data) if isinstance(data, dict) else ""

    def _load_state(self, session: requests.Session) -> CabinetState:
        accounts = self._accounts(session)
        owner = self._profile_owner(session)
        meters: list[Meter] = []
        chosen = accounts[0]
        reading_state = ""
        for account in accounts:
            account_id = str(account.get("id") or "")
            register = str((account.get("tenancy") or {}).get("register") or account_id)
            provider = str((account.get("service") or {}).get("providerId") or "")
            loaded = self._meters(session, account_id, register, provider)
            if loaded:
                chosen = account
                meters = loaded
                reading_state = self._reading_state(session, account_id)
                if any("электро" in meter.service.lower() for meter in loaded):
                    break
        if not meters:
            raise CabinetError("счётчики в кабинете не найдены")
        tenancy = chosen.get("tenancy") or {}
        return CabinetState(
            account=str(tenancy.get("register") or chosen.get("id") or ""),
            account_id=str(chosen.get("id") or ""),
            base_id=str((chosen.get("service") or {}).get("providerId") or ""),
            owner=owner,
            address=str(chosen.get("address") or ""),
            meters=meters,
            reading_state=reading_state,
        )

    def _meters(
        self,
        session: requests.Session,
        account_id: str,
        register: str,
        provider: str,
    ) -> list[Meter]:
        response = _request(session, "GET", f"{API}/v6/accounts/{account_id}/meters/info")
        if response.status_code != 200:
            raise CabinetError(_error_message(response))
        data = response.json()
        if not isinstance(data, list):
            return []
        meters: list[Meter] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            identity = item.get("id") if isinstance(item.get("id"), dict) else {}
            scales: list[Scale] = []
            for scale in item.get("indications") or []:
                if not isinstance(scale, dict):
                    continue
                scales.append(
                    Scale(
                        scale_id=int(scale.get("meterScaleId") or 0),
                        name=str(scale.get("scaleName") or ""),
                        last=_parse_float(scale.get("previousReading")),
                        last_date=str(scale.get("previousReadingDate") or "") or None,
                        unit=str(scale.get("unit") or ""),
                    )
                )
            subservice = item.get("subservice") if isinstance(item.get("subservice"), dict) else {}
            first = scales[0] if scales else None
            meters.append(
                Meter(
                    account=register,
                    account_id=account_id,
                    base_id=str(identity.get("provider") or provider),
                    counter_id=str(identity.get("registration") or ""),
                    counter_number=str(item.get("serial") or ""),
                    service=str(subservice.get("name") or item.get("name") or "Электроэнергия"),
                    counter_name=str(item.get("name") or ""),
                    scales=scales,
                    last=first.last if first else None,
                    last_date=first.last_date if first else None,
                )
            )
        electricity = [meter for meter in meters if "электро" in meter.service.lower()]
        return electricity or meters

    def _reading_state(self, session: requests.Session, account_id: str) -> str:
        response = _request(session, "GET", f"{API}/v6/accounts/{account_id}/reading/state")
        if response.status_code != 200:
            return ""
        try:
            data = response.json()
        except ValueError:
            return response.text.strip().strip('"')
        return str(data).strip().strip('"')

    def submit(self, value: float, night: float | None = None) -> CabinetState:
        session = self._session()
        self._login(session)
        state = self._load_state(session)
        self._post_readings(session, state, value, night)
        return self._load_state(session)

    def _post_readings(
        self,
        session: requests.Session,
        state: CabinetState,
        value: float,
        night: float | None,
    ) -> None:
        meter = state.meter
        if meter is None or not meter.counter_id or not meter.scales:
            raise CabinetError("нечего отправлять")
        readings = [(meter.scales[0], value)]
        if night is not None:
            if len(meter.scales) < 2:
                raise CabinetError("у счётчика нет второй тарифной зоны")
            readings.append((meter.scales[1], night))
        payload = []
        for scale, reading in readings:
            if scale.last is not None and reading < scale.last:
                raise CabinetError(
                    f"новое показание {reading:g} меньше последнего {scale.last:g} "
                    f"(счётчик {meter.counter_number}, {scale.name or 'тариф'})"
                )
            payload.append({"scaleId": scale.scale_id, "value": reading})
        response = _request(
            session,
            "POST",
            f"{API}/v8/accounts/{meter.account_id}/meters/{quote(meter.counter_id, safe='')}/reading",
            json=payload,
        )
        if response.status_code not in {200, 201, 204}:
            raise CabinetError(_error_message(response))
        _LOGGER.debug("reading submit HTTP %s", response.status_code)
