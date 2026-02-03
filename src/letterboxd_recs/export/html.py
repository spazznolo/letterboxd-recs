from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ExportFilm:
    title: str
    year: int | None
    genres: list[str]
    score: float
    score_scaled: float
    letterboxd_url: str | None
    providers: dict[str, bool]
    stream: bool


def render_recs_html(
    username: str,
    films: Iterable[ExportFilm],
    provider_columns: list[str],
    out_path: Path,
) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "username": username,
        "providers": provider_columns,
        "films": [film.__dict__ for film in films],
    }
    data_json = json.dumps(payload, ensure_ascii=True)
    html = _HTML_TEMPLATE.replace("/*__DATA__*/", data_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Letterboxd Recs</title>
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
    <link
      href=\"https://fonts.googleapis.com/css2?family=Fraunces:wght@400;600;700&family=Space+Grotesk:wght@400;500;600&display=swap\"
      rel=\"stylesheet\"
    />
    <style>
      :root {
        --bg: #0f141a;
        --panel: #151e26;
        --panel-2: #1b2633;
        --text: #e8eef5;
        --muted: #9fb0c3;
        --accent: #7cf6c6;
        --accent-2: #59b7ff;
        --warn: #f9c784;
        --shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        font-family: \"Space Grotesk\", system-ui, sans-serif;
        background: radial-gradient(circle at top left, #1a2531 0%, #0f141a 45%, #0b0f14 100%);
        color: var(--text);
        min-height: 100vh;
      }

      header {
        padding: 36px clamp(20px, 4vw, 64px) 24px;
      }

      h1 {
        font-family: \"Fraunces\", serif;
        font-weight: 700;
        font-size: clamp(28px, 5vw, 52px);
        margin: 0 0 8px;
        letter-spacing: 0.5px;
      }

      .subtitle {
        color: var(--muted);
        font-size: 15px;
      }

      .filters {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        padding: 0 clamp(20px, 4vw, 64px) 24px;
      }

      .filter-card {
        background: var(--panel);
        padding: 12px 14px;
        border-radius: 14px;
        box-shadow: var(--shadow);
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--muted);
      }

      select, input {
        background: var(--panel-2);
        border: 1px solid #223242;
        border-radius: 10px;
        padding: 8px 10px;
        color: var(--text);
        font-size: 14px;
      }

      .toggle {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
      }

      .content {
        padding: 0 clamp(20px, 4vw, 64px) 60px;
      }

      .grid {
        display: grid;
        gap: 16px;
      }

      .card {
        background: linear-gradient(135deg, rgba(34,46,61,0.9), rgba(17,25,35,0.9));
        border: 1px solid #27384a;
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: var(--shadow);
        display: grid;
        grid-template-columns: 80px 1fr auto;
        gap: 14px;
        align-items: center;
      }

      .rank {
        font-family: \"Fraunces\", serif;
        font-size: 26px;
        color: var(--accent);
      }

      .title {
        font-size: 18px;
        margin: 0 0 6px;
      }

      .meta {
        color: var(--muted);
        font-size: 13px;
      }

      .score {
        font-size: 18px;
        font-weight: 600;
        color: var(--accent-2);
      }

      .pill {
        display: inline-flex;
        padding: 4px 8px;
        border-radius: 999px;
        font-size: 12px;
        background: rgba(124, 246, 198, 0.15);
        color: var(--accent);
        margin-right: 6px;
      }

      .pill.stream {
        background: rgba(89, 183, 255, 0.2);
        color: var(--accent-2);
      }

      .provider-list {
        margin-top: 8px;
        color: var(--muted);
        font-size: 12px;
      }

      @media (max-width: 720px) {
        .card {
          grid-template-columns: 1fr;
          text-align: left;
        }
        .score {
          justify-self: start;
        }
      }
    </style>
  </head>
  <body>
    <header>
      <h1>Letterboxd Recs</h1>
      <div class=\"subtitle\" id=\"subtitle\"></div>
    </header>

    <section class=\"filters\">
      <div class=\"filter-card\">
        <label for=\"search\">Search</label>
        <input id=\"search\" placeholder=\"Title contains...\" />
      </div>
      <div class=\"filter-card\">
        <label for=\"provider\">Provider</label>
        <select id=\"provider\"></select>
      </div>
      <div class=\"filter-card\">
        <label for=\"genre\">Genre</label>
        <select id=\"genre\"></select>
      </div>
      <div class=\"filter-card\">
        <label for=\"minYear\">Min Year</label>
        <input id=\"minYear\" type=\"number\" placeholder=\"e.g. 2010\" />
      </div>
      <div class=\"filter-card\">
        <label>Stream Only</label>
        <div class=\"toggle\">
          <input id=\"streamOnly\" type=\"checkbox\" />
          <span>Require free stream/play</span>
        </div>
      </div>
    </section>

    <section class=\"content\">
      <div class=\"grid\" id=\"grid\"></div>
    </section>

    <script id="recs-data" type="application/json">/*__DATA__*/</script>
    <script>
      window.addEventListener("DOMContentLoaded", () => {
        let data;
        try {
          const raw = document.getElementById("recs-data").textContent || "{}";
          data = JSON.parse(raw);
        } catch (err) {
          console.error("Failed to parse recs data", err);
          data = { username: "unknown", generated_at: "", providers: [], films: [] };
        }
        const subtitle = document.getElementById("subtitle");
        if (subtitle) {
          subtitle.textContent = `Generated for ${data.username} on ${data.generated_at}`;
        }

        const providerSelect = document.getElementById("provider");
        const genreSelect = document.getElementById("genre");
        const grid = document.getElementById("grid");
        if (!providerSelect || !genreSelect || !grid) {
          console.error("Missing expected DOM elements for filters.");
        }

        const allGenres = new Set();
        data.films.forEach((film) => {
          (film.genres || []).forEach((g) => allGenres.add(g));
        });

        const addOption = (select, value, label) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          select.appendChild(option);
        };

        if (providerSelect && genreSelect) {
          addOption(providerSelect, "", "All providers");
          data.providers.forEach((p) => addOption(providerSelect, p, p.replace(/_/g, " ")));
          addOption(genreSelect, "", "All genres");
          [...allGenres].sort().forEach((g) => addOption(genreSelect, g, g));
        }

        const render = () => {
          const searchEl = document.getElementById("search");
          const minYearEl = document.getElementById("minYear");
          const streamEl = document.getElementById("streamOnly");
          const search = searchEl ? searchEl.value.toLowerCase() : "";
          const provider = providerSelect ? providerSelect.value : "";
          const genre = genreSelect ? genreSelect.value : "";
          const minYear = minYearEl ? parseInt(minYearEl.value, 10) : NaN;
          const streamOnly = streamEl ? streamEl.checked : false;

          const filtered = data.films.filter((film) => {
            if (search && !film.title.toLowerCase().includes(search)) return false;
            if (provider && !film.providers[provider]) return false;
            if (genre && !(film.genres || []).includes(genre)) return false;
            if (!isNaN(minYear) && film.year && film.year < minYear) return false;
            if (streamOnly && !film.stream) return false;
            return true;
          });

          if (!grid) {
            return;
          }
          grid.innerHTML = "";
          if (!filtered.length) {
            grid.innerHTML = '<div class="meta">No films match the current filters.</div>';
            return;
          }
          filtered.forEach((film, idx) => {
            const card = document.createElement("div");
            card.className = "card";
            const providers = Object.entries(film.providers)
              .filter(([_, v]) => v)
              .map(([k]) => k.replace(/_/g, " "));

            card.innerHTML = `
              <div class="rank">${idx + 1}</div>
              <div>
                <div class="title">${film.title}${film.year ? " (" + film.year + ")" : ""}</div>
                <div class="meta">${film.genres.join(", ") || "Unknown genre"}</div>
                <div class="provider-list">
                  ${film.stream ? '<span class="pill stream">Stream</span>' : '<span class="pill">Rent only</span>'}
                  ${providers.map((p) => `<span class="pill">${p}</span>`).join(" ")}
                </div>
              </div>
              <div class="score">${film.score_scaled.toFixed(2)}</div>
            `;
            grid.appendChild(card);
          });
        };

        ["search", "provider", "genre", "minYear", "streamOnly"].forEach((id) => {
          const el = document.getElementById(id);
          if (!el) return;
          el.addEventListener("input", render);
          el.addEventListener("change", render);
        });

        render();
      });
    </script>
  </body>
</html>
"""
