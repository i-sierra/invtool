// ---- LocalStorage helpers ----
const LS_KEYS = {
  location: "inv:last:location_code",
  from: "inv:last:from_location",
  to: "inv:last:to_location",
  refType: "inv:last:ref_type",
};

/** Fallback mapping (used only if API is not reachable). */
const REF_PREFIX_FALLBACK = {
  PO: "PO-",
  RMA: "RMA-",
  WO: "WO-",
  JOB: "JOB-",
  MOVE: "MOVE-",
  COUNT: "COUNT-",
  SCRAP: "SCRAP-",
  ADJ: "ADJ-",
};

/** Runtime mapping loaded from backend. */
let REF_PREFIX = null;

/** Fetch `/config/ref-types` once; then run `cb`. */
function ensureRefTypesLoaded(cb) {
  if (REF_PREFIX) { cb && cb(); return; }
  fetch("/config/ref-types", { headers: { "Accept": "application/json" } })
    .then(r => r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status)))
    .then(json => { REF_PREFIX = json; cb && cb(); })
    .catch(() => { REF_PREFIX = REF_PREFIX_FALLBACK; cb && cb(); });
}

/** Populate all `<select name="ref_type">` within `root` from `REF_PREFIX` keys. */
function populateRefTypeSelects(root) {
  const selects = root.querySelectorAll('select[name="ref_type"]');
  if (!selects.length) return;
  const keys = Object.keys(REF_PREFIX || {}).sort();
  const last = (localStorage.getItem(LS_KEYS.refType) || "").toUpperCase();

  selects.forEach(sel => {
    const current = (sel.value || "").toUpperCase();

    // Build options
    sel.innerHTML = "";
    const optBlank = document.createElement("option");
    optBlank.value = "";
    optBlank.textContent = "—";
    sel.appendChild(optBlank);
    keys.forEach(k => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      sel.appendChild(opt);
    });

    // Restore selection: prefer current > last-used
    if (current && keys.includes(current)) {
      sel.value = current;
    } else if (last && keys.includes(last)) {
      sel.value = last;
    } else {
      sel.value = "";
    }

    // Update placeholder for sibling `ref_id`
    applyRefTypePlaceholder(sel);

    // Autofill `ref_id` prefix only if empty
    const refId = sel.closest("form")?.querySelector('input[name="ref_id"]');
    if (refId && !refId.value) {
      const prefix = (REF_PREFIX && REF_PREFIX[sel.value]) || "";
      if (prefix) refId.value = prefix;
    }
  });
}

/** Update placeholder for `ref_id` based on current `ref_type` value. */
function applyRefTypePlaceholder(refTypeField) {
  const form = refTypeField.closest("form");
  if (!form) return;
  const refId = form.querySelector('input[name="ref_id"]');
  if (!refId) return;
  const val = (refTypeField.value || "").toUpperCase();
  const prefix = (REF_PREFIX && REF_PREFIX[val]) || "";
  refId.placeholder = prefix ? `${prefix}XXXX` : "Reference ID";
}

/** Apply last-used selections to selects/inputs within root. */
function applyLastSelections(root) {
  // Location code
  const selLoc = root.querySelector('select[name="location_code"]');
  if (selLoc) {
    const v = localStorage.getItem(LS_KEYS.location);
    if (v && [...selLoc.options].some(o => o.value === v)) selLoc.value = v;
  }
  // From location
  const selFrom = root.querySelector('select[name="from_location"]');
  if (selFrom) {
    const v = localStorage.getItem(LS_KEYS.from);
    if (v && [...selFrom.options].some(o => o.value === v)) selFrom.value = v;
  }
  // To location
  const selTo = root.querySelector('select[name="to_location"]');
  if (selTo) {
    const v = localStorage.getItem(LS_KEYS.to);
    if (v && [...selTo.options].some(o => o.value === v)) selTo.value = v;
  }

  // Load ref types then populate the selects and set placeholders
  ensureRefTypesLoaded(() => {
    populateRefTypeSelects(root);
  });
}

/** Install change handlers to persist selections and drive `ref_id` placeholder/autofill. */
function installHandlers(root) {
  // Location code
  const selLoc = root.querySelector('select[name="location_code"]');
  if (selLoc) selLoc.addEventListener("change", () => {
    localStorage.setItem(LS_KEYS.location, selLoc.value);
  });
  // From location
  const selFrom = root.querySelector('select[name="from_location"]');
  if (selFrom) selFrom.addEventListener("change", () => {
    localStorage.setItem(LS_KEYS.from, selFrom.value);
  });
  // To location
  const selTo = root.querySelector('select[name="to_location"]');
  if (selTo) selTo.addEventListener("change", () => {
    localStorage.setItem(LS_KEYS.to, selTo.value);
  });

  // Ref type select + ref id linkage
  root.querySelectorAll('select[name="ref_type"]').forEach(sel => {
    sel.addEventListener("change", () => {
      const val = (sel.value || "").toUpperCase();
      localStorage.setItem(LS_KEYS.refType, val);
      applyRefTypePlaceholder(sel);
      // Autofill only if `ref_id` is empty
      const refId = sel.closest("form")?.querySelector('input[name="ref_id"]');
      if (refId && !refId.value) {
        const prefix = (REF_PREFIX && REF_PREFIX[val]) || "";
        if (prefix) refId.value = prefix;
      }
    });
  });
}

// Init for initial page
document.addEventListener("DOMContentLoaded", () => {
  applyLastSelections(document);
  installHandlers(document);
});

// Re-init when HTMX swaps in the movements fragment
document.body.addEventListener("htmx:afterSwap", (evt) => {
  // Use the actual swapped element from HTMX event detail
  const swapped = evt.detail && evt.detail.target ? evt.detail.target : null;
  if (swapped && swapped.id === "movements") {
    applyLastSelections(swapped);
    installHandlers(swapped);
  }
});
