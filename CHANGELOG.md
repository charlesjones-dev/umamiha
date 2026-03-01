# Changelog

All notable changes to this project will be documented in this file.

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
