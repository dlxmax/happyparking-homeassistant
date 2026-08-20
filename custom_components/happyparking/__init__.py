"""The HappyParking integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, LOGGER, PLATFORMS, SERVICE_TEST_PUSH
from .coordinator import HappyParkingCoordinator

TEST_PUSH_SCHEMA = vol.Schema(
    {vol.Optional("message", default="Home Assistant"): cv.string}
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HappyParking from a config entry."""
    coordinator = HappyParkingCoordinator(hass, entry)
    await coordinator.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, lambda _evt: hass.async_create_task(coordinator.async_stop())
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_TEST_PUSH):
        hass.services.async_register(
            DOMAIN, SERVICE_TEST_PUSH, _make_test_push(hass), schema=TEST_PUSH_SCHEMA
        )
    return True


def _make_test_push(hass: HomeAssistant):
    """Ask the parking server to push to us, so delivery can be tested on demand."""

    async def _test_push(call: ServiceCall) -> None:
        for coordinator in hass.data.get(DOMAIN, {}).values():
            try:
                await coordinator.async_test_push(call.data["message"])
            except Exception as err:  # noqa: BLE001
                LOGGER.warning("test push failed: %s", err)

    return _test_push


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HappyParkingCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_TEST_PUSH)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
