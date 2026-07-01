const chapters = [
  "Об издании DNS и проекте Клуб-DP",
  "Цифровизация естественно-научных дисциплин",
  "ИСО и социальные системы",
  "ФИНТЕХ системы и экономика",
  "ИИ и образование",
  "ИИ и здоровье",
  "Цифровые технологии в гуманитарных науках и искусстве",
  "Искусственный интеллект и цифровые технологии в торговле",
  "Цифровизация в ЖКХ, производственной и транспортной отраслях",
  "Разное интересное по тематике",
];

const chaptersList = document.querySelector("#chapters-list");
const chapterSearch = document.querySelector("#chapter-search");
const hashStatusDot = document.querySelector("#hash-status-dot");
const hashStatusTitle = document.querySelector("#hash-status-title");
const hashStatusText = document.querySelector("#hash-status-text");
const registryList = document.querySelector("#registry-list");
const refreshRegistryButton = document.querySelector("#refresh-registry");
const materialBotUrl = "https://t.me/dp_registration_bot";
const hashApiUrl = "http://127.0.0.1:8091";

function renderChapters(query = "") {
  const normalizedQuery = query.trim().toLowerCase();
  const filteredChapters = chapters
    .map((title, index) => ({ title, index: index + 1 }))
    .filter(({ title, index }) => {
      const value = `глава ${index} ${title}`.toLowerCase();
      return value.includes(normalizedQuery);
    });

  chaptersList.innerHTML = "";

  if (!filteredChapters.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Такой главы пока нет в текущем оглавлении.";
    chaptersList.append(empty);
    return;
  }

  filteredChapters.forEach(({ title, index }) => {
    const item = document.createElement("article");
    item.className = "chapter-item";

    item.innerHTML = `
      <span class="chapter-index">${index}</span>
      <span>
        <strong>Глава ${index}. ${title}</strong>
        <small>Материалы принимаются онлайн через Telegram</small>
      </span>
      <a href="${materialBotUrl}" target="_blank" rel="noreferrer">Передать</a>
    `;

    chaptersList.append(item);
  });
}

chapterSearch.addEventListener("input", (event) => {
  renderChapters(event.target.value);
});

function setHashStatus(isOnline, text) {
  hashStatusDot.classList.toggle("is-online", isOnline);
  hashStatusDot.classList.toggle("is-offline", !isOnline);
  hashStatusTitle.textContent = isOnline ? "Прием материалов работает" : "Прием материалов временно недоступен";
  hashStatusText.textContent = text;
}

function renderRegistry(records) {
  registryList.innerHTML = "";

  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Пока нет зафиксированных материалов.";
    registryList.append(empty);
    return;
  }

  records.forEach((record) => {
    const item = document.createElement("article");
    item.className = "registry-item";
    const annotation = record.annotation?.text
      ? `<p>${escapeHtml(record.annotation.text)}</p>`
      : "";
    item.innerHTML = `
      <strong>${escapeHtml(record.file_name || "Материал без названия")}</strong>
      <span>${escapeHtml(record.author || "Автор не указан")} · ${escapeHtml(record.branch || "Раздел не указан")}</span>
      <span>${escapeHtml(record.registered_at || "Дата не указана")}</span>
      ${annotation}
      <code>${escapeHtml(record.sha256 || "")}</code>
    `;
    registryList.append(item);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadHashRegistry() {
  try {
    const health = await fetch(`${hashApiUrl}/health`);
    if (!health.ok) {
      throw new Error("health failed");
    }

    setHashStatus(true, "Новые материалы будут сохраняться с датой отправки и SHA256-хэшем файла.");

    const response = await fetch(`${hashApiUrl}/api/v1/records?limit=6`);
    if (!response.ok) {
      throw new Error("records failed");
    }

    const records = await response.json();
    renderRegistry(records);
  } catch (error) {
    setHashStatus(false, "Сейчас сайт не видит локальный сервис фиксации материалов.");
    renderRegistry([]);
  }
}

refreshRegistryButton.addEventListener("click", loadHashRegistry);

renderChapters();
loadHashRegistry();
