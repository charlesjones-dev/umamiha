/**
 * Umami Analytics Card - Custom Lovelace card for Home Assistant
 * Displays realtime visitor data from Umami analytics.
 */

const CARD_VERSION = "1.1.0";

class UmamiAnalyticsCard extends HTMLElement {
  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  static getConfigElement() {
    return document.createElement("umami-analytics-card-editor");
  }

  static getStubConfig() {
    return { entity: "" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._previousVisitors = null;
    this._animating = false;
    this._lastStateKey = null;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;

    const stateObj = hass.states[this._config.entity];
    if (!stateObj) {
      if (this._lastStateKey !== null) {
        this._lastStateKey = null;
        this._render();
      }
      return;
    }

    const stateKey = JSON.stringify({
      s: stateObj.state,
      c: stateObj.attributes.countries,
      u: stateObj.attributes.urls,
      r: stateObj.attributes.series,
    });
    if (stateKey === this._lastStateKey) return;
    this._lastStateKey = stateKey;
    this._render();
  }

  _render() {
    if (!this._config || !this._hass) return;

    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];

    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div style="padding: 16px; text-align: center; color: var(--secondary-text-color);">
            Entity not found: ${entityId}
          </div>
        </ha-card>
      `;
      return;
    }

    const visitors = stateObj.state === "unavailable" ? null : parseInt(stateObj.state, 10);
    const attrs = stateObj.attributes;
    const websiteName = attrs.website_name || "";
    const countries = attrs.countries || [];
    const urls = attrs.urls || [];
    const series = attrs.series || [];

    // Detect visitor change for animation
    const shouldAnimate = this._previousVisitors !== null && this._previousVisitors !== visitors;
    this._previousVisitors = visitors;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --card-bg: var(--ha-card-background, var(--card-background-color, #fff));
          --text-primary: var(--primary-text-color, #212121);
          --text-secondary: var(--secondary-text-color, #727272);
          --text-muted: var(--disabled-text-color, #bdbdbd);
          --accent: var(--primary-color, #03a9f4);
        }

        ha-card {
          position: relative;
          overflow: hidden;
          height: 100%;
          min-height: 200px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 16px;
          box-sizing: border-box;
        }

        .sparkline-bg {
          position: absolute;
          inset: 0;
          pointer-events: none;
          z-index: 0;
        }

        .sparkline-bg svg {
          width: 100%;
          height: 100%;
        }

        .website-name {
          position: absolute;
          top: 16px;
          left: 20px;
          font-size: 0.875rem;
          font-weight: 500;
          color: var(--text-secondary);
          z-index: 1;
          text-decoration: none;
        }

        .countries {
          position: absolute;
          top: 16px;
          right: 20px;
          text-align: right;
          z-index: 1;
        }

        .countries li {
          font-size: 0.75rem;
          color: var(--text-secondary);
          line-height: 1.6;
          font-variant-numeric: tabular-nums;
          list-style: none;
        }

        .countries .count {
          font-weight: 600;
          color: var(--text-primary);
        }

        .visitor-center {
          text-align: center;
          z-index: 1;
          position: relative;
        }

        .visitor-count {
          font-size: 4rem;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          line-height: 1;
          color: var(--text-primary);
          transition: transform 0.3s ease, opacity 0.3s ease;
        }

        .visitor-count.animate {
          animation: pop 0.4s ease;
        }

        @keyframes pop {
          0% { transform: scale(1); }
          50% { transform: scale(1.08); }
          100% { transform: scale(1); }
        }

        .visitor-label {
          font-size: 0.8rem;
          color: var(--text-secondary);
          margin-top: 4px;
        }

        .urls {
          position: absolute;
          bottom: 16px;
          left: 20px;
          z-index: 1;
          max-width: 55%;
        }

        .urls li {
          font-size: 0.75rem;
          color: var(--text-secondary);
          line-height: 1.6;
          font-variant-numeric: tabular-nums;
          list-style: none;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .urls .count {
          font-weight: 600;
          color: var(--text-primary);
        }

        ul {
          margin: 0;
          padding: 0;
        }

        .time-hint {
          position: absolute;
          bottom: 4px;
          left: 8px;
          font-size: 9px;
          color: var(--text-muted);
          opacity: 0.5;
          z-index: 1;
        }

        .peak-hint {
          position: absolute;
          font-size: 10px;
          font-variant-numeric: tabular-nums;
          font-weight: 500;
          color: var(--text-muted);
          opacity: 0.5;
          z-index: 1;
        }

        .peak-left {
          left: 6px;
        }

        .peak-right {
          right: 6px;
        }
      </style>

      <ha-card>
        ${this._renderSparkline(series)}

        <span class="website-name">${this._escapeHtml(websiteName)}</span>

        ${this._renderCountries(countries)}

        <div class="visitor-center">
          <div class="visitor-count ${shouldAnimate ? "animate" : ""}">
            ${visitors === null || isNaN(visitors) ? "..." : visitors}
          </div>
          <div class="visitor-label">active visitors</div>
        </div>

        ${this._renderUrls(urls)}
      </ha-card>
    `;
  }

  _renderSparkline(series) {
    if (!series || series.length < 2) return "";

    const maxVal = Math.max(...series.map((p) => p.y), 1);
    const barCount = series.length;
    const slotWidth = 100 / barCount;
    const gap = slotWidth * 0.15;
    const barWidth = slotWidth - gap;
    const maxHeight = 45;

    let bars = "";
    for (let i = 0; i < series.length; i++) {
      const p = series[i];
      const height = (p.y / maxVal) * maxHeight;
      const x = i * slotWidth + gap / 2;
      const y = 100 - height;
      const h = p.y > 0 ? Math.max(height, 1) : 0;
      bars += `<rect x="${x}" y="${y}" width="${barWidth}" height="${h}" fill="url(#umami-grad)" />`;
    }

    // Peak value positioning
    const peakBottom = maxHeight + 1;

    return `
      <div class="sparkline-bg">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id="umami-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.2" />
              <stop offset="100%" stop-color="var(--accent)" stop-opacity="0.05" />
            </linearGradient>
          </defs>
          ${bars}
        </svg>
      </div>
      ${maxVal > 0 ? `
        <span class="peak-hint peak-left" style="bottom: ${peakBottom}%">${maxVal}</span>
        <span class="peak-hint peak-right" style="bottom: ${peakBottom}%">${maxVal}</span>
      ` : ""}
      <span class="time-hint">-24h</span>
    `;
  }

  _renderCountries(countries) {
    if (!countries || countries.length === 0) return "";
    const items = countries
      .map(
        (c) =>
          `<li>${this._countryFlag(c.country)} <span class="count">${c.visitors}</span></li>`
      )
      .join("");
    return `<ul class="countries">${items}</ul>`;
  }

  _renderUrls(urls) {
    if (!urls || urls.length === 0) return "";
    const items = urls
      .map(
        (u) =>
          `<li><span class="count">${u.visitors}</span> ${this._escapeHtml(this._truncate(u.url, 25))}</li>`
      )
      .join("");
    return `<ul class="urls">${items}</ul>`;
  }

  _countryFlag(countryCode) {
    if (!countryCode || countryCode.length !== 2) return countryCode || "";
    const code = countryCode.toUpperCase();
    const flag = String.fromCodePoint(
      ...[...code].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)
    );
    return flag;
  }

  _truncate(str, max) {
    if (!str) return "";
    return str.length > max ? str.slice(0, max) + "..." : str;
  }

  _escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  getCardSize() {
    return 4;
  }
}

class UmamiAnalyticsCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  _escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;

    // Find all umami sensor entities
    const entities = Object.keys(this._hass.states)
      .filter((eid) => eid.startsWith("sensor.umami_"))
      .sort();

    const options = entities
      .map(
        (eid) =>
          `<option value="${this._escapeHtml(eid)}" ${eid === (this._config?.entity || "") ? "selected" : ""}>${this._escapeHtml(this._hass.states[eid].attributes.friendly_name || eid)}</option>`
      )
      .join("");

    this.shadowRoot.innerHTML = `
      <style>
        .editor {
          padding: 16px;
        }
        label {
          display: block;
          font-weight: 500;
          margin-bottom: 8px;
          color: var(--primary-text-color);
        }
        select {
          width: 100%;
          padding: 8px;
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: 4px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
          font-size: 14px;
        }
      </style>
      <div class="editor">
        <label for="entity">Entity</label>
        <select id="entity">
          <option value="">Select an entity</option>
          ${options}
        </select>
      </div>
    `;

    this.shadowRoot.getElementById("entity").addEventListener("change", (e) => {
      this._config = { ...this._config, entity: e.target.value };
      const event = new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      });
      this.dispatchEvent(event);
    });
  }
}

customElements.define("umami-analytics-card", UmamiAnalyticsCard);
customElements.define("umami-analytics-card-editor", UmamiAnalyticsCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "umami-analytics-card",
  name: "UmamiHA",
  description: "Unofficial realtime visitor analytics card for Umami.",
  preview: true,
  documentationURL: "https://github.com/charlesjones-dev/umamiha",
});

console.info(
  `%c UMAMIHA-CARD %c v${CARD_VERSION} `,
  "color: white; background: #03a9f4; font-weight: bold; padding: 2px 6px; border-radius: 3px 0 0 3px;",
  "color: #03a9f4; background: #e3f2fd; font-weight: bold; padding: 2px 6px; border-radius: 0 3px 3px 0;"
);
