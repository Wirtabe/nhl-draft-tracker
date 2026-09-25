async function load() {
  const meta = document.querySelector("#meta");
  const summary = document.querySelector("#summary");
  const teams = document.querySelector("#teams");
  const status = document.querySelector("#status");

  try {
    const response = await fetch(`./data.json?cacheBust=${Date.now()}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    const updated = new Date(data.generated_at);
    meta.textContent =
      `Draft-kausi ${data.season.slice(0, 4)}–${data.season.slice(4)} -- ` +
      `Pistelasku: kenttäpelaajilla tehopisteet, maalivahdeilla voitot x2 + nollapelit x2 + tehopisteet -- Päivitetty ${updated.toLocaleString("fi-FI")}`;

    summary.innerHTML = data.teams.slice(0, 3).map(team => `
      <article class="card">
        <div class="rank">#${team.rank}</div>
        <div class="name">${escapeHtml(team.name)}</div>
        <div class="points">${team.points}</div>
        <div class="muted">pistettä</div>
      </article>
    `).join("");

    teams.innerHTML = data.teams.map(team => `
      <article class="team">
        <div class="team-header">
          <div>
            <div class="team-name">#${team.rank} ${escapeHtml(team.name)}</div>
            ${team.owner ? `<div class="team-owner">${escapeHtml(team.owner)}</div>` : ""}
          </div>
          <div class="team-points">${team.points} p</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Pelaaja</th>
              <th>P</th>
            </tr>
          </thead>
          <tbody>
            ${team.players.map(player => `
              <tr>
                <td>
                  ${escapeHtml(player.name)}
                  ${player.status === "error"
                    ? `<div class="error">Tietojen haku epäonnistui</div>`
                    : player.warning
                      ? `<div class="warning">${escapeHtml(player.warning)}</div>`
                      : ""}
                </td>
                <td><strong>${player.points ?? 0}</strong></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </article>
    `).join("");

    status.textContent =
      data.api_status === "ok"
        ? "Kaikki pelaajat päivitettiin onnistuneesti."
        : "Huomio: joidenkin pelaajien tilastojen päivityksessä oli ongelmia.";

  } catch (error) {
    meta.textContent = "Raportin tietojen lataus epäonnistui.";
    status.textContent = error.message;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

load();
