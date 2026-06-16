// Extracted JS from index.html
const AUTH_TOKEN_KEY = "door_jwt";

function getStoredJwt() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

function storeJwt(token) {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
}

function clearJwt() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

function redirectToForbiddenPage() {
  window.location.replace("/static/forbidden.html");
}

function revealAppShell() {
  document.body.classList.remove("auth-pending");
}

function getActivationTokenFromUrl() {
  return new URLSearchParams(window.location.search).get("activation_token");
}

async function loadFingerprintVisitorId() {
  if (!window.FingerprintJS) {
    throw new Error("FingerprintJS failed to load");
  }
  const fp = await window.FingerprintJS.load();
  const result = await fp.get();
  return result.visitorId;
}

function getDeviceType() {
  const ua = navigator.userAgent || "";
  const isMobile =
    /Mobi|Android|iPhone|iPad|iPod/i.test(ua) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/i.test(ua));
  return isMobile ? "mobile" : "desktop";
}

async function postAuthJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let message = "Authentication failed";
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}

async function activateFromRegistrationToken(token) {
  const visitorId = await loadFingerprintVisitorId();
  const deviceLabel = [navigator.platform, navigator.userAgent.split(" ")[0]]
    .filter(Boolean)
    .join(" ");
  const data = await postAuthJson("/auth/activate", {
    token,
    visitor_id: visitorId,
    device_label: deviceLabel,
    device_type: getDeviceType(),
  });
  if (data && data.token) {
    storeJwt(data.token);
    window.history.replaceState({}, document.title, "/");
    return true;
  }
  return false;
}

async function recoverJwtFromFingerprint() {
  const visitorId = await loadFingerprintVisitorId();
  const data = await postAuthJson("/auth/recover", { visitor_id: visitorId });
  if (data && data.token) {
    storeJwt(data.token);
    return true;
  }
  return false;
}

async function checkCurrentAuth() {
  const headers = new Headers();
  const token = getStoredJwt();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch("/check-auth", {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    return false;
  }

  try {
    const data = await response.json();
    return data && data.authenticated === true;
  } catch (_) {
    return false;
  }
}

async function ensureAuthenticated() {
  const activationToken = getActivationTokenFromUrl();
  if (activationToken) {
    const activated = await activateFromRegistrationToken(activationToken);
    if (!activated) {
      redirectToForbiddenPage();
    }
    return activated;
  }

  try {
    if (await checkCurrentAuth()) {
      revealAppShell();
      return true;
    }
  } catch (_) {
    // Fall through to fingerprint recovery.
  }

  try {
    const recovered = await recoverJwtFromFingerprint();
    if (!recovered) {
      redirectToForbiddenPage();
      return false;
    }
    revealAppShell();
    return recovered;
  } catch (_) {
    redirectToForbiddenPage();
    return false;
  }
}

const authReadyPromise = ensureAuthenticated();

authReadyPromise
  .then((authenticated) => {
    if (authenticated) {
      revealAppShell();
    }
  })
  .catch(() => {
    redirectToForbiddenPage();
  });

async function authFetch(url, options = {}) {
  await authReadyPromise;
  const requestOptions = { ...options };
  const headers = new Headers(requestOptions.headers || {});
  const token = getStoredJwt();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  requestOptions.headers = headers;

  let response = await fetch(url, requestOptions);
  if (response.status === 401 && token) {
    clearJwt();
    try {
      const recovered = await recoverJwtFromFingerprint();
      if (recovered) {
        headers.set("Authorization", `Bearer ${getStoredJwt()}`);
        response = await fetch(url, requestOptions);
      } else {
        redirectToForbiddenPage();
      }
    } catch (_) {
      redirectToForbiddenPage();
    }
  }
  return response;
}

const toggleSwitch = document.getElementById("toggleSwitch");
const toggleSlider = document.getElementById("toggleSlider");
const toggleOptions = document.querySelectorAll(".toggle-option");
const toggleHint = document.getElementById("toggleHint");
const singleInputsDiv = document.getElementById("singleInputs");
const bulkInputsDiv = document.getElementById("bulkInputs");
const excelInput = document.getElementById("excelFile");
const form = document.getElementById("dxfForm");
// New UI elements
const doorType = document.getElementById("doorType");
const subType = document.getElementById("subType");
const fireOption = document.getElementById("fireOption");
const fireOptionsContainer = document.getElementById("fireOptionsContainer");
const holeOffset = document.getElementById("holeOffset");
const defaultAllowance = document.getElementById("defaultAllowance");
const allowanceInputs = document.getElementById("allowanceInputs");
const horizontalAllowancesHeader = document.getElementById(
  "horizontalAllowancesHeader"
);
const verticalAllowancesHeader = document.getElementById(
  "verticalAllowancesHeader"
);
const verticalAllowanceInputs = document.getElementById(
  "verticalAllowanceInputs"
);
const sheetSize = document.getElementById("sheetSize");

let currentMode = "single";
let touchStartX = 0;
let touchEndX = 0;

// Validation rules
const MIN_DIM = 200;
const MAX_DIM = 3000;
const MIN_ALLOW = 0;
const MAX_ALLOW = 50;

function markInvalid(el) {
  if (!el) return;
  el.style.outline = "2px solid rgba(220,20,60,0.9)";
  el.scrollIntoView({ block: "center", behavior: "smooth" });
}

function clearInvalid(el) {
  if (!el) return;
  el.style.outline = "";
}

function validateInputs() {
  // returns { ok: bool, messages: [string], firstEl: HTMLElement|null }
  const msgs = [];
  let firstEl = null;

  // width and height required
  const widthIn = document.querySelector('input[name="width_measurement"]');
  const heightIn = document.querySelector('input[name="height_measurement"]');
  const width = Number(widthIn && widthIn.value);
  const height = Number(heightIn && heightIn.value);

  // clear prior outlines
  clearInvalid(widthIn);
  clearInvalid(heightIn);

  if (!Number.isFinite(width) || width <= 0) {
    msgs.push("Width is required and must be a number.");
    firstEl = firstEl || widthIn;
    markInvalid(widthIn);
  } else if (width < MIN_DIM || width > MAX_DIM) {
    msgs.push(`Width must be between ${MIN_DIM} and ${MAX_DIM} mm.`);
    firstEl = firstEl || widthIn;
    markInvalid(widthIn);
  }

  if (!Number.isFinite(height) || height <= 0) {
    msgs.push("Height is required and must be a number.");
    firstEl = firstEl || heightIn;
    markInvalid(heightIn);
  } else if (height < MIN_DIM || height > MAX_DIM) {
    msgs.push(`Height must be between ${MIN_DIM} and ${MAX_DIM} mm.`);
    firstEl = firstEl || heightIn;
    markInvalid(heightIn);
  }

  // Door type / Sub type validation (selects)
  const doorTypeEl = document.getElementById("doorType");
  const subTypeEl = document.getElementById("subType");
  // clear prior outlines for selects
  if (doorTypeEl) clearInvalid(doorTypeEl);
  if (subTypeEl) clearInvalid(subTypeEl);

  if (doorTypeEl && (!doorTypeEl.value || doorTypeEl.value.trim() === "")) {
    msgs.push("Door type is required.");
    firstEl = firstEl || doorTypeEl;
    markInvalid(doorTypeEl);
  }

  if (subTypeEl && (!subTypeEl.value || subTypeEl.value.trim() === "")) {
    msgs.push("Sub type is required.");
    firstEl = firstEl || subTypeEl;
    markInvalid(subTypeEl);
  }

  // allowances: if allowance inputs visible (defaultAllowance === 'no') validate them
  const defaultAllow = defaultAllowance && defaultAllowance.value === "yes";
  if (!defaultAllow) {
    const allowNames = [
      "left_side_allowance_width",
      "right_side_allowance_width",
      "top_side_allowance_height",
      "bottom_side_allowance_height",
    ];
    for (const name of allowNames) {
      const el = document.querySelector(`input[name="${name}"]`);
      if (!el) continue;
      clearInvalid(el);
      const v = Number(el.value);
      if (!Number.isFinite(v)) {
        msgs.push(`${name.replace(/_/g, " ")} must be a number.`);
        firstEl = firstEl || el;
        markInvalid(el);
      } else if (v !== 0 && v !== 25) {
        msgs.push(`${name.replace(/_/g, " ")} must be either 0 or 25 mm.`);
        firstEl = firstEl || el;
        markInvalid(el);
      }
    }
  }

  return { ok: msgs.length === 0, messages: msgs, firstEl };
}

// Fire door width validation - returns { ok: bool, warning: string|null, width: number }
function validateFireDoorWidth() {
  const widthIn = document.querySelector('input[name="width_measurement"]');
  const width = Number(widthIn && widthIn.value);

  // Check if it's a fire door
  const subTypeEl = document.getElementById("subType");
  if (!subTypeEl || subTypeEl.value !== "fire") {
    return { ok: true, warning: null, width };
  }

  const doorTypeEl = document.getElementById("doorType");
  const isDoorDouble = doorTypeEl && doorTypeEl.value === "double";

  // Fire door clearance is 190mm on each side (L-R)
  const fireClearance = 190;
  const minWidthSingle = 398; // 190 + 190 + minimum usable space
  const minWidthDouble = 341; // minimum for double door

  if (isDoorDouble) {
    if (width < minWidthDouble) {
      return {
        ok: false,
        warning: `⚠️ Fire Door Width Warning\n\nYou are attempting to create a double fire door with width ${width}mm.\n\nWith the required clearance of ${fireClearance}mm on each side, the application may not be able to maintain proper offset for doors less than ${minWidthDouble}mm.\n\nDo you want to continue with drawing anyway?`,
        width,
      };
    }
  } else {
    if (width < minWidthSingle) {
      return {
        ok: false,
        warning: `⚠️ Fire Door Width Warning\n\nYou are attempting to create a single fire door with width ${width}mm.\n\nThe application cannot draw a fire door with less than ${minWidthSingle}mm dimension with the provided clearance of ${fireClearance}mm on each side.\n\nDo you want to continue with drawing anyway?`,
        width,
      };
    }
  }

  return { ok: true, warning: null, width };
}

// Hole offset height validation - returns { ok: bool, warning: string|null, needsChange: bool, height: number }
function validateHoleOffsetHeight() {
  const heightIn = document.querySelector('input[name="height_measurement"]');
  const height = Number(heightIn && heightIn.value);

  const holeOffsetEl = document.getElementById("holeOffset");
  if (!holeOffsetEl) {
    return { ok: true, warning: null, needsChange: false, height };
  }

  const holeOffset = holeOffsetEl.value;
  const minHeightFor150x40 = 458;

  // Only validate if hole offset is 150x40 and height is less than minimum
  if (holeOffset === "150x40" && height < minHeightFor150x40) {
    return {
      ok: false,
      warning: `⚠️ Hole Offset Height Warning\n\nYou are attempting to create a door with height ${height}mm and hole offset 150×40.\n\nThe minimum height required for hole offset 150×40 is ${minHeightFor150x40}mm.\n\nWould you like to change the hole offset to 40×80 or edit the height value?`,
      needsChange: true,
      height,
    };
  }

  return { ok: true, warning: null, needsChange: false, height };
}

// Fire door height validation - returns { ok: bool, warning: string|null, height: number }
function validateFireDoorHeight() {
  const heightIn = document.querySelector('input[name="height_measurement"]');
  const height = Number(heightIn && heightIn.value);

  // Check if it's a fire door
  const subTypeEl = document.getElementById("subType");
  if (!subTypeEl || subTypeEl.value !== "fire") {
    return { ok: true, warning: null, height };
  }

  const doorTypeEl = document.getElementById("doorType");
  const fireOptionEl = document.getElementById("fireOption");
  const fireOptionsContainerEl = document.getElementById(
    "fireOptionsContainer"
  );

  // Only validate if fire options are visible and selected
  if (
    !fireOptionEl ||
    !fireOptionsContainerEl ||
    fireOptionsContainerEl.classList.contains("hidden")
  ) {
    return { ok: true, warning: null, height };
  }

  const isDoorDouble = doorTypeEl && doorTypeEl.value === "double";
  const fireOption = fireOptionEl.value;

  // Define minimum heights for each fire option type
  let minHeight = 0;
  let optionLabel = "";

  if (isDoorDouble) {
    if (fireOption === "standarddouble") {
      minHeight = 411;
      optionLabel = "Standard Fire Door";
    } else if (fireOption === "fourglass") {
      minHeight = 601;
      optionLabel = "Four Glass Fire Door";
    }
  } else {
    if (fireOption === "topfixed") {
      minHeight = 361;
      optionLabel = "Top-Fixed Fire Door";
    } else if (fireOption === "bottomfixed") {
      minHeight = 501;
      optionLabel = "Bottom-Fixed Fire Door";
    } else if (fireOption === "standard") {
      minHeight = 431;
      optionLabel = "Standard Fire Door";
    }
  }

  if (minHeight > 0 && height < minHeight) {
    return {
      ok: false,
      warning: `⚠️ Fire Door Height Warning\n\nYou are attempting to create a ${optionLabel} with height ${height}mm.\n\nThe minimum height required for ${optionLabel} is ${minHeight}mm.\n\nDo you want to continue with drawing anyway?`,
      height,
    };
  }

  return { ok: true, warning: null, height };
}

function setTogglePosition() {
  const activeOption = document.querySelector(".toggle-option.active");
  const sliderWidth = activeOption.offsetWidth;
  const sliderLeft = activeOption.offsetLeft;

  toggleSlider.style.width = sliderWidth + "px";
  toggleSlider.style.transform = `translateX(${sliderLeft - 4}px)`;
}

function switchMode(mode) {
  if (currentMode === mode) return;

  currentMode = mode;

  toggleOptions.forEach((option) => {
    if (option.dataset.value === mode) {
      option.classList.add("active");
    } else {
      option.classList.remove("active");
    }
  });

  setTogglePosition();

  if (mode === "bulk") {
    bulkInputsDiv.classList.remove("hidden");
    bulkInputsDiv.classList.add("fade-in");
    singleInputsDiv.classList.add("hidden");
    excelInput.required = true;
    toggleHint.textContent = "Upload Excel file";
    // mark body for bulk-mode so CSS can hide preview controls robustly
    document.body.classList.add("bulk-mode");
  } else {
    singleInputsDiv.classList.remove("hidden");
    singleInputsDiv.classList.add("fade-in");
    bulkInputsDiv.classList.add("hidden");
    excelInput.required = false;
    toggleHint.textContent = "Enter parameters below";
    document.body.classList.remove("bulk-mode");
  }

  // Hide preview controls in bulk mode, show them in single mode.
  // Use getElementById here to avoid referencing variables that may be declared later.
  const previewBtnEl = document.getElementById("previewBtn");
  const previewContainerEl = document.getElementById("previewContainer");
  const pdfBtnEl = document.getElementById("generatePdfBtn");
  if (mode === "bulk") {
    // hide both the Preview button and the preview container in bulk mode
    if (previewBtnEl) previewBtnEl.classList.add("hidden");
    if (previewContainerEl) previewContainerEl.classList.add("hidden");
    if (pdfBtnEl) {
      pdfBtnEl.classList.add("hidden");
      pdfBtnEl.setAttribute("aria-hidden", "true");
    }
  } else {
    if (previewBtnEl) previewBtnEl.classList.remove("hidden");
    if (previewContainerEl) previewContainerEl.classList.remove("hidden");
    if (pdfBtnEl) {
      pdfBtnEl.classList.remove("hidden");
      pdfBtnEl.setAttribute("aria-hidden", "false");
    }
  }
}

// Top-level delegated fallback for Generate PDF button
// This listener lives at document-level so it attaches early and will catch
// clicks even when direct addEventListener on the element fails in some
// environments (extensions or browser quirks). It mirrors the direct
// `pdfBtn` handler's behaviour.
document.addEventListener("click", (e) => {
  try {
    const btn =
      e.target && e.target.closest && e.target.closest("#generatePdfBtn");
    if (!btn) return;
    e.preventDefault();

    (async () => {
      if (currentMode !== "single") {
        showToast("Generate PDF is only available in Single mode", "error");
        return;
      }

      const v = validateInputs();
      if (!v.ok) {
        showToast("Please fix input errors: " + v.messages.join(" "), "error");
        if (v.firstEl) v.firstEl.focus();
        return;
      }

      // Check fire door width validation
      const fireCheck = validateFireDoorWidth();
      if (!fireCheck.ok) {
        const userConfirmed = await showConfirmDialog(fireCheck.warning);
        if (!userConfirmed) {
          return; // User chose to edit values
        }
      }

      // Check hole offset height validation
      const holeCheck = validateHoleOffsetHeight();
      if (!holeCheck.ok) {
        const userAction = await showHoleOffsetDialog(holeCheck.warning);
        if (userAction === "edit") {
          return; // User chose to edit height
        } else if (userAction === "change") {
          // Change hole offset to 40x80
          const holeOffsetEl = document.getElementById("holeOffset");
          if (holeOffsetEl) holeOffsetEl.value = "40x80";
          showToast("Hole offset changed to 40×80", "success");
        }
      }

      // Check fire door height validation
      const fireHeightCheck = validateFireDoorHeight();
      if (!fireHeightCheck.ok) {
        const userConfirmed = await showConfirmDialog(fireHeightCheck.warning);
        if (!userConfirmed) {
          return; // User chose to edit values
        }
      }

      btn.disabled = true;
      form.classList.add("loading");

      try {
        const payload = buildRequestPayload();

        const resp = await authFetch("/generate-single-dxf/?output_format=pdf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!resp.ok) throw new Error("PDF generation failed");

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);

        const suggestedName =
          (payload.metadata && payload.metadata.file_name) || "door_output.dxf";
        const pdfName = suggestedName.replace(/\.dxf$/i, ".pdf");

        const a = document.createElement("a");
        a.href = url;
        a.download = pdfName;
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();

        // Clean up after a short delay
        setTimeout(() => {
          a.remove();
          window.URL.revokeObjectURL(url);
        }, 100);

        showToast(`✅ PDF (${pdfName}) generated`, "success");
      } catch (err) {
        showToast("❌ " + err.message, "error");
      } finally {
        btn.disabled = false;
        form.classList.remove("loading");
      }
    })();
  } catch (e) {
    console.error("Error in top-level delegated PDF click handler", e);
  }
});

toggleOptions.forEach((option) => {
  option.addEventListener("click", () => {
    switchMode(option.dataset.value);
  });
});

// Show/hide fire options when subtype changes
if (subType) {
  subType.addEventListener("change", () => {
    if (subType.value === "fire") {
      fireOptionsContainer.classList.remove("hidden");
    } else {
      fireOptionsContainer.classList.add("hidden");
    }
  });
}

// Populate fire options depending on door type
function populateFireOptions(doorTypeValue = "single") {
  if (!fireOption) return;
  // clear existing
  fireOption.innerHTML = "";

  if (doorTypeValue === "double") {
    // double: only two options
    const opts = [
      {
        value: "standarddouble",
        label: "Standard Fire Door (Top 150 / Bottom 240 / L-R 190)",
      },
      {
        value: "fourglass",
        label: "Four Glass with Centre Aligned from Top and Bottom",
      },
    ];
    opts.forEach((o) => {
      const el = document.createElement("option");
      el.value = o.value;
      el.textContent = o.label;
      fireOption.appendChild(el);
    });
  } else {
    // single: three options (keep original labels)
    const opts = [
      {
        value: "standard",
        label: "Standard Fire Door (Top 170 / Bottom 240 / L-R 190)",
      },
      {
        value: "topfixed",
        label: "Top-Fixed Fire Door (Top 170 / Bottom Flexible / L-R 190)",
      },
      {
        value: "bottomfixed",
        label: "Bottom-Fixed Fire Door (Bottom 240 / Top Flexible / L-R 190)",
      },
    ];
    opts.forEach((o) => {
      const el = document.createElement("option");
      el.value = o.value;
      el.textContent = o.label;
      fireOption.appendChild(el);
    });
  }
}

// When doorType changes, repopulate fire options
if (doorType) {
  doorType.addEventListener("change", () => {
    populateFireOptions(doorType.value);
    // If subtype is fire, ensure container reflects any change
    if (subType && subType.value === "fire") {
      fireOptionsContainer.classList.remove("hidden");
    }
  });
}

// Show/hide allowance inputs based on defaultAllowance
if (defaultAllowance) {
  defaultAllowance.addEventListener("change", () => {
    if (defaultAllowance.value === "yes") {
      allowanceInputs.classList.add("hidden");
      horizontalAllowancesHeader.classList.add("hidden");
      verticalAllowancesHeader.classList.add("hidden");
      verticalAllowanceInputs.classList.add("hidden");
    } else {
      allowanceInputs.classList.remove("hidden");
      horizontalAllowancesHeader.classList.remove("hidden");
      verticalAllowancesHeader.classList.remove("hidden");
      verticalAllowanceInputs.classList.remove("hidden");
    }
  });
}

// Initialize visibility on load
document.addEventListener("DOMContentLoaded", () => {
  if (defaultAllowance && defaultAllowance.value === "yes") {
    allowanceInputs.classList.add("hidden");
    horizontalAllowancesHeader.classList.add("hidden");
    verticalAllowancesHeader.classList.add("hidden");
    verticalAllowanceInputs.classList.add("hidden");
  }
  // Fire options visibility
  if (subType && subType.value === "fire") {
    fireOptionsContainer.classList.remove("hidden");
  }
  // Populate fire options according to initial door type
  populateFireOptions(doorType ? doorType.value : "single");
  // Ensure preview controls visibility matches initial mode (in case toggle state
  // is set server-side or by persisted UI). Hide preview if bulk is active.
  const _previewBtn = document.getElementById("previewBtn");
  const _previewContainer = document.getElementById("previewContainer");
  const _pdfBtn = document.getElementById("generatePdfBtn");
  const activeToggle = document.querySelector(".toggle-option.active");
  const initialMode = activeToggle ? activeToggle.dataset.value : currentMode;
  if (initialMode === "bulk") {
    if (_previewBtn) _previewBtn.classList.add("hidden");
    if (_previewContainer) _previewContainer.classList.add("hidden");
    if (_pdfBtn) {
      _pdfBtn.classList.add("hidden");
      _pdfBtn.setAttribute("aria-hidden", "true");
    }
    document.body.classList.add("bulk-mode");
  } else {
    if (_previewBtn) _previewBtn.classList.remove("hidden");
    if (_previewContainer) _previewContainer.classList.remove("hidden");
    if (_pdfBtn) {
      _pdfBtn.classList.remove("hidden");
      _pdfBtn.setAttribute("aria-hidden", "false");
    }
    document.body.classList.remove("bulk-mode");
  }
});

toggleSwitch.addEventListener("touchstart", (e) => {
  touchStartX = e.changedTouches[0].screenX;
});

toggleSwitch.addEventListener("touchend", (e) => {
  touchEndX = e.changedTouches[0].screenX;
  handleSwipe();
});

function handleSwipe() {
  const swipeThreshold = 50;

  if (touchEndX < touchStartX - swipeThreshold) {
    switchMode("bulk");
  }

  if (touchEndX > touchStartX + swipeThreshold) {
    switchMode("single");
  }
}

setTogglePosition();
window.addEventListener("resize", setTogglePosition);

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // validate before doing any work
  if (currentMode === "single") {
    const v = validateInputs();
    if (!v.ok) {
      showToast("Please fix input errors: " + v.messages.join(" "), "error");
      // remove loading state if previously set
      form.classList.remove("loading");
      if (v.firstEl) v.firstEl.focus();
      return;
    }

    // Check fire door width validation
    const fireCheck = validateFireDoorWidth();
    if (!fireCheck.ok) {
      const userConfirmed = await showConfirmDialog(fireCheck.warning);
      if (!userConfirmed) {
        return; // User chose to edit values
      }
    }

    // Check hole offset height validation
    const holeCheck = validateHoleOffsetHeight();
    if (!holeCheck.ok) {
      const userAction = await showHoleOffsetDialog(holeCheck.warning);
      if (userAction === "edit") {
        return; // User chose to edit height
      } else if (userAction === "change") {
        // Change hole offset to 40x80
        const holeOffsetEl = document.getElementById("holeOffset");
        if (holeOffsetEl) holeOffsetEl.value = "40x80";
        showToast("Hole offset changed to 40×80", "success");
      }
    }

    // Check fire door height validation
    const fireHeightCheck = validateFireDoorHeight();
    if (!fireHeightCheck.ok) {
      const userConfirmed = await showConfirmDialog(fireHeightCheck.warning);
      if (!userConfirmed) {
        return; // User chose to edit values
      }
    }
  }

  form.classList.add("loading");

  if (currentMode === "single") {
    const data = {};
    // Collect inputs
    singleInputsDiv.querySelectorAll("input").forEach((input) => {
      data[input.name] = parseFloat(input.value);
    });
    // Collect selects
    if (doorType) data.door_type = doorType.value;
    if (subType) data.sub_type = subType.value;
    if (fireOption && !fireOptionsContainer.classList.contains("hidden"))
      data.fire_option = fireOption.value;
    if (holeOffset) data.hole_offset = holeOffset.value;
    if (defaultAllowance) data.default_allowance = defaultAllowance.value;

    Object.assign(data, {
      door_minus_measurement_width: 68,
      door_minus_measurement_height: 70,
      bending_width: 31,
      bending_height: 24,
      file_name: "Single_door.dxf",
    });

    // Backwards compatibility: map renamed vertical allowance fields
    // to the original backend keys so existing server code continues to work.
    if (data.top_side_allowance_height !== undefined) {
      data.left_side_allowance_height = data.top_side_allowance_height;
    }
    if (data.bottom_side_allowance_height !== undefined) {
      data.right_side_allowance_height = data.bottom_side_allowance_height;
    }

    try {
      const requestPayload = buildRequestPayload();

      const response = await authFetch("/generate-single-dxf/?output_format=dxf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });

      if (!response.ok) throw new Error("DXF generation failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const downloadName =
        (requestPayload.metadata && requestPayload.metadata.file_name) ||
        "door_output.dxf";

      const a = document.createElement("a");
      a.href = url;
      a.download = downloadName;
      document.body.appendChild(a);
      a.click();
      a.remove();

      showToast(
        `✅ DXF file (${downloadName}) generated successfully`,
        "success"
      );
    } catch (err) {
      showToast("❌ " + err.message, "error");
    } finally {
      form.classList.remove("loading");
    }
  } else if (currentMode === "bulk") {
    if (!excelInput.files.length) {
      showToast("⚠️ Please select an Excel file!", "error");
      form.classList.remove("loading");
      return;
    }

    const formData = new FormData();
    formData.append("file", excelInput.files[0]);
    // include selected sheet size (format: WIDTHxHEIGHT, e.g. "1250x2500")
    if (sheetSize && sheetSize.value) {
      formData.append("sheet_size", sheetSize.value);
    }
    // include annotation and pdf generation flags
    formData.append("annotation_required", "false");
    formData.append("pdf_required", "true");

    try {
      const response = await authFetch("/generate-dxf/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("DXF ZIP generation failed");

      // Try to extract filename from the response header
      const contentDisposition = response.headers.get("Content-Disposition");
      let zipFileName = "Doors.zip";

      if (contentDisposition && contentDisposition.includes("filename=")) {
        const match = contentDisposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) {
          zipFileName = match[1];
        }
      } else {
        // fallback: timestamp-based filename
        const timestamp = Date.now();
        zipFileName = `Doors_${timestamp}.zip`;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      // Trigger ZIP download
      const a = document.createElement("a");
      a.href = url;
      a.download = zipFileName;
      document.body.appendChild(a);
      a.click();
      a.remove();

      showToast(
        `✅ ZIP file (${zipFileName}) generated successfully`,
        "success"
      );
    } catch (err) {
      showToast("❌ " + err.message, "error");
    } finally {
      form.classList.remove("loading");
    }
  }
});
// Helper to build the same request payload used for generation
function buildRequestPayload() {
  const data = {};
  singleInputsDiv.querySelectorAll("input").forEach((input) => {
    data[input.name] = parseFloat(input.value);
  });
  if (doorType) data.door_type = doorType.value;
  if (subType) data.sub_type = subType.value;
  if (fireOption && !fireOptionsContainer.classList.contains("hidden"))
    data.fire_option = fireOption.value;
  if (holeOffset) data.hole_offset = holeOffset.value;
  if (defaultAllowance) data.default_allowance = defaultAllowance.value;

  Object.assign(data, {
    door_minus_measurement_width: 68,
    door_minus_measurement_height: 70,
    bending_width: 31,
    bending_height: 24,
    file_name: "Single_door.dxf",
  });

  // Map allowances back to backend keys if present
  if (data.top_side_allowance_height !== undefined) {
    data.left_side_allowance_height = data.top_side_allowance_height;
  }
  if (data.bottom_side_allowance_height !== undefined) {
    data.right_side_allowance_height = data.bottom_side_allowance_height;
  }

  function toNumberOrDefault(value, defaultVal) {
    const n = Number(value);
    return Number.isFinite(n) ? n : defaultVal;
  }

  const allowanceDefault =
    defaultAllowance && defaultAllowance.value === "yes" ? 25 : 0;

  // Extract width & height for filename and other metadata
  const width = toNumberOrDefault(data.width_measurement, 0);
  const height = toNumberOrDefault(data.height_measurement, 0);
  // Determine door type and subtype safely
  const category = doorType?.value === "double" ? "Double" : "Single";
  const subtype = subType?.value || "Normal";

  // Sanitize values for safe filenames
  const safe = (value) => String(value).replace(/[^a-zA-Z0-9_.-]/g, "_");
  const safeWidth = safe(width).replace(/\./g, "_");
  const safeHeight = safe(height).replace(/\./g, "_");
  const safeCategory = safe(category);
  const safeSubtype = safe(subtype);

  // Generate formatted timestamp
  const formattedTimestamp = getFormattedTimestamp();

  // Build dynamic filename
  const dynamicFileName = `${safeCategory}_${safeSubtype}_${safeWidth}x${safeHeight}_${formattedTimestamp}.dxf`;

  const requestPayload = {
    mode: "generate",
    door: {
      category: doorType
        ? doorType.value === "double"
          ? "Double"
          : "Single"
        : "Single",
      type: subType ? subType.value || "Normal" : "Normal",
      option:
        fireOption && !fireOptionsContainer.classList.contains("hidden")
          ? fireOption.value || null
          : null,
      hole_offset: holeOffset ? holeOffset.value : "",
      default_allowance: defaultAllowance ? defaultAllowance.value : "yes",
    },
    dimensions: {
      width_measurement: toNumberOrDefault(data.width_measurement, 0),
      height_measurement: toNumberOrDefault(data.height_measurement, 0),
      left_side_allowance_width: toNumberOrDefault(
        data.left_side_allowance_width,
        allowanceDefault
      ),
      right_side_allowance_width: toNumberOrDefault(
        data.right_side_allowance_width,
        allowanceDefault
      ),
      top_side_allowance_height: toNumberOrDefault(
        data.top_side_allowance_height,
        allowanceDefault
      ),
      bottom_side_allowance_height: toNumberOrDefault(
        data.bottom_side_allowance_height,
        allowanceDefault
      ),
    },
    metadata: {
      label: dynamicFileName.replace(/\.dxf$/i, ""),
      file_name: dynamicFileName,
      width: 0,
      height: 0,
      rotated: false,
      is_annotation_required: true,
      offset: [0.0, 0.0],
    },
    defaults: {
      door_minus_measurement_width:
        Number(data.door_minus_measurement_width) || 68,
      door_minus_measurement_height:
        Number(data.door_minus_measurement_height) || 70,
      bending_width: Number(data.bending_width) || 31,
      bending_height: Number(data.bending_height) || 24,
    },
  };

  return requestPayload;
}

// Generate PDF: handled via top-level delegated listener only.
// The delegated `document.addEventListener('click', ...)` further down in
// this file is the single source of truth for PDF generation. Keeping only
// the delegated handler avoids duplicate logic and ensures the handler
// attaches early even when direct element event attachment fails.

// Preview button behaviour
const previewBtn = document.getElementById("previewBtn");
const previewBox = document.getElementById("previewBox");
const previewContainer = document.getElementById("previewContainer");
if (previewBtn) {
  previewBtn.addEventListener("click", async () => {
    // Only allow preview in single mode
    if (currentMode !== "single") {
      showToast("Preview is only available in Single mode", "error");
      return;
    }

    // validate before preview
    const v = validateInputs();
    if (!v.ok) {
      showToast("Please fix input errors: " + v.messages.join(" "), "error");
      if (v.firstEl) v.firstEl.focus();
      return;
    }

    // Check fire door width validation
    const fireCheck = validateFireDoorWidth();
    if (!fireCheck.ok) {
      const userConfirmed = await showConfirmDialog(fireCheck.warning);
      if (!userConfirmed) {
        return; // User chose to edit values
      }
    }

    // Check hole offset height validation
    const holeCheck = validateHoleOffsetHeight();
    if (!holeCheck.ok) {
      const userAction = await showHoleOffsetDialog(holeCheck.warning);
      if (userAction === "edit") {
        return; // User chose to edit height
      } else if (userAction === "change") {
        // Change hole offset to 40x80
        const holeOffsetEl = document.getElementById("holeOffset");
        if (holeOffsetEl) holeOffsetEl.value = "40x80";
        showToast("Hole offset changed to 40×80", "success");
      }
    }

    // Check fire door height validation
    const fireHeightCheck = validateFireDoorHeight();
    if (!fireHeightCheck.ok) {
      const userConfirmed = await showConfirmDialog(fireHeightCheck.warning);
      if (!userConfirmed) {
        return; // User chose to edit values
      }
    }

    const payload = buildRequestPayload();
    previewBox.classList.remove("hidden");
    previewBox.textContent = "Loading...";

    try {
      const resp = await authFetch("/dxf/geometry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) throw new Error("Preview request failed");

      const json = await resp.json();
      previewBox.textContent = JSON.stringify(json, null, 2);
    } catch (err) {
      previewBox.textContent = "Error: " + err.message;
    }
  });
}

// drawGeometryToSVG removed and replaced by Fabric implementation above

function showToast(msg, type = "success") {
  const toast = document.createElement("div");
  toast.textContent = msg;
  const bg = type === "success" ? "#16a34a" : "#dc2626";
  toast.style.cssText = `
    position: fixed; bottom: 30px; right: 20px;
    background: ${bg};
    color: white; padding: 10px 16px; border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3); z-index: 9999;
    animation: fadeInOut 3s forwards;
  `;
  toast.setAttribute("role", "alert");
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// Show confirmation dialog and return promise that resolves to true/false
function showConfirmDialog(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5); z-index: 10000;
      display: flex; align-items: center; justify-content: center;
    `;

    const dialog = document.createElement("div");
    dialog.style.cssText = `
      background: white; padding: 24px; border-radius: 12px;
      max-width: 500px; margin: 20px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    `;

    const messageEl = document.createElement("pre");
    messageEl.textContent = message;
    messageEl.style.cssText = `
      margin: 0 0 20px 0; white-space: pre-wrap;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px; line-height: 1.6; color: #333;
    `;

    const btnContainer = document.createElement("div");
    btnContainer.style.cssText = `
      display: flex; gap: 12px; justify-content: flex-end;
    `;

    const btnCancel = document.createElement("button");
    btnCancel.textContent = "Edit Values";
    btnCancel.style.cssText = `
      padding: 10px 20px; border: 1px solid #ccc;
      background: white; border-radius: 6px; cursor: pointer;
      font-size: 14px; font-weight: 500;
    `;
    btnCancel.onclick = () => {
      overlay.remove();
      resolve(false);
    };

    const btnConfirm = document.createElement("button");
    btnConfirm.textContent = "Continue Drawing";
    btnConfirm.style.cssText = `
      padding: 10px 20px; border: none;
      background: #dc2626; color: white; border-radius: 6px;
      cursor: pointer; font-size: 14px; font-weight: 500;
    `;
    btnConfirm.onclick = () => {
      overlay.remove();
      resolve(true);
    };

    btnContainer.appendChild(btnCancel);
    btnContainer.appendChild(btnConfirm);
    dialog.appendChild(messageEl);
    dialog.appendChild(btnContainer);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
  });
}

// Show hole offset change dialog - returns 'change' to change offset, 'edit' to edit values, 'continue' to proceed
function showHoleOffsetDialog(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5); z-index: 10000;
      display: flex; align-items: center; justify-content: center;
    `;

    const dialog = document.createElement("div");
    dialog.style.cssText = `
      background: white; padding: 24px; border-radius: 12px;
      max-width: 500px; margin: 20px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    `;

    const messageEl = document.createElement("pre");
    messageEl.textContent = message;
    messageEl.style.cssText = `
      margin: 0 0 20px 0; white-space: pre-wrap;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px; line-height: 1.6; color: #333;
    `;

    const btnContainer = document.createElement("div");
    btnContainer.style.cssText = `
      display: flex; gap: 12px; justify-content: flex-end;
    `;

    const btnEdit = document.createElement("button");
    btnEdit.textContent = "Edit Height";
    btnEdit.style.cssText = `
      padding: 10px 20px; border: 1px solid #ccc;
      background: white; border-radius: 6px; cursor: pointer;
      font-size: 14px; font-weight: 500;
    `;
    btnEdit.onclick = () => {
      overlay.remove();
      resolve("edit");
    };

    const btnChange = document.createElement("button");
    btnChange.textContent = "Change to 40×80";
    btnChange.style.cssText = `
      padding: 10px 20px; border: none;
      background: #16a34a; color: white; border-radius: 6px;
      cursor: pointer; font-size: 14px; font-weight: 500;
    `;
    btnChange.onclick = () => {
      overlay.remove();
      resolve("change");
    };

    btnContainer.appendChild(btnEdit);
    btnContainer.appendChild(btnChange);
    dialog.appendChild(messageEl);
    dialog.appendChild(btnContainer);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
  });
}

document.querySelector("h2").addEventListener("click", () => {
  showToast("Developed by Jinesh 🧠", "success");
});

// Formats current date and time as ddmmyy_hhmmss
function getFormattedTimestamp() {
  const now = new Date();

  const pad = (n) => String(n).padStart(2, "0");

  const dd = pad(now.getDate());
  const mm = pad(now.getMonth() + 1);
  const yy = String(now.getFullYear()).slice(-2);
  const hh = pad(now.getHours());
  const mi = pad(now.getMinutes());
  const ss = pad(now.getSeconds());

  return `${dd}${mm}${yy}_${hh}${mi}${ss}`;
}
