// Extracted JS from index.html
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
      } else if (v < MIN_ALLOW || v > MAX_ALLOW) {
        msgs.push(
          `${name.replace(
            /_/g,
            " "
          )} must be between ${MIN_ALLOW} and ${MAX_ALLOW} mm.`
        );
        firstEl = firstEl || el;
        markInvalid(el);
      }
    }
  }

  return { ok: msgs.length === 0, messages: msgs, firstEl };
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

      btn.disabled = true;
      form.classList.add("loading");

      try {
        const payload = buildRequestPayload();

        const resp = await fetch("/generate-single-dxf/?save_pdf=true", {
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
        document.body.appendChild(a);
        try {
          a.click();
        } catch (e) {
          console.warn(
            "Programmatic download failed, will fallback to opening in new tab",
            e
          );
        }
        a.remove();

        try {
          const ua = navigator.userAgent || "";
          const isChrome =
            ua.includes("Chrome") && !ua.includes("Edg") && !ua.includes("OPR");
          if (isChrome && blob && blob.type === "application/pdf") {
            setTimeout(() => {
              try {
                window.open(url, "_blank");
              } catch (e) {
                console.warn("Failed to open PDF in new tab as fallback", e);
              }
            }, 700);
          }
        } catch (e) {
          /* ignore UA/open errors */
        }

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

      const response = await fetch("/generate-single-dxf/", {
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

    try {
      const response = await fetch("/generate-dxf/", {
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

    const payload = buildRequestPayload();
    previewBox.classList.remove("hidden");
    previewBox.textContent = "Loading...";

    try {
      const resp = await fetch("/dxf/geometry", {
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
