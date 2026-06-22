from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


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
    current_rank: int | None = None
    previous_rank: int | None = None
    rank_change: int | None = None


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


def load_previous_rankings(out_path: Path) -> dict[tuple[str, str], int]:
    if not out_path.exists():
        return {}
    try:
        html = out_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    match = re.search(
        r'<script id="recs-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if match is None:
        return {}
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}

    rankings: dict[tuple[str, str], int] = {}
    for idx, film in enumerate(payload.get("films", []), start=1):
        key = film_identity_key(film)
        if key is None or key in rankings:
            continue
        rankings[key] = idx
    return rankings


def film_identity_key(film: ExportFilm | dict[str, Any]) -> tuple[str, str] | None:
    if isinstance(film, ExportFilm):
        letterboxd_url = film.letterboxd_url
        title = film.title
        year = film.year
    else:
        letterboxd_url = film.get("letterboxd_url")
        title = film.get("title")
        year = film.get("year")

    if isinstance(letterboxd_url, str) and letterboxd_url:
        return ("url", letterboxd_url.rstrip("/"))
    if isinstance(title, str) and title:
        year_text = "" if year is None else str(year)
        return ("title-year", f"{title.strip().lower()}::{year_text}")
    return None


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Letterboxd Recs</title>
    <style>
      :root {
        --bg: #0d0f11;
        --panel: #14181c;
        --text: #f3f3f3;
        --muted: #9aa3ad;
        --rule: #252a30;
        --accent: #f3f3f3;
        --mono: "SF Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        font-family: "Graphik", "Helvetica Neue", Arial, sans-serif;
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
        grid-template-columns: 62px 90px 70px 1.6fr 86px 1.6fr 130px;
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
        font-family: "Tiempos Headline", "Times New Roman", serif;
        font-size: 16px;
        font-weight: 600;
      }

      .row .title-link {
        color: var(--text);
        text-decoration: none;
      }

      .row .title-link:hover {
        text-decoration: underline;
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

      .row .movement {
        font-size: 12px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }

      .row .movement.up {
        color: #7dd3a0;
      }

      .row .movement.down {
        color: #f59e8b;
      }

      .row .movement.flat,
      .row .movement.new {
        color: var(--muted);
      }

      @media (max-width: 900px) {
        .row,
        .controls-row {
          grid-template-columns: 52px 82px 64px 1.4fr 76px 1.2fr 90px;
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
          font-family: "Tiempos Headline", "Times New Roman", serif;
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
          <span>Movement</span>
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

        const formatMovement = (rankChange, previousRank) => {
          if (previousRank === null || previousRank === undefined) {
            return '<span class="movement new">NEW</span>';
          }
          if (!Number.isFinite(Number(rankChange)) || Number(rankChange) === 0) {
            return '<span class="movement flat">-</span>';
          }
          if (Number(rankChange) > 0) {
            return `<span class="movement up">↑${Number(rankChange)}</span>`;
          }
          return `<span class="movement down">↓${Math.abs(Number(rankChange))}</span>`;
        };

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
            const normalizedScore = Number.isFinite(Number(film.score_scaled))
              ? Number(film.score_scaled)
              : Number(film.score);
            const displayScore = Math.max(0, Math.min(10, Number.isFinite(normalizedScore) ? normalizedScore : 0));
            const titleHtml = film.letterboxd_url
              ? `<a class="title title-link" href="${film.letterboxd_url}" target="_blank" rel="noopener noreferrer">${film.title}</a>`
              : `<span class="title">${film.title}</span>`;
            row.innerHTML = `
              <span>${idx + 1}</span>
              <span>${formatMovement(film.rank_change, film.previous_rank)}</span>
              <span>${displayScore.toFixed(2)}</span>
              ${titleHtml}
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
