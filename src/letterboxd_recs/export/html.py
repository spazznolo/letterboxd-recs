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
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Letterboxd Recs</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
      rel="stylesheet"
    />
    <style>
      :root {
        --bg: #0d0f11;
        --panel: #14181c;
        --text: #f3f3f3;
        --muted: #9aa3ad;
        --rule: #252a30;
        --accent: #f3f3f3;
        --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        font-family: "EB Garamond", serif;
        background: var(--bg);
        color: var(--text);
        min-height: 100vh;
      }

      .toolbar {
        padding: 28px clamp(20px, 6vw, 96px) 14px;
      }

      .subtitle {
        color: var(--muted);
        font-size: 12px;
        font-family: var(--mono);
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .content {
        padding: 0 clamp(20px, 6vw, 96px) 60px;
      }

      .grid {
        display: grid;
        gap: 0;
        border-top: 1px solid var(--rule);
      }

      .row,
      .controls-row {
        display: grid;
        grid-template-columns: 62px 70px 1.6fr 86px 1.6fr 130px;
        gap: 12px;
        align-items: center;
        padding: 10px 4px;
        border-bottom: 1px solid var(--rule);
        font-size: 14px;
      }

      .controls-row {
        font-family: var(--mono);
        font-size: 12px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }

      .controls-row select,
      .controls-row input {
        background: var(--panel);
        border: 1px solid var(--rule);
        padding: 6px 8px;
        color: var(--text);
        font-size: 12px;
        font-family: var(--mono);
      }

      .controls-row input[type="number"] {
        max-width: 72px;
      }

      .controls-row .toggle {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
        text-transform: none;
        letter-spacing: 0.02em;
      }

      .row span {
        font-family: var(--mono);
      }

      .row .title {
        font-family: "EB Garamond", serif;
        font-size: 16px;
        font-weight: 600;
      }

      .row .genres {
        color: var(--muted);
        font-size: 13px;
      }

      .row .availability {
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 11px;
        color: var(--muted);
      }

      .row .availability strong {
        color: var(--accent);
      }

      @media (max-width: 900px) {
        .row,
        .controls-row {
          grid-template-columns: 52px 64px 1.4fr 76px 1.2fr 90px;
          font-size: 13px;
        }
        .controls-row input[type="number"] {
          max-width: 64px;
        }
      }

      @media (max-width: 700px) {
        .row,
        .controls-row {
          grid-template-columns: 1fr;
          gap: 6px;
        }
        .row span {
          font-family: "EB Garamond", serif;
        }
      }
    </style>
  </head>
  <body>
    <section class="toolbar">
      <div class="subtitle" id="subtitle"></div>
    </section>

    <section class="content">
      <div class="grid" id="grid">
        <div class="controls-row">
          <span>Rank</span>
          <span>Score</span>
          <span>Provider <select id="provider"></select></span>
          <span>Min Year <input id="minYear" type="number" placeholder="min" /></span>
          <span>Genre <select id="genre"></select></span>
          <span>Stream <label class="toggle"><input id="streamOnly" type="checkbox" /> Only</label></span>
        </div>
        <div id="rows"></div>
      </div>
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
          subtitle.textContent = `Last Updated: ${data.generated_at}`;
        }

        const providerSelect = document.getElementById("provider");
        const genreSelect = document.getElementById("genre");
        const minYearInput = document.getElementById("minYear");
        const streamOnlyInput = document.getElementById("streamOnly");
        const rows = document.getElementById("rows");

        if (!providerSelect || !genreSelect || !minYearInput || !streamOnlyInput || !rows) return;

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

        addOption(providerSelect, "", "All");
        data.providers.forEach((p) => addOption(providerSelect, p, p.replace(/_/g, " ")));
        addOption(genreSelect, "", "All");
        [...allGenres].sort().forEach((g) => addOption(genreSelect, g, g));

        const render = () => {
          const provider = providerSelect.value;
          const genre = genreSelect.value;
          const minYear = parseInt(minYearInput.value, 10);
          const streamOnly = streamOnlyInput.checked;

          const filtered = data.films.filter((film) => {
            if (provider && !film.providers[provider]) return false;
            if (genre && !(film.genres || []).includes(genre)) return false;
            if (!isNaN(minYear) && film.year && film.year < minYear) return false;
            if (streamOnly && !film.stream) return false;
            return true;
          });

          rows.innerHTML = "";

          if (!filtered.length) {
            const empty = document.createElement("div");
            empty.className = "row";
            empty.innerHTML = '<span class="genres">No films match the current filters.</span>';
            rows.appendChild(empty);
            return;
          }

          filtered.forEach((film, idx) => {
            const row = document.createElement("div");
            row.className = "row";
            const genres = (film.genres || []).join(", ") || "Unknown";
            const availability = film.stream ? "stream" : "rent";
            row.innerHTML = `
              <span>${idx + 1}</span>
              <span>${film.score.toFixed(2)}</span>
              <span class="title">${film.title}</span>
              <span>${film.year || "-"}</span>
              <span class="genres">${genres}</span>
              <span class="availability"><strong>${availability}</strong></span>
            `;
            rows.appendChild(row);
          });
        };

        providerSelect.addEventListener("change", render);
        genreSelect.addEventListener("change", render);
        minYearInput.addEventListener("input", render);
        streamOnlyInput.addEventListener("change", render);

        render();
      });
    </script>
  </body>
</html>
"""
