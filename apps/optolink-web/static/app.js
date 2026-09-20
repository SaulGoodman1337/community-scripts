let datapoints = [];
let config = {};

const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

async function api(url, options = {}) {
  const response = await fetch(url, {headers: {"Content-Type":"application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : response.statusText);
  return data;
}

function valueText(dp) {
  if (dp.value === null || dp.value === undefined) return "–";
  return String(dp.value) + (dp.unit ? " " + dp.unit : "");
}

async function loadConfig() {
  config = await api("/api/config");
  $("writeState").textContent = config.allow_writes ? "aktiv" : "gesperrt";
  $("configResult").textContent = JSON.stringify(config, null, 2);
}

async function loadStatus() {
  try {
    const s = await api("/api/status");
    $("deviceIdent").textContent = s.device_ident || "–";
    $("tcpState").textContent = s.tcp.ok ? "online" : "offline";
    $("mqttState").textContent = !s.mqtt.configured ? "nicht konfiguriert" : (s.mqtt.connected ? "online (" + s.mqtt.topic_count + ")" : "offline");
    $("health").textContent = s.tcp.ok ? "Optolink online" : "Optolink offline";
    $("health").className = "health " + (s.tcp.ok ? "ok" : "bad");
  } catch (e) {
    $("health").textContent = e.message;
    $("health").className = "health bad";
  }
}

async function loadDatapoints() {
  const data = await api("/api/datapoints");
  datapoints = data.items;
  renderCards();
  renderTable();
}

function renderCards() {
  $("cards").innerHTML = datapoints.filter(d => d.featured).map(dp =>
    '<article class="card">' +
    '<span>' + esc(dp.label) + '</span>' +
    '<strong>' + esc(valueText(dp)) + '</strong>' +
    '<small>0x' + esc(dp.address) + '</small>' +
    '</article>'
  ).join("");
}

function renderTable() {
  const needle = $("filter").value.trim().toLowerCase();
  const rows = datapoints.filter(dp => !needle || (dp.label + " " + dp.name + " " + dp.group + " " + dp.address).toLowerCase().includes(needle));
  $("dpBody").innerHTML = rows.map(dp => {
    const writeUi = dp.write_available
      ? '<div class="writebox"><input type="number" step="' + esc(dp.step ?? "any") + '" min="' + esc(dp.min ?? "") + '" max="' + esc(dp.max ?? "") + '" value="' + esc(dp.value ?? "") + '" data-write="' + esc(dp.name) + '"><button data-write-btn="' + esc(dp.name) + '">Set</button></div>'
      : "";
    return '<tr>' +
      '<td><strong>' + esc(dp.label) + '</strong><small>' + esc(dp.name) + '</small></td>' +
      '<td>' + esc(dp.group) + '</td>' +
      '<td><code>0x' + esc(dp.address) + '</code> / ' + esc(dp.length) + ' B</td>' +
      '<td>' + esc(valueText(dp)) + '</td>' +
      '<td><div class="actions"><button class="secondary" data-read="' + esc(dp.name) + '">Read</button>' + writeUi + '</div></td>' +
      '</tr>';
  }).join("");
}

async function readDp(name, button) {
  button.disabled = true;
  try {
    const result = await api("/api/datapoints/" + encodeURIComponent(name) + "/read", {method:"POST"});
    const dp = datapoints.find(x => x.name === name);
    if (dp) dp.value = result.value;
    renderCards();
    renderTable();
  } catch (e) {
    alert("Read fehlgeschlagen: " + e.message);
  } finally {
    button.disabled = false;
  }
}

async function writeDp(name, button) {
  const input = document.querySelector('[data-write="' + CSS.escape(name) + '"]');
  if (!input || input.value === "") return;
  if (!confirm(name + " wirklich auf " + input.value + " setzen?")) return;
  button.disabled = true;
  try {
    await api("/api/datapoints/" + encodeURIComponent(name) + "/write", {method:"POST", body: JSON.stringify({value: Number(input.value)})});
    setTimeout(loadDatapoints, 1200);
  } catch (e) {
    alert("Write fehlgeschlagen: " + e.message);
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const nav = event.target.closest("[data-view]");
  if (nav) {
    document.querySelectorAll(".nav,.view").forEach(el => el.classList.remove("active"));
    nav.classList.add("active");
    $(nav.dataset.view).classList.add("active");
  }
  const read = event.target.closest("[data-read]");
  if (read) readDp(read.dataset.read, read);
  const write = event.target.closest("[data-write-btn]");
  if (write) writeDp(write.dataset.writeBtn, write);
});

$("filter").addEventListener("input", renderTable);
$("refreshDp").addEventListener("click", loadDatapoints);
$("rawForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("rawResult").textContent = "reading…";
  try {
    const body = {
      address: $("rawAddress").value.trim(),
      length: Number($("rawLength").value),
      scale: $("rawScale").value.trim() || null,
      signed: $("rawSigned").checked
    };
    $("rawResult").textContent = JSON.stringify(await api("/api/raw/read", {method:"POST", body: JSON.stringify(body)}), null, 2);
  } catch (e) {
    $("rawResult").textContent = e.message;
  }
});

Promise.all([loadConfig(), loadStatus(), loadDatapoints()]).catch(console.error);
setInterval(loadDatapoints, 3000);
setInterval(loadStatus, 15000);
