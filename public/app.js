const teamSelect = document.querySelector("#team-select");
const teamList = document.querySelector("#team-list");
const updated = document.querySelector("#updated");

const positionNames = {
  C: "Keskushyökkääjät",
  LW: "Vasen laitahyökkääjät",
  RW: "Oikea laitahyökkääjät",
  D: "Puolustajat",
  G: "Maalivahdit",
  F: "Hyökkääjät",
  "?": "Pelipaikka tuntematon"
};

const positionOrder = ["C", "LW", "RW", "F", "D", "G", "?"];

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
    teamList.innerHTML = `<p class="muted">Valitulla suodatuksella ei löytynyt joukkueita.</p>`;
    return;
  }

  teamList.innerHTML = teams.map((team) => {
    const groups = new Map();

    for (const player of team.players || []) {
      const position = player.position || "?";
      if (!groups.has(position)) groups.set(position, []);
      groups.get(position).push(player);
    }

    const orderedGroups = [...groups.entries()].sort(
      (a, b) => positionOrder.indexOf(a[0]) - positionOrder.indexOf(b[0])
    );

    const positionHtml = orderedGroups.map(([position, players]) => `
      <details class="position-group">
        <summary>
          <span>${escapeHtml(positionNames[position] || position)}</span>
          <span class="position-count">${players.length} pelaaja${players.length === 1 ? "" : "a"}</span>
        </summary>

        <div class="player-list">
          ${players.map((player) => `
            <div class="player-row">
              <div>
                <div class="player-name">${escapeHtml(player.name)}</div>
                <div class="player-meta">
                  ${escapeHtml(player.position || "?")}
                  ${player.status === "not-found" ? " · ei tilastoriviä" : ""}
                  ${player.status === "error" ? " · virhe haettaessa" : ""}
                </div>
              </div>
              <div class="player-stats">
                <span>${player.goals ?? 0}</span>
                <span>${player.assists ?? 0}</span>
                <strong>${player.points ?? 0}</strong>
              </div>
            </div>
          `).join("")}
        </div>
      </details>
    `).join("");

    return `
      <article class="team">
        <div class="team-header">
          <div>
            <div class="team-rank">#${team.rank}</div>
            <div class="team-name">${escapeHtml(team.name)}</div>
            ${team.owner ? `<div class="team-owner">${escapeHtml(team.owner)}</div>` : ""}
          </div>
          <div class="team-points">${team.points} <span>p</span></div>
        </div>

        <div class="position-header">
          <span>Pelaaja</span>
          <div class="player-stats">
            <span>M</span>
            <span>S</span>
            <span>P</span>
          </div>
        </div>

        <div class="positions">
          ${positionHtml}
        </div>
      </article>
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

    updated.textContent =
      `Päivitetty ${formatDate(data.generated_at)} · kausi ${data.season}`;

    teamSelect.innerHTML = `
      <option value="all">Kaikki joukkueet</option>
      ${(data.teams || []).map(team => `
        <option value="${escapeHtml(team.name)}">${escapeHtml(team.name)}</option>
      `).join("")}
    `;

    const render = () => {
      const selected = teamSelect.value;
      const teams = selected === "all"
        ? data.teams
        : data.teams.filter(team => team.name === selected);

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
