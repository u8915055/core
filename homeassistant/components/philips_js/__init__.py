"""The Philips TV integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Callable, Dict, Optional

from haphilipsjs import ConnectionFailure, PhilipsTV

from homeassistant.components.automation import AutomationActionType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import CALLBACK_TYPE, Context, HassJob, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS = ["media_player"]

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Philips TV component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Philips TV from a config entry."""

    tvapi = PhilipsTV(
        entry.data[CONF_HOST],
        entry.data[CONF_API_VERSION],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    coordinator = PhilipsTVDataUpdateCoordinator(hass, tvapi)

    await coordinator.async_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PluggableAction:
    """A pluggable action handler."""

    def __init__(self, update: Callable[[], None]):
        """Initialize."""
        self._update = update
        self._actions: Dict[Any, AutomationActionType] = {}

    def __bool__(self):
        """Return if we have something attached."""
        return bool(self._actions)

    @callback
    def async_attach(self, action: AutomationActionType, variables: Dict[str, Any]):
        """Attach a device trigger for turn on."""

        @callback
        def _remove():
            del self._actions[_remove]
            self._update()

        job = HassJob(action)

        self._actions[_remove] = (job, variables)
        self._update()

        return _remove

    async def async_run(
        self, hass: HomeAssistantType, context: Optional[Context] = None
    ):
        """Run all turn on triggers."""
        for job, variables in self._actions.values():
            hass.async_run_hass_job(job, variables, context)


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    def __init__(self, hass, api: PhilipsTV) -> None:
        """Set up the coordinator."""
        self.api = api
        self._notify_future: Optional[asyncio.Task] = None

        @callback
        def _update_listeners():
            for update_callback in self._listeners:
                update_callback()

        self.turn_on = PluggableAction(_update_listeners)

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=2.0, immediate=False
            ),
        )

    async def _notify_task(self):
        while self.api.on and self.api.notify_change_supported:
            if await self.api.notifyChange(130):
                self.async_set_updated_data(None)

    @callback
    def _async_notify_stop(self):
        if self._notify_future:
            self._notify_future.cancel()
            self._notify_future = None

    @callback
    def _async_notify_schedule(self):
        if (
            (self._notify_future is None or self._notify_future.done())
            and self.api.on
            and self.api.notify_change_supported
        ):
            self._notify_future = self.hass.loop.create_task(self._notify_task())

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update."""
        super().async_remove_listener(update_callback)
        if not self._listeners:
            self._async_notify_stop()

    @callback
    def _async_stop_refresh(self, event: asyncio.Event) -> None:
        super()._async_stop_refresh(event)
        self._async_notify_stop()

    @callback
    async def _async_update_data(self):
        """Fetch the latest data from the source."""
        try:
            await self.api.update()
            self._async_notify_schedule()
        except ConnectionFailure:
            pass
