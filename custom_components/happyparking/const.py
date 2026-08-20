"""Constants for the HappyParking integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "happyparking"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [Platform.EVENT]

# Config keys
CONF_BASE_URL = "base_url"
CONF_USER_ID = "user_id"
CONF_SITE_CODE = "site_code"
CONF_DEVICE_ID = "device_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_VERIFY_SSL = "verify_ssl"

# HappyParking cloud (account/discovery) service
CLOUD_URL = "https://app.hparking.co.kr/cloud"

# HappyParking's own login page, offering the same Kakao and id/password
# sign-ins as the app. Setup links here rather than to any provider directly.
LOGIN_URL = "https://app.hparking.co.kr/happyparking/login"

DEFAULT_DEVICE_ID = "hass-happyparking"
DEFAULT_SCAN_INTERVAL = 120  # seconds; poll fallback. 0 = push-only.
DEFAULT_VERIFY_SSL = True

# Events fired on the HA bus (in addition to the event entity)
EVENT_CAR = "happyparking_car"
# Every raw push the parking server sends us, so push delivery is observable
# even when the log is not reachable.
EVENT_PUSH = "happyparking_push"

# The visit list is ordered by ENTRY time, and an exit is written back onto the
# original row. A car parked while the other comes and goes sinks down the list,
# so a sweep keeps paging until every visit still awaiting an exit is accounted
# for, rather than trusting the first page.
POLL_PAGE_SIZE = 20
MAX_POLL_PAGES = 10

SERVICE_TEST_PUSH = "test_push"

EVENT_TYPES = ["entered", "exited"]

# Firebase project of the HappyParking app (extracted from the APK; stable app identity)
FIREBASE = {
    "project_id": "newhappyparkingvisitor",
    "app_id": "1:840195079176:android:a9e70a44ba57dac036a5bd",
    "api_key": "AIzaSyBf56YKbE5ZBhHAfnk_y0hT4H95HMbQMas",
    "messaging_sender_id": "840195079176",
    "bundle_id": "com.bnids.happyparking",
}
