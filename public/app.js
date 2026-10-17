let activeTeams = new Set();
let latestData = null;
let latestHistory = null;

const teamList = document.querySelector("#team-list");
const updated = document.querySelector("#updated");

function formatDate(value) {
  if (!value) return "Ei tietoa";

  return new Intl.DateTimeFormat("fi-FI", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function initializeActiveTeams(teams) {
  if (activeTeams.size > 0) return;

  for (const team of teams || []) {
    if (team?.name) {
      activeTeams.add(team.name);
    }
  }
}

function renderTeamToggleBar(teams) {
  const bar = document.querySelector("#team-toggle-bar");
  if (!bar) return;

  initializeActiveTeams(teams);

  bar.innerHTML = (teams || []).map((team) => {
    const name = team?.name || "";
    const isActive = activeTeams.has(name);

    return `
      <button
        type="button"
        class="team-toggle ${isActive ? "is-active" : "is-inactive"}"
        data-team="${escapeHtml(name)}"
        aria-pressed="${isActive ? "true" : "false"}"
      >
        ${escapeHtml(name)}
      </button>
    `;
  }).join("");

  bar.querySelectorAll(".team-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.team;
      if (!name) return;

      if (activeTeams.has(name)) {
        activeTeams.delete(name);
      } else {
        activeTeams.add(name);
      }

      renderTeamToggleBar(teams);

      if (latestData) {
        renderTeams(latestData.teams || []);
      }

      if (latestHistory) {
        renderHistoryChart(latestHistory);
      }
    });
  });
}

function renderTeams(teams) {
  if (!teamList) return;

  const visibleTeams = (teams || []).filter((team) =>
    activeTeams.has(team.name)
  );

  if (!visibleTeams.length) {
    teamList.innerHTML =
      `<p class="muted">Valitse vähintään yksi joukkue yllä olevasta palkista.</p>`;
    return;
  }

  teamList.innerHTML = visibleTeams.map((team, index) => {
    const rank = Number.isFinite(Number(team.rank))
      ? Number(team.rank)
      : index + 1;

    const teamPoints = Number.isFinite(Number(team.points))
      ? Number(team.points)
      : 0;

    return `
      <details class="team">
        <summary class="team-summary">
          <div class="team-main">
            <div class="team-rank">#${rank}</div>
            <div>
              <div class="team-name">${escapeHtml(team.name)}</div>
              ${team.coach
                ? `<div class="team-coach">Valmentaja: ${escapeHtml(team.coach)}</div>`
                : ""}
            </div>
          </div>

          <div class="team-points">
            ${teamPoints} <span>p</span>
          </div>
        </summary>

        <div class="players">
          <div class="player-header">
            <span></span>
            <span></span>
            <span>Pisteet</span>
          </div>

          ${(() => {
            let previousPosition = null;

            return (team.players || []).map((player) => {
              const playerPoints = Number.isFinite(Number(player.points))
                ? Number(player.points)
                : 0;

              const currentPosition = player.position || "?";
              const spacer =
                previousPosition !== null &&
                previousPosition !== currentPosition
                  ? `<div class="position-spacer" aria-hidden="true"></div>`
                  : "";

              previousPosition = currentPosition;

              return `
                ${spacer}
                <div class="player-row">
                  <div class="player-position">${escapeHtml(currentPosition)}</div>
                  <div class="player-name-wrap">
                    <div class="player-name">${escapeHtml(player.name)}</div>
                    ${player.status === "unresolved"
                      ? `<div class="player-status error">NHL-pelaajaa ei tunnistettu</div>`
                      : player.status === "stale"
                        ? `<div class="player-status">Näytetään viimeisin onnistunut pistetieto</div>`
                        : player.status === "no-stats"
                          ? `<div class="player-status">Ei vielä tilastopisteitä tällä kaudella</div>`
                          : ""}
                  </div>
                  <div class="player-points">${playerPoints}</div>
                </div>
              `;
            }).join("");
          })()}
        </div>
      </details>
    `;
  }).join("");
}

function renderHistoryChart(history) {
  const chart = document.querySelector("#history-chart");
  const legend = document.querySelector("#history-legend");

  if (!chart || !legend) return;

  const dates = history?.dates || [];
  const series = (history?.series || []).filter((item) =>
    activeTeams.has(item.team)
  );

  if (!dates.length) {
    chart.innerHTML =
      `<p class="muted history-empty">Historiaa ei ole vielä saatavilla.</p>`;
    legend.innerHTML = "";
    return;
  }

  if (!series.length) {
    chart.innerHTML =
      `<p class="muted history-empty">Valitse vähintään yksi joukkue yllä olevasta palkista.</p>`;
    legend.innerHTML = "";
    return;
  }

  const width = 960;
  const height = 360;
  const pad = { top: 20, right: 24, bottom: 42, left: 48 };
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;

  const maxPoints = Math.max(
    1,
    ...series.flatMap((item) => item.points || []).map(Number)
  );

  const x = (index) => {
    if (dates.length === 1) {
      return pad.left + innerWidth / 2;
    }
    return pad.left + (index / (dates.length - 1)) * innerWidth;
  };

  const y = (value) =>
    pad.top +
    innerHeight -
    (Number(value || 0) / maxPoints) * innerHeight;

  const colors = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
    "#7f7f7f"
  ];

  const ticks = Array.from(
    { length: 5 },
    (_, index) => Math.round((maxPoints * index) / 4)
  );

  const grid = ticks.map((value) => `
    <line
      x1="${pad.left}"
      y1="${y(value)}"
      x2="${width - pad.right}"
      y2="${y(value)}"
      class="chart-grid"
    />
    <text
      x="${pad.left - 10}"
      y="${y(value) + 4}"
      text-anchor="end"
      class="chart-axis-label"
    >${value}</text>
  `).join("");

  const tickIndexes = [...new Set([
    0,
    Math.floor((dates.length - 1) * 0.25),
    Math.floor((dates.length - 1) * 0.5),
    Math.floor((dates.length - 1) * 0.75),
    dates.length - 1
  ])];

  const labels = tickIndexes.map((index) => {
    const [, month, day] = String(dates[index]).split("-");

    return `
      <text
        x="${x(index)}"
        y="${height - 14}"
        text-anchor="middle"
        class="chart-axis-label"
      >${Number(day)}.${Number(month)}.</text>
    `;
  }).join("");

  const lines = series.map((item, seriesIndex) => {
    const points = (item.points || []).map((value, index) =>
      `${x(index)},${y(value)}`
    ).join(" ");

    const lastIndex = Math.max(0, (item.points || []).length - 1);
    const lastValue = Number(item.points?.[lastIndex] || 0);
    const color = colors[seriesIndex % colors.length];

    return `
      <polyline
        points="${points}"
        fill="none"
        stroke="${color}"
        stroke-width="2.5"
        stroke-linejoin="round"
        stroke-linecap="round"
        vector-effect="non-scaling-stroke"
      />
      <circle
        cx="${x(lastIndex)}"
        cy="${y(lastValue)}"
        r="3.5"
        fill="${color}"
      />
    `;
  }).join("");

  chart.innerHTML = `
    <div class="chart-scroll">
      <svg
        class="history-svg"
        viewBox="0 0 ${width} ${height}"
        role="img"
        aria-label="Joukkueiden pistekehitys"
      >
        ${grid}
        ${labels}
        ${lines}
      </svg>
    </div>
  `;

  legend.innerHTML = series.map((item, index) => `
    <div class="legend-item">
      <span
        class="legend-swatch"
        style="background:${colors[index % colors.length]}"
      ></span>
      <span>${escapeHtml(item.team)}</span>
      <strong>${Number(item.points?.at(-1) || 0)} p</strong>
    </div>
  `).join("");
}

async function loadData() {
  try {
    const response = await fetch(`./data.json?v=${Date.now()}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    latestData = data;

    initializeActiveTeams(data.teams || []);
    renderTeamToggleBar(data.teams || []);
    renderTeams(data.teams || []);

    if (latestHistory) {
      renderHistoryChart(latestHistory);
    }

    const statsInfo =
      Number.isFinite(Number(data.players_with_stats))
        ? ` · tilastot ${data.players_with_stats}/${data.player_count ?? "?"} pelaajalle`
        : "";

    updated.textContent =
      `Päivitetty ${formatDate(data.generated_at)} · kausi ${data.season}${statsInfo}`;
  } catch (error) {
    console.error(error);
    updated.textContent = "Tietojen lataus epäonnistui.";

    if (teamList) {
      teamList.innerHTML = `
        <p class="error">
          Raportin tietoja ei voitu ladata. Yritä päivittää sivu myöhemmin.
        </p>
      `;
    }
  }
}

async function loadHistory() {
  try {
    const response = await fetch(`./history.json?v=${Date.now()}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    latestHistory = await response.json();

    if (latestData) {
      renderHistoryChart(latestHistory);
    }
  } catch (error) {
    console.error(error);
    renderHistoryChart(null);
  }
}

loadData();
loadHistory();
