const API = "/api/v1";

const state = {
  accessToken: localStorage.getItem("access_token") || null,
  refreshToken: localStorage.getItem("refresh_token") || null,
  user: null,
  productsPage: 1,
  productsPages: 0,
};

let currentOrderId = null;
let selectedPaymentMethod = null;

const $ = (selector) => document.querySelector(selector);

function saveTokens(tokens) {
  state.accessToken = tokens.access_token;
  state.refreshToken = tokens.refresh_token;
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

function clearSession() {
  state.accessToken = null;
  state.refreshToken = null;
  state.user = null;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

function showToast(message, type = "success") {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");

  setTimeout(() => {
    toast.classList.add("hidden");
  }, 3500);
}

async function getErrorMessage(response) {
  const data = await response.json().catch(() => null);
  if (!data) return `Ошибка HTTP ${response.status}`;
  if (data.message) return data.message;
  if (data.detail) {
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  }
  return "Произошла ошибка при выполнении запроса";
}

async function refreshTokens() {
  if (!state.refreshToken) return false;
  try {
    const response = await fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    saveTokens(data);
    return true;
  } catch {
    return false;
  }
}

async function apiFetch(path, options = {}, useAuth = true) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (useAuth && state.accessToken) headers["Authorization"] = `Bearer ${state.accessToken}`;

  let response = await fetch(`${API}${path}`, { ...options, headers });

  if (response.status === 401 && useAuth && !options._retry) {
    options._retry = true;
    const refreshed = await refreshTokens();
    if (refreshed) return apiFetch(path, options, useAuth);
    clearSession();
    showAuth();
    throw new Error("Сессия истекла. Пожалуйста, войдите снова.");
  }

  if (!response.ok) {
    const message = await getErrorMessage(response);
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

function formatMoney(value) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

function showView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.add("hidden"));
  $(`#view-${name}`).classList.remove("hidden");

  document.querySelectorAll(".nav-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });

  if (name === "catalog") loadProducts();
  if (name === "cart") loadCart();
  if (name === "orders") loadOrders();
  if (name === "admin") loadAdminProducts();
}

function showAuth() {
  $("#nav").classList.add("hidden");
  $("#user-box").classList.add("hidden");
  document.querySelectorAll(".view").forEach((view) => view.classList.add("hidden"));
  $("#view-auth").classList.remove("hidden");
}

function renderNav() {
  if (!state.user) return;
  $("#nav").classList.remove("hidden");
  $("#user-box").classList.remove("hidden");
  $("#user-name").textContent = state.user.full_name;
  $("#admin-nav").classList.toggle("hidden", !state.user.is_admin);
  $("#inactive-filter").classList.toggle("hidden", !state.user.is_admin);
}

async function loadMe() {
  state.user = await apiFetch("/auth/me");
  renderNav();
}

async function login(identifier, password) {
  console.log("Попытка входа по адресу:", `${API}/auth/login`);
  const tokens = await apiFetch(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
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
  await login(payload.email, payload.password);
}

function productCard(product) {
  const imageHtml = product.image_url
    ? `<img src="${product.image_url}" alt="${product.name}" class="product-image" onerror="this.outerHTML='<div class=\\'product-image-placeholder\\'>📦</div>'" />`
    : `<div class="product-image-placeholder">📦</div>`;

  const descriptionHtml = product.description
    ? `<p class="product-description">${product.description}</p>`
    : "";

  return `
    <article class="product-card">
      ${imageHtml}
      <div class="product-card-header">
        <div class="product-name">${product.name}</div>
        <span class="badge ${product.is_active ? "" : "inactive"}">
          ${product.is_active ? "✓" : "✗"}
        </span>
      </div>
      ${descriptionHtml}
      <div class="product-price">${formatMoney(product.price)}</div>
      <button class="btn btn-primary" data-action="add-to-cart" data-id="${product.id}" ${!product.is_active ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ""}>
        ${product.is_active ? "В корзину" : "Недоступен"}
      </button>
    </article>
  `;
}

async function loadProducts() {
  const params = new URLSearchParams({
    page: state.productsPage,
    size: 9,
    sort_by: $("#filter-sort-by").value,
    sort_order: $("#filter-sort-order").value,
  });

  const name = $("#filter-name").value.trim();
  const minPrice = $("#filter-min-price").value;
  const maxPrice = $("#filter-max-price").value;

  if (name) params.set("name", name);
  if (minPrice) params.set("min_price", minPrice);
  if (maxPrice) params.set("max_price", maxPrice);
  if (state.user?.is_admin && $("#filter-include-inactive").checked) {
    params.set("include_inactive", "true");
  }

  const data = await apiFetch(`/products?${params.toString()}`);
  state.productsPages = data.pages || 1;

  $("#products").innerHTML = data.items.length
    ? data.items.map(productCard).join("")
    : '<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 40px;">Товары не найдены</p>';

  $("#page-info").textContent = `Страница ${data.page} из ${state.productsPages}`;
}

async function addToCart(productId) {
  await apiFetch("/cart/items", {
    method: "POST",
    body: JSON.stringify({ items: [{ product_id: Number(productId), quantity: 1 }] }),
  });
  showToast("Товар добавлен в корзину");
  updateCartBadge();
}

async function updateCartBadge() {
  try {
    const cart = await apiFetch("/cart");
    const count = cart.items.reduce((sum, item) => sum + item.quantity, 0);
    const badge = $("#cart-badge");
    badge.textContent = count;
    badge.classList.toggle("badge-hidden", count === 0);
  } catch (e) {
    // ignore
  }
}

function cartItemRow(item) {
  return `
    <div class="row">
      <div style="flex: 1;">
        <div style="font-weight: 600;">${item.name}</div>
        <div class="muted">${formatMoney(item.price)} × ${item.quantity}</div>
      </div>
      <div class="actions" style="display: flex; align-items: center; gap: 16px;">
        <div style="font-weight: 700;">${formatMoney(item.subtotal)}</div>
        <button class="btn btn-danger btn-sm" data-action="remove-cart-item" data-id="${item.product_id}">
          Удалить
        </button>
      </div>
    </div>
  `;
}

async function loadCart() {
  const cart = await apiFetch("/cart");
  $("#cart-items").innerHTML = cart.items.length
    ? cart.items.map(cartItemRow).join("")
    : '<p style="text-align: center; color: var(--text-secondary); padding: 40px;">Корзина пуста</p>';
  $("#cart-total").textContent = formatMoney(cart.total);
  updateCartBadge();
}

async function checkout() {
  await apiFetch("/orders/checkout", { method: "POST" });
  showToast("Заказ создан! Перейдите к оплате.");
  showView("orders");
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

  const actionButtons =
    order.status === "pending_payment" || order.status === "created"
      ? `<div style="display: flex; gap: 12px;">
           <button class="btn btn-primary btn-sm" data-action="pay-order" data-id="${order.id}">Оплатить</button>
           <button class="btn btn-danger btn-sm" data-action="cancel-order" data-id="${order.id}">Отменить</button>
         </div>`
      : order.status === "paid" && order.paid_at
      ? `<span style="color: var(--text-secondary); font-size: 13px;">Оплачено ${new Date(order.paid_at).toLocaleString("ru-RU")}</span>`
      : "";

  return `
    <div class="card glass-inset" style="margin-bottom: 16px;">
      <div class="row" style="border: none; background: transparent; padding: 0 0 16px 0;">
        <div>
          <div style="font-weight: 700; font-size: 18px;">Заказ #${order.id}</div>
          <div class="muted">${new Date(order.created_at).toLocaleString("ru-RU")}</div>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
          <span class="status-badge ${statusClass[order.status] || "pending"}">${statusText[order.status] || order.status}</span>
          ${order.payment_method ? `<span style="font-size: 13px; color: var(--text-secondary);">${paymentMethodText[order.payment_method] || order.payment_method}</span>` : ""}
        </div>
      </div>
      <div class="stack" style="gap: 8px;">
        ${order.items
          .map(
            (item) => `
          <div class="row" style="padding: 12px;">
            <div style="flex: 1;">${item.product_name}</div>
            <div class="muted">${formatMoney(item.price)} × ${item.quantity}</div>
            <div style="font-weight: 600;">${formatMoney(item.subtotal)}</div>
          </div>
        `
          )
          .join("")}
      </div>
      <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        ${actionButtons}
        <span style="font-size: 20px; font-weight: 800;">Итого: ${formatMoney(order.total_amount)}</span>
      </div>
    </div>
  `;
}

async function loadOrders() {
  const orders = await apiFetch("/orders");
  $("#orders").innerHTML = orders.length
    ? orders.map(orderCard).join("")
    : '<p style="text-align: center; color: var(--text-secondary); padding: 40px;">У вас пока нет заказов</p>';
}

function adminProductRow(product) {
  const thumbHtml = product.image_url
    ? `<img src="${product.image_url}" alt="${product.name}" style="width: 48px; height: 48px; object-fit: cover; border-radius: 8px; margin-right: 12px;" onerror="this.style.display='none'" />`
    : "";

  return `
    <div class="row">
      <div style="flex: 1; display: flex; align-items: center;">
        ${thumbHtml}
        <div>
          <div style="font-weight: 600;">${product.name}</div>
          <div class="muted">${formatMoney(product.price)}</div>
        </div>
      </div>
      <div class="actions" style="display: flex; gap: 8px; flex-wrap: wrap;">
        <span class="badge ${product.is_active ? "" : "inactive"}">
          ${product.is_active ? "Активен" : "Неактивен"}
        </span>
        <button class="btn btn-secondary btn-sm" data-action="edit-product" data-id="${product.id}" data-name="${product.name}" data-price="${product.price}">
          Изменить
        </button>
        <button class="btn btn-secondary btn-sm" data-action="toggle-product" data-id="${product.id}">
          ${product.is_active ? "Деактивировать" : "Активировать"}
        </button>
        <button class="btn btn-danger btn-sm" data-action="delete-product" data-id="${product.id}">
          Удалить
        </button>
      </div>
    </div>
  `;
}

async function loadAdminProducts() {
  const data = await apiFetch("/products?size=100&include_inactive=true");
  $("#admin-products").innerHTML = data.items.length
    ? data.items.map(adminProductRow).join("")
    : '<p style="text-align: center; color: var(--text-secondary); padding: 20px;">Товаров нет</p>';
}

async function createProduct(payload) {
  await apiFetch("/products", { method: "POST", body: JSON.stringify(payload) });
  showToast("Товар успешно создан");
  loadAdminProducts();
}

async function editProduct(productId, currentName, currentPrice) {
  const name = prompt("Новое название товара:", currentName);
  if (!name) return;
  const price = prompt("Новая цена товара:", currentPrice);
  if (!price) return;

  await apiFetch(`/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify({ name, price: Number(price) }),
  });
  showToast("Товар обновлён");
  loadAdminProducts();
}

async function toggleProduct(productId, isActive) {
  await apiFetch(`/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: !isActive }),
  });
  showToast("Статус товара изменён");
  loadAdminProducts();
}

async function deleteProduct(productId) {
  if (!confirm("Вы уверены, что хотите деактивировать этот товар?")) return;
  await apiFetch(`/products/${productId}`, { method: "DELETE" });
  showToast("Товар деактивирован");
  loadAdminProducts();
}

async function logout() {
  try {
    await fetch(`${API}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
  } catch {
    // ignore
  }
  clearSession();
  showAuth();
  showToast("Вы вышли из аккаунта");
}

// === Payment Modal Functions ===

function openPaymentModal(orderId) {
  currentOrderId = orderId;
  selectedPaymentMethod = null;

  const modal = $("#payment-modal");
  modal.classList.remove("hidden");

  const content = $("#payment-content");
  content.innerHTML = `
    <div class="payment-methods">
      <div class="payment-method" data-method="card">
        <div class="payment-method-icon">💳</div>
        <div class="payment-method-info">
          <div class="payment-method-name">Банковская карта</div>
          <div class="payment-method-desc">Visa, Mastercard, МИР</div>
        </div>
      </div>
      <div class="payment-method" data-method="sbp">
        <div class="payment-method-icon">📱</div>
        <div class="payment-method-info">
          <div class="payment-method-name">Система быстрых платежей</div>
          <div class="payment-method-desc">Оплата по QR-коду</div>
        </div>
      </div>
      <div class="payment-method" data-method="cash">
        <div class="payment-method-icon">💵</div>
        <div class="payment-method-info">
          <div class="payment-method-name">Наличными при получении</div>
          <div class="payment-method-desc">Оплата курьеру</div>
        </div>
      </div>
    </div>
    <div style="display: flex; gap: 12px;">
      <button id="cancel-payment" class="btn btn-secondary" style="flex: 1;">Отмена</button>
      <button id="confirm-payment" class="btn btn-primary" style="flex: 1;" disabled>Оплатить</button>
    </div>
  `;

  content.querySelectorAll(".payment-method").forEach((el) => {
    el.addEventListener("click", () => {
      content.querySelectorAll(".payment-method").forEach((e) => e.classList.remove("selected"));
      el.classList.add("selected");
      selectedPaymentMethod = el.dataset.method;
      content.querySelector("#confirm-payment").disabled = false;
    });
  });

  content.querySelector("#cancel-payment").addEventListener("click", closePaymentModal);
  content.querySelector("#confirm-payment").addEventListener("click", processPayment);
}

function closePaymentModal() {
  $("#payment-modal").classList.add("hidden");
  currentOrderId = null;
  selectedPaymentMethod = null;
}

async function processPayment() {
  if (!currentOrderId || !selectedPaymentMethod) return;

  const content = $("#payment-content");
  content.innerHTML = `
    <div class="payment-processing">
      <div class="spinner"></div>
      <p>Обработка платежа...</p>
    </div>
  `;

  try {
    await apiFetch(`/orders/${currentOrderId}/pay`, {
      method: "POST",
      body: JSON.stringify({ payment_method: selectedPaymentMethod }),
    });

    showToast("Оплата прошла успешно!");
    closePaymentModal();
    loadOrders();
  } catch (error) {
    showToast(error.message, "error");
    closePaymentModal();
  }
}

async function cancelOrder(orderId) {
  try {
    await apiFetch(`/orders/${orderId}/cancel`, { method: "POST" });
    showToast("Заказ отменён");
    loadOrders();
  } catch (error) {
    showToast(error.message, "error");
  }
}

// === Forms ===

function bindForms() {
  // ДОБАВЛЕНО: Переключение вкладок Вход / Регистрация
  document.querySelectorAll(".auth-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      if (tab.dataset.tab === "login") {
        $("#login-form").classList.remove("hidden");
        $("#register-form").classList.add("hidden");
      } else {
        $("#login-form").classList.add("hidden");
        $("#register-form").classList.remove("hidden");
      }
    });
  });

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await login($("#login-identifier").value, $("#login-password").value);
      showToast("Добро пожаловать!");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const password = $("#register-password").value;
    const passwordConfirm = $("#register-password-confirm").value;

    if (password !== passwordConfirm) {
      showToast("Пароли не совпадают", "error");
      return;
    }

    try {
      await registerAndLogin({
        full_name: $("#register-full-name").value,
        email: $("#register-email").value,
        phone: $("#register-phone").value,
        password,
        password_confirm: passwordConfirm,
      });
      showToast("Аккаунт успешно создан!");
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  $("#create-product-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await createProduct({
        name: $("#product-name").value,
        price: Number($("#product-price").value),
        description: $("#product-description").value || null,
        image_url: $("#product-image-url").value || null,
        is_active: $("#product-is-active").checked,
      });
      e.target.reset();
      $("#product-is-active").checked = true;
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}

function bindGlobalActions() {
  document.addEventListener("click", async (e) => {
    const target = e.target.closest("[data-action]");
    if (!target) return;

    const action = target.dataset.action;
    try {
      if (action === "nav-view") showView(target.dataset.view);
      if (action === "logout") await logout();
      if (action === "search-products") {
        state.productsPage = 1;
        await loadProducts();
      }
      if (action === "page-prev" && state.productsPage > 1) {
        state.productsPage -= 1;
        await loadProducts();
      }
      if (action === "page-next" && state.productsPage < state.productsPages) {
        state.productsPage += 1;
        await loadProducts();
      }
      if (action === "add-to-cart") await addToCart(target.dataset.id);
      if (action === "remove-cart-item") {
        await apiFetch(`/cart/items/${target.dataset.id}`, { method: "DELETE" });
        await loadCart();
      }
      if (action === "clear-cart") {
        await apiFetch("/cart", { method: "DELETE" });
        await loadCart();
      }
      if (action === "checkout") await checkout();
      if (action === "edit-product")
        await editProduct(target.dataset.id, target.dataset.name, target.dataset.price);
      if (action === "toggle-product") {
        const product = await apiFetch(`/products/${target.dataset.id}`);
        await toggleProduct(target.dataset.id, product.is_active);
      }
      if (action === "delete-product") await deleteProduct(target.dataset.id);
      if (action === "pay-order") openPaymentModal(target.dataset.id);
      if (action === "cancel-order") {
        if (confirm("Вы уверены, что хотите отменить заказ?")) {
          await cancelOrder(target.dataset.id);
        }
      }
    } catch (error) {
      showToast(error.message, "error");
    }
  });

  document.addEventListener("click", (e) => {
    if (e.target.id === "payment-modal") {
      closePaymentModal();
    }
  });
}

async function init() {
  bindForms();
  bindGlobalActions();

  if (!state.accessToken) {
    showAuth();
    return;
  }

  try {
    await loadMe();
    showView("catalog");
  } catch {
    clearSession();
    showAuth();
  }
}

init();