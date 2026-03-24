# UmamiHA

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![HACS Validation](https://github.com/charlesjones-dev/umamiha/actions/workflows/hacs.yml/badge.svg)](https://github.com/charlesjones-dev/umamiha/actions/workflows/hacs.yml)
[![Hassfest Validation](https://github.com/charlesjones-dev/umamiha/actions/workflows/hassfest.yml/badge.svg)](https://github.com/charlesjones-dev/umamiha/actions/workflows/hassfest.yml)
[![License: MIT](https://img.shields.io/github/license/charlesjones-dev/umamiha)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/charlesjones-dev/umamiha)](https://github.com/charlesjones-dev/umamiha/releases)
[![HA Min Version](https://img.shields.io/badge/HA-2024.1.0+-blue)](https://www.home-assistant.io)

Unofficial Home Assistant integration for [Umami](https://umami.is) via HACS.

Provides sensor entities and a custom Lovelace card showing realtime visitor data from your self-hosted Umami instance.

## Features

- Active visitor count per website
- Top 5 countries with visitor counts (emoji flags)
- Top 5 URLs with visitor counts
- 24-hour pageview sparkline
- Configurable poll interval (5-300 seconds)
- Multi-website support (including Umami Teams)
- Dark/light mode support

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Search for "UmamiHA" in the Community Store
3. Click Install
4. Restart Home Assistant

### Manual

Copy the `custom_components/umamiha` directory to your Home Assistant `config/custom_components/` directory.

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "UmamiHA"
3. Enter your Umami instance URL, username, and password
4. Select which websites to track

### Add the Card to a Dashboard

The Lovelace card resource is registered automatically. After setup, hard refresh your browser (**Ctrl+Shift+R**), then:

1. Edit a dashboard > **+ Add Card** > search for "UmamiHA"
2. Or use **Manual** card and paste:

```yaml
type: custom:umami-analytics-card
entity: sensor.umami_mysite_visitors
```

Replace `mysite` with your website's slug (check **Developer Tools > States** and search for `sensor.umami_` to find your entity IDs).

## Options

After setup, click Configure on the integration to change:

- **Update interval** - How often to poll Umami (5-300 seconds, default 60)
- **Websites** - Which websites to track

## Cloudflare Rate Limiting

If your Umami instance is behind Cloudflare, you will likely need to add a WAF rule to allow traffic from your Home Assistant IP.

The Umami API does not provide a single endpoint for all the data this integration needs. Each poll cycle makes **up to 2 API requests per website** (active visitors, plus realtime events only when visitors are present). The 24h pageview series is fetched separately every 5 minutes, adding 1 request per website per 5-minute cycle. With 9 websites at a 60-second interval, that's up to ~18 requests every 60 seconds plus ~9 series requests every 5 minutes. Lowering the interval or adding more websites increases this further.

Cloudflare's default rate limiting will flag this as suspicious and start blocking requests, causing the integration to show errors or stale data.

**Recommended Cloudflare WAF rule:**

1. Go to your Cloudflare dashboard > Security > WAF
2. Create a rule that allows traffic from your Home Assistant's public IP
3. Set the rule to **Skip** all managed rules and rate limiting for that IP
4. Scope it to your Umami domain

## See Also

Looking for a standalone web dashboard instead of a Home Assistant integration? Check out [UmamiDash](https://github.com/charlesjones-dev/umamidash), a realtime analytics dashboard for Umami that runs as its own website.

## Contributing

Contributions are welcome. Please open an issue or pull request on [GitHub](https://github.com/charlesjones-dev/umamiha).

## License

This project is licensed under the [MIT License](LICENSE).

## Disclaimer

This is an unofficial, community-built integration and is not affiliated with, endorsed by, or associated with Umami Software, Inc. "Umami" is a trademark of Umami Software, Inc. This project interacts with the Umami API but does not include any Umami source code.
