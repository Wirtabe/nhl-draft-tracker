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

  teamList.innerHTML = teams.map((team) => `
    <details class="team">
      <summary class="team-summary">
        <div class="team-main">
          <div class="team-rank">#${team.rank}</div>
          <div>
            <div class="team-name">${escapeHtml(team.name)}</div>
            ${team.coach
              ? `<div class="team-coach">Valmentaja: ${escapeHtml(team.coach)}</div>`
              : ""}
          </div>
        </div>

        <div class="team-points">
          ${team.points} <span>p</span>
        </div>
      </summary>

      <div class="players">
        <div class="player-header">
          <span></span>
          <span></span>
          <span>Pisteet</span>
        </div>

        ${(team.players || []).map((player) => `
          <div class="player-row">
            <div class="player-position">${escapeHtml(player.position || "?")}</div>
            <div class="player-name-wrap">
              <div class="player-name">${escapeHtml(player.name)}</div>
              ${player.status === "not-found"
                ? `<div class="player-status">Pelaajalle ei löytynyt tilastoja tälle kaudelle</div>`
                : player.status === "error"
                  ? `<div class="player-status error">Tilastojen haku epäonnistui</div>`
                  : ""}
            </div>
            <div class="player-points">${player.points ?? 0}</div>
          </div>
        `).join("")}
      </div>
    </details>
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

    updated.textContent =
      `Päivitetty ${formatDate(data.generated_at)} -- kausi 2026-27`;

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
