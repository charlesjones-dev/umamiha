# Changelog

All notable changes to this project will be documented in this file.

## [1.1.1] - 2026-03-24

### Fixed

- Fix Lovelace card resource not auto-registering due to incorrect `hass.data` key lookup and missing `lovelace` dependency

## [1.1.0] - 2026-03-23

### Fixed

- Pass `startAt` parameter to `/api/realtime` endpoint for server-side event filtering, drastically reducing response payload size
- Skip realtime API call when active visitors is 0

### Changed

- Default scan interval increased from 30s to 60s for new installs

## [1.0.0] - 2026-03-01

### Added

- Initial release
- Umami API client with JWT auth and token refresh
- Two-step config flow (connection, website selection)
- Support for Umami Teams (fetches team-owned websites)
- DataUpdateCoordinator with parallel fetching per website
- Sensor entities with active visitor count, top countries, top URLs, and 24h sparkline
- Custom Lovelace card with sparkline background, country flags, and URL list
- Auto-registration of Lovelace card resource
- Options flow for update interval and website selection
- HACS and Hassfest CI validation workflows
