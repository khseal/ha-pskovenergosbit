# Псковэнергосбыт для Home Assistant

Кастомная интеграция [личного кабинета](https://epd.pskovenergosbit.ru/) АО Псковэнергосбыт: показывает последние показания электросчётчика и позволяет передать новые прямо из Home Assistant.

Неофициальный проект, не связан с АО «Псковэнергосбыт».

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/khseal/ha-pskovenergosbit?include_prereleases)](https://github.com/khseal/ha-pskovenergosbit/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=khseal&repository=ha-pskovenergosbit&category=integration)

## Возможности

- Вход в кабинет по логину и паролю из интерфейса Home Assistant
- Датчик последних показаний (кВт⋅ч)
- Диагностика: лицевой счёт, номер счётчика, адрес, владелец, дата передачи, состояние
- Поле **Новое показание** и кнопка **Отправить показания**
- Служба `pskovenergosbit.submit_readings` для автоматизаций
- Опрос кабинета раз в 6 часов (настраивается)
- Логотип ПЭС в интерфейсе на Home Assistant 2026.3 и новее

Передаётся **полное** значение счётчика, а не прирост. Новое показание должно быть не меньше предыдущего.

## Установка через HACS

1. HACS → Интеграции → три точки → Пользовательские репозитории.
2. URL: `https://github.com/khseal/ha-pskovenergosbit`, категория **Integration**.
3. Найдите **Псковэнергосбыт** и установите.
4. Перезапустите Home Assistant.
5. Настройки → Устройства и службы → Добавить интеграцию → **Псковэнергосбыт**.
6. Введите логин и пароль от [epd.pskovenergosbit.ru](https://epd.pskovenergosbit.ru/).

## Ручная установка

1. Скопируйте папку `custom_components/pskovenergosbit` в `/config/custom_components/pskovenergosbit`.
2. Перезапустите Home Assistant.
3. Добавьте интеграцию и введите логин с паролем.

## Сущности

| Сущность | Описание |
| --- | --- |
| `sensor.*_poslednie_pokazaniya` | Последние принятые показания, кВт⋅ч |
| `sensor.*_sostoyanie` | `ok` / `error` / `unknown` |
| `sensor.*_data_peredachi` | Дата последней передачи |
| `sensor.*_litsevoy_schyot` | Лицевой счёт |
| `sensor.*_nomer_schyotchika` | Номер прибора учёта |
| `sensor.*_adres` | Адрес |
| `sensor.*_vladelets` | Владелец лицевого счёта |
| `number.*_novoe_pokazanie` | Полное значение, которое будет отправлено |
| `button.*_otpravit_pokazaniya` | Отправка в кабинет |

Интервал опроса задаётся в параметрах интеграции (1–72 часа, по умолчанию 6).

## Служба

```yaml
action: pskovenergosbit.submit_readings
data:
  value: 26370
  # night: 12010   # только для двухтарифного счётчика
```

Пример автоматизации 21-го числа каждого месяца:

```yaml
alias: Показания Псковэнергосбыт
triggers:
  - trigger: time
    at: "14:00:00"
conditions:
  - condition: template
    value_template: "{{ now().day == 21 }}"
actions:
  - action: pskovenergosbit.submit_readings
    data:
      value: "{{ states('sensor.your_energy_meter') | float }}"
```

## Скрипт из командной строки

Зависимости: `pip install -r requirements.txt` либо пакеты `python3-requests` и `python3-bs4`.

```bash
export PES_LOGIN="ваш_логин"
export PES_PASSWORD="ваш_пароль"

python3 send_readings.py --info
python3 send_readings.py 26370
python3 send_readings.py 26370 --dry-run
```

Логин и пароль также можно передать флагами `--login` и `--password`.

## Замечания

- Кабинет: [epd.pskovenergosbit.ru](https://epd.pskovenergosbit.ru/), вход через ЖКХ ID.
- Старый сайт `fl.pskovenergosbit.ru` не используется.
- Интеграция ходит в интернет при каждом обновлении и при отправке показаний.
- Логотип и название принадлежат АО «Псковэнергосбыт» и используются только для идентификации сервиса.
