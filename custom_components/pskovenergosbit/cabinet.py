"""Клиент ЛК Псковэнергосбыт (epd.pskovenergosbit.ru)."""

from __future__ import annotations

import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

EPD = "https://epd.pskovenergosbit.ru"
ID = "https://id.pskovenergosbit.ru"
LOGIN_START = (
    f"{EPD}/ClientIdentity/Account/ExternalLogin"
    "?provider=sso&prompt=select_account&handler=Challenge"
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
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
class Meter:
    account: str
    base_id: str
    counter_id: str
    counter_number: str
    service: str
    counter_name: str = ""
    last: float | None = None
    last_date: str | None = None


@dataclass
class CabinetState:
    account: str
    base_id: str
    owner: str = ""
    address: str = ""
    meters: list[Meter] = field(default_factory=list)
    token: str = ""

    @property
    def meter(self) -> Meter | None:
        return self.meters[0] if self.meters else None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _form_data(form) -> dict[str, str]:
    data: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or "text").lower()
        if itype in {"checkbox", "radio"} and not inp.has_attr("checked"):
            continue
        data[name] = inp.get("value") or ""
    return data


def _csrf_token(session: requests.Session, html: str) -> str:
    hidden = _soup(html).find("input", attrs={"name": "__RequestVerificationToken"})
    if hidden and hidden.get("value"):
        return str(hidden["value"])
    for cookie in session.cookies:
        if "Antiforgery" in cookie.name:
            return cookie.value or ""
    return ""


def _request(session: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
    timeout = kwargs.pop("timeout", 45)
    try:
        return session.request(method, url, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise CabinetError(f"сеть: {exc}") from exc


def _parse_float(raw: Any) -> float | None:
    if raw in ("", None):
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None


def _parse_meters(html: str, account: str, base_id: str) -> list[Meter]:
    page = _soup(html)
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", html)
    last_date = date_match.group(1) if date_match else None
    meters: list[Meter] = []
    for inp in page.select("input.new-indication, input[name^='newIndication']"):
        counter_id = inp.get("data-id") or ""
        name = inp.get("name") or ""
        if not counter_id:
            match = re.search(r"\[(\d+)\]", name)
            counter_id = match.group(1) if match else ""
        last_el = page.select_one(f"input.last-indication[data-id='{counter_id}']")
        last = _parse_float(last_el.get("value") if last_el else None)
        meters.append(
            Meter(
                account=account,
                base_id=base_id,
                counter_id=str(counter_id),
                counter_number=inp.get("data-number") or "",
                service=inp.get("data-service") or "Электроснабжение",
                counter_name=inp.get("data-name") or "",
                last=last,
                last_date=last_date,
            )
        )
    return meters


class PskovenergosbitClient:
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def _session(self) -> requests.Session:
        force_ipv4()
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        return session

    def _login(self, session: requests.Session) -> None:
        first = _request(session, "GET", LOGIN_START, allow_redirects=True)
        page = _soup(first.text)
        form = page.find("form", id="account") or page.find("form")
        if not form:
            raise CabinetError("нет формы входа")
        data = _form_data(form)
        data["Input.Login"] = self._username
        data["Input.Password"] = self._password
        data["Input.RememberLogin"] = "false"
        data["RecaptchaToken"] = data.get("RecaptchaToken", "")
        response = _request(
            session,
            "POST",
            first.url,
            data=data,
            allow_redirects=True,
            headers={"Referer": first.url, "Origin": ID},
        )
        if "Неверный логин или пароль" in response.text:
            raise AuthError("неверный логин или пароль")
        if "id.pskovenergosbit.ru/Auth/Login" in response.url and "Input.Password" in response.text:
            raise AuthError("логин отклонён")
        if "code" in response.text and "signin-oidc" in response.text:
            response = self._follow_oidc(session, response)
        if "epd.pskovenergosbit.ru" not in response.url:
            raise CabinetError(f"после входа неожиданный URL: {response.url}")

    def _follow_oidc(self, session: requests.Session, response: requests.Response) -> requests.Response:
        page = _soup(response.text)
        for form in page.find_all("form"):
            data = _form_data(form)
            if "code" in data and "state" in data:
                action = urljoin(response.url, form.get("action") or "")
                return _request(session, "POST", action, data=data, allow_redirects=True)
        raise CabinetError("не найдена форма OIDC после логина")

    def fetch(self) -> CabinetState:
        session = self._session()
        self._login(session)
        return self._load_state(session)

    def _load_state(self, session: requests.Session) -> CabinetState:
        accounts_page = _request(session, "GET", f"{EPD}/SN/AllAccountsIndications")
        token = _csrf_token(session, accounts_page.text)
        page = _soup(accounts_page.text)
        hidden = page.select_one("form input[name='accountNumber']")
        base_el = page.select_one("form input[name='baseId']")
        if not hidden or not base_el:
            raise CabinetError("не найден лицевой счёт в кабинете")
        account = str(hidden.get("value") or "")
        base_id = str(base_el.get("value") or "")
        owner_el = page.select_one("form input[name='owner']")
        address_el = page.select_one("form input[name='address']")
        indications = _request(
            session,
            "GET",
            f"{EPD}/SN/GetIndications",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        meters = _parse_meters(indications.text, account, base_id)
        if not meters:
            card = _request(
                session,
                "POST",
                f"{EPD}/SN/GetAccountIndications",
                data={
                    "baseId": base_id,
                    "accountNumber": account,
                    "__RequestVerificationToken": token,
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            meters = _parse_meters(card.text, account, base_id)
        if not meters:
            raise CabinetError("счётчики на странице показаний не найдены")
        return CabinetState(
            account=account,
            base_id=base_id,
            owner=str(owner_el.get("value") or "") if owner_el else "",
            address=str(address_el.get("value") or "") if address_el else "",
            meters=meters,
            token=token,
        )

    def submit(self, value: float, night: float | None = None) -> CabinetState:
        session = self._session()
        self._login(session)
        state = self._load_state(session)
        values: dict[str, float] = {"t1": value}
        if night is not None:
            values["t2"] = night
        self._post_readings(session, state, values)
        return self._load_state(session)

    def _post_readings(
        self,
        session: requests.Session,
        state: CabinetState,
        values: dict[str, float],
    ) -> None:
        meters = state.meters
        model: list[dict[str, str]] = []
        for i, meter in enumerate(meters):
            zone = "t1" if i == 0 else f"t{i + 1}"
            if zone not in values:
                continue
            val = values[zone]
            if meter.last is not None and val < meter.last:
                raise CabinetError(
                    f"новое показание {val:g} меньше последнего {meter.last:g} "
                    f"(счётчик {meter.counter_number})"
                )
            model.append(
                {
                    "account": meter.account,
                    "baseId": meter.base_id,
                    "counterId": meter.counter_id,
                    "serviceTypeName": meter.service,
                    "counterNumber": meter.counter_number,
                    "counterName": meter.counter_name,
                    "val": f"{val:g}",
                }
            )
        if not model:
            raise CabinetError("нечего отправлять")

        payload: dict[str, str] = {}
        if state.token:
            payload["__RequestVerificationToken"] = state.token
        for i, item in enumerate(model):
            for key, item_value in item.items():
                payload[f"model[{i}].{key}"] = item_value

        response = _request(
            session,
            "POST",
            f"{EPD}/SN/SetReadings",
            data=payload,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{EPD}/SN/AllAccountsIndications",
                "Origin": EPD,
                "RequestVerificationToken": state.token,
            },
        )
        self._raise_if_failed(response)
        _LOGGER.debug("SetReadings HTTP %s: %s", response.status_code, response.text[:500])

    def _raise_if_failed(self, response: requests.Response) -> None:
        ctype = response.headers.get("Content-Type", "")
        body = response.text.strip()
        if "json" in ctype:
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, list):
                ok = [x for x in data if isinstance(x, dict) and x.get("code") in (0, "0")]
                errors = [
                    x
                    for x in data
                    if isinstance(x, dict) and x.get("code") not in (0, 1, "0", "1", None)
                ]
                if ok:
                    return
                if errors:
                    msgs = "; ".join(str(x.get("message") or x) for x in errors)
                    raise CabinetError(msgs or "сервер вернул ошибку")
            if isinstance(data, dict) and data.get("success") is False:
                raise CabinetError(str(data.get("message") or data))
            return
        low = body.lower()
        if any(word in low for word in ("успеш", "принят", "сохранен", "переданы")):
            return
        snippet = re.sub(r"\s+", " ", _soup(body).get_text(" ", strip=True))[:400]
        if any(word in low for word in ("ошиб", "неверн", "нельзя")):
            raise CabinetError(snippet or f"HTTP {response.status_code}")
