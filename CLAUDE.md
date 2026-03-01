# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UmamiHA is a custom Home Assistant integration (HACS-compatible) that connects to self-hosted [Umami](https://umami.is) analytics instances. It provides sensor entities and a custom Lovelace card showing realtime visitor data.

## Architecture

**Python backend** (`custom_components/umamiha/`):
- `api.py` - Async Umami API client using aiohttp. Handles JWT auth with auto-refresh (23h cycle), 401 retry logic. Makes 2 API calls per website per poll (active visitors, realtime events). The 24h pageview series is fetched on a separate 5-minute cycle.
- `coordinator.py` - HA `DataUpdateCoordinator` subclass. Fetches all websites in parallel via `asyncio.gather`. Preserves stale data on partial failures. Caches series data between 5-minute refresh cycles.
- `sensor.py` - One `UmamiVisitorSensor` per tracked website. State = active visitor count. Extra attributes: countries, urls, series (consumed by the Lovelace card).
- `config_flow.py` - Two-step setup flow (credentials, then website selection). Options flow for interval/website changes. Supports Umami Teams websites.
- `__init__.py` - Entry setup, frontend card auto-registration as a Lovelace resource.
- `const.py` - Domain and config key constants.

**Frontend** (`custom_components/umamiha/www/`):
- `umami-analytics-card.js` - Vanilla Web Component (Shadow DOM). Renders sparkline SVG background, country flags (emoji), URL list, and animated visitor count. Includes a card editor for the HA UI.

## Key Patterns

- Config data (url, username, password) lives in `entry.data`; mutable settings (websites list, scan_interval) live in `entry.options`. Options changes trigger a full reload via `_async_update_listener`.
- Website objects carry both `id` and `name`. The API returns paginated responses with a `{"data": [...]}` wrapper, but some endpoints return plain arrays - the client handles both.
- The Lovelace card is auto-registered as a static path at `/umamiha/umami-analytics-card.js` and added to `lovelace_resources` on first setup.

## Validation

Two GitHub Actions CI workflows run on push/PR:
- **hassfest** - Home Assistant manifest validation
- **HACS validation** - HACS repository structure validation

No local test suite exists. To validate locally, use the HA development container or copy to a HA instance's `custom_components/` directory.

## Versioning

Version is tracked in three places that must stay in sync:
- `custom_components/umamiha/manifest.json` (`version` field)
- `custom_components/umamiha/www/umami-analytics-card.js` (`CARD_VERSION` const)
- `CHANGELOG.md`
