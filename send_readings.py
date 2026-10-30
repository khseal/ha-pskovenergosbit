#!/usr/bin/env python3
"""Отправка показаний в ЛК ДомРесурс (domres.ru).

Примеры:
  python3 send_readings.py --info
  python3 send_readings.py 26370
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "custom_components" / "pskovenergosbit"))
from cabinet import AuthError, CabinetError, PskovenergosbitClient  # noqa: E402

DEFAULT_LOGIN = os.environ.get("PES_LOGIN")
DEFAULT_PASSWORD = os.environ.get("PES_PASSWORD")


def die(message: str, code: int = 1) -> None:
    print(f"Ошибка: {message}", file=sys.stderr)
    raise SystemExit(code)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Показания Псковэнергосбыт (EPD)")
    parser.add_argument("value", nargs="?", type=float, help="полное новое показание")
    parser.add_argument("--login", default=DEFAULT_LOGIN)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--info", action="store_true", help="показать счётчики")
    parser.add_argument("-n", "--night", dest="t2", type=float, help="ночь / Т2")
    parser.add_argument("--dry-run", action="store_true", help="не отправлять")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.login or not args.password:
        die("укажите --login/--password или переменные PES_LOGIN и PES_PASSWORD")
    if not args.info and args.value is None:
        die("укажите показание, например: python3 send_readings.py 26370")

    client = PskovenergosbitClient(args.login, args.password)
    try:
        state = client.fetch()
    except AuthError as exc:
        die(f"вход: {exc}")
    except CabinetError as exc:
        die(str(exc))

    print(f"ЛС {state.account}")
    if state.owner:
        print(f"Владелец: {state.owner}")
    if state.address:
        print(f"Адрес: {state.address}")
    print("Счётчики:")
    for meter in state.meters:
        last = f"{meter.last:g}" if meter.last is not None else "?"
        date = f" ({meter.last_date})" if meter.last_date else ""
        print(f"  № {meter.counter_number}: {meter.service} последнее={last}{date}")

    if args.info or args.value is None:
        return 0
    if args.dry_run:
        print(f"Черновой прогон: отправить {args.value:g}")
        return 0
    try:
        client.submit(args.value, args.t2)
    except CabinetError as exc:
        die(str(exc))
    print("Показания отправлены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
