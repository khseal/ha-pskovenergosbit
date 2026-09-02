"""Constants for the Pskovenergosbit integration."""

from datetime import timedelta

DOMAIN = "pskovenergosbit"
PLATFORMS = ["sensor", "number", "button"]

DEFAULT_SCAN_INTERVAL = timedelta(hours=6)
CONF_SCAN_INTERVAL = "scan_interval_hours"

ATTR_VALUE = "value"
ATTR_NIGHT = "night"
SERVICE_SUBMIT = "submit_readings"
