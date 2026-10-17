
function renderHistoryChart(history) {
  const chart = document.querySelector("#history-chart");
  const legend = document.querySelector("#history-legend");
  if (!chart || !legend) return;

  const dates = history?.dates || [];
  const series = history?.series || [];
  if (!dates.length || !series.length) {
    chart.innerHTML = `<p class="muted history-empty">Historiaa ei ole vielä saatavilla.</p>`;
    legend.innerHTML = "";
    return;
  }

  const width = 960, height = 360;
  const pad = {top: 20, right: 24, bottom: 42, left: 48};
  const iw = width - pad.left - pad.right;
  const ih = height - pad.top - pad.bottom;
  const maxPoints = Math.max(1, ...series.flatMap(s => s.points || []).map(Number));
  const x = i => dates.length === 1 ? pad.left + iw/2 : pad.left + i/(dates.length-1)*iw;
  const y = v => pad.top + ih - Number(v || 0)/maxPoints*ih;
  const colors = ["#1f77b4","#d62728","#2ca02c","#9467bd","#ff7f0e","#17becf","#8c564b","#7f7f7f"];

  const ticks = Array.from({length:5}, (_,i)=>Math.round(maxPoints*i/4));
  const grid = ticks.map(v => `
    <line x1="${pad.left}" y1="${y(v)}" x2="${width-pad.right}" y2="${y(v)}" class="chart-grid"/>
    <text x="${pad.left-10}" y="${y(v)+4}" text-anchor="end" class="chart-axis-label">${v}</text>
  `).join("");

  const idxs = [...new Set([0, Math.floor((dates.length-1)*.25), Math.floor((dates.length-1)*.5), Math.floor((dates.length-1)*.75), dates.length-1])];
  const labels = idxs.map(i => {
    const [yy,mm,dd] = dates[i].split("-");
    return `<text x="${x(i)}" y="${height-14}" text-anchor="middle" class="chart-axis-label">${Number(dd)}.${Number(mm)}.</text>`;
  }).join("");

  const lines = series.map((s,si) => {
    const pts = (s.points || []).map((v,i)=>`${x(i)},${y(v)}`).join(" ");
    const li = Math.max(0,(s.points||[]).length-1);
    return `<polyline points="${pts}" fill="none" stroke="${colors[si%colors.length]}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
    <circle cx="${x(li)}" cy="${y(s.points?.[li]||0)}" r="3.5" fill="${colors[si%colors.length]}"/>`;
  }).join("");

  chart.innerHTML = `<div class="chart-scroll"><svg class="history-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Joukkueiden pistekehitys">${grid}${labels}${lines}</svg></div>`;

  legend.innerHTML = series.map((s,i)=>`
    <div class="legend-item">
      <span class="legend-swatch" style="background:${colors[i%colors.length]}"></span>
      <span>${escapeHtml(s.team)}</span>
      <strong>${Number(s.points?.at(-1)||0)} p</strong>
    </div>
  `).join("");
}

async function loadHistory() {
  try {
    const response = await fetch(`./history.json?v=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderHistoryChart(await response.json());
  } catch (error) {
    console.error(error);
    renderHistoryChart(null);
  }
}

const teamSelect = document.querySelector("#team-select");
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

function renderTeams(teams) {
  if (!teams.length) {
    teamList.innerHTML =
      `<p class="muted">Valitulla suodatuksella ei löytynyt joukkueita.</p>`;
    return;
  }

  teamList.innerHTML = teams.map((team, index) => {
    // If rank is missing from data.json, keep the current team order
    // and use it as the default ranking: 1, 2, 3, ...
    const rank = Number.isFinite(Number(team.rank))
      ? Number(team.rank)
      : index + 1;

    // If team points are missing, null, undefined or invalid, show 0.
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
              previousPosition !== null && previousPosition !== currentPosition
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

async function loadData() {
  try {
    const response = await fetch(`./data.json?v=${Date.now()}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    const statsInfo =
      Number.isFinite(Number(data.players_with_stats))
        ? ` · tilastot ${data.players_with_stats}/${data.player_count ?? "?"} pelaajalle`
        : "";

    updated.textContent =
      `Päivitetty ${formatDate(data.generated_at)} · kausi ${data.season}${statsInfo}`;

    teamSelect.innerHTML = `
      <option value="all">Kaikki joukkueet</option>
      ${(data.teams || []).map((team) => `
        <option value="${escapeHtml(team.name)}">${escapeHtml(team.name)}</option>
      `).join("")}
    `;

    const render = () => {
      const selected = teamSelect.value;
      const teams = selected === "all"
        ? data.teams
        : data.teams.filter((team) => team.name === selected);

      renderTeams(teams);
    };

    teamSelect.addEventListener("change", render);
    render();
  } catch (error) {
    console.error(error);
    updated.textContent = "Tietojen lataus epäonnistui.";
    teamList.innerHTML = `
      <p class="error">
        Raportin tietoja ei voitu ladata. Yritä päivittää sivu myöhemmin.
      </p>
    `;
  }
}

loadData();

loadHistory();
