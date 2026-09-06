/*
 * frontend/js/app.js
 *
 * Основной frontend магазина.
 *
 * API:
 *   /api/v1/auth
 *   /api/v1/products
 *   /api/v1/categories
 *   /api/v1/cart
 *   /api/v1/orders
 */

const API = "/api/v1";

const state = {
    accessToken: localStorage.getItem("access_token") || null,
    refreshToken: localStorage.getItem("refresh_token") || null,
    user: null,
    productsPage: 1,
    productsPages: 1,
    isRefreshing: false,
    editingCategoryId: null,
    editingProductId: null,
    cartItems: [],
    cartSelected: null,
    checkoutSelected: [],
};

const WISHLIST_KEY = "garden_wishlist";

let currentOrderId = null;
let selectedPaymentMethod = null;
let allCategories = [];
let adminOrdersRefreshTimer = null;


/* ============================================================
   DOM
   ============================================================ */

const $ = (selector) => document.querySelector(selector);

function getElement(selector) {
    return document.querySelector(selector);
}


/* ============================================================
   HTML SECURITY
   ============================================================ */

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeAttribute(value) {
    return escapeHtml(value);
}


/* ============================================================
   AUTH / TOKENS
   ============================================================ */

function saveTokens(tokens) {
    if (!tokens || !tokens.access_token) {
        throw new Error("Сервер не вернул access token.");
    }

    state.accessToken = tokens.access_token;

    if (tokens.refresh_token) {
        state.refreshToken = tokens.refresh_token;
    }

    localStorage.setItem("access_token", state.accessToken);

    if (state.refreshToken) {
        localStorage.setItem("refresh_token", state.refreshToken);
    }
}


function clearSession() {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;

    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
}


function isAuthenticated() {
    return Boolean(state.accessToken);
}


/* ============================================================
   TOAST
   ============================================================ */

let toastTimer = null;

function showToast(message, type = "success") {
    const toast = $("#toast");

    if (!toast) {
        console[type === "error" ? "error" : "log"](message);
        return;
    }

    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove("hidden");

    if (toastTimer) {
        clearTimeout(toastTimer);
    }

    toastTimer = setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}


/* ============================================================
   ERROR HANDLING
   ============================================================ */

async function getResponseData(response) {
    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
        return null;
    }

    try {
        return await response.json();
    } catch {
        return null;
    }
}


function extractValidationMessage(detail) {
    if (!Array.isArray(detail)) {
        return null;
    }

    const messages = detail
        .map((item) => {
            if (!item) {
                return null;
            }

            const message = item.msg || item.message;

            if (!message) {
                return null;
            }

            const location = Array.isArray(item.loc)
                ? item.loc.filter((part) => part !== "body").join(".")
                : "";

            return location
                ? `${location}: ${message}`
                : message;
        })
        .filter(Boolean);

    return messages.length ? messages.join("\n") : null;
}


async function getErrorMessage(response) {
    const data = await getResponseData(response);

    if (!data) {
        switch (response.status) {
            case 400:
                return "Некорректный запрос.";
            case 401:
                return "Необходима авторизация.";
            case 403:
                return "Недостаточно прав.";
            case 404:
                return "Запрашиваемый ресурс не найден.";
            case 409:
                return "Такие данные уже существуют.";
            case 422:
                return "Проверьте правильность введённых данных.";
            case 429:
                return "Слишком много запросов. Попробуйте позже.";
            case 500:
                return "Внутренняя ошибка сервера.";
            case 502:
                return "Сервис временно недоступен.";
            case 503:
                return "Сервис временно недоступен.";
            default:
                return `Ошибка HTTP ${response.status}`;
        }
    }

    if (data.message) {
        return String(data.message);
    }

    if (data.detail) {
        if (typeof data.detail === "string") {
            return data.detail;
        }

        const validationMessage = extractValidationMessage(data.detail);

        if (validationMessage) {
            return validationMessage;
        }

        if (Array.isArray(data.detail) && data.detail[0]?.msg) {
            return data.detail[0].msg;
        }
    }

    if (data.error) {
        return String(data.error);
    }

    switch (response.status) {
        case 400:
            return "Некорректный запрос.";
        case 401:
            return "Необходима авторизация.";
        case 403:
            return "Недостаточно прав.";
        case 404:
            return "Ресурс не найден.";
        case 409:
            return "Конфликт данных.";
        case 422:
            return "Ошибка валидации данных.";
        case 429:
            return "Слишком много запросов.";
        case 500:
            return "Внутренняя ошибка сервера.";
        case 502:
            return "Сервис временно недоступен.";
        case 503:
            return "Сервис временно недоступен.";
        default:
            return "Произошла неизвестная ошибка.";
    }
}


/* ============================================================
   TOKEN REFRESH
   ============================================================ */

async function refreshTokens() {
    if (!state.refreshToken) {
        return false;
    }

    if (state.isRefreshing) {
        return false;
    }

    state.isRefreshing = true;

    try {
        const response = await fetch(`${API}/auth/refresh`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body: JSON.stringify({
                refresh_token: state.refreshToken,
            }),
        });

        if (!response.ok) {
            clearSession();
            return false;
        }

        const tokens = await response.json();

        saveTokens(tokens);

        return true;
    } catch (error) {
        console.error("Token refresh failed:", error);
        clearSession();
        return false;
    } finally {
        state.isRefreshing = false;
    }
}


/* ============================================================
   API REQUEST
   ============================================================ */

async function apiFetch(path, options = {}, useAuth = true) {
    const requestOptions = {
        ...options,
    };

    const headers = {
        Accept: "application/json",
        ...(options.headers || {}),
    };

    /*
     * Не устанавливаем Content-Type для FormData.
     * Для JSON-запросов устанавливаем автоматически.
     */
    if (
        options.body &&
        !(options.body instanceof FormData) &&
        typeof options.body === "string"
    ) {
        headers["Content-Type"] = "application/json";
    }

    if (useAuth && state.accessToken) {
        headers["Authorization"] = `Bearer ${state.accessToken}`;
    }

    requestOptions.headers = headers;

    /*
     * _retry не должен уходить в fetch.
     */
    delete requestOptions._retry;

    let response;

    try {
        response = await fetch(`${API}${path}`, requestOptions);
    } catch (error) {
        console.error("Network error:", error);
        throw new Error(
            "Не удалось подключиться к серверу. Проверьте, запущен ли backend."
        );
    }

    /*
     * Access token истёк.
     */
    if (
        response.status === 401 &&
        useAuth &&
        !options._retry &&
        state.refreshToken
    ) {
        const refreshed = await refreshTokens();

        if (refreshed) {
            return apiFetch(
                path,
                {
                    ...options,
                    _retry: true,
                },
                useAuth
            );
        }

        clearSession();
        showAuth();

        throw new Error("Сессия истекла. Войдите в аккаунт снова.");
    }

    if (!response.ok) {
        throw new Error(await getErrorMessage(response));
    }

    if (response.status === 204) {
        return null;
    }

    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
        return response.text();
    }

    return response.json();
}


/* ============================================================
   UPLOADS
   ============================================================ */

async function uploadImage(file, folder) {
    if (!file) {
        return null;
    }

    const formData = new FormData();
    formData.append("folder", folder);
    formData.append("file", file);

    const result = await apiFetch("/uploads", {
        method: "POST",
        body: formData,
    });

    return result?.url || null;
}


/* ============================================================
   FORMATTING
   ============================================================ */

function formatMoney(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "0 ₽";
    }

    return new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: "RUB",
        maximumFractionDigits: 0,
    }).format(number);
}


function formatDate(value) {
    if (!value) {
        return "";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    return date.toLocaleString("ru-RU");
}


/* ============================================================
   CATEGORIES
   ============================================================ */

function getCategoryById(id) {
    return allCategories.find(
        (category) => category.id === Number(id)
    );
}


const SLUG_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "iu", "я": "ia",
};


function slugify(value) {
    const lower = String(value || "")
        .toLowerCase()
        .trim();

    let result = "";

    for (const char of lower) {
        const translit = SLUG_TRANSLIT[char];

        if (translit !== undefined) {
            result += translit;
        } else if (/[a-z0-9]/.test(char)) {
            result += char;
        } else if (/[\s_-]/.test(char)) {
            result += "-";
        }
    }

    result = result.replace(/-{2,}/g, "-");
    result = result.replace(/^-+|-+$/g, "");

    // Несколько слов подряд складываем через дефис у исходных пробелов.
    result = result.replace(/\s+/g, "-");

    return result;
}


function bindCategorySlugAutofill() {
    const nameInput = $("#category-name");
    const slugInput = $("#category-slug");

    if (!nameInput || !slugInput) {
        return;
    }

    nameInput.addEventListener("input", () => {
        // Автозаполняем только если пользователь ещё не вводил slug вручную.
        if (!slugInput.dataset.edited) {
            slugInput.value = slugify(nameInput.value);
        }
    });

    slugInput.addEventListener("input", () => {
        slugInput.dataset.edited = "1";
    });
}


async function loadCategories() {
    try {
        const data = await apiFetch("/categories", {}, false);

        allCategories = Array.isArray(data)
            ? data
            : data?.items || [];

        renderCategories();
        renderCategorySelects();
    } catch (error) {
        console.error("Failed to load categories:", error);
    }
}


function renderCategories() {
    const categoryGrid = $("#category-grid");

    if (!categoryGrid) {
        return;
    }

    if (!allCategories.length) {
        categoryGrid.innerHTML = "";
        return;
    }

    categoryGrid.innerHTML = allCategories
        .map((category) => {
            const id = Number(category.id);
            const name = escapeHtml(category.name);
            const icon = escapeHtml(category.icon || "🌿");
            const description = escapeHtml(category.description || "");

            const imageUrl = category.image_url
                ? escapeAttribute(category.image_url)
                : "";

            const image = imageUrl
                ? `
                    <img
                        class="category-image"
                        src="${imageUrl}"
                        alt="${name}"
                        loading="lazy"
                        onerror="this.style.display='none'"
                    />
                `
                : "";

            return `
                <div
                    class="category-card"
                    data-category-id="${id}"
                    role="button"
                    tabindex="0"
                >
                    <div class="category-icon">${icon}</div>
                    ${image}
                    <h3>${name}</h3>
                    <p>${description}</p>
                </div>
            `;
        })
        .join("");
}


function renderCategorySelects() {
    const filterSelect = $("#product-category");

    if (filterSelect) {
        filterSelect.innerHTML =
            '<option value="">Все категории</option>' +
            allCategories
                .map(
                    (category) =>
                        `<option value="${Number(category.id)}">${escapeHtml(
                            category.name
                        )}</option>`
                )
                .join("");
    }

    const createSelect = $("#product-category-create");

    if (createSelect) {
        createSelect.innerHTML = allCategories
            .map(
                (category) =>
                    `<option value="${Number(category.id)}">${escapeHtml(
                        category.name
                    )}</option>`
            )
            .join("");
    }
}


function filterByCategory(categoryId) {
    const categorySelect = $("#product-category");

    if (categorySelect) {
        categorySelect.value = String(categoryId);
    }

    state.productsPage = 1;

    showView("catalog");

    const category = getCategoryById(categoryId);

    showToast(
        `Категория: ${category ? category.name : categoryId}`
    );

    const productsHeading = $("#products");

    if (productsHeading) {
        productsHeading.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
}


/* ============================================================
   NAVIGATION / VIEWS
   ============================================================ */

function showView(name) {
    if (adminOrdersRefreshTimer) {
        clearInterval(adminOrdersRefreshTimer);
        adminOrdersRefreshTimer = null;
    }

    document
        .querySelectorAll(".view")
        .forEach((view) => view.classList.add("hidden"));

    const target = $(`#view-${name}`);

    if (!target) {
        console.warn(`View not found: view-${name}`);
        return;
    }

    target.classList.remove("hidden");

    document
        .querySelectorAll(".nav-btn")
        .forEach((button) => {
            button.classList.toggle(
                "active",
                button.dataset.view === name
            );
        });

    if (name === "catalog") {
        loadProducts().catch((error) => {
            showToast(error.message, "error");
        });
    }

    if (name === "cart") {
        if (!isAuthenticated()) {
            showAuthModal();
            return;
        }

        loadCart().catch((error) => {
            showToast(error.message, "error");
        });
    }

    if (name === "orders") {
        if (!isAuthenticated()) {
            showAuthModal();
            return;
        }

        loadOrders().catch((error) => {
            showToast(error.message, "error");
        });
    }

    if (name === "admin") {
        if (!state.user?.is_admin) {
            showToast("Доступ запрещён.", "error");
            showView("catalog");
            return;
        }

        loadAdminProducts().catch((error) => {
            showToast(error.message, "error");
        });

        loadAdminCategories().catch((error) => {
            showToast(error.message, "error");
        });

        loadAdminOrders().catch((error) => {
            showToast(error.message, "error");
        });

        adminOrdersRefreshTimer = setInterval(() => {
            loadAdminOrders().catch((error) => {
                console.warn("Failed to refresh admin orders:", error);
            });
        }, 20000);
    }
}


function showAuth() {
    const nav = $("#nav");
    const userBox = $("#user-box");
    const guestLoginButton = $("#guest-login-btn");

    if (nav) nav.classList.add("hidden");
    if (userBox) userBox.classList.add("hidden");
    if (guestLoginButton) guestLoginButton.classList.add("hidden");

    document
        .querySelectorAll(".view")
        .forEach((view) => view.classList.add("hidden"));

    const authView = $("#view-auth");

    if (authView) {
        authView.classList.remove("hidden");
    }
}


function showCatalogForGuest() {
    const nav = $("#nav");
    const userBox = $("#user-box");
    const guestLoginButton = $("#guest-login-btn");

    if (nav) nav.classList.add("hidden");
    if (userBox) userBox.classList.add("hidden");
    if (guestLoginButton) guestLoginButton.classList.remove("hidden");

    document
        .querySelectorAll(".view")
        .forEach((view) => view.classList.add("hidden"));

    const catalog = $("#view-catalog");

    if (catalog) {
        catalog.classList.remove("hidden");
    }

    loadProducts().catch((error) => {
        showToast(error.message, "error");
    });
}


function renderNav() {
    if (!state.user) {
        return;
    }

    const nav = $("#nav");
    const userBox = $("#user-box");
    const guestLoginButton = $("#guest-login-btn");
    const userName = $("#user-name");
    const adminNav = $("#admin-nav");
    const inactiveFilter = $("#inactive-filter");

    if (nav) nav.classList.remove("hidden");
    if (userBox) userBox.classList.remove("hidden");
    if (guestLoginButton) guestLoginButton.classList.add("hidden");

    if (userName) {
        userName.textContent = state.user.full_name || "";
    }

    if (adminNav) {
        adminNav.classList.toggle(
            "hidden",
            !state.user.is_admin
        );
    }

    if (inactiveFilter) {
        inactiveFilter.classList.toggle(
            "hidden",
            !state.user.is_admin
        );
    }
}


/* ============================================================
   AUTH
   ============================================================ */

async function loadMe() {
    state.user = await apiFetch("/auth/me");
    renderNav();

    await updateCartBadge();
}


async function login(identifier, password) {
    const tokens = await apiFetch(
        "/auth/login",
        {
            method: "POST",
            body: JSON.stringify({
                identifier: identifier.trim(),
                password,
            }),
        },
        false
    );

    saveTokens(tokens);

    await loadMe();

    showView("catalog");
}


async function registerAndLogin(payload) {
    await apiFetch(
        "/auth/register",
        {
            method: "POST",
            body: JSON.stringify(payload),
        },
        false
    );

    /*
     * После успешной регистрации автоматически авторизуем пользователя.
     */
    await login(payload.email, payload.password);
}


/* ============================================================
   PASSWORD VALIDATION
   ============================================================ */

function validatePasswordClient(password) {
    if (!password || password.length < 8) {
        return "Пароль должен содержать минимум 8 символов.";
    }

    if (!/^[A-Za-z0-9$%&!:]+$/.test(password)) {
        return "Пароль может содержать только латинские буквы, цифры и символы $%&!:";
    }

    if (!/[A-Z]/.test(password)) {
        return "Пароль должен содержать хотя бы одну заглавную латинскую букву.";
    }

    if (!/[$%&!:]/.test(password)) {
        return "Пароль должен содержать хотя бы один специальный символ: $%&!:";
    }

    return null;
}


/* ============================================================
   PRODUCTS
   ============================================================ */

function productCard(product) {
    const id = Number(product.id);
    const name = escapeHtml(product.name);
    const sku = escapeHtml(product.sku);
    const size = escapeHtml(product.size || "");
    const imageUrl = product.image_url
        ? escapeAttribute(product.image_url)
        : "";

    const category = getCategoryById(product.category_id);

    const categoryHtml = category
        ? `${escapeHtml(category.icon || "🌿")} ${escapeHtml(
              category.name
          )}`
        : "Без категории";

    const imageHtml = imageUrl
        ? `
            <img
                src="${imageUrl}"
                alt="${name}"
                class="product-image"
                loading="lazy"
                onerror="this.outerHTML='<div class=&quot;product-image-placeholder&quot;>📦</div>'"
            />
        `
        : `
            <div class="product-image-placeholder">
                📦
            </div>
        `;

    const sizeHtml = size
        ? `<div class="product-size">📏 ${size}</div>`
        : "";

    const isActive = Boolean(product.is_active);
    const wishlisted = isWishlisted(id);

    return `
        <article class="product-card" data-id="${id}">
            <button
                type="button"
                class="wishlist-btn ${wishlisted ? "active" : ""}"
                data-action="toggle-wishlist"
                data-id="${id}"
                aria-label="В избранное"
                title="В избранное"
            >
                ${wishlisted ? "♥" : "♡"}
            </button>

            ${imageHtml}

            <div class="product-card-header">
                <div class="product-name">${name}</div>

                <span class="badge ${isActive ? "" : "inactive"}">
                    ${isActive ? "✓" : "✗"}
                </span>
            </div>

            <div class="product-meta">
                <span class="product-category">
                    ${categoryHtml}
                </span>

                <span class="product-sku">
                    Артикул: ${sku}
                </span>
            </div>

            ${sizeHtml}

            <div class="product-price">
                ${formatMoney(product.price)}
            </div>

            <button
                class="btn btn-primary"
                data-action="add-to-cart"
                data-id="${id}"
                ${!isActive ? "disabled" : ""}
            >
                ${isActive ? "В корзину" : "Недоступен"}
            </button>
        </article>
    `;
}


async function loadProducts() {
    const productsContainer = $("#products");

    if (!productsContainer) {
        return;
    }

    const sortBy = $("#filter-sort-by")?.value || "name";
    const sortOrder = $("#filter-sort-order")?.value || "asc";

    const params = new URLSearchParams({
        page: String(state.productsPage),
        size: "9",
        sort_by: sortBy,
        sort_order: sortOrder,
    });

    const name = $("#filter-name")?.value.trim();
    const minPrice = $("#filter-min-price")?.value;
    const maxPrice = $("#filter-max-price")?.value;
    const categoryFilter = $("#product-category")?.value;

    if (name) {
        params.set("name", name);
    }

    if (minPrice) {
        params.set("min_price", minPrice);
    }

    if (maxPrice) {
        params.set("max_price", maxPrice);
    }

    if (categoryFilter) {
        params.set("category_id", categoryFilter);
    }

    const includeInactive =
        state.user?.is_admin &&
        $("#filter-include-inactive")?.checked;

    if (includeInactive) {
        params.set("include_inactive", "true");
    }

    const data = await apiFetch(
        `/products?${params.toString()}`,
        {},
        false
    );

    let items = Array.isArray(data)
        ? data
        : data?.items || [];

    const wishlistOnly =
        $("#filter-wishlist-only")?.checked;

    if (wishlistOnly) {
        const wishlistIds = new Set(getWishlist());
        items = items.filter(
            (product) =>
                wishlistIds.has(Number(product.id))
        );
    }

    state.productsPages = Number(data?.pages || 1);

    productsContainer.innerHTML = items.length
        ? items.map(productCard).join("")
        : `
            <p style="
                grid-column: 1/-1;
                text-align: center;
                color: var(--text-secondary);
                padding: 40px;
            ">
                ${
                    wishlistOnly
                        ? "В избранном нет товаров"
                        : "Товары не найдены"
                }
            </p>
        `;

    const pageInfo = $("#page-info");

    if (pageInfo) {
        pageInfo.textContent =
            `Страница ${state.productsPage} из ${state.productsPages}`;
    }
}


async function showProduct(productId) {
    const container = $("#product-detail");

    if (!container) {
        return;
    }

    container.innerHTML = `
        <div class="modal-loading">
            Загрузка...
        </div>
    `;

    showView("product");

    try {
        const product = await apiFetch(
            `/products/${Number(productId)}`,
            {},
            false
        );

        const id = Number(product.id);
        const name = escapeHtml(product.name);
        const sku = escapeHtml(product.sku || "");
        const size = escapeHtml(product.size || "");
        const description = escapeHtml(product.description || "");
        const isActive = Boolean(product.is_active);
        const wishlisted = isWishlisted(id);

        const category = getCategoryById(product.category_id);

        const categoryHtml = category
            ? `${escapeHtml(category.icon || "🌿")} ${escapeHtml(
                  category.name
              )}`
            : "Без категории";

        const imageHtml = product.image_url
            ? `
                <img
                    src="${escapeAttribute(product.image_url)}"
                    alt="${name}"
                    class="product-detail-image"
                    onerror="this.outerHTML='<div class=&quot;product-detail-placeholder&quot;>📦</div>'"
                />
            `
            : `
                <div class="product-detail-placeholder">
                    📦
                </div>
            `;

        container.innerHTML = `
            <div class="product-detail">
                <div class="product-detail-actions">
                    <button
                        type="button"
                        class="btn btn-secondary btn-sm"
                        data-action="back-to-catalog"
                    >
                        ← Назад
                    </button>
                </div>

                <div class="product-detail-grid">
                    ${imageHtml}

                    <div class="product-detail-info">
                        <div class="product-detail-category">
                            ${categoryHtml}
                        </div>

                        <h1 class="product-detail-title">
                            ${name}
                        </h1>

                        <div class="product-detail-price">
                            ${formatMoney(product.price)}
                        </div>

                        <div class="product-detail-meta">
                            <span>Артикул: ${sku}</span>
                            ${
                                size
                                    ? `<span>Размер: ${size}</span>`
                                    : ""
                            }
                        </div>

                        <div class="product-detail-buttons">
                            <button
                                type="button"
                                class="btn btn-secondary"
                                data-action="toggle-wishlist"
                                data-id="${id}"
                            >
                                ${
                                    wishlisted
                                        ? "♥ В избранном"
                                        : "♡ Добавить в избранное"
                                }
                            </button>

                            <button
                                type="button"
                                class="btn btn-primary"
                                data-action="order-product"
                                data-id="${id}"
                                ${!isActive ? "disabled" : ""}
                            >
                                Заказать
                            </button>

                            <button
                                type="button"
                                class="btn btn-secondary"
                                data-action="add-to-cart"
                                data-id="${id}"
                                ${!isActive ? "disabled" : ""}
                            >
                                Добавить в корзину
                            </button>
                        </div>
                    </div>
                </div>

                <div class="product-detail-description">
                    <h2>Описание</h2>
                    <p>
                        ${
                            description ||
                            "Описание отсутствует"
                        }
                    </p>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `
            <p class="modal-error">
                Ошибка: ${escapeHtml(error.message)}
            </p>
        `;
    }
}


function backToCatalog() {
    showView("catalog");
}


async function orderProduct(productId) {
    if (!isAuthenticated()) {
        showAuthModal();
        return;
    }

    try {
        await apiFetch("/cart/items", {
            method: "POST",
            body: JSON.stringify({
                items: [
                    {
                        product_id: Number(productId),
                        quantity: 1,
                    },
                ],
            }),
        });

        showToast("Товар добавлен для заказа");

        await updateCartBadge();

        showView("cart");
    } catch (error) {
        showToast(error.message, "error");
    }
}


/* ============================================================
   CART
   ============================================================ */

async function addToCart(productId) {
    if (!isAuthenticated()) {
        showAuthModal();
        return;
    }

    try {
        await apiFetch("/cart/items", {
            method: "POST",
            body: JSON.stringify({
                items: [
                    {
                        product_id: Number(productId),
                        quantity: 1,
                    },
                ],
            }),
        });

        showToast("Товар добавлен в корзину");

        await updateCartBadge();
    } catch (error) {
        showToast(error.message, "error");
    }
}


async function updateCartBadge() {
    const badge = $("#cart-badge");

    if (!badge) {
        return;
    }

    if (!isAuthenticated()) {
        badge.textContent = "0";
        badge.classList.add("badge-hidden");
        return;
    }

    try {
        const cart = await apiFetch("/cart");

        const items = Array.isArray(cart?.items)
            ? cart.items
            : [];

        const count = items.reduce(
            (sum, item) => sum + Number(item.quantity || 0),
            0
        );

        badge.textContent = String(count);

        badge.classList.toggle(
            "badge-hidden",
            count === 0
        );
    } catch (error) {
        console.error(
            "Failed to update cart badge:",
            error
        );
    }
}


/* ============================================================
   WISHLIST
   ============================================================ */

function getWishlist() {
    try {
        const raw = localStorage.getItem(WISHLIST_KEY);
        const ids = raw ? JSON.parse(raw) : [];
        return Array.isArray(ids)
            ? ids.map(Number).filter(Number.isFinite)
            : [];
    } catch (error) {
        return [];
    }
}


function isWishlisted(productId) {
    return getWishlist().includes(Number(productId));
}


function updateWishlistBadge() {
    const badge = $("#wishlist-badge");

    if (!badge) {
        return;
    }

    const count = getWishlist().length;
    badge.textContent = String(count);
    badge.classList.toggle("badge-hidden", count === 0);
}


function toggleWishlist(productId) {
    const id = Number(productId);
    const list = getWishlist();
    const index = list.indexOf(id);

    if (index === -1) {
        list.push(id);
    } else {
        list.splice(index, 1);
    }

    localStorage.setItem(WISHLIST_KEY, JSON.stringify(list));

    updateWishlistBadge();

    return index === -1;
}


function cartItemRow(item) {
    const productId = Number(item.product_id);
    const name = escapeHtml(item.name);
    const selected =
        state.cartSelected === null ||
        state.cartSelected.includes(productId);

    return `
        <div class="row cart-item-row ${selected ? "" : "unselected"}">

            <label class="cart-select">
                <input
                    type="checkbox"
                    data-action="toggle-cart-selection"
                    data-id="${productId}"
                    ${selected ? "checked" : ""}
                    aria-label="Выбрать товар"
                >
            </label>

            <div style="flex: 1;">
                <div style="font-weight: 600;">
                    ${name}
                </div>

                <div class="muted">
                    ${formatMoney(item.price)}
                    ×
                    ${Number(item.quantity || 0)}
                </div>
            </div>

            <div style="
                display: flex;
                align-items: center;
                gap: 16px;
            ">
                <div style="font-weight: 700;">
                    ${formatMoney(item.subtotal)}
                </div>

                <button
                    class="btn btn-danger btn-sm"
                    data-action="remove-cart-item"
                    data-id="${productId}"
                >
                    Удалить
                </button>
            </div>

        </div>
    `;
}


async function loadCart() {
    const container = $("#cart-items");

    if (!container) {
        return;
    }

    const cart = await apiFetch("/cart");

    const items = Array.isArray(cart?.items)
        ? cart.items
        : [];

    state.cartItems = items;

    const itemIds = items.map((item) =>
        Number(item.product_id)
    );

    if (state.cartSelected === null) {
        state.cartSelected = itemIds;
    } else {
        state.cartSelected = state.cartSelected.filter(
            (id) => itemIds.includes(id)
        );
    }

    container.innerHTML = items.length
        ? items.map(cartItemRow).join("")
        : `
            <p style="
                text-align: center;
                color: var(--text-secondary);
                padding: 40px;
            ">
                Корзина пуста
            </p>
        `;

    const selectedIds = new Set(state.cartSelected);

    const selectedTotal = items.reduce(
        (sum, item) =>
            selectedIds.has(Number(item.product_id))
                ? sum + Number(item.subtotal || 0)
                : sum,
        0
    );

    const total = $("#cart-total");

    if (total) {
        total.textContent = formatMoney(selectedTotal);
    }

    await updateCartBadge();
}


function toggleCartSelection(productId) {
    const id = Number(productId);

    const current =
        state.cartSelected === null
            ? (state.cartItems || []).map((item) =>
                  Number(item.product_id)
              )
            : [...state.cartSelected];

    const index = current.indexOf(id);

    if (index === -1) {
        current.push(id);
    } else {
        current.splice(index, 1);
    }

    state.cartSelected = current;
}


/* ============================================================
   ORDERS
   ============================================================ */

async function checkout() {
    const selected =
        state.cartSelected === null
            ? (state.cartItems || []).map((item) =>
                  Number(item.product_id)
              )
            : [...state.cartSelected];

    if (selected.length === 0) {
        showToast(
            "Выберите товары для заказа.",
            "error"
        );
        return;
    }

    state.checkoutSelected = selected;

    openCheckoutModal();
}


function openCheckoutModal() {
    const modal = $("#checkout-modal");
    const content = $("#checkout-content");

    if (!modal || !content) {
        return;
    }

    content.innerHTML = `
        <div class="checkout-form">
            <div class="form-group">
                <label>Способ доставки</label>
                <select id="checkout-delivery-method">
                    <option value="pickup">Самовывоз</option>
                    <option value="delivery">Транспортная компания (доставка)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Стоимость доставки (₽)</label>
                <input
                    type="number"
                    id="checkout-delivery-cost"
                    value="0"
                    min="0"
                >
            </div>

            <div class="form-group">
                <label>Адрес доставки</label>
                <input
                    type="text"
                    id="checkout-delivery-address"
                    placeholder="Город, улица, дом"
                >
            </div>

            <div class="form-group">
                <label>ФИО получателя (полностью)</label>
                <input
                    type="text"
                    id="checkout-recipient-name"
                    placeholder="Иванов Иван Иванович"
                >
            </div>

            <div class="modal-buttons">
                <button
                    type="button"
                    class="btn btn-secondary"
                    data-action="close-checkout-modal"
                >
                    Отмена
                </button>
                <button
                    type="button"
                    class="btn btn-primary"
                    data-action="confirm-checkout"
                >
                    Подтвердить заказ
                </button>
            </div>
        </div>
    `;

    const methodSelect = content.querySelector(
        "#checkout-delivery-method"
    );

    const addressGroup = content.querySelector(
        "#checkout-delivery-address"
    ).closest(".form-group");

    const costGroup = content.querySelector(
        "#checkout-delivery-cost"
    ).closest(".form-group");

    function syncMethod() {
        const method = methodSelect.value;
        const isDelivery = method === "delivery";
        addressGroup.style.display = isDelivery
            ? "flex"
            : "none";
        costGroup.style.display = isDelivery
            ? "flex"
            : "none";
    }

    methodSelect.addEventListener("change", syncMethod);
    syncMethod();

    modal.classList.remove("hidden");
}


function closeCheckoutModal() {
    const modal = $("#checkout-modal");

    if (modal) {
        modal.classList.add("hidden");
    }
}


async function confirmCheckout() {
    const deliveryMethod = $("#checkout-delivery-method")?.value;

    const deliveryCost = Number(
        $("#checkout-delivery-cost")?.value || 0
    );

    const deliveryAddress =
        $("#checkout-delivery-address")?.value.trim() || "";

    const recipientName =
        $("#checkout-recipient-name")?.value.trim() || "";

    const isDelivery = deliveryMethod === "delivery";

    if (isDelivery && (!deliveryAddress || !recipientName)) {
        showToast(
            "Укажите адрес доставки и ФИО получателя.",
            "error"
        );
        return;
    }

    try {
        await apiFetch(
            "/orders/checkout",
            {
                method: "POST",
                body: JSON.stringify({
                    product_ids: state.checkoutSelected,
                    delivery_method: deliveryMethod,
                    delivery_cost: isDelivery
                        ? deliveryCost
                        : 0,
                    delivery_address: isDelivery
                        ? deliveryAddress
                        : null,
                    recipient_name: isDelivery
                        ? recipientName
                        : null,
                }),
            }
        );

        state.cartSelected = null;

        closeCheckoutModal();

        showToast("Заказ успешно создан!");

        showView("orders");

        if (state.user?.is_admin) {
            loadAdminOrders().catch((error) => {
                console.warn("Failed to refresh admin orders:", error);
            });
        }
    } catch (error) {
        showToast(error.message, "error");
    }
}


function orderCard(order) {
    const statusText = {
        pending_payment: "Ожидает оплаты",
        paid: "Оплачен",
        cancelled: "Отменён",
        created: "Создан",
    };

    const statusClass = {
        pending_payment: "pending",
        paid: "paid",
        cancelled: "cancelled",
        created: "pending",
    };

    const paymentMethodText = {
        card: "💳 Карта",
        sbp: "📱 СБП",
        cash: "💵 Наличные",
    };

    const status = order.status;

    let actionButtons = "";

    if (
        status === "pending_payment" ||
        status === "created"
    ) {
        actionButtons = `
            <div style="
                display: flex;
                gap: 12px;
            ">
                <button
                    class="btn btn-primary btn-sm"
                    data-action="pay-order"
                    data-id="${Number(order.id)}"
                >
                    Оплатить
                </button>

                <button
                    class="btn btn-danger btn-sm"
                    data-action="cancel-order"
                    data-id="${Number(order.id)}"
                >
                    Отменить
                </button>
            </div>
        `;
    } else if (
        status === "paid" &&
        order.paid_at
    ) {
        actionButtons = `
            <span style="
                color: var(--text-secondary);
                font-size: 13px;
            ">
                Оплачено ${formatDate(order.paid_at)}
            </span>
        `;
    }

    const items = Array.isArray(order.items)
        ? order.items
        : [];

    return `
        <div
            class="card glass-inset"
            style="margin-bottom: 16px;"
        >

            <div
                class="row"
                style="
                    border: none;
                    background: transparent;
                    padding: 0 0 16px 0;
                "
            >

                <div>
                    <div style="
                        font-weight: 700;
                        font-size: 18px;
                    ">
                        Заказ #${Number(order.id)}
                    </div>

                    <div class="muted">
                        ${formatDate(order.created_at)}
                    </div>

                    <div class="order-items-count">
                        Товаров: ${items.length}
                    </div>
                </div>

                <div style="
                    display: flex;
                    flex-direction: column;
                    align-items: flex-end;
                    gap: 8px;
                ">

                    <span class="status-badge ${
                        statusClass[status] || "pending"
                    }">
                        ${
                            escapeHtml(
                                statusText[status] || status
                            )
                        }
                    </span>

                    ${
                        order.payment_method
                            ? `
                                <span style="
                                    font-size: 13px;
                                    color: var(--text-secondary);
                                ">
                                    ${
                                        escapeHtml(
                                            paymentMethodText[
                                                order.payment_method
                                            ] ||
                                            order.payment_method
                                        )
                                    }
                                </span>
                            `
                            : ""
                    }

                </div>
            </div>

            <div style="
                gap: 8px;
                display: flex;
                flex-direction: column;
            ">

                ${
                    items
                        .map(
                            (item) => `
                                <div
                                    class="row"
                                    style="padding: 12px;"
                                >
                                    <div style="flex: 1;">
                                        ${escapeHtml(
                                            item.product_name
                                        )}
                                    </div>

                                    <div class="muted">
                                        ${formatMoney(item.price)}
                                        ×
                                        ${Number(
                                            item.quantity || 0
                                        )}
                                    </div>

                                    <div style="
                                        font-weight: 600;
                                    ">
                                        ${formatMoney(
                                            item.subtotal
                                        )}
                                    </div>
                                </div>
                            `
                        )
                        .join("")
                }

            </div>

            <div class="order-delivery">
                <div class="order-delivery-title">
                    🚚 Доставка
                </div>

                ${
                    order.delivery_method === "delivery"
                        ? `
                            <div>
                                Транспортная компания
                            </div>
                            <div>
                                Стоимость доставки:
                                ${formatMoney(
                                    Number(
                                        order.delivery_cost || 0
                                    )
                                )}
                            </div>
                            <div>
                                Адрес: ${escapeHtml(
                                    order.delivery_address || ""
                                )}
                            </div>
                            <div>
                                Получатель: ${escapeHtml(
                                    order.recipient_name || ""
                                )}
                            </div>
                        `
                        : `
                            <div>Самовывоз</div>
                        `
                }
            </div>

            <div style="
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid var(--glass-border);
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            ">

                ${actionButtons}

                <span style="
                    font-size: 20px;
                    font-weight: 800;
                ">
                    Итого:
                    ${formatMoney(order.total_amount)}
                </span>

            </div>

        </div>
    `;
}


async function loadOrders() {
    const container = $("#orders");

    if (!container) {
        return;
    }

    const data = await apiFetch("/orders");

    const orders = Array.isArray(data)
        ? data
        : data?.items || [];

    container.innerHTML = orders.length
        ? orders.map(orderCard).join("")
        : `
            <p style="
                text-align: center;
                color: var(--text-secondary);
                padding: 40px;
            ">
                У вас пока нет заказов
            </p>
        `;
}


/* ============================================================
   ADMIN PRODUCTS
   ============================================================ */

function adminProductRow(product) {
    const id = Number(product.id);

    const name = escapeHtml(product.name);
    const sku = escapeHtml(product.sku);
    const size = escapeHtml(product.size || "");

    const imageUrl = product.image_url
        ? escapeAttribute(product.image_url)
        : "";

    const category = getCategoryById(
        product.category_id
    );

    const categoryText = category
        ? `${escapeHtml(category.icon || "")} ${escapeHtml(
              category.name
          )}`
        : "Без категории";

    const thumbHtml = imageUrl
        ? `
            <img
                src="${imageUrl}"
                alt="${name}"
                style="
                    width: 48px;
                    height: 48px;
                    object-fit: cover;
                    border-radius: 8px;
                    margin-right: 12px;
                "
                loading="lazy"
                onerror="this.style.display='none'"
            />
        `
        : "";

    return `
        <div class="row">

            <div style="
                flex: 1;
                display: flex;
                align-items: center;
            ">

                ${thumbHtml}

                <div>
                    <div style="font-weight: 600;">
                        ${name}
                    </div>

                    <div class="muted">
                        ${formatMoney(product.price)}
                        •
                        ${categoryText}
                        •
                        ${sku}
                        ${size ? ` • ${size}` : ""}
                    </div>
                </div>

            </div>

            <div style="
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            ">

                <span class="badge ${
                    product.is_active
                        ? ""
                        : "inactive"
                }">
                    ${
                        product.is_active
                            ? "Активен"
                            : "Неактивен"
                    }
                </span>

                <button
                    class="btn btn-secondary btn-sm"
                    data-action="edit-product"
                    data-id="${id}"
                >
                    Изменить
                </button>

                <button
                    class="btn btn-secondary btn-sm"
                    data-action="toggle-product"
                    data-id="${id}"
                    data-active="${
                        Boolean(product.is_active)
                    }"
                >
                    ${
                        product.is_active
                            ? "Деактивировать"
                            : "Активировать"
                    }
                </button>

                <button
                    class="btn btn-danger btn-sm"
                    data-action="delete-product"
                    data-id="${id}"
                >
                    Удалить
                </button>

            </div>

        </div>
    `;
}


async function loadAdminProducts() {
    const container = $("#admin-products");

    if (!container) {
        return;
    }

    if (!state.user?.is_admin) {
        container.innerHTML = "";
        return;
    }

    const data = await apiFetch(
        "/products?size=100&include_inactive=true"
    );

    const products = Array.isArray(data)
        ? data
        : data?.items || [];

    container.innerHTML = products.length
        ? products.map(adminProductRow).join("")
        : `
            <p style="
                text-align: center;
                color: var(--text-secondary);
                padding: 20px;
            ">
                Товаров нет
            </p>
        `;
}


/* ============================================================
   ADMIN CATEGORIES
   ============================================================ */

function adminCategoryRow(category) {
    const id = Number(category.id);
    const name = escapeHtml(category.name);
    const slug = escapeHtml(category.slug);
    const icon = escapeHtml(category.icon || "");
    const imageUrl = category.image_url
        ? escapeAttribute(category.image_url)
        : "";

    const thumbHtml = imageUrl
        ? `
            <img
                src="${imageUrl}"
                alt="${name}"
                style="
                    width: 48px;
                    height: 48px;
                    object-fit: cover;
                    border-radius: 8px;
                    margin-right: 12px;
                "
                loading="lazy"
                onerror="this.style.display='none'"
            />
        `
        : "";

    return `
        <div class="row">

            <div style="
                flex: 1;
                display: flex;
                align-items: center;
            ">

                ${thumbHtml}

                <div>
                    <div style="font-weight: 600;">
                        ${icon} ${name}
                    </div>

                    <div class="muted">
                        ${slug}
                    </div>
                </div>

            </div>

            <div style="
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            ">

                <button
                    class="btn btn-secondary btn-sm"
                    data-action="edit-category"
                    data-id="${id}"
                >
                    Изменить
                </button>

                <button
                    class="btn btn-danger btn-sm"
                    data-action="delete-category"
                    data-id="${id}"
                >
                    Удалить
                </button>

            </div>

        </div>
    `;
}


async function loadAdminCategories() {
    const container = $("#admin-categories");

    if (!container) {
        return;
    }

    if (!state.user?.is_admin) {
        container.innerHTML = "";
        return;
    }

    const data = await apiFetch(
        "/categories",
        {},
        false
    );

    allCategories = Array.isArray(data)
        ? data
        : data?.items || [];

    renderCategorySelects();

        container.innerHTML = allCategories.length
        ? allCategories.map(adminCategoryRow).join("")
        : `
            <p style="
                text-align: center;
                color: var(--text-secondary);
                padding: 20px;
            ">
                Категорий нет
            </p>
        `;
}


/* ============================================================
   ADMIN ORDERS
   ============================================================ */

function adminOrderCard(order) {
    const statusText = {
        pending_payment: "Ожидает оплаты",
        paid: "Оплачен",
        cancelled: "Отменён",
        created: "Создан",
    };

    const items = Array.isArray(order.items)
        ? order.items
        : [];

    const deliveryText =
        order.delivery_method === "delivery"
            ? `Транспортная компания (${formatMoney(
                  Number(order.delivery_cost || 0)
              )})`
            : "Самовывоз";

    return `
        <div class="admin-order-row">
            <div class="admin-order-main">
                <div class="admin-order-title">
                    Заказ #${Number(order.id)}
                </div>

                <div class="muted">
                    ${formatDate(order.created_at)}
                </div>

                <div class="admin-order-user">
                    Пользователь #${Number(order.user_id)}
                </div>
            </div>

            <div class="admin-order-info">
                <div>
                    Товаров: ${items.length}
                </div>
                <div>${deliveryText}</div>
            </div>

            <div class="admin-order-total">
                ${formatMoney(order.total_amount)}
            </div>

            <div class="admin-order-status">
                <span class="status-badge ${
                    statusClassFor(order.status)
                }">
                    ${escapeHtml(
                        statusText[order.status] || order.status
                    )}
                </span>

                <select
                    class="admin-status-select"
                    data-action="admin-change-status"
                    data-id="${Number(order.id)}"
                >
                    <option value="pending_payment"
                        ${order.status === "pending_payment" ? "selected" : ""}>
                        Ожидает оплаты
                    </option>
                    <option value="paid"
                        ${order.status === "paid" ? "selected" : ""}>
                        Оплачен
                    </option>
                    <option value="cancelled"
                        ${order.status === "cancelled" ? "selected" : ""}>
                        Отменён
                    </option>
                </select>
            </div>
        </div>
    `;
}


function statusClassFor(status) {
    if (status === "paid") {
        return "paid";
    }

    if (status === "cancelled") {
        return "cancelled";
    }

    return "pending";
}


function renderAdminOrderStats(orders) {
    const statsElement = $("#admin-orders-stats");

    if (!statsElement) {
        return;
    }

    const total = orders.length;
    const pending = orders.filter(
        (order) =>
            order.status === "pending_payment" ||
            order.status === "created"
    ).length;
    const paid = orders.filter(
        (order) => order.status === "paid"
    ).length;
    const cancelled = orders.filter(
        (order) => order.status === "cancelled"
    ).length;
    const revenue = orders
        .filter((order) => order.status === "paid")
        .reduce(
            (sum, order) =>
                sum + Number(order.total_amount || 0),
            0
        );

    statsElement.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${total}</div>
            <div class="stat-label">Всего заказов</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${pending}</div>
            <div class="stat-label">Ожидают оплаты</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${paid}</div>
            <div class="stat-label">Оплачено</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${cancelled}</div>
            <div class="stat-label">Отменено</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${formatMoney(revenue)}</div>
            <div class="stat-label">Выручка</div>
        </div>
    `;
}


async function loadAdminOrders() {
    const container = $("#admin-orders");
    const statsElement = $("#admin-orders-stats");

    if (!container || !statsElement) {
        return;
    }

    if (!state.user?.is_admin) {
        container.innerHTML = "";
        statsElement.innerHTML = "";
        return;
    }

    const data = await apiFetch(
        "/orders/admin/all",
        {},
        false
    );

    const orders = Array.isArray(data)
        ? data
        : data?.items || [];

    renderAdminOrderStats(orders);

    container.innerHTML = orders.length
        ? orders.map(adminOrderCard).join("")
        : `
            <p style="
                text-align: center;
                color: var(--text-secondary);
                padding: 20px;
            ">
                Заказов нет
            </p>
        `;
}


async function adminChangeOrderStatus(orderId, status) {
    await apiFetch(
        `/orders/admin/${Number(orderId)}/status`,
        {
            method: "PATCH",
            body: JSON.stringify({ status }),
        }
    );

    showToast("Статус заказа обновлён");

    await loadAdminOrders();
}


async function createCategory(payload) {
    await apiFetch("/categories", {
        method: "POST",
        body: JSON.stringify(payload),
    });

    showToast("Категория создана");

    await loadAdminCategories();
}


async function editCategory(categoryId) {
    const id = Number(categoryId);

    const category = await apiFetch(
        `/categories/${id}`,
        {},
        false
    );

    if (!category || typeof category !== "object") {
        showToast("Не удалось загрузить категорию.", "error");
        return;
    }

    const name = $("#category-name");
    const slug = $("#category-slug");
    const icon = $("#category-icon");
    const description = $("#category-description");
    const currentImage = $("#category-current-image");
    const title = $("#category-form-title");
    const submitBtn = $("#category-submit-btn");
    const banner = $("#category-edit-banner");
    const fileInput = $("#category-image-file");
    const existingImageUrl = category.image_url || null;

    if (name) name.value = category.name || "";
    if (slug) slug.value = category.slug || "";
    if (icon) icon.value = category.icon || "";
    if (description) description.value = category.description || "";
    if (fileInput) fileInput.value = "";

    if (currentImage) {
        if (existingImageUrl) {
            currentImage.innerHTML = `
                <div class="muted" style="margin-bottom: 6px;">Текущее фото:</div>
                <img
                    src="${escapeAttribute(existingImageUrl)}"
                    alt=""
                    style="width: 96px; height: 96px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border);"
                    onerror="this.style.display='none'"
                />
            `;
            currentImage.classList.remove("hidden");
            currentImage.style.display = "block";
        } else {
            currentImage.innerHTML = "";
            currentImage.classList.add("hidden");
            currentImage.style.display = "none";
        }
    }

    if (title) title.textContent = "Изменить категорию";
    if (submitBtn) submitBtn.textContent = "Сохранить изменения";

    if (banner) {
        banner.classList.remove("hidden");
        banner.style.display = "flex";
    }

    state.editingCategoryId = id;

    const formCard = document.querySelector(".admin-form-card");
    if (formCard) {
        formCard.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
}


function resetCategoryForm() {
    state.editingCategoryId = null;

    const form = $("#create-category-form");
    if (form) form.reset();

    const currentImage = $("#category-current-image");
    if (currentImage) {
        currentImage.innerHTML = "";
        currentImage.classList.add("hidden");
        currentImage.style.display = "none";
    }

    const title = $("#category-form-title");
    if (title) title.textContent = "Добавить категорию";

    const submitBtn = $("#category-submit-btn");
    if (submitBtn) submitBtn.textContent = "Создать категорию";

    const banner = $("#category-edit-banner");
    if (banner) {
        banner.classList.add("hidden");
        banner.style.display = "none";
    }

    const slugInput = $("#category-slug");
    if (slugInput) delete slugInput.dataset.edited;
}


function cancelCategoryEdit() {
    resetCategoryForm();
}


async function loadCategoriesData() {
    try {
        const data = await apiFetch(
            "/categories",
            {},
            false
        );

        allCategories = Array.isArray(data)
            ? data
            : data?.items || [];

        renderCategories();
        renderCategorySelects();
    } catch (error) {
        console.error(
            "Failed to reload categories:",
            error
        );
    }
}


async function deleteCategory(categoryId) {
    if (
        !confirm(
            "Удалить категорию? (нельзя удалить, если в ней есть товары)"
        )
    ) {
        return;
    }

    try {
        await apiFetch(
            `/categories/${Number(categoryId)}`,
            {
                method: "DELETE",
            }
        );

        showToast("Категория удалена");

        await loadAdminCategories();
        await loadCategories();
    } catch (error) {
        showToast(error.message, "error");
    }
}


async function createProduct(payload) {
    await apiFetch("/products", {
        method: "POST",
        body: JSON.stringify(payload),
    });

    showToast("Товар создан");

    await loadAdminProducts();
}


async function editProduct(productId) {
    const id = Number(productId);

    const product = await apiFetch(
        `/products/${id}`
    );

    if (!product || typeof product !== "object") {
        showToast("Не удалось загрузить товар.", "error");
        return;
    }

    const name = $("#product-name");
    const sku = $("#product-sku");
    const price = $("#product-price");
    const category = $("#product-category-create");
    const size = $("#product-size");
    const description = $("#product-description");
    const active = $("#product-is-active");
    const fileInput = $("#product-image-file");
    const currentImage = $("#product-current-image");
    const title = $("#product-form-title");
    const submitBtn = $("#product-submit-btn");
    const banner = $("#product-edit-banner");

    if (name) name.value = product.name || "";
    if (sku) sku.value = product.sku || "";
    if (price) price.value = product.price ?? "";
    if (size) size.value = product.size || "";
    if (description) description.value = product.description || "";
    if (active) active.checked = product.is_active !== false;
    if (fileInput) fileInput.value = "";

    if (category) {
        const categoryId = String(product.category_id ?? "");
        category.value = categoryId;
    }

    if (currentImage) {
        const existingImageUrl = product.image_url || null;

        if (existingImageUrl) {
            currentImage.innerHTML = `
                <div class="muted" style="margin-bottom: 6px;">Текущее фото:</div>
                <img
                    src="${escapeAttribute(existingImageUrl)}"
                    alt=""
                    style="width: 96px; height: 96px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border);"
                    onerror="this.style.display='none'"
                />
            `;
            currentImage.classList.remove("hidden");
            currentImage.style.display = "block";
        } else {
            currentImage.innerHTML = "";
            currentImage.classList.add("hidden");
            currentImage.style.display = "none";
        }
    }

    if (title) title.textContent = "Изменить товар";
    if (submitBtn) submitBtn.textContent = "Сохранить изменения";

    if (banner) {
        banner.classList.remove("hidden");
        banner.style.display = "flex";
    }

    state.editingProductId = id;

    const formCard = document.querySelector(
        ".admin-form-card"
    );

    if (formCard) {
        formCard.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
}


function resetProductForm() {
    state.editingProductId = null;

    const form = $("#create-product-form");
    if (form) form.reset();

    const active = $("#product-is-active");
    if (active) active.checked = true;

    const currentImage = $("#product-current-image");
    if (currentImage) {
        currentImage.innerHTML = "";
        currentImage.classList.add("hidden");
        currentImage.style.display = "none";
    }

    const title = $("#product-form-title");
    if (title) title.textContent = "Добавить новый товар";

    const submitBtn = $("#product-submit-btn");
    if (submitBtn) submitBtn.textContent = "Создать товар";

    const banner = $("#product-edit-banner");
    if (banner) {
        banner.classList.add("hidden");
        banner.style.display = "none";
    }
}


function cancelProductEdit() {
    resetProductForm();
}


async function toggleProduct(productId, isActive) {
    await apiFetch(
        `/products/${Number(productId)}`,
        {
            method: "PATCH",
            body: JSON.stringify({
                is_active: !isActive,
            }),
        }
    );

    showToast("Статус товара изменён");

    await loadAdminProducts();
}


async function deleteProduct(productId) {
    if (
        !confirm(
            "Удалить товар навсегда? (товар, который есть в заказах, удалить нельзя)"
        )
    ) {
        return;
    }

    try {
        await apiFetch(
            `/products/${Number(productId)}`,
            {
                method: "DELETE",
            }
        );

        showToast("Товар удалён");

        await loadAdminProducts();
    } catch (error) {
        showToast(error.message, "error");
    }
}


/* ============================================================
   LOGOUT
   ============================================================ */

async function logout() {
    try {
        if (state.refreshToken) {
            await fetch(`${API}/auth/logout`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify({
                    refresh_token: state.refreshToken,
                }),
            });
        }
    } catch (error) {
        console.warn("Logout request failed:", error);
    }

    clearSession();

    showAuth();

    showToast("Вы вышли из аккаунта");
}


/* ============================================================
   PAYMENT
   ============================================================ */

function openPaymentModal(orderId) {
    currentOrderId = Number(orderId);
    selectedPaymentMethod = null;

    const modal = $("#payment-modal");
    const content = $("#payment-content");

    if (!modal || !content) {
        return;
    }

    modal.classList.remove("hidden");

    content.innerHTML = `
        <div class="payment-methods">

            <div
                class="payment-method"
                data-method="card"
                tabindex="0"
            >
                <div class="payment-method-icon">
                    💳
                </div>

                <div class="payment-method-info">
                    <div class="payment-method-name">
                        Банковская карта
                    </div>

                    <div class="payment-method-desc">
                        Visa, Mastercard, МИР
                    </div>
                </div>
            </div>

            <div
                class="payment-method"
                data-method="sbp"
                tabindex="0"
            >
                <div class="payment-method-icon">
                    📱
                </div>

                <div class="payment-method-info">
                    <div class="payment-method-name">
                        СБП
                    </div>

                    <div class="payment-method-desc">
                        Оплата по QR-коду
                    </div>
                </div>
            </div>

            <div
                class="payment-method"
                data-method="cash"
                tabindex="0"
            >
                <div class="payment-method-icon">
                    💵
                </div>

                <div class="payment-method-info">
                    <div class="payment-method-name">
                        Наличными
                    </div>

                    <div class="payment-method-desc">
                        Оплата при получении
                    </div>
                </div>
            </div>

        </div>

        <div style="
            display: flex;
            gap: 12px;
        ">

            <button
                id="cancel-payment"
                class="btn btn-secondary"
                style="flex: 1;"
            >
                Отмена
            </button>

            <button
                id="confirm-payment"
                class="btn btn-primary"
                style="flex: 1;"
                disabled
            >
                Оплатить
            </button>

        </div>
    `;

    content
        .querySelectorAll(".payment-method")
        .forEach((element) => {
            element.addEventListener("click", () => {
                content
                    .querySelectorAll(".payment-method")
                    .forEach((item) =>
                        item.classList.remove("selected")
                    );

                element.classList.add("selected");

                selectedPaymentMethod =
                    element.dataset.method;

                const confirmButton =
                    content.querySelector(
                        "#confirm-payment"
                    );

                if (confirmButton) {
                    confirmButton.disabled = false;
                }
            });
        });

    const cancelButton =
        content.querySelector("#cancel-payment");

    if (cancelButton) {
        cancelButton.addEventListener(
            "click",
            closePaymentModal
        );
    }

    const confirmButton =
        content.querySelector("#confirm-payment");

    if (confirmButton) {
        confirmButton.addEventListener(
            "click",
            processPayment
        );
    }
}


function closePaymentModal() {
    const modal = $("#payment-modal");

    if (modal) {
        modal.classList.add("hidden");
    }

    currentOrderId = null;
    selectedPaymentMethod = null;
}


async function processPayment() {
    if (
        !currentOrderId ||
        !selectedPaymentMethod
    ) {
        return;
    }

    const content = $("#payment-content");

    if (content) {
        content.innerHTML = `
            <div class="payment-processing">
                <div class="spinner"></div>
                <p>Обработка платежа...</p>
            </div>
        `;
    }

    try {
        await apiFetch(
            `/orders/${currentOrderId}/pay`,
            {
                method: "POST",
                body: JSON.stringify({
                    payment_method:
                        selectedPaymentMethod,
                }),
            }
        );

        showToast("Оплата успешно выполнена!");

        closePaymentModal();

        await loadOrders();

        if (state.user?.is_admin) {
            loadAdminOrders().catch((error) => {
                console.warn("Failed to refresh admin orders:", error);
            });
        }
    } catch (error) {
        showToast(error.message, "error");
        closePaymentModal();
    }
}


async function cancelOrder(orderId) {
    try {
        await apiFetch(
            `/orders/${Number(orderId)}/cancel`,
            {
                method: "POST",
            }
        );

        showToast("Заказ отменён");

        await loadOrders();
    } catch (error) {
        showToast(error.message, "error");
    }
}


/* ============================================================
   AUTH MODAL
   ============================================================ */

function showAuthModal() {
    const modal = $("#authModal");

    if (modal) {
        modal.classList.remove("hidden");
    }

    const loginIdentifier = $("#login-identifier");
    const loginPassword = $("#login-password");
    if (loginIdentifier) loginIdentifier.value = "";
    if (loginPassword) loginPassword.value = "";
}


function closeAuthModal() {
    const modal = $("#authModal");

    if (modal) {
        modal.classList.add("hidden");
    }
}


function showLoginFromModal() {
    closeAuthModal();
    showAuth();
}


function showRegisterFromModal() {
    closeAuthModal();
    showAuth();

    const registerTab =
        document.querySelector(
            '.auth-tab[data-tab="register"]'
        );

    if (registerTab) {
        registerTab.click();
    }
}


/* ============================================================
   PASSWORD TOGGLES
   ============================================================ */

function initPasswordToggles() {
    document
        .querySelectorAll(".password-toggle")
        .forEach((button) => {
            button.classList.remove("visible");

            button.addEventListener("click", (event) => {
                event.preventDefault();

                const targetId =
                    button.dataset.target;

                const input =
                    document.getElementById(targetId);

                if (!input) {
                    return;
                }

                const showPassword =
                    input.type === "password";

                input.type = showPassword
                    ? "text"
                    : "password";

                button.classList.toggle(
                    "visible",
                    showPassword
                );
            });
        });
}


/* ============================================================
   PASSWORD RESET
   ============================================================ */

function showResetModal() {
    const modal = $("#resetModal");

    if (!modal) {
        return;
    }

    modal.classList.remove("hidden");

    const step1 = $("#reset-step-1");
    const step2 = $("#reset-step-2");
    const emailInput = $("#reset-email");

    if (step1) {
        step1.classList.remove("hidden");
    }

    if (step2) {
        step2.classList.add("hidden");
    }

    if (emailInput) {
        emailInput.value = "";
    }
}


function closeResetModal() {
    const modal = $("#resetModal");

    if (modal) {
        modal.classList.add("hidden");
    }
}


async function requestResetToken() {
    const emailInput = $("#reset-email");

    if (!emailInput) {
        return;
    }

    const email = emailInput.value.trim();

    if (!email) {
        showToast("Введите email.", "error");
        return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showToast(
            "Введите корректный email.",
            "error"
        );
        return;
    }

    try {
        const response = await apiFetch(
            "/auth/forgot-password",
            {
                method: "POST",
                body: JSON.stringify({
                    email,
                }),
            },
            false
        );

        /*
         * В production backend должен отправить
         * письмо пользователю.
         *
         * reset_token здесь используется только
         * если backend явно возвращает его.
         */
        if (response?.reset_token) {
            const tokenInput = $("#reset-token");

            if (tokenInput) {
                tokenInput.value =
                    response.reset_token;
            }
        }

        const step1 = $("#reset-step-1");
        const step2 = $("#reset-step-2");

        if (step1) {
            step1.classList.add("hidden");
        }

        if (step2) {
            step2.classList.remove("hidden");
        }

        showToast(
            response?.message ||
                "Если такой email зарегистрирован, ссылка для восстановления отправлена."
        );
    } catch (error) {
        showToast(error.message, "error");
    }
}


async function confirmResetPassword() {
    const tokenInput = $("#reset-token");
    const passwordInput =
        $("#reset-new-password");

    if (!tokenInput || !passwordInput) {
        return;
    }

    const token = tokenInput.value.trim();
    const newPassword = passwordInput.value;

    if (!token) {
        showToast(
            "Введите токен восстановления.",
            "error"
        );
        return;
    }

    const passwordError =
        validatePasswordClient(newPassword);

    if (passwordError) {
        showToast(passwordError, "error");
        return;
    }

    try {
        const response = await apiFetch(
            "/auth/reset-password",
            {
                method: "POST",
                body: JSON.stringify({
                    token,
                    new_password: newPassword,
                }),
            },
            false
        );

        showToast(
            response?.message ||
                "Пароль успешно изменён!"
        );

        closeResetModal();

        const loginIdentifier =
            $("#login-identifier");

        if (loginIdentifier) {
            loginIdentifier.focus();
        }

        showAuth();
    } catch (error) {
        showToast(error.message, "error");
    }
}


function handleResetTokenFromUrl() {
    const url = new URL(
        window.location.href
    );

    const token = url.searchParams.get("token");

    if (!token) {
        return;
    }

    const modal = $("#resetModal");

    if (!modal) {
        return;
    }

    showResetModal();

    const step1 = $("#reset-step-1");
    const step2 = $("#reset-step-2");
    const tokenInput = $("#reset-token");

    if (tokenInput) {
        tokenInput.value = token;
    }

    if (step1) {
        step1.classList.add("hidden");
    }

    if (step2) {
        step2.classList.remove("hidden");
    }

    /*
     * Убираем token из адресной строки,
     * чтобы он не оставался в истории браузера.
     */
    window.history.replaceState(
        {},
        document.title,
        url.pathname
    );
}


/* ============================================================
   FORMS
   ============================================================ */

function bindForms() {
    document
        .querySelectorAll(".auth-tab")
        .forEach((tab) => {
            tab.addEventListener("click", () => {
                document
                    .querySelectorAll(".auth-tab")
                    .forEach((item) =>
                        item.classList.remove(
                            "active"
                        )
                    );

                tab.classList.add("active");

                const isLogin =
                    tab.dataset.tab === "login";

                const loginForm =
                    $("#login-form");

                const registerForm =
                    $("#register-form");

                if (loginForm) {
                    loginForm.classList.toggle(
                        "hidden",
                        !isLogin
                    );
                }

                if (registerForm) {
                    registerForm.classList.toggle(
                        "hidden",
                        isLogin
                    );
                }
            });
        });

    const loginForm = $("#login-form");

    if (loginForm) {
        loginForm.addEventListener(
            "submit",
            async (event) => {
                event.preventDefault();

                const identifier =
                    $("#login-identifier")?.value ||
                    "";

                const password =
                    $("#login-password")?.value ||
                    "";

                if (!identifier.trim()) {
                    showToast(
                        "Введите email или телефон.",
                        "error"
                    );
                    return;
                }

                if (!password) {
                    showToast(
                        "Введите пароль.",
                        "error"
                    );
                    return;
                }

                try {
                    await login(
                        identifier,
                        password
                    );

                    showToast(
                        "Добро пожаловать!"
                    );
                } catch (error) {
                    showToast(
                        error.message,
                        "error"
                    );
                }
            }
        );
    }


    const registerForm =
        $("#register-form");

    if (registerForm) {
        registerForm.addEventListener(
            "submit",
            async (event) => {
                event.preventDefault();

                const fullName =
                    $("#register-full-name")
                        ?.value
                        .trim() || "";

                const email =
                    $("#register-email")
                        ?.value
                        .trim() || "";

                const phone =
                    $("#register-phone")
                        ?.value
                        .trim() || "";

                const password =
                    $("#register-password")
                        ?.value || "";

                const passwordConfirm =
                    $(
                        "#register-password-confirm"
                    )?.value || "";

                if (fullName.length < 3) {
                    showToast(
                        "ФИО должно содержать минимум 3 символа.",
                        "error"
                    );
                    return;
                }

                if (
                    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
                        email
                    )
                ) {
                    showToast(
                        "Введите корректный email.",
                        "error"
                    );
                    return;
                }

                if (!/^\+7\d{10}$/.test(phone)) {
                    showToast(
                        "Телефон должен быть в формате +79991234567.",
                        "error"
                    );
                    return;
                }

                const consent = document.getElementById("register-consent");
                if (!consent || !consent.checked) {
                    showToast(
                        "Необходимо согласиться с условиями магазина и обработкой персональных данных.",
                        "error"
                    );
                    return;
                }

                const passwordError =
                    validatePasswordClient(
                        password
                    );

                if (passwordError) {
                    showToast(
                        passwordError,
                        "error"
                    );
                    return;
                }

                if (
                    password !==
                    passwordConfirm
                ) {
                    showToast(
                        "Пароли не совпадают.",
                        "error"
                    );
                    return;
                }

                try {
                    await registerAndLogin({
                        full_name: fullName,
                        email,
                        phone,
                        password,
                        password_confirm:
                            passwordConfirm,
                    });

                    showToast(
                        "Аккаунт успешно создан!"
                    );
                } catch (error) {
                    showToast(
                        error.message,
                        "error"
                    );
                }
            }
        );
    }


    const createProductForm =
        $("#create-product-form");

    const productCancelBtn =
        $("#product-cancel-btn");

    if (productCancelBtn) {
        productCancelBtn.addEventListener(
            "click",
            () => {
                cancelProductEdit();
            }
        );
    }

    if (createProductForm) {
        createProductForm.addEventListener(
            "submit",
            async (event) => {
                event.preventDefault();

                try {
                    const categoryValue =
                        $(
                            "#product-category-create"
                        )?.value;

                    if (!categoryValue) {
                        showToast(
                            "Выберите категорию.",
                            "error"
                        );
                        return;
                    }

                    const name = $(
                        "#product-name"
                    )?.value.trim() || "";

                    const sku = $(
                        "#product-sku"
                    )?.value.trim() || "";

                    if (!name) {
                        showToast(
                            "Введите название.",
                            "error"
                        );
                        return;
                    }

                    if (!sku) {
                        showToast(
                            "Введите артикул.",
                            "error"
                        );
                        return;
                    }

                    const price = Number(
                        $("#product-price")
                            ?.value
                    );

                    if (
                        !Number.isFinite(price) ||
                        price <= 0
                    ) {
                        showToast(
                            "Введите корректную цену.",
                            "error"
                        );
                        return;
                    }

                    const size =
                        $(
                            "#product-size"
                        )?.value.trim() ||
                        null;

                    const description =
                        $(
                            "#product-description"
                        )?.value.trim() ||
                        null;

                    const isActive =
                        $(
                            "#product-is-active"
                        )?.checked ?? true;

                    const imageFile =
                        $("#product-image-file")
                            ?.files?.[0];

                    const editingId =
                        state.editingProductId;

                    if (editingId !== null) {
                        // Редактирование: фото опционально.
                        const payload = {
                            name,
                            sku,
                            price,
                            category_id: Number(
                                categoryValue
                            ),
                            size,
                            description,
                            is_active: isActive,
                        };

                        if (imageFile) {
                            showToast(
                                "Загрузка фото..."
                            );
                            payload.image_url =
                                await uploadImage(
                                    imageFile,
                                    "products"
                                );
                        }

                        await apiFetch(
                            `/products/${editingId}`,
                            {
                                method: "PATCH",
                                body: JSON.stringify(
                                    payload
                                ),
                            }
                        );

                        showToast(
                            "Товар обновлён"
                        );

                        resetProductForm();

                        await loadAdminProducts();
                    } else {
                        const imageUrl = await uploadImage(
                            imageFile,
                            "products"
                        );

                        await createProduct({
                            name,
                            sku,
                            price,
                            category_id:
                                Number(
                                    categoryValue
                                ),
                            size,
                            description,
                            image_url: imageUrl,
                            is_active: isActive,
                        });

                        createProductForm.reset();

                        const activeCheckbox =
                            $(
                                "#product-is-active"
                            );

                        if (activeCheckbox) {
                            activeCheckbox.checked =
                                true;
                        }

                        await loadAdminProducts();
                    }
                } catch (error) {
                    showToast(
                        error.message,
                        "error"
                    );
                }
            }
        );
    }


    const createCategoryForm =
        $("#create-category-form");

    const categoryCancelBtn =
        $("#category-cancel-btn");

    if (categoryCancelBtn) {
        categoryCancelBtn.addEventListener(
            "click",
            () => {
                cancelCategoryEdit();
            }
        );
    }

    if (createCategoryForm) {
        createCategoryForm.addEventListener(
            "submit",
            async (event) => {
                event.preventDefault();

                try {
                    const nameForm =
                        $("#category-name")
                            ?.value.trim() || "";

                    const slugForm =
                        $("#category-slug")
                            ?.value.trim() || "";

                    if (!nameForm) {
                        showToast(
                            "Введите название.",
                            "error"
                        );
                        return;
                    }

                    // Если slug не задан вручную — генерируем из названия.
                    // В любом случае приводим к корректному формату.
                    const effectiveSlug = slugForm
                        ? slugify(slugForm)
                        : slugify(nameForm);

                    if (!effectiveSlug) {
                        showToast(
                            "Не удалось сформировать slug.",
                            "error"
                        );
                        return;
                    }

                    const iconForm =
                        $("#category-icon")
                            ?.value.trim() || null;

                    const descriptionForm =
                        $("#category-description")
                            ?.value.trim() || null;

                    const imageFile =
                        $("#category-image-file")
                            ?.files?.[0];

                    const editingId =
                        state.editingCategoryId;

                    if (editingId !== null) {
                        // Режим редактирования: фото не обязательное.
                        // Если файл не выбран — прежнее фото сохраняется.
                        let newImageUrl;
                        let currentImageUrl = null;

                        try {
                            const current =
                                await apiFetch(
                                    `/categories/${editingId}`,
                                    {},
                                    false
                                );
                            currentImageUrl =
                                current?.image_url || null;
                        } catch (_ignored) {
                            currentImageUrl = null;
                        }

                        if (imageFile) {
                            showToast(
                                "Загрузка фото..."
                            );
                            newImageUrl =
                                await uploadImage(
                                    imageFile,
                                    "categories"
                                );
                        } else {
                            newImageUrl =
                                currentImageUrl;
                        }

                        await apiFetch(
                            `/categories/${editingId}`,
                            {
                                method: "PATCH",
                                body: JSON.stringify({
                                    name: nameForm,
                                    slug: effectiveSlug,
                                    icon: iconForm,
                                    description: descriptionForm || null,
                                    image_url: newImageUrl,
                                }),
                            }
                        );

                        showToast(
                            "Категория обновлена"
                        );

                        resetCategoryForm();

                        await loadAdminCategories();
                        await loadCategoriesData();
                    } else {
                        const imageUrl = await uploadImage(
                            imageFile,
                            "categories"
                        );

                        await createCategory({
                            name: nameForm,
                            slug: effectiveSlug,
                            icon: iconForm,
                            description: descriptionForm,
                            image_url: imageUrl,
                        });

                        createCategoryForm.reset();

                        const slugInput =
                            $("#category-slug");

                        if (slugInput) {
                            delete slugInput.dataset.edited;
                            slugInput.value = slugify(
                                $("#category-name")?.value || ""
                            );
                        }

                        await loadCategories();
                    }
                } catch (error) {
                    showToast(
                        error.message,
                        "error"
                    );
                }
            }
        );
    }
}


/* ============================================================
   GLOBAL ACTIONS
   ============================================================ */

function bindGlobalActions() {
    document.addEventListener(
        "click",
        async (event) => {
            const target =
                event.target.closest(
                    "[data-action]"
                );

            if (!target) {
                return;
            }

            const action =
                target.dataset.action;

            try {
                if (
                    action === "nav-view"
                ) {
                    showView(
                        target.dataset.view
                    );
                    return;
                }

                if (action === "logout") {
                    await logout();
                    return;
                }

                if (action === "show-auth") {
                    showAuth();
                    return;
                }

                if (
                    action ===
                    "search-products"
                ) {
                    state.productsPage = 1;
                    await loadProducts();
                    return;
                }

                if (
                    action ===
                    "reset-filters"
                ) {
                    resetFilters();
                    return;
                }

                if (
                    action === "page-prev"
                ) {
                    if (
                        state.productsPage >
                        1
                    ) {
                        state.productsPage--;
                        await loadProducts();
                    }
                    return;
                }

                if (
                    action === "page-next"
                ) {
                    if (
                        state.productsPage <
                        state.productsPages
                    ) {
                        state.productsPage++;
                        await loadProducts();
                    }
                    return;
                }

                if (
                    action === "add-to-cart"
                ) {
                    await addToCart(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action ===
                    "remove-cart-item"
                ) {
                    await apiFetch(
                        `/cart/items/${Number(
                            target.dataset.id
                        )}`,
                        {
                            method: "DELETE",
                        }
                    );

                    await loadCart();
                    return;
                }

                if (
                    action === "clear-cart"
                ) {
                    await apiFetch(
                        "/cart",
                        {
                            method: "DELETE",
                        }
                    );

                    await loadCart();
                    return;
                }

                if (
                    action === "checkout"
                ) {
                    await checkout();
                    return;
                }

                if (
                    action ===
                    "close-checkout-modal"
                ) {
                    closeCheckoutModal();
                    return;
                }

                if (
                    action ===
                    "confirm-checkout"
                ) {
                    await confirmCheckout();
                    return;
                }

                if (
                    action ===
                    "show-wishlist"
                ) {
                    const wishlistFilter =
                        $("#filter-wishlist-only");

                    if (wishlistFilter) {
                        wishlistFilter.checked = true;
                    }

                    state.productsPage = 1;
                    showView("catalog");
                    return;
                }

                if (
                    action ===
                    "toggle-wishlist"
                ) {
                    const id = Number(
                        target.dataset.id
                    );
                    const added =
                        toggleWishlist(id);

                    showToast(
                        added
                            ? "Добавлено в избранное"
                            : "Удалено из избранного"
                    );

                    const productView =
                        $("#view-product");

                    if (
                        productView &&
                        !productView.classList.contains(
                            "hidden"
                        )
                    ) {
                        await showProduct(id);
                    } else {
                        await loadProducts();
                    }
                    return;
                }

                if (
                    action ===
                    "toggle-cart-selection"
                ) {
                    toggleCartSelection(
                        target.dataset.id
                    );
                    await loadCart();
                    return;
                }

                if (
                    action ===
                    "back-to-catalog"
                ) {
                    backToCatalog();
                    return;
                }

                if (
                    action ===
                    "order-product"
                ) {
                    await orderProduct(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action === "edit-product"
                ) {
                    await editProduct(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action ===
                    "toggle-product"
                ) {
                    const isActive =
                        target.dataset.active ===
                        "true";

                    await toggleProduct(
                        target.dataset.id,
                        isActive
                    );

                    return;
                }

                if (
                    action ===
                    "delete-product"
                ) {
                    await deleteProduct(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action ===
                    "edit-category"
                ) {
                    await editCategory(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action ===
                    "delete-category"
                ) {
                    await deleteCategory(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action === "pay-order"
                ) {
                    openPaymentModal(
                        target.dataset.id
                    );
                    return;
                }

                if (
                    action ===
                    "cancel-order"
                ) {
                    if (
                        confirm(
                            "Отменить заказ?"
                        )
                    ) {
                        await cancelOrder(
                            target.dataset.id
                        );
                    }

                    return;
                }

                if (
                    action ===
                    "close-auth-modal"
                ) {
                    closeAuthModal();
                    return;
                }

                if (
                    action ===
                    "close-payment-modal"
                ) {
                    closePaymentModal();
                    return;
                }

                if (
                    action ===
                    "show-reset-modal"
                ) {
                    showResetModal();
                    return;
                }

                if (
                    action ===
                    "close-reset-modal"
                ) {
                    closeResetModal();
                    return;
                }

                if (
                    action ===
                    "request-reset"
                ) {
                    await requestResetToken();
                    return;
                }

                if (
                    action ===
                    "confirm-reset"
                ) {
                    await confirmResetPassword();
                    return;
                }

                if (
                    action ===
                    "back-to-reset-step-1"
                ) {
                    const step1 =
                        $("#reset-step-1");

                    const step2 =
                        $("#reset-step-2");

                    if (step1) {
                        step1.classList.remove(
                            "hidden"
                        );
                    }

                    if (step2) {
                        step2.classList.add(
                            "hidden"
                        );
                    }

                    return;
                }

                if (
                    action ===
                    "show-login-from-modal"
                ) {
                    showLoginFromModal();
                    return;
                }

                if (
                    action ===
                    "show-register-from-modal"
                ) {
                    showRegisterFromModal();
                    return;
                }
            } catch (error) {
                console.error(
                    `Action ${action} failed:`,
                    error
                );

                showToast(
                    error.message ||
                        "Произошла ошибка.",
                    "error"
                );
            }
        }
    );


    document.addEventListener(
        "click",
        (event) => {
            if (
                event.target.id ===
                "payment-modal"
            ) {
                closePaymentModal();
            }

            if (
                event.target.id ===
                "authModal"
            ) {
                closeAuthModal();
            }

            if (
                event.target.id ===
                "resetModal"
            ) {
                closeResetModal();
            }

            if (
                event.target.id ===
                "checkout-modal"
            ) {
                closeCheckoutModal();
            }
        }
    );


    /*
     * Клик по товару — открыть полное описание.
     */
    document.addEventListener(
        "click",
        (event) => {
            if (
                event.target.closest(
                    "[data-action]"
                )
            ) {
                return;
            }

            const card = event.target.closest(
                ".product-card"
            );

            if (!card) {
                return;
            }

            const id = Number(
                card.dataset.id
            );

            if (id) {
                showProduct(id).catch(
                    (error) =>
                        showToast(
                            error.message,
                            "error"
                        )
                );
            }
        }
    );


    /*
     * Категории.
     */
    document.addEventListener(
        "click",
        (event) => {
            const category =
                event.target.closest(
                    ".category-card"
                );

            if (!category) {
                return;
            }

            const categoryId =
                Number(
                    category.dataset.categoryId
                );

            if (categoryId) {
                filterByCategory(
                    categoryId
                );
            }
        }
    );


    document.addEventListener(
        "change",
        async (event) => {
            const select = event.target.closest(
                "[data-action='admin-change-status']"
            );

            if (!select) {
                return;
            }

            const orderId = Number(
                select.dataset.id
            );

            if (!orderId) {
                return;
            }

            const status = select.value;

            try {
                await adminChangeOrderStatus(
                    orderId,
                    status
                );
            } catch (error) {
                select.value =
                    select.querySelector(
                        "option[selected]"
                    )?.value || "";

                showToast(
                    error.message,
                    "error"
                );

                await loadAdminOrders();
            }
        }
    );
}


/* ============================================================
   FILTER EVENTS
   ============================================================ */

function resetFilters() {
    const fields = {
        "#filter-name": "",
        "#filter-min-price": "",
        "#filter-max-price": "",
        "#filter-sort-by": "name",
        "#filter-sort-order": "asc",
        "#product-category": "",
    };

    for (const [selector, defaultValue] of Object.entries(fields)) {
        const element = $(selector);

        if (element) {
            element.value = defaultValue;
        }
    }

    const inactive = $("#filter-include-inactive");

    if (inactive) {
        inactive.checked = false;
    }

    const wishlistOnly = $("#filter-wishlist-only");

    if (wishlistOnly) {
        wishlistOnly.checked = false;
    }

    state.productsPage = 1;

    loadProducts().catch((error) => {
        showToast(error.message, "error");
    });
}


function bindFilterEvents() {
    const sortBy =
        $("#filter-sort-by");

    const sortOrder =
        $("#filter-sort-order");

    const category =
        $("#product-category");

    const inactive =
        $("#filter-include-inactive");

    const wishlistOnly =
        $("#filter-wishlist-only");

    if (sortBy) {
        sortBy.addEventListener(
            "change",
            () => {
                state.productsPage = 1;
                loadProducts().catch(
                    (error) =>
                        showToast(
                            error.message,
                            "error"
                        )
                );
            }
        );
    }

    if (sortOrder) {
        sortOrder.addEventListener(
            "change",
            () => {
                state.productsPage = 1;
                loadProducts().catch(
                    (error) =>
                        showToast(
                            error.message,
                            "error"
                        )
                );
            }
        );
    }

    if (category) {
        category.addEventListener(
            "change",
            () => {
                state.productsPage = 1;
                loadProducts().catch(
                    (error) =>
                        showToast(
                            error.message,
                            "error"
                        )
                );
            }
        );
    }

    if (inactive) {
        inactive.addEventListener(
            "change",
            () => {
                state.productsPage = 1;
                loadProducts().catch(
                    (error) =>
                        showToast(
                            error.message,
                            "error"
                        )
                );
            }
        );
    }

    if (wishlistOnly) {
        wishlistOnly.addEventListener(
            "change",
            () => {
                state.productsPage = 1;
                loadProducts().catch(
                    (error) =>
                        showToast(
                            error.message,
                            "error"
                        )
                );
            }
        );
    }
}


/* ============================================================
   INITIALIZATION
   ============================================================ */

async function init() {
    try {
        bindForms();
        bindGlobalActions();
        bindFilterEvents();
        initPasswordToggles();
        bindCategorySlugAutofill();
        updateWishlistBadge();

        await loadCategories();

        if (state.accessToken) {
            try {
                await loadMe();
                showView("catalog");
            } catch (error) {
                console.warn(
                    "Stored session is invalid:",
                    error
                );

                clearSession();
                showCatalogForGuest();
            }
        } else {
            showCatalogForGuest();
        }

        handleResetTokenFromUrl();
    } catch (error) {
        console.error(
            "Application initialization failed:",
            error
        );

        showToast(
            "Не удалось загрузить приложение. Обновите страницу.",
            "error"
        );
    }
}


/* ============================================================
   START
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    init
);
