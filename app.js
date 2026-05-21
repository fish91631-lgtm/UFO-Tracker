// PURSUE Tracker · client-side renderer
// Reads /data.json (built daily by scraper/scrape.py via GitHub Actions),
// renders the list + filters + detail view.

const UFOTracker = (() => {
  const DATA_URL = "data.json";
  const SEEN_KEY = "pursue.last_seen_run";

  async function loadData() {
    const res = await fetch(`${DATA_URL}?ts=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching data.json`);
    return res.json();
  }

  // --- index page --------------------------------------------------------

  function init(data) {
    setupBanner(data);
    setupMeta(data);
    setupFilters(data);
    setupSearch(data);
    render(data);
    document.getElementById("reload-btn")?.addEventListener("click", () => {
      location.reload();
    });
  }

  function setupBanner(data) {
    const banner = document.getElementById("update-banner");
    const text = document.getElementById("update-banner-text");
    if (!banner || !text) return;

    const lastSeen = localStorage.getItem(SEEN_KEY);
    const isNewToUser = lastSeen !== data.generated_at;
    const shouldShow = data.has_new_today && isNewToUser;

    if (shouldShow) {
      const n = data.new_count || (data.new_ids || []).length;
      text.textContent =
        `今日抓取偵測到 ${n} 筆新增資料 (更新時間: ${formatDate(data.generated_at)})`;
      banner.classList.remove("hidden");
    }
    document.getElementById("dismiss-banner")?.addEventListener("click", () => {
      localStorage.setItem(SEEN_KEY, data.generated_at);
      banner.classList.add("hidden");
    });
  }

  function setupMeta(data) {
    const total = (data.entries || []).length;
    document.getElementById("entry-count").textContent =
      `共 ${total} 筆檔案`;
    const updatedEl = document.getElementById("last-updated");
    if (updatedEl) {
      updatedEl.textContent = `最後更新: ${formatDate(data.generated_at)}`;
    }
  }

  const state = {
    activeTags: new Set(),
    search: "",
  };

  function setupFilters(data) {
    const container = document.getElementById("tag-filters");
    if (!container) return;
    container.innerHTML = "";
    const cats = data.categories || [];
    for (const tag of cats) {
      const pill = document.createElement("span");
      pill.className = "tag-pill";
      pill.textContent = tag;
      pill.dataset.tag = tag;
      pill.addEventListener("click", () => {
        if (state.activeTags.has(tag)) {
          state.activeTags.delete(tag);
          pill.classList.remove("active");
        } else {
          state.activeTags.add(tag);
          pill.classList.add("active");
        }
        render(data);
      });
      container.appendChild(pill);
    }
  }

  function setupSearch(data) {
    const input = document.getElementById("search");
    if (!input) return;
    let debounce;
    input.addEventListener("input", e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        state.search = e.target.value.trim().toLowerCase();
        render(data);
      }, 120);
    });
  }

  function filterEntries(data) {
    const newIds = new Set(data.new_ids || []);
    return (data.entries || []).filter(entry => {
      // tag filter
      if (state.activeTags.size > 0) {
        const entryTags = new Set(entry.tags || []);
        let match = false;
        for (const t of state.activeTags) {
          if (entryTags.has(t)) { match = true; break; }
        }
        if (!match) return false;
      }
      // search
      if (state.search) {
        const hay = [
          entry.title_en, entry.title_zh,
          entry.description_en, entry.description_zh,
          entry.agency, entry.agency_zh,
          entry.incident_location, entry.incident_location_zh,
          entry.type, entry.type_zh,
        ].join(" ").toLowerCase();
        if (!hay.includes(state.search)) return false;
      }
      return true;
    }).map(e => ({ ...e, __isNew: newIds.has(e.id) }));
  }

  function render(data) {
    const root = document.getElementById("entries");
    const tmpl = document.getElementById("entry-card-tmpl");
    if (!root || !tmpl) return;

    const filtered = filterEntries(data);
    root.innerHTML = "";

    if (filtered.length === 0) {
      root.innerHTML = `<p style="color:var(--text-dim)">沒有符合條件的檔案。</p>`;
      return;
    }

    // Newest first: new entries on top, then by release_n desc.
    filtered.sort((a, b) => {
      if (a.__isNew && !b.__isNew) return -1;
      if (!a.__isNew && b.__isNew) return 1;
      return (b.release_n || 0) - (a.release_n || 0);
    });

    for (const entry of filtered) {
      const node = tmpl.content.cloneNode(true);
      const card = node.querySelector(".entry-card");
      if (entry.__isNew) card.classList.add("is-new");

      node.querySelector(".title-en").textContent = entry.title_en || "(無標題)";
      node.querySelector(".title-zh").textContent = entry.title_zh || "";

      const tagsEl = node.querySelector(".card-tags");
      if (entry.__isNew) {
        const chip = document.createElement("span");
        chip.className = "tag-chip is-new";
        chip.textContent = "新增";
        tagsEl.appendChild(chip);
      }
      for (const t of entry.tags || []) {
        const chip = document.createElement("span");
        chip.className = "tag-chip";
        chip.textContent = t;
        tagsEl.appendChild(chip);
      }

      const metaEl = node.querySelector(".card-meta");
      metaEl.innerHTML = "";
      addMeta(metaEl, "機構", entry.agency_zh || entry.agency);
      addMeta(metaEl, "釋出批次", entry.release);
      addMeta(metaEl, "事件日期", entry.incident_date);
      addMeta(metaEl, "地點", entry.incident_location_zh || entry.incident_location);

      const colEn = node.querySelector(".col-en");
      const colZh = node.querySelector(".col-zh");
      colEn.setAttribute("data-label", "English (original)");
      colZh.setAttribute("data-label", "繁體中文 (翻譯)");
      node.querySelector(".desc-en").textContent = truncate(entry.description_en, 320);
      node.querySelector(".desc-zh").textContent = truncate(entry.description_zh, 320);

      const link = node.querySelector(".detail-link");
      link.href = `detail.html?id=${encodeURIComponent(entry.id)}`;

      root.appendChild(node);
    }
  }

  function addMeta(parent, label, value) {
    if (!value) return;
    const el = document.createElement("span");
    el.innerHTML = `<strong style="color:var(--text)">${label}:</strong> ${escapeHTML(value)}`;
    parent.appendChild(el);
  }

  function truncate(s, n) {
    s = s || "";
    if (s.length <= n) return s;
    return s.slice(0, n - 1) + "…";
  }

  function escapeHTML(s) {
    return String(s || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
    }[ch]));
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("zh-TW", { hour12: false });
    } catch { return iso; }
  }

  // --- detail page -------------------------------------------------------

  function renderDetail(data, id) {
    const entry = (data.entries || []).find(e => e.id === id);
    const root = document.getElementById("detail-root");
    const titleEl = document.getElementById("detail-title");

    if (!entry) {
      titleEl.textContent = "找不到該檔案";
      root.innerHTML = `<p>ID <code>${escapeHTML(id)}</code> 不存在於目前的資料集。可能已被原網站移除,或還未抓取。</p>`;
      return;
    }

    titleEl.innerHTML =
      `<span>${escapeHTML(entry.title_en)}</span><br>` +
      `<span style="color:var(--text-dim); font-size:1rem; font-weight:500">${escapeHTML(entry.title_zh)}</span>`;

    const tagsHtml = (entry.tags || []).map(t =>
      `<span class="tag-chip">${escapeHTML(t)}</span>`).join(" ");

    const metaHtml = `
      <div class="detail-meta">
        <strong>機構 Agency</strong><span>${escapeHTML(entry.agency_zh || "")}${entry.agency ? ` (${escapeHTML(entry.agency)})` : "—"}</span>
        <strong>釋出批次 Release</strong><span>${escapeHTML(entry.release || "—")}</span>
        <strong>事件日期 Date</strong><span>${escapeHTML(entry.incident_date || "—")}</span>
        <strong>地點 Location</strong><span>${escapeHTML(entry.incident_location_zh || "")}${entry.incident_location ? ` (${escapeHTML(entry.incident_location)})` : "—"}</span>
        <strong>類型 Type</strong><span>${escapeHTML(entry.type_zh || "")}${entry.type ? ` (${escapeHTML(entry.type)})` : "—"}</span>
        <strong>標籤 Tags</strong><span>${tagsHtml || "—"}</span>
      </div>
    `;

    const descGrid = `
      <div class="detail-grid">
        <div>
          <h3>English (original)</h3>
          <p>${escapeHTML(entry.description_en || "(no description)")}</p>
        </div>
        <div>
          <h3>繁體中文 (翻譯)</h3>
          <p>${escapeHTML(entry.description_zh || "(無描述)")}</p>
        </div>
      </div>
    `;

    const imgs = entry.image_urls || [];
    const imagesHtml = imgs.length === 0 ? "" : `
      <h3 style="margin-top:1.5rem">相關圖片 Images</h3>
      <div class="detail-images">
        ${imgs.map(u =>
          `<a href="${escapeHTML(u)}" target="_blank" rel="noopener">
             <img src="${escapeHTML(u)}" alt="" loading="lazy"
                  onerror="this.style.display='none'">
           </a>`).join("")}
      </div>
    `;

    const linksHtml = `
      <div class="detail-links">
        ${entry.file_url ? `<a href="${escapeHTML(entry.file_url)}" target="_blank" rel="noopener">📄 下載原始檔案</a>` : ""}
        ${entry.video_url ? `<a href="${escapeHTML(entry.video_url)}" target="_blank" rel="noopener">🎬 觀看影片</a>` : ""}
        ${entry.source_csv ? `<a href="${escapeHTML(entry.source_csv)}" target="_blank" rel="noopener">📊 來源 CSV</a>` : ""}
        <a href="${escapeHTML(data.source)}" target="_blank" rel="noopener">🌐 前往 war.gov/UFO/</a>
      </div>
    `;

    root.innerHTML = metaHtml + descGrid + imagesHtml + linksHtml;
  }

  // --- bootstrap (index page) -------------------------------------------
  if (document.getElementById("entries")) {
    loadData()
      .then(init)
      .catch(err => {
        document.getElementById("entries").innerHTML =
          `<p class="error">無法載入 data.json: ${err.message}<br>
           若你是第一次部署,請先在 GitHub 上手動觸發一次 Actions(Run workflow)以產生資料。</p>`;
      });
  }

  return { loadData, renderDetail };
})();
