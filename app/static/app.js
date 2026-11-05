"use strict";
/* RetailDesk single-page UI — vanilla JS talking to the FastAPI backend.
   Backend location comes from config.js (window.API_BASE): "" means
   same-origin (FastAPI serves this page); set it to the Render URL when
   this page is hosted separately on Vercel. */
const API_BASE = (window.API_BASE || "").replace(/\/+$/, "");

const state = {
  token: localStorage.getItem("rd_token") || null,
  user: JSON.parse(localStorage.getItem("rd_user") || "null"),
  products: [],
  customers: [],
};

const $ = (sel) => document.querySelector(sel);
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  if (options.body && typeof options.body === "object" && !(options.body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(API_BASE + path, { ...options, headers });
  if (res.status === 401) { logout(); throw new Error("Session expired — please login again."); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

/* ---------------- auth ---------------- */
$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#loginError").textContent = "";
  try {
    const body = new URLSearchParams({
      username: $("#loginEmail").value.trim(),
      password: $("#loginPassword").value,
    });
    const data = await api("/api/auth/login", { method: "POST", body });
    state.token = data.access_token;
    localStorage.setItem("rd_token", state.token);
    state.user = await api("/api/auth/me");
    localStorage.setItem("rd_user", JSON.stringify(state.user));
    showApp();
  } catch (err) {
    $("#loginError").textContent = err.message;
  }
});

function logout() {
  state.token = null; state.user = null;
  localStorage.removeItem("rd_token"); localStorage.removeItem("rd_user");
  $("#appView").classList.add("hidden");
  $("#loginView").classList.remove("hidden");
}
$("#logoutBtn").addEventListener("click", logout);

function showApp() {
  $("#loginView").classList.add("hidden");
  $("#appView").classList.remove("hidden");
  $("#userInfo").textContent = `${state.user.name} · ${state.user.role.toUpperCase()}`;
  switchView("dashboard");
}

/* ---------------- navigation ---------------- */
document.querySelectorAll(".nav-btn").forEach((btn) =>
  btn.addEventListener("click", () => switchView(btn.dataset.view))
);

function switchView(name) {
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("hidden", v.id !== "view-" + name));
  if (name === "dashboard") loadDashboard();
  if (name === "products") loadProducts();
  if (name === "billing") loadBilling();
  if (name === "customers") loadCustomers();
}

/* ---------------- dashboard ---------------- */
async function loadDashboard() {
  $("#dashboardError").textContent = "";
  try {
    const s = await api("/api/reports/dashboard");
    $("#statRevenueToday").textContent = money(s.revenue_today);
    $("#statRevenueMonth").textContent = money(s.revenue_this_month);
    $("#statBillsToday").textContent = s.bills_today;
    $("#statLowStock").textContent = s.low_stock_count;
    const tbody = $("#topProductsTable tbody");
    tbody.innerHTML = s.top_products.map((p) =>
      `<tr><td data-label="Product">${escapeHtml(p.product_name)}</td><td data-label="Qty Sold">${p.quantity_sold}</td><td data-label="Revenue">${money(p.revenue)}</td></tr>`).join("")
      || `<tr><td colspan="3">No sales yet</td></tr>`;
    drawChart(s.last_7_days);
  } catch (err) {
    $("#dashboardError").textContent = err.message + (state.user.role === "staff" ? " (Reports are owner-only.)" : "");
  }
}

function drawChart(days) {
  const canvas = $("#revenueChart");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const max = Math.max(...days.map((d) => d.revenue), 1);
  const pad = 34, chartH = H - pad - 18, barW = (W - 16) / days.length - 14;
  ctx.strokeStyle = "#d0d5dd"; ctx.beginPath(); ctx.moveTo(4, H - pad); ctx.lineTo(W - 4, H - pad); ctx.stroke();
  days.forEach((d, i) => {
    const x = 12 + i * ((W - 16) / days.length);
    const h = (d.revenue / max) * chartH;
    ctx.fillStyle = "#2f54eb";
    ctx.fillRect(x, H - pad - h, barW, h);
    ctx.fillStyle = "#1f2430"; ctx.font = "10px sans-serif"; ctx.textAlign = "center";
    ctx.fillText(d.date.slice(5), x + barW / 2, H - pad + 13);
    ctx.fillText("₹" + Math.round(d.revenue), x + barW / 2, H - pad - h - 4);
  });
}

/* ---------------- products ---------------- */
let showingLowStock = false;

async function loadProducts() {
  $("#productError").textContent = "";
  try {
    let items;
    if (showingLowStock) {
      items = await api("/api/products/low-stock");
    } else {
      const q = $("#productSearch").value.trim();
      const page = await api("/api/products?page_size=100" + (q ? "&search=" + encodeURIComponent(q) : ""));
      items = page.items;
    }
    state.products = items;
    const isOwner = state.user.role === "owner";
    $("#productsTable tbody").innerHTML = items.map((p) => `
      <tr>
        <td data-label="Name">${escapeHtml(p.name)}</td><td data-label="SKU">${escapeHtml(p.sku)}</td><td data-label="Category">${escapeHtml(p.category || "-")}</td>
        <td data-label="Price">${money(p.price)}</td><td data-label="GST %">${p.gst_percent}%</td><td data-label="Stock">${p.stock_qty}</td>
        <td data-label="Status"><span class="badge ${p.is_low_stock ? "low" : "ok"}">${p.is_low_stock ? "Low Stock" : "In Stock"}</span></td>
        <td class="actions-cell">
          <button class="btn small" onclick="restock(${p.id}, '${escapeHtml(p.name)}')">Restock</button>
          ${isOwner ? `<button class="btn small danger" onclick="deleteProduct(${p.id})">Delete</button>` : ""}
        </td>
      </tr>`).join("") || `<tr><td colspan="8">No products found</td></tr>`;
  } catch (err) { $("#productError").textContent = err.message; }
}

let searchTimer;
$("#productSearch").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { showingLowStock = false; loadProducts(); }, 300);
});
$("#lowStockBtn").addEventListener("click", () => { showingLowStock = true; loadProducts(); });
$("#allProductsBtn").addEventListener("click", () => { showingLowStock = false; loadProducts(); });

$("#productForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const payload = {
    name: f.get("name"), sku: f.get("sku"), category: f.get("category") || null,
    price: parseFloat(f.get("price")),
    gst_percent: f.get("gst_percent") ? parseFloat(f.get("gst_percent")) : 5,
    stock_qty: f.get("stock_qty") ? parseInt(f.get("stock_qty")) : 0,
    low_stock_threshold: f.get("low_stock_threshold") ? parseInt(f.get("low_stock_threshold")) : 5,
  };
  try { await api("/api/products", { method: "POST", body: payload }); e.target.reset(); showingLowStock = false; loadProducts(); }
  catch (err) { $("#productError").textContent = err.message; }
});

window.restock = async (id, name) => {
  const add = prompt(`Add stock for "${name}" — quantity to add:`);
  if (!add) return;
  try {
    const product = state.products.find((p) => p.id === id);
    await api("/api/products/" + id, { method: "PUT", body: { stock_qty: product.stock_qty + parseInt(add) } });
    loadProducts();
  } catch (err) { $("#productError").textContent = err.message; }
};

window.deleteProduct = async (id) => {
  if (!confirm("Delete this product?")) return;
  try { await api("/api/products/" + id, { method: "DELETE" }); loadProducts(); }
  catch (err) { $("#productError").textContent = err.message; }
};

/* ---------------- billing ---------------- */
async function loadBilling() {
  $("#billError").textContent = ""; $("#billSuccess").textContent = "";
  try {
    const page = await api("/api/products?page_size=100");
    state.products = page.items;
    state.customers = await api("/api/customers");
    $("#billCustomer").innerHTML = `<option value="">Walk-in Customer</option>` +
      state.customers.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    if (!$("#billItems").children.length) addBillRow();
    refreshBillRows();
    loadBillsTable();
  } catch (err) { $("#billError").textContent = err.message; }
}

function addBillRow() {
  const row = document.createElement("div");
  row.className = "bill-row";
  row.innerHTML = `
    <select class="bill-product"></select>
    <input type="number" class="bill-qty" value="1" min="1" />
    <button class="btn small danger" type="button">✕</button>`;
  row.querySelector("button").addEventListener("click", () => { row.remove(); updateEstimate(); });
  row.querySelector(".bill-product").addEventListener("change", updateEstimate);
  row.querySelector(".bill-qty").addEventListener("input", updateEstimate);
  $("#billItems").appendChild(row);
  refreshBillRows();
}
$("#addBillItemBtn").addEventListener("click", addBillRow);

function refreshBillRows() {
  document.querySelectorAll(".bill-product").forEach((sel) => {
    const current = sel.value;
    sel.innerHTML = state.products.map((p) =>
      `<option value="${p.id}">${escapeHtml(p.name)} — ${money(p.price)} (stock: ${p.stock_qty})</option>`).join("");
    if (current) sel.value = current;
  });
  updateEstimate();
}

function billItemsFromUI() {
  const items = [];
  document.querySelectorAll(".bill-row").forEach((row) => {
    const pid = parseInt(row.querySelector(".bill-product").value);
    const qty = parseInt(row.querySelector(".bill-qty").value);
    if (pid && qty > 0) items.push({ product_id: pid, quantity: qty });
  });
  return items;
}

function updateEstimate() {
  let total = 0;
  billItemsFromUI().forEach((it) => {
    const p = state.products.find((x) => x.id === it.product_id);
    if (p) total += p.price * it.quantity * (1 + p.gst_percent / 100);
  });
  $("#billEstimate").textContent = "Estimated Total (incl. GST): " + money(total);
}

$("#createBillBtn").addEventListener("click", async () => {
  $("#billError").textContent = ""; $("#billSuccess").textContent = "";
  const items = billItemsFromUI();
  if (!items.length) { $("#billError").textContent = "Add at least one item."; return; }
  const payload = {
    items,
    payment_mode: $("#billPayment").value,
    customer_id: $("#billCustomer").value ? parseInt($("#billCustomer").value) : null,
  };
  try {
    const bill = await api("/api/bills", { method: "POST", body: payload });
    $("#billSuccess").innerHTML =
      `✅ Bill ${bill.bill_number} created — Total ${money(bill.grand_total)} (GST ${money(bill.gst_total)}). ` +
      `<a href="#" onclick="downloadInvoice(${bill.id}); return false;">Download Invoice PDF</a>`;
    $("#billItems").innerHTML = ""; addBillRow();
    loadBillsTable();
  } catch (err) { $("#billError").textContent = err.message; }
});

async function loadBillsTable() {
  try {
    const bills = await api("/api/bills?limit=15");
    $("#billsTable tbody").innerHTML = bills.map((b) => `
      <tr><td data-label="Bill No.">${b.bill_number}</td><td data-label="Total">${money(b.grand_total)}</td><td data-label="Payment">${b.payment_mode.toUpperCase()}</td>
      <td data-label="Invoice"><a href="#" onclick="downloadInvoice(${b.id}); return false;">PDF</a></td></tr>`).join("")
      || `<tr><td colspan="4">No bills yet</td></tr>`;
  } catch (err) { $("#billError").textContent = err.message; }
}

window.downloadInvoice = async (billId) => {
  const res = await fetch(`${API_BASE}/api/bills/${billId}/invoice`, {
    headers: { Authorization: "Bearer " + state.token },
  });
  if (!res.ok) { alert("Could not download invoice"); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `invoice-${billId}.pdf`; a.click();
  URL.revokeObjectURL(url);
};

/* ---------------- customers ---------------- */
async function loadCustomers() {
  $("#customerError").textContent = "";
  try {
    const customers = await api("/api/customers");
    state.customers = customers;
    $("#customersTable tbody").innerHTML = customers.map((c) =>
      `<tr><td data-label="Name">${escapeHtml(c.name)}</td><td data-label="Phone">${escapeHtml(c.phone || "-")}</td><td data-label="Email">${escapeHtml(c.email || "-")}</td></tr>`).join("")
      || `<tr><td colspan="3">No customers yet</td></tr>`;
  } catch (err) { $("#customerError").textContent = err.message; }
}

$("#customerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/customers", {
      method: "POST",
      body: { name: f.get("name"), phone: f.get("phone") || null, email: f.get("email") || null },
    });
    e.target.reset(); loadCustomers();
  } catch (err) { $("#customerError").textContent = err.message; }
});

/* ---------------- utils / boot ---------------- */
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

if (state.token && state.user) showApp();
