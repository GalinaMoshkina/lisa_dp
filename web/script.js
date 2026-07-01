const STORAGE_KEY = "digitalParallelsPrototype";

const defaultState = {
  currentLogin: "",
  users: [
    {
      firstName: "Демо",
      lastName: "Автор",
      middleName: "",
      name: "Демо Автор",
      login: "demo",
      email: "demo@itmo.ru",
      emailVerified: true,
      password: "demo",
      institute: "ИТМО",
      city: "Санкт-Петербург",
      country: "Россия",
      role: "Автор",
    },
  ],
  publications: [
    {
      id: "pub-demo-1",
      title: "Интеллектуальная среда обитания",
      summary: "Демонстрационная публикация о гибридных сообществах и цифровых системах.",
      branch: "Гибридные сообщества",
      fileName: "intellectual-environment.pdf",
      fileDataUrl: "",
      authorLogin: "demo",
      institute: "ИТМО",
      createdAt: "2026-05-17",
      updatedAt: "2026-05-17",
      comments: [
        {
          id: "comment-demo-1",
          authorLogin: "demo",
          text: "Первый комментарий можно использовать как пример обсуждения материала.",
          createdAt: "2026-05-17",
        },
      ],
    },
  ],
};

let state = loadState();
let activeInstitute = "ИТМО";
let activeAuthorLogin = "demo";
let activePublicationId = "pub-demo-1";
let editPublicationId = "";
let preselectedBranch = "";
let pendingEmailCode = "";
let pendingEmail = "";
let activeScreen = "home";
let screenHistory = [];

const screens = [...document.querySelectorAll("[data-screen]")];
const registerForm = document.querySelector("#register-form");
const loginForm = document.querySelector("#login-form");
const publishForm = document.querySelector("#publish-form");
const commentForm = document.querySelector("#comment-form");
const searchInput = document.querySelector("#global-search");
const searchResults = document.querySelector("#search-results");

function loadState() {
  const saved = localStorage.getItem(STORAGE_KEY);
  let loaded = structuredClone(defaultState);

  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      loaded = {
        ...loaded,
        ...parsed,
        users: parsed.users?.length ? parsed.users : loaded.users,
        publications: parsed.publications?.length ? parsed.publications : loaded.publications,
      };
    } catch {
      loaded = structuredClone(defaultState);
    }
  }

  loaded.users = loaded.users.map(migrateUser);
  loaded.publications = loaded.publications.map((publication) => ({
    fileDataUrl: "",
    updatedAt: publication.createdAt,
    comments: [],
    ...publication,
  }));
  return loaded;
}

function migrateUser(user) {
  if (user.firstName || user.lastName) {
    return {
      email: user.email || `${user.login || "user"}@example.org`,
      emailVerified: Boolean(user.emailVerified),
      middleName: user.middleName || "",
      name: fullName(user),
      ...user,
    };
  }

  const parts = (user.name || "").split(/\s+/).filter(Boolean);
  const migrated = {
    ...user,
    lastName: parts[1] || parts[0] || "",
    firstName: parts[0] || "",
    middleName: parts.slice(2).join(" "),
    email: user.email || `${user.login || "user"}@example.org`,
    emailVerified: Boolean(user.emailVerified),
  };
  migrated.name = fullName(migrated);
  return migrated;
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function showScreen(name, options = {}) {
  if (["dashboard", "publish"].includes(name) && !currentUser()) {
    name = "login";
  }

  const shouldPush = options.push !== false;
  if (shouldPush && activeScreen && activeScreen !== name) {
    screenHistory.push(activeScreen);
  }
  activeScreen = name;

  document.body.classList.toggle("is-home", name === "home");
  document.body.classList.toggle("is-authenticated", Boolean(currentUser()));
  document.body.classList.toggle("has-history", screenHistory.length > 0);
  screens.forEach((screen) => {
    screen.classList.toggle("is-active", screen.dataset.screen === name);
  });

  if (name === "dashboard") renderDashboard();
  if (name === "publish") renderPublishForm();
  if (name === "institute") renderInstitute(activeInstitute);
  if (name === "author") renderAuthor(activeAuthorLogin);
  if (name === "article") renderArticle(activePublicationId);
  if (name === "instituteAuthors") renderInstituteAuthors(activeInstitute);

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function currentUser() {
  return state.users.find((user) => user.login === state.currentLogin) || null;
}

function normalize(value = "") {
  return String(value).trim().toLowerCase();
}

function fullName(user) {
  return [user.lastName, user.firstName, user.middleName].filter(Boolean).join(" ").trim() || user.name || user.login;
}

function setMessage(element, text, type = "success") {
  element.textContent = text;
  element.classList.remove("is-error", "is-success");
  if (text) element.classList.add(type === "error" ? "is-error" : "is-success");
}

function requireUser() {
  const user = currentUser();
  if (user) return user;
  showScreen("login");
  return null;
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function userBranches(user) {
  const branches = state.publications
    .filter((publication) => publication.authorLogin === user.login)
    .map((publication) => publication.branch);
  return [...new Set(branches)];
}

function publicationWord(count) {
  if (count === 1) return "1 публикация";
  if (count > 1 && count < 5) return `${count} публикации`;
  return `${count} публикаций`;
}

function renderDashboard() {
  const user = requireUser();
  if (!user) return;

  const name = fullName(user);
  document.querySelector("#profile-avatar").textContent = initials(name);
  document.querySelector("#profile-name").textContent = name;
  document.querySelector("#profile-login").textContent = user.login;
  document.querySelector("#profile-role").textContent = user.role;
  document.querySelector("#profile-institute").textContent = user.institute;
  document.querySelector("#profile-location").textContent = `${user.city}, ${user.country}`;

  const userRecords = state.publications.filter((publication) => publication.authorLogin === user.login);
  const publications = userRecords.filter((publication) => !publication.isBranchPlaceholder);
  document.querySelector("#works-count").textContent = publicationWord(publications.length);

  const emptyWorks = document.querySelector("#empty-works");
  const branchList = document.querySelector("#branch-list");
  branchList.innerHTML = "";
  emptyWorks.classList.toggle("is-hidden", userRecords.length > 0);

  const branches = [...new Set(userRecords.map((publication) => publication.branch))];
  branchList.innerHTML = renderBranchGroups(publications, branches, { owner: true, canAdd: true });
}

function renderBranchGroups(publications, branches, options = {}) {
  return branches
    .map((branch) => {
      const branchPublications = publications.filter((publication) => publication.branch === branch);
      return `
        <article class="branch-card">
          <div class="branch-heading">
            <h4>${branch}<span>${publicationWord(branchPublications.length)}</span></h4>
            ${
              options.canAdd
                ? `<button class="mini-button dark" type="button" data-add-article="${escapeAttr(branch)}">Добавить статью</button>`
                : ""
            }
          </div>
          <div class="publication-list">
            ${
              branchPublications.length
                ? branchPublications.map((publication) => renderPublicationItem(publication, { owner: options.owner })).join("")
                : `<article class="publication-item"><strong>Статей пока нет</strong><span>В этой ветке пока нет публикаций.</span></article>`
            }
          </div>
        </article>
      `;
    })
    .join("");
}

function renderPublicationItem(publication, options = {}) {
  const author = state.users.find((user) => user.login === publication.authorLogin);
  const actions = options.owner
    ? `
      <div class="publication-actions">
        <button class="mini-button" type="button" data-open-publication="${publication.id}">Открыть</button>
        <button class="mini-button dark" type="button" data-view-file="${publication.id}">Файл</button>
        <button class="mini-button" type="button" data-edit-publication="${publication.id}">Редактировать</button>
      </div>
    `
    : `
      <div class="publication-actions">
        <button class="mini-button" type="button" data-open-publication="${publication.id}">Открыть</button>
        <button class="mini-button dark" type="button" data-view-file="${publication.id}">Файл</button>
      </div>
    `;

  return `
    <article class="publication-item">
      <strong>${publication.title}</strong>
      <span>${fullName(author || { name: publication.authorLogin })} · ${publication.institute} · ${publication.branch}</span>
      <small>${publication.fileName} · ${publication.createdAt}</small>
      ${actions}
    </article>
  `;
}

function escapeAttr(value) {
  return String(value).replaceAll('"', "&quot;");
}

function addBranch() {
  const user = requireUser();
  if (!user) return;

  const branch = prompt("Название научной ветки", "Нейропсихология");
  if (!branch?.trim()) return;

  const exists = state.publications.some(
    (publication) => publication.authorLogin === user.login && normalize(publication.branch) === normalize(branch),
  );

  if (!exists) {
    state.publications.push({
      id: `branch-${Date.now()}`,
      title: "Черновик ветки",
      summary: "Служебная запись ветки. Добавьте первую статью в этот раздел.",
      branch: branch.trim(),
      fileName: "без файла",
      fileDataUrl: "",
      authorLogin: user.login,
      institute: user.institute,
      createdAt: new Date().toISOString().slice(0, 10),
      updatedAt: new Date().toISOString().slice(0, 10),
      isBranchPlaceholder: true,
    });
    saveState();
  }

  renderDashboard();
}

function renderPublishForm() {
  const user = requireUser();
  if (!user) return;

  const select = document.querySelector("#publication-branch");
  const fileNote = document.querySelector("#current-file-note");
  const submitButton = document.querySelector("#publish-submit-button");
  const fileInput = publishForm.elements.file;
  const branches = userBranches(user).filter(Boolean);
  const baseBranches = ["Биология", "Нейропсихология", "Математика", "Цифровое естествознание"];
  const options = [...new Set([...branches, ...baseBranches])];
  select.innerHTML = options.map((branch) => `<option value="${branch}">${branch}</option>`).join("");

  const publication = state.publications.find((item) => item.id === editPublicationId);
  publishForm.reset();
  publishForm.elements.publicationId.value = publication?.id || "";
  fileNote.textContent = "";
  submitButton.textContent = publication ? "Сохранить изменения" : "Опубликовать";
  fileInput.required = !publication;

  if (publication) {
    publishForm.elements.branch.value = publication.branch;
    publishForm.elements.title.value = publication.title;
    publishForm.elements.summary.value = publication.summary;
    fileNote.textContent = publication.fileName ? `Текущий файл: ${publication.fileName}` : "";
  } else if (preselectedBranch) {
    publishForm.elements.branch.value = preselectedBranch;
  }
}

function renderInstitute(instituteName) {
  const institute = instituteName || currentUser()?.institute || "ИТМО";
  activeInstitute = institute;

  const authors = state.users.filter((user) => sameInstitute(user.institute, institute));
  let publications = state.publications.filter(
    (publication) => sameInstitute(publication.institute, institute) && !publication.isBranchPlaceholder,
  );
  publications = sortPublications(publications, document.querySelector("#institute-sort").value);
  const branches = [...new Set(publications.map((publication) => publication.branch))];
  const firstAuthor = authors[0];
  const link = instituteLink(institute);

  document.querySelector("#institute-name").textContent = institute;
  document.querySelector("#institute-location").textContent = firstAuthor
    ? `${firstAuthor.city}, ${firstAuthor.country}`
    : "Институт найден через поиск. Данные можно расширить в профиле организации.";
  document.querySelector("#institute-author-count").textContent = String(authors.length);
  document.querySelector("#institute-publication-count").textContent = String(publications.length);
  document.querySelector("#institute-branch-count").textContent = String(branches.length);

  const instituteLinkElement = document.querySelector("#institute-link");
  instituteLinkElement.href = link || "#";
  instituteLinkElement.classList.toggle("is-hidden", !link);

  document.querySelector("#institute-publications").innerHTML = publications.length
    ? renderBranchGroups(publications, branches)
    : `<div class="empty-state"><h4>Публикаций пока нет</h4><p>Когда авторы института добавят статьи, они появятся здесь.</p></div>`;

  document.querySelector("#institute-authors").innerHTML = authors.length
    ? authors.slice(0, 4).map(renderAuthorItem).join("")
    : `<div class="empty-state"><h4>Авторы не найдены</h4><p>Зарегистрируйте первого участника этого института.</p></div>`;
}

function sameInstitute(left, right) {
  const a = normalize(left);
  const b = normalize(right);
  return a === b || (["итмо", "itmo", "itmo university"].includes(a) && ["итмо", "itmo", "itmo university"].includes(b));
}

function instituteLink(institute) {
  return ["итмо", "itmo", "itmo university"].includes(normalize(institute)) ? "https://itmo.ru/" : "";
}

function sortPublications(publications, mode) {
  return [...publications].sort((a, b) => {
    if (mode === "title-asc") return a.title.localeCompare(b.title, "ru");
    if (mode === "date-asc") return a.createdAt.localeCompare(b.createdAt);
    return b.createdAt.localeCompare(a.createdAt);
  });
}

function renderAuthorItem(author) {
  return `
    <article class="author-item">
      <strong>${fullName(author)}</strong>
      <span>@${author.login} · ${author.role}</span>
      <button class="mini-button" type="button" data-open-author="${author.login}">Открыть профиль</button>
    </article>
  `;
}

function renderAuthor(login) {
  const author = state.users.find((user) => user.login === login) || state.users[0];
  activeAuthorLogin = author.login;
  const publications = state.publications.filter(
    (publication) => publication.authorLogin === author.login && !publication.isBranchPlaceholder,
  );
  const branches = [...new Set(publications.map((publication) => publication.branch))];

  document.querySelector("#author-name").textContent = fullName(author);
  document.querySelector("#author-avatar").textContent = initials(fullName(author));
  document.querySelector("#author-login").textContent = author.login;
  document.querySelector("#author-role").textContent = author.role;
  document.querySelector("#author-institute").textContent = author.institute;
  document.querySelector("#author-email").textContent = `${author.email}${author.emailVerified ? " · email подтвержден" : ""}`;
  document.querySelector("#author-publications").innerHTML = publications.length
    ? renderBranchGroups(publications, branches)
    : `<div class="empty-state"><h4>Публикаций пока нет</h4><p>У автора пока нет опубликованных материалов.</p></div>`;
}

function renderArticle(id) {
  const publication = state.publications.find((item) => item.id === id) || state.publications.find((item) => !item.isBranchPlaceholder);
  if (!publication) return showScreen("dashboard");

  activePublicationId = publication.id;
  const author = state.users.find((user) => user.login === publication.authorLogin);
  document.querySelector("#article-title").textContent = publication.title;
  document.querySelector("#article-meta").textContent =
    `${fullName(author || { name: publication.authorLogin })} · ${publication.institute} · ${publication.branch} · ${publication.createdAt}`;
  document.querySelector("#article-summary").textContent = publication.summary;
  renderComments(publication);
}

function renderComments(publication) {
  const comments = publication.comments || [];
  document.querySelector("#comments-count").textContent = commentWord(comments.length);
  document.querySelector("#comments-list").innerHTML = comments.length
    ? comments.map(renderCommentItem).join("")
    : `<div class="empty-state"><h4>Комментариев пока нет</h4><p>Будьте первым, кто начнет обсуждение этой статьи.</p></div>`;
}

function renderCommentItem(comment) {
  const author = state.users.find((user) => user.login === comment.authorLogin);
  return `
    <article class="comment-item">
      <strong>${fullName(author || { name: comment.authorLogin })}</strong>
      <small>@${comment.authorLogin} · ${comment.createdAt}</small>
      <p>${escapeHtml(comment.text)}</p>
    </article>
  `;
}

function commentWord(count) {
  if (count === 1) return "1 комментарий";
  if (count > 1 && count < 5) return `${count} комментария`;
  return `${count} комментариев`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderInstituteAuthors(instituteName) {
  const institute = instituteName || activeInstitute;
  const authors = state.users.filter((user) => sameInstitute(user.institute, institute));
  document.querySelector("#authors-list-title").textContent = `Авторы: ${institute}`;
  document.querySelector("#authors-list").innerHTML = authors.length
    ? authors.map(renderAuthorItem).join("")
    : `<div class="empty-state"><h4>Авторы не найдены</h4><p>В этом институте пока нет зарегистрированных участников.</p></div>`;
}

function renderSearch() {
  if (!searchInput || !searchResults) return;

  const query = normalize(searchInput.value);
  searchResults.innerHTML = "";

  if (!query) {
    searchResults.classList.remove("is-visible");
    return;
  }

  const articleResults = state.publications
    .filter((publication) => !publication.isBranchPlaceholder)
    .filter((publication) => normalize(publication.title).includes(query))
    .map((publication) => ({
      type: "Статья",
      title: publication.title,
      meta: `${publication.institute} · ${publication.branch}`,
      action: () => {
        activePublicationId = publication.id;
        showScreen("article");
      },
    }));

  const authorResults = state.users
    .filter((user) => normalize(fullName(user)).includes(query) || normalize(user.login).includes(query))
    .map((user) => ({
      type: "Автор",
      title: fullName(user),
      meta: `@${user.login} · ${user.institute}`,
      action: () => {
        activeAuthorLogin = user.login;
        showScreen("author");
      },
    }));

  const institutes = [...new Set(state.users.map((user) => user.institute))];
  if (!institutes.some((name) => normalize(name) === "итмо")) institutes.push("ИТМО");
  if (!institutes.some((name) => normalize(name) === "itmo")) institutes.push("ITMO");

  const instituteResults = institutes
    .filter((institute) => normalize(institute).includes(query))
    .map((institute) => ({
      type: "Институт",
      title: institute,
      meta: "Страница организации",
      action: () => {
        activeInstitute = institute === "ITMO" ? "ИТМО" : institute;
        showScreen("institute");
      },
    }));

  const results = [...articleResults, ...authorResults, ...instituteResults].slice(0, 8);
  if (!results.length) {
    searchResults.innerHTML = `<div class="search-result"><span>Ничего не найдено</span><small>Попробуйте другой запрос</small></div>`;
    searchResults.classList.add("is-visible");
    return;
  }

  results.forEach((result) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-result";
    button.innerHTML = `<span><strong>${result.title}</strong><br><small>${result.meta}</small></span><small>${result.type}</small>`;
    button.addEventListener("click", () => {
      searchInput.value = "";
      searchResults.classList.remove("is-visible");
      result.action();
    });
    searchResults.append(button);
  });

  searchResults.classList.add("is-visible");
}

function viewFile(publicationId) {
  const publication = state.publications.find((item) => item.id === publicationId);
  if (!publication?.fileDataUrl) {
    alert("В прототипе файл демо-публикации не хранится. Для новых загруженных файлов просмотр работает в этом браузере.");
    return;
  }

  const win = window.open();
  win.document.write(`<iframe src="${publication.fileDataUrl}" title="${publication.fileName}" style="border:0;width:100%;height:100vh"></iframe>`);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve("");
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

document.querySelectorAll("[data-screen-link]").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.screenLink === "publish") {
      editPublicationId = "";
      preselectedBranch = "";
    }
    showScreen(button.dataset.screenLink);
  });
});

document.querySelector("#back-button").addEventListener("click", () => {
  const previous = screenHistory.pop();
  if (!previous) return;
  showScreen(previous, { push: false });
});

registerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(registerForm));
  const message = document.querySelector("#register-message");

  if (data.password.length < 4) {
    setMessage(message, "Пароль должен быть не короче 4 символов.", "error");
    return;
  }

  if (state.users.some((user) => normalize(user.login) === normalize(data.login))) {
    setMessage(message, "Такой логин уже занят.", "error");
    return;
  }

  if (state.users.some((user) => normalize(user.email) === normalize(data.email))) {
    setMessage(message, "Такой email уже используется.", "error");
    return;
  }

  if (!pendingEmailCode || data.emailCode.trim() !== pendingEmailCode || normalize(data.email) !== normalize(pendingEmail)) {
    setMessage(message, "Введите корректный код подтверждения email.", "error");
    return;
  }

  const user = {
    firstName: data.firstName.trim(),
    lastName: data.lastName.trim(),
    middleName: data.middleName.trim(),
    login: data.login.trim(),
    email: data.email.trim(),
    emailVerified: true,
    password: data.password,
    institute: data.institute.trim(),
    city: data.city.trim(),
    country: data.country.trim(),
    role: data.role,
  };
  user.name = fullName(user);

  state.users.push(user);
  state.currentLogin = user.login;
  pendingEmailCode = "";
  pendingEmail = "";
  saveState();
  registerForm.reset();
  setMessage(message, "Email подтвержден, аккаунт создан. Открываю личный кабинет.", "success");
  setTimeout(() => showScreen("dashboard"), 450);
});

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(loginForm));
  const message = document.querySelector("#login-message");
  const user = state.users.find(
    (item) => normalize(item.login) === normalize(data.login) && item.password === data.password,
  );

  if (!user) {
    setMessage(message, "Логин или пароль не совпадают.", "error");
    return;
  }

  state.currentLogin = user.login;
  saveState();
  loginForm.reset();
  setMessage(message, "Вход выполнен.", "success");
  setTimeout(() => showScreen("dashboard"), 300);
});

publishForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const user = requireUser();
  if (!user) return;

  const data = Object.fromEntries(new FormData(publishForm));
  const file = publishForm.elements.file.files[0];
  const publicationId = data.publicationId;
  const existing = state.publications.find((publication) => publication.id === publicationId);
  const branch = data.newBranch.trim() || data.branch;

  if (!existing && !file) {
    setMessage(document.querySelector("#publish-message"), "Прикрепите файл публикации.", "error");
    return;
  }

  const fileDataUrl = file ? await readFileAsDataUrl(file) : existing.fileDataUrl;
  state.publications = state.publications.filter(
    (publication) => !(publication.authorLogin === user.login && publication.branch === branch && publication.isBranchPlaceholder),
  );

  if (existing) {
    Object.assign(existing, {
      title: data.title.trim(),
      summary: data.summary.trim(),
      branch,
      fileName: file?.name || existing.fileName,
      fileDataUrl,
      updatedAt: new Date().toISOString().slice(0, 10),
    });
  } else {
    state.publications.push({
      id: `pub-${Date.now()}`,
      title: data.title.trim(),
      summary: data.summary.trim(),
      branch,
      fileName: file.name,
      fileDataUrl,
      authorLogin: user.login,
      institute: user.institute,
      createdAt: new Date().toISOString().slice(0, 10),
      updatedAt: new Date().toISOString().slice(0, 10),
      comments: [],
    });
  }

  saveState();
  publishForm.reset();
  editPublicationId = "";
  preselectedBranch = "";
  showScreen("dashboard");
});

commentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const user = requireUser();
  if (!user) return;

  const publication = state.publications.find((item) => item.id === activePublicationId);
  if (!publication) return;

  const text = commentForm.elements.comment.value.trim();
  if (!text) return;

  publication.comments = publication.comments || [];
  publication.comments.push({
    id: `comment-${Date.now()}`,
    authorLogin: user.login,
    text,
    createdAt: new Date().toISOString().slice(0, 10),
  });

  saveState();
  commentForm.reset();
  renderComments(publication);
});

document.querySelector("#send-email-code").addEventListener("click", () => {
  const email = registerForm.elements.email.value.trim();
  const message = document.querySelector("#register-message");
  if (!email) {
    setMessage(message, "Сначала укажите email.", "error");
    return;
  }
  pendingEmailCode = String(Math.floor(100000 + Math.random() * 900000));
  pendingEmail = email;
  setMessage(message, `Код подтверждения для прототипа: ${pendingEmailCode}`, "success");
});

document.querySelector("#add-branch-button").addEventListener("click", addBranch);
document.querySelector("#empty-add-branch-button").addEventListener("click", addBranch);
document.querySelector("#profile-institute").addEventListener("click", () => {
  const user = requireUser();
  if (!user) return;
  activeInstitute = user.institute;
  showScreen("institute");
});
document.querySelector("#author-institute").addEventListener("click", () => {
  const author = state.users.find((user) => user.login === activeAuthorLogin);
  if (!author) return;
  activeInstitute = author.institute;
  showScreen("institute");
});
document.querySelector("#logout-button").addEventListener("click", () => {
  state.currentLogin = "";
  screenHistory = [];
  saveState();
  showScreen("home");
});
document.querySelector("#institute-sort").addEventListener("change", () => renderInstitute(activeInstitute));
document.querySelector("#article-view-file").addEventListener("click", () => viewFile(activePublicationId));
document.querySelector("#article-author-link").addEventListener("click", () => {
  const publication = state.publications.find((item) => item.id === activePublicationId);
  if (!publication) return;
  activeAuthorLogin = publication.authorLogin;
  showScreen("author");
});
document.querySelector("#article-institute-link").addEventListener("click", () => {
  const publication = state.publications.find((item) => item.id === activePublicationId);
  if (!publication) return;
  activeInstitute = publication.institute;
  showScreen("institute");
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;

  if (button.dataset.addArticle) {
    editPublicationId = "";
    preselectedBranch = button.dataset.addArticle;
    showScreen("publish");
  }

  if (button.dataset.openPublication) {
    activePublicationId = button.dataset.openPublication;
    showScreen("article");
  }

  if (button.dataset.viewFile) {
    viewFile(button.dataset.viewFile);
  }

  if (button.dataset.editPublication) {
    editPublicationId = button.dataset.editPublication;
    preselectedBranch = "";
    showScreen("publish");
  }

  if (button.dataset.openAuthor) {
    activeAuthorLogin = button.dataset.openAuthor;
    showScreen("author");
  }
});

searchInput.addEventListener("input", renderSearch);

showScreen("home");
