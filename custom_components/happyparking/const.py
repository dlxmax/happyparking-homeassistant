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
CONF_ENABLE_PUSH = "enable_push"
CONF_ENABLE_NOTIFY = "enable_notify"
CONF_ENABLE_VISITORS = "enable_visitors"
# How the bridge signs in again on its own. The parking server's push
# endpoints need a login that lasts 24 hours, and the app renews it by
# signing in to the cloud afresh, so one of these has to be kept.
CONF_KAKAO_ID = "kakao_id"
CONF_LOGIN_ID = "login_id"
CONF_PASSWORD = "password"
CREDENTIAL_KEYS = (CONF_KAKAO_ID, CONF_LOGIN_ID, CONF_PASSWORD)

# HappyParking cloud (account/discovery) service
CLOUD_URL = "https://app.hparking.co.kr/cloud"

# HappyParking's own login page, offering the same Kakao and id/password
# sign-ins as the app. Setup links here rather than to any provider directly.
LOGIN_URL = "https://app.hparking.co.kr/happyparking/login"

DEFAULT_DEVICE_ID = "hass-happyparking"
DEFAULT_SCAN_INTERVAL = 120  # seconds; poll fallback. 0 = push-only.
DEFAULT_VERIFY_SSL = True
# Registering a push token writes a row the parking server shares with the
# phone app, so it has to be possible to stay out of that table entirely.
DEFAULT_ENABLE_PUSH = True
# A notification per car movement is the point of the integration for
# most people, but it is the first thing to become noise on a busy gate,
# so it has to be switchable without giving up the events themselves.
DEFAULT_ENABLE_NOTIFY = True
# Visitor cars are the same list shape under a different path, and they
# are the ones you are least likely to be expecting, so they are on by
# default. They cost a second sweep per poll, hence the switch.
DEFAULT_ENABLE_VISITORS = True

# Events fired on the HA bus (in addition to the event entities). Household
# and visitor cars get their own event and their own entity, so a doorbell
# automation and an "are we home" automation never have to tell them apart.
EVENT_CAR = "happyparking_car"
EVENT_VISITOR = "happyparking_visitor"
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

# The two visit lists. Both live at
# /local/api/visitcar/<kind>/appuser/<user_id>/recent and return the same
# record shape; only the path segment differs.
KIND_HOUSEHOLD = "household"
KIND_VISITOR = "visitor"

# Firebase project of the HappyParking app (extracted from the APK; stable app identity)
FIREBASE = {
    "project_id": "newhappyparkingvisitor",
    "app_id": "1:840195079176:android:a9e70a44ba57dac036a5bd",
    "api_key": "AIzaSyBf56YKbE5ZBhHAfnk_y0hT4H95HMbQMas",
    "messaging_sender_id": "840195079176",
    "bundle_id": "com.bnids.happyparking",
}
