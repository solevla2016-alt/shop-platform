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
};

let currentOrderId = null;
let selectedPaymentMethod = null;
let allCategories = [];


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
}


/* ============================================================
   NAVIGATION / VIEWS
   ============================================================ */

function showView(name) {
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
        userName.textContent = state.user.full_name || state.user.email;
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
    const description = escapeHtml(product.description || "");
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

    const descriptionHtml = description
        ? `<p class="product-description">${description}</p>`
        : "";

    const sizeHtml = size
        ? `<div class="product-size">📏 ${size}</div>`
        : "";

    const isActive = Boolean(product.is_active);

    return `
        <article class="product-card">
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

            ${descriptionHtml}

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

    const items = Array.isArray(data)
        ? data
        : data?.items || [];

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
                Товары не найдены
            </p>
        `;

    const pageInfo = $("#page-info");

    if (pageInfo) {
        pageInfo.textContent =
            `Страница ${state.productsPage} из ${state.productsPages}`;
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


function cartItemRow(item) {
    const productId = Number(item.product_id);
    const name = escapeHtml(item.name);

    return `
        <div class="row">

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

    const total = $("#cart-total");

    if (total) {
        total.textContent = formatMoney(cart?.total || 0);
    }

    await updateCartBadge();
}


/* ============================================================
   ORDERS
   ============================================================ */

async function checkout() {
    try {
        await apiFetch(
            "/orders/checkout",
            {
                method: "POST",
            }
        );

        showToast("Заказ успешно создан!");

        showView("orders");
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


async function createProduct(payload) {
    await apiFetch("/products", {
        method: "POST",
        body: JSON.stringify(payload),
    });

    showToast("Товар создан");

    await loadAdminProducts();
}


async function editProduct(productId) {
    const product = await apiFetch(
        `/products/${Number(productId)}`
    );

    const currentName = product.name || "";
    const currentPrice = product.price || 0;

    const name = prompt(
        "Новое название:",
        currentName
    );

    if (name === null) {
        return;
    }

    const cleanName = name.trim();

    if (!cleanName) {
        showToast(
            "Название не может быть пустым.",
            "error"
        );
        return;
    }

    const price = prompt(
        "Новая цена:",
        currentPrice
    );

    if (price === null) {
        return;
    }

    const numericPrice = Number(price);

    if (
        !Number.isFinite(numericPrice) ||
        numericPrice <= 0
    ) {
        showToast(
            "Цена должна быть положительным числом.",
            "error"
        );
        return;
    }

    await apiFetch(
        `/products/${Number(productId)}`,
        {
            method: "PATCH",
            body: JSON.stringify({
                name: cleanName,
                price: numericPrice,
            }),
        }
    );

    showToast("Товар обновлён");

    await loadAdminProducts();
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
    if (!confirm("Деактивировать товар?")) {
        return;
    }

    await apiFetch(
        `/products/${Number(productId)}`,
        {
            method: "DELETE",
        }
    );

    showToast("Товар деактивирован");

    await loadAdminProducts();
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
            button.addEventListener("click", (event) => {
                event.preventDefault();

                const targetId =
                    button.dataset.target;

                const input =
                    document.getElementById(targetId);

                if (!input) {
                    return;
                }

                if (input.type === "password") {
                    input.type = "text";
                    button.textContent = "🙈";
                } else {
                    input.type = "password";
                    button.textContent = "👁️";
                }
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

                    await createProduct({
                        name:
                            $(
                                "#product-name"
                            )?.value.trim() || "",

                        sku:
                            $(
                                "#product-sku"
                            )?.value.trim() || "",

                        price,

                        category_id:
                            Number(
                                categoryValue
                            ),

                        size:
                            $(
                                "#product-size"
                            )?.value.trim() ||
                            null,

                        description:
                            $(
                                "#product-description"
                            )?.value.trim() ||
                            null,

                        image_url:
                            $(
                                "#product-image-url"
                            )?.value.trim() ||
                            null,

                        is_active:
                            $(
                                "#product-is-active"
                            )?.checked ?? true,
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
}


/* ============================================================
   FILTER EVENTS
   ============================================================ */

function bindFilterEvents() {
    const sortBy =
        $("#filter-sort-by");

    const sortOrder =
        $("#filter-sort-order");

    const category =
        $("#product-category");

    const inactive =
        $("#filter-include-inactive");

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
