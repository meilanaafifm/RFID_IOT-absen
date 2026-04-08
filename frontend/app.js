const state = {
  token: localStorage.getItem("token") || "",
  role: localStorage.getItem("role") || "",
  userId: localStorage.getItem("userId") || "",
  siswaRows: [],
  guruRows: [],
};

const views = {
  login: document.getElementById("loginView"),
  admin: document.getElementById("adminView"),
  guru: document.getElementById("guruView"),
  siswa: document.getElementById("siswaView"),
};

function decodeJwt(token) {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalized));
  } catch {
    return null;
  }
}

function setSession(token, role) {
  const payload = decodeJwt(token);
  state.token = token;
  state.role = role;
  state.userId = payload?.sub || "";
  localStorage.setItem("token", token);
  localStorage.setItem("role", role);
  localStorage.setItem("userId", state.userId);
}

function clearSession() {
  state.token = "";
  state.role = "";
  state.userId = "";
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  localStorage.removeItem("userId");
}

async function api(path, { method = "GET", body = null, withRoleHeader = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (withRoleHeader && state.userId) headers["x-user-id"] = state.userId;

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Terjadi kesalahan request");
  }
  return data;
}

function showRoleView() {
  const label = document.getElementById("sessionLabel");
  const logoutBtn = document.getElementById("logoutBtn");

  Object.values(views).forEach((v) => v.classList.add("hidden"));
  if (!state.token || !state.role) {
    views.login.classList.remove("hidden");
    logoutBtn.classList.add("hidden");
    label.textContent = "Belum login";
    return;
  }

  logoutBtn.classList.remove("hidden");
  label.textContent = `Login sebagai ${state.role}`;

  if (state.role === "Admin") views.admin.classList.remove("hidden");
  if (state.role === "Guru") views.guru.classList.remove("hidden");
  if (state.role === "Siswa") views.siswa.classList.remove("hidden");
}

function renderStats(stats) {
  const target = document.getElementById("adminStats");
  target.innerHTML = `
    <div class="stat-card"><strong>${stats.hadir}</strong><span>Hadir</span></div>
    <div class="stat-card"><strong>${stats.terlambat}</strong><span>Terlambat</span></div>
    <div class="stat-card"><strong>${stats.alpa}</strong><span>Alpa</span></div>
  `;
}

function renderUserList(targetId, rows, type) {
  const el = document.getElementById(targetId);
  if (!rows.length) {
    el.innerHTML = '<div class="item">Belum ada data</div>';
    return;
  }

  el.innerHTML = rows
    .map((row) => {
      const meta = type === "siswa"
        ? `Kelas ${row.kelas} | UID ${row.uid_rfid}`
        : `NIP ${row.nip} | ${row.mata_pelajaran}`;

      return `
      <div class="item">
        <div>
          <strong>${row.nama}</strong>
          <div class="meta">${row.username} - ${meta}</div>
        </div>
        <div class="row-actions">
          <button class="btn" onclick="edit${type}(${row.id})">Edit</button>
          <button class="btn danger" onclick="delete${type}(${row.id})">Hapus</button>
        </div>
      </div>`;
    })
    .join("");
}

function filterSiswaRows(keyword) {
  const q = keyword.trim().toLowerCase();
  if (!q) return state.siswaRows;
  return state.siswaRows.filter(
    (row) =>
      row.nama.toLowerCase().includes(q)
      || row.username.toLowerCase().includes(q)
      || row.kelas.toLowerCase().includes(q)
      || row.uid_rfid.toLowerCase().includes(q)
  );
}

function filterGuruRows(keyword) {
  const q = keyword.trim().toLowerCase();
  if (!q) return state.guruRows;
  return state.guruRows.filter(
    (row) =>
      row.nama.toLowerCase().includes(q)
      || row.username.toLowerCase().includes(q)
      || row.nip.toLowerCase().includes(q)
      || row.mata_pelajaran.toLowerCase().includes(q)
  );
}

function applySiswaSearch() {
  const keyword = document.getElementById("searchSiswa")?.value || "";
  renderUserList("siswaList", filterSiswaRows(keyword), "siswa");
}

function applyGuruSearch() {
  const keyword = document.getElementById("searchGuru")?.value || "";
  renderUserList("guruList", filterGuruRows(keyword), "guru");
}

function renderKelasList(rows) {
  const el = document.getElementById("kelasList");
  if (!rows.length) {
    el.innerHTML = '<div class="item">Tidak ada siswa pada kelas ini</div>';
    return;
  }
  el.innerHTML = rows
    .map(
      (r) => `
      <div class="item">
        <div>
          <strong>${r.nama}</strong>
          <div class="meta">ID ${r.siswa_id} | ${r.kelas}</div>
        </div>
        <div>
          <strong>${r.status}</strong>
          <div class="meta">${r.jam_scan ? new Date(r.jam_scan).toLocaleString() : "Belum scan"}</div>
        </div>
      </div>
    `
    )
    .join("");
}

function renderHistory(rows) {
  const el = document.getElementById("historyList");
  if (!rows.length) {
    el.innerHTML = '<div class="item">Belum ada riwayat 30 hari terakhir</div>';
    return;
  }

  el.innerHTML = rows
    .map(
      (row) => `
      <div class="item">
        <div>
          <strong>${row.status}</strong>
          <div class="meta">${new Date(row.waktu_scan).toLocaleString()}</div>
        </div>
        <div class="meta">${row.keterangan || "-"}</div>
      </div>
    `
    )
    .join("");
}

function normalizeTimeInput(value) {
  if (!value) return value;
  return value.length === 5 ? `${value}:00` : value;
}

async function loadAdminStats() {
  const stats = await api("/admin/stats", { withRoleHeader: true });
  renderStats(stats);
}

async function loadAttendanceConfig() {
  const cfg = await api("/admin/config/attendance-time", { withRoleHeader: true });
  document.getElementById("hadirBatas").value = cfg.hadir_batas.slice(0, 8);
  document.getElementById("terlambatBatas").value = cfg.terlambat_batas.slice(0, 8);
}

async function loadSiswaList() {
  const rows = await api("/admin/siswa", { withRoleHeader: true });
  state.siswaRows = rows;
  applySiswaSearch();
}

async function loadGuruList() {
  const rows = await api("/admin/guru", { withRoleHeader: true });
  state.guruRows = rows;
  applyGuruSearch();
}

window.editsiswa = async (id) => {
  const row = (state.siswaRows || []).find((x) => x.id === id);
  if (!row) return;

  const nama = prompt("Nama", row.nama) || row.nama;
  const kelas = prompt("Kelas", row.kelas) || row.kelas;
  const uid = prompt("UID RFID", row.uid_rfid) || row.uid_rfid;
  await api(`/admin/siswa/${id}`, {
    method: "PUT",
    withRoleHeader: true,
    body: { nama, kelas, uid_rfid: uid },
  });
  await loadSiswaList();
};

window.deletesiswa = async (id) => {
  if (!confirm("Hapus siswa ini?")) return;
  await api(`/admin/siswa/${id}`, { method: "DELETE", withRoleHeader: true });
  await loadSiswaList();
  await loadAdminStats();
};

window.editguru = async (id) => {
  const row = (state.guruRows || []).find((x) => x.id === id);
  if (!row) return;
  const nama = prompt("Nama", row.nama) || row.nama;
  const mapel = prompt("Mata Pelajaran", row.mata_pelajaran) || row.mata_pelajaran;
  await api(`/admin/guru/${id}`, {
    method: "PUT",
    withRoleHeader: true,
    body: { nama, mata_pelajaran: mapel },
  });
  await loadGuruList();
};

window.deleteguru = async (id) => {
  if (!confirm("Hapus guru ini?")) return;
  await api(`/admin/guru/${id}`, { method: "DELETE", withRoleHeader: true });
  await loadGuruList();
};

async function loadSiswaNotification() {
  const data = await api("/siswa/notification-data");
  document.getElementById("notifCard").innerHTML = `
    <strong>${data.nama} (${data.kelas})</strong>
    <p>${data.pesan}</p>
    <p>Status: ${data.status || "Belum ada"}</p>
    <p>Jam Scan: ${data.jam_scan ? new Date(data.jam_scan).toLocaleString() : "-"}</p>
  `;
}

async function loadSiswaHistory() {
  const rows = await api("/siswa/my-history");
  renderHistory(rows);
}

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("loginMessage");
  msg.textContent = "Memproses login...";

  try {
    const res = await api("/auth/login", {
      method: "POST",
      body: {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
      },
    });

    setSession(res.access_token, res.role);
    showRoleView();
    msg.textContent = "Login berhasil.";
    await initRoleData();
  } catch (err) {
    msg.textContent = err.message;
  }
});

document.getElementById("logoutBtn").addEventListener("click", () => {
  clearSession();
  showRoleView();
});

document.getElementById("refreshStatsBtn").addEventListener("click", loadAdminStats);

document.getElementById("configForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("configMessage");
  try {
    const hadirBatas = document.getElementById("hadirBatas").value;
    const terlambatBatas = document.getElementById("terlambatBatas").value;
    await api("/admin/config/attendance-time", {
      method: "PUT",
      withRoleHeader: true,
      body: {
        hadir_batas: normalizeTimeInput(hadirBatas),
        terlambat_batas: normalizeTimeInput(terlambatBatas),
      },
    });
    msg.textContent = "Konfigurasi berhasil diperbarui.";
  } catch (err) {
    msg.textContent = err.message;
  }
});

document.getElementById("createSiswaForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("siswaMessage");
  msg.textContent = "Menyimpan data siswa...";
  try {
    await api("/admin/siswa", {
      method: "POST",
      withRoleHeader: true,
      body: {
        username: document.getElementById("sUsername").value,
        password: document.getElementById("sPassword").value,
        uid_rfid: document.getElementById("sUid").value,
        nama: document.getElementById("sNama").value,
        kelas: document.getElementById("sKelas").value,
        no_ortu: document.getElementById("sOrtu").value,
      },
    });
    e.target.reset();
    await loadSiswaList();
    await loadAdminStats();
    msg.textContent = "Data siswa berhasil ditambahkan.";
  } catch (err) {
    msg.textContent = err.message;
  }
});

document.getElementById("createGuruForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("guruMessage");
  msg.textContent = "Menyimpan data guru...";
  try {
    await api("/admin/guru", {
      method: "POST",
      withRoleHeader: true,
      body: {
        username: document.getElementById("gUsername").value,
        password: document.getElementById("gPassword").value,
        nama: document.getElementById("gNama").value,
        nip: document.getElementById("gNip").value,
        mata_pelajaran: document.getElementById("gMapel").value,
      },
    });
    e.target.reset();
    await loadGuruList();
    msg.textContent = "Data guru berhasil ditambahkan.";
  } catch (err) {
    msg.textContent = err.message;
  }
});

document.getElementById("kelasForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const kelas = document.getElementById("kelasInput").value;
    const rows = await api(`/guru/presensi-kelas/${encodeURIComponent(kelas)}`, { withRoleHeader: true });
    renderKelasList(rows);
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("overrideForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("overrideMessage");
  try {
    const data = await api("/guru/presensi/override", {
      method: "PUT",
      withRoleHeader: true,
      body: {
        siswa_id: Number(document.getElementById("ovSiswaId").value),
        status: document.getElementById("ovStatus").value,
        keterangan: document.getElementById("ovKet").value || null,
      },
    });
    msg.textContent = `Override berhasil untuk ${data.nama} (${data.status}).`;
  } catch (err) {
    msg.textContent = err.message;
  }
});

document.getElementById("exportForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const kelas = document.getElementById("expKelas").value;
    const bulan = Number(document.getElementById("expBulan").value);
    const tahun = Number(document.getElementById("expTahun").value);
    const data = await api(`/guru/export/presensi-bulanan?kelas=${encodeURIComponent(kelas)}&bulan=${bulan}&tahun=${tahun}`, {
      withRoleHeader: true,
    });
    document.getElementById("exportResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    document.getElementById("exportResult").textContent = err.message;
  }
});

document.getElementById("notifBtn").addEventListener("click", loadSiswaNotification);
document.getElementById("historyBtn").addEventListener("click", loadSiswaHistory);
document.getElementById("searchSiswa")?.addEventListener("input", applySiswaSearch);
document.getElementById("searchGuru")?.addEventListener("input", applyGuruSearch);

async function initRoleData() {
  try {
    if (state.role === "Admin") {
      await Promise.all([loadAdminStats(), loadAttendanceConfig(), loadSiswaList(), loadGuruList()]);
    }
    if (state.role === "Guru") {
      document.getElementById("kelasList").innerHTML = '<div class="item">Masukkan nama kelas untuk melihat data live.</div>';
    }
    if (state.role === "Siswa") {
      await Promise.all([loadSiswaNotification(), loadSiswaHistory()]);
    }
  } catch (err) {
    alert(err.message);
  }
}

showRoleView();
if (state.token) {
  initRoleData();
}
