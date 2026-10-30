# Псковэнергосбыт для Home Assistant

Кастомная интеграция [личного кабинета ДомРесурс](https://domres.ru/) для АО Псковэнергосбыт: показывает последние показания электросчётчика и позволяет передать новые прямо из Home Assistant.

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
6. Введите email или телефон и пароль от [domres.ru](https://domres.ru/).

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

Готовая автоматизация на 21-е число каждого месяца: к последним показаниям из кабинета прибавляется **140 кВт⋅ч**, в кабинет уходит полное значение. Файл: [`examples/monthly_add_140.yaml`](examples/monthly_add_140.yaml).

Настройки → Автоматизации → создать → меню ⋮ → «Изменить в YAML» — вставьте содержимое файла.

```yaml
alias: Показания Псковэнергосбыт +140
description: 21-го числа каждого месяца передаёт последние показания плюс 140 кВт⋅ч.
mode: single
triggers:
  - trigger: time
    at: "10:00:00"
conditions:
  - condition: template
    value_template: "{{ now().day == 21 }}"
actions:
  - variables:
      increment: 140
      last: >-
        {% set found = states.sensor
           | selectattr('attributes.account', 'defined')
           | selectattr('attributes.meter', 'defined')
           | selectattr('attributes.last_date', 'defined')
           | list %}
        {{ found[0].state | float(none) if found else none }}
  - if:
      - condition: template
        value_template: "{{ last is number }}"
    then:
      - action: pskovenergosbit.submit_readings
        data:
          value: "{{ last + increment }}"
      - action: persistent_notification.create
        data:
          title: Псковэнергосбыт
          message: "Отправлены показания {{ (last + increment) | round(0) }} (было {{ last | round(0) }} + {{ increment }} кВт⋅ч)."
    else:
      - action: persistent_notification.create
        data:
          title: Псковэнергосбыт
          message: Не удалось прочитать последние показания, отправка пропущена.
```

Время отправки — 10:00, его можно поменять. Если датчик последних показаний не находится сам, подставьте его `entity_id` вместо блока `last`:

```yaml
last: "{{ states('sensor.pskovenergosbyt_poslednie_pokazaniya') | float(none) }}"
```

## Скрипт из командной строки

Зависимости: `pip install -r requirements.txt` либо пакет `python3-requests`.

```bash
export PES_LOGIN="ваш_логин"
export PES_PASSWORD="ваш_пароль"

python3 send_readings.py --info
python3 send_readings.py 26370
python3 send_readings.py 26370 --dry-run
```

Логин и пароль также можно передать флагами `--login` и `--password`.

## Замечания

- Кабинет: [domres.ru](https://domres.ru/). Старые сайты `epd.pskovenergosbit.ru` и `fl.pskovenergosbit.ru` больше не используются.
- Лицевой счёт должен быть привязан к профилю ДомРесурс.
- Интеграция ходит в интернет при каждом обновлении и при отправке показаний.
- Логотип и название принадлежат АО «Псковэнергосбыт» и используются только для идентификации сервиса.
