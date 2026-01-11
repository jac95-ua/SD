const API_URL = 'http://localhost:9001/api/status'; // (O similar)

async function loadCPs() {
  const r = await fetch(`${API_BASE}/status/cps`);
  const cps = await r.json();
  const tbody = document.querySelector("#tblCPs tbody");
  tbody.innerHTML = "";
  cps.forEach(cp => {
    const tr = document.createElement("tr");
    if (cp.weatherStatus === "ALERT") tr.classList.add("alert");
    tr.innerHTML = `
      <td>${cp.cp_id}</td>
      <td>${cp.alias ?? ""}</td>
      <td>${cp.location ?? ""}</td>
      <td>${cp.city ?? ""}</td>
      <td>${cp.status ?? ""}</td>
      <td>${cp.temp_c ?? ""}</td>
      <td>${cp.weatherStatus ?? ""}</td>
      <td>${cp.total_sessions ?? ""}</td>
      <td>${cp.total_energy_kwh ?? ""}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadDrivers() {
  const r = await fetch(`${API_BASE}/status/drivers`);
  const drivers = await r.json();
  const tbody = document.querySelector("#tblDrivers tbody");
  tbody.innerHTML = "";
  drivers.forEach(d => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${d.driver_id}</td>
      <td>${d.name ?? ""}</td>
      <td>${d.last_cp_id ?? ""}</td>
      <td>${d.active ? "Sí" : "No"}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function refresh() {
  await Promise.all([loadCPs(), loadDrivers()]);
}

setInterval(refresh, 3000);
refresh();
