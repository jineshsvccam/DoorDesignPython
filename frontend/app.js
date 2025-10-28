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

let currentMode = "single";
let touchStartX = 0;
let touchEndX = 0;

// Validation rules
const MIN_DIM = 200;
const MAX_DIM = 2000;
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
  if (mode === "bulk") {
    // hide both the Preview button and the preview container in bulk mode
    if (previewBtnEl) previewBtnEl.classList.add("hidden");
    if (previewContainerEl) previewContainerEl.classList.add("hidden");
  } else {
    if (previewBtnEl) previewBtnEl.classList.remove("hidden");
    if (previewContainerEl) previewContainerEl.classList.remove("hidden");
  }
}

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
  const activeToggle = document.querySelector(".toggle-option.active");
  const initialMode = activeToggle ? activeToggle.dataset.value : currentMode;
  if (initialMode === "bulk") {
    if (_previewBtn) _previewBtn.classList.add("hidden");
    if (_previewContainer) _previewContainer.classList.add("hidden");
    document.body.classList.add("bulk-mode");
  } else {
    if (_previewBtn) _previewBtn.classList.remove("hidden");
    if (_previewContainer) _previewContainer.classList.remove("hidden");
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
      // Build request payload matching the DoorDXFRequest schema expected by the server
      // safe numeric parse helper: preserves explicit 0, rejects NaN
      function toNumberOrDefault(value, defaultVal) {
        const n = Number(value);
        return Number.isFinite(n) ? n : defaultVal;
      }

      const allowanceDefault =
        defaultAllowance && defaultAllowance.value === "yes" ? 25 : 0;

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
          label: data.file_name
            ? data.file_name.replace(/\.dxf$/i, "")
            : "Single",
          file_name: data.file_name || "Single_door.dxf",
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

      const response = await fetch("/generate-single-dxf/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });

      if (!response.ok) throw new Error("DXF generation failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Single_door.dxf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast("✅ DXF file generated successfully", "success");
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

    try {
      const response = await fetch("/generate-dxf/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("DXF ZIP generation failed");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Doors.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast("✅ ZIP generated successfully", "success");
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
      label: data.file_name ? data.file_name.replace(/\.dxf$/i, "") : "Single",
      file_name: data.file_name || "Single_door.dxf",
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
      // draw into Fabric preview (replaces SVG) - pass full response so
      // the drawing code can use metadata (width/height) to size the canvas.
      try {
        await drawGeometryToFabric(json);
      } catch (err) {
        console.error("Fabric draw error", err);
      }
    } catch (err) {
      previewBox.textContent = "Error: " + err.message;
    }
  });
}

// ----------------------
// Fabric.js preview code
// ----------------------

// Small helper to load Fabric.js dynamically if not already present
function ensureFabric() {
  return new Promise((resolve, reject) => {
    if (window.fabric) return resolve(window.fabric);
    const existing = document.querySelector('script[data-fabric-cdn="true"]');
    if (existing) {
      existing.addEventListener("load", () => resolve(window.fabric));
      existing.addEventListener("error", () =>
        reject(new Error("Fabric load error"))
      );
      return;
    }
    const s = document.createElement("script");
    s.src =
      "https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.0/fabric.min.js";
    s.async = true;
    s.setAttribute("data-fabric-cdn", "true");
    s.onload = () => resolve(window.fabric);
    s.onerror = () => reject(new Error("Fabric failed to load"));
    document.head.appendChild(s);
  });
}

/**
 * Draw geometry into a Fabric canvas.
 * - If #fabricCanvas exists, it uses that. If not, it will attempt to replace
 *   an existing #svgPreview or insert into #svgPreviewWrapper.
 */
async function drawGeometryToFabric(responseOrGeometry) {
  await ensureFabric();

  console.debug("drawGeometryToFabric: fabric available?", !!window.fabric);

  // Accept either the full response (which contains .geometry and .metadata)
  // or the raw geometry object. Normalize here.
  // find or create canvas element
  let canvasEl = document.getElementById("fabricCanvas");
  let geometry =
    responseOrGeometry && responseOrGeometry.geometry
      ? responseOrGeometry.geometry
      : responseOrGeometry;
  let metadata =
    responseOrGeometry && responseOrGeometry.metadata
      ? responseOrGeometry.metadata
      : null;
  // if metadata not supplied, try to find in geometry (some endpoints may embed it there)
  if (!metadata && geometry && geometry.metadata) metadata = geometry.metadata;
  // compute metadata-derived size up-front so we can apply it even when a
  // canvas already exists (prevents stale sizes when previewing multiple
  // different doors without refreshing the page).
  const metaW =
    metadata && Number.isFinite(Number(metadata.width))
      ? Number(metadata.width)
      : 1000;
  const metaH =
    metadata && Number.isFinite(Number(metadata.height))
      ? Number(metadata.height)
      : 700;

  if (!canvasEl) {
    // prefer a wrapper if present
    const wrapper =
      document.getElementById("svgPreviewWrapper") ||
      document.getElementById("previewContainer");
    if (wrapper) {
      // remove any old SVG preview if present
      const oldSvg = document.getElementById("svgPreview");
      if (oldSvg) oldSvg.remove();
      canvasEl = document.createElement("canvas");
      canvasEl.id = "fabricCanvas";
      // set canvas size based on metadata (use mm as px 1:1). Add 20 pts extra for labels.
      canvasEl.width = Math.max(100, Math.round(metaW + 20));
      canvasEl.height = Math.max(100, Math.round(metaH + 20));
      // insert at end of wrapper
      wrapper.appendChild(canvasEl);
      // Ensure the canvas visually fits the wrapper while keeping the
      // high-resolution internal buffer. Compute a display size that
      // preserves aspect ratio and does not overflow the wrapper.
      try {
        // compute wrapper-constrained display size and apply mobile caps so the
        // preview remains compact on small screens. Preserve aspect ratio.
        const maxViewportW = Math.max(160, window.innerWidth - 40);
        const maxViewportH = Math.max(160, window.innerHeight - 120);
        const wrapperW =
          wrapper.clientWidth || Math.min(maxViewportW, canvasEl.width);
        const wrapperH =
          wrapper.clientHeight || Math.min(maxViewportH, canvasEl.height);
        let displayW = Math.min(canvasEl.width, wrapperW);
        let displayH = Math.round(
          (canvasEl.height * displayW) / canvasEl.width
        );
        // mobile: cap height to a fraction of viewport so it doesn't dominate screen
        if (window.innerWidth <= 600) {
          const mobileMaxH = Math.round(window.innerHeight * 0.6);
          displayH = Math.min(displayH, mobileMaxH);
          displayW = Math.min(displayW, window.innerWidth - 24);
        }
        canvasEl.style.width = displayW + "px";
        canvasEl.style.height =
          Math.max(80, Math.min(displayH, wrapperH)) + "px";
        canvasEl.style.maxWidth = "100%";
      } catch (e) {
        /* ignore display sizing errors */
      }
    } else {
      console.warn("No container available for Fabric canvas");
      return;
    }
  } else {
    // If the canvas element already exists, update its natural size based on
    // the new metadata so subsequent Fabric initialization uses the correct
    // buffer size. Also update the CSS display sizing to fit the wrapper.
    try {
      canvasEl.width = Math.max(100, Math.round(metaW + 20));
      canvasEl.height = Math.max(100, Math.round(metaH + 20));
      const wrapper =
        document.getElementById("svgPreviewWrapper") ||
        document.getElementById("previewContainer");
      if (wrapper && canvasEl) {
        const maxViewportW = Math.max(160, window.innerWidth - 40);
        const maxViewportH = Math.max(160, window.innerHeight - 120);
        const wrapperW =
          wrapper.clientWidth || Math.min(maxViewportW, canvasEl.width);
        const wrapperH =
          wrapper.clientHeight || Math.min(maxViewportH, canvasEl.height);
        let displayW = Math.min(canvasEl.width, wrapperW);
        let displayH = Math.round(
          (canvasEl.height * displayW) / canvasEl.width
        );
        if (window.innerWidth <= 600) {
          const mobileMaxH = Math.round(window.innerHeight * 0.6);
          displayH = Math.min(displayH, mobileMaxH);
          displayW = Math.min(displayW, window.innerWidth - 24);
        }
        canvasEl.style.width = displayW + "px";
        canvasEl.style.height =
          Math.max(80, Math.min(displayH, wrapperH)) + "px";
        canvasEl.style.maxWidth = "100%";
      }
    } catch (e) {
      /* ignore sizing errors */
    }
  }

  // Initialize or reset Fabric canvas
  // Ensure we always have a fresh Fabric canvas instance. If an existing
  // instance is present, dispose it cleanly to avoid stale event handlers
  // or internal state that can prevent rendering.
  if (window.fabricCanvas) {
    try {
      if (typeof window.fabricCanvas.dispose === "function") {
        window.fabricCanvas.dispose();
      }
    } catch (e) {
      console.warn("Error disposing existing fabricCanvas:", e);
    }
    window.fabricCanvas = null;
  }

  try {
    // Create a new fabric.Canvas and size it to the element's natural size.
    window.fabricCanvas = new fabric.Canvas("fabricCanvas", {
      backgroundColor: "#f8f9fb",
      selection: false,
      renderOnAddRemove: true,
    });
    // Set canvas dimensions to match the element (use client size if available)
    try {
      const w = canvasEl.width || canvasEl.clientWidth || 1000;
      const h = canvasEl.height || canvasEl.clientHeight || 700;
      window.fabricCanvas.setWidth(w);
      window.fabricCanvas.setHeight(h);
    } catch (e) {
      /* ignore sizing errors */
    }
    // Also ensure the canvas CSS display size fits the preview wrapper
    try {
      const wrapperEl =
        document.getElementById("svgPreviewWrapper") ||
        document.getElementById("previewContainer");
      if (wrapperEl && canvasEl) {
        const wrapperW =
          wrapperEl.clientWidth ||
          Math.min(window.innerWidth - 40, canvasEl.width);
        const wrapperH =
          wrapperEl.clientHeight ||
          Math.min(window.innerHeight - 120, canvasEl.height);
        const displayW = Math.min(canvasEl.width, wrapperW);
        const displayH = Math.round(
          (canvasEl.height * displayW) / canvasEl.width
        );
        canvasEl.style.width = displayW + "px";
        canvasEl.style.height =
          Math.max(100, Math.min(displayH, wrapperH)) + "px";
      }
    } catch (e) {
      /* ignore */
    }
  } catch (err) {
    console.error("Failed to create fabric.Canvas:", err);
    // rethrow so callers (preview flow) can handle it
    throw err;
  }
  const canvas = window.fabricCanvas;

  // Normalize canvas size using the Fabric canvas's dimensions. Using the
  // Fabric instance avoids mismatches when the element is CSS-scaled or when
  // Fabric has adjusted its internal size. Fall back to element natural size.
  const canvasWidth =
    (canvas && typeof canvas.getWidth === "function" && canvas.getWidth()) ||
    canvasEl.width ||
    1000;
  const canvasHeight =
    (canvas && typeof canvas.getHeight === "function" && canvas.getHeight()) ||
    canvasEl.height ||
    700;

  // collect all points to compute bounds
  const points = [];
  (geometry.frames || []).forEach((f) =>
    f.points.forEach((p) => points.push(p))
  );
  (geometry.cutouts || []).forEach((c) =>
    c.points.forEach((p) => points.push(p))
  );
  (geometry.holes || []).forEach((h) => points.push(h.center));

  if (points.length === 0) {
    // blank placeholder
    const rect = new fabric.Rect({
      left: 50,
      top: 50,
      width: canvasWidth - 100,
      height: canvasHeight - 100,
      fill: "",
      stroke: "#ccc",
      strokeWidth: 1,
      selectable: false,
    });
    canvas.add(rect);
    canvas.renderAll();
    return;
  }

  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs);
  const minY = Math.min(...ys),
    maxY = Math.max(...ys);

  const vbW = Math.max(1, maxX - minX);
  const vbH = Math.max(1, maxY - minY);

  // keep padding so dims/labels are visible
  const padding = 40;
  const usableW = canvasWidth - padding * 2;
  const usableH = canvasHeight - padding * 2;
  const scale = Math.min(usableW / vbW, usableH / vbH);

  const offsetX = padding - minX * scale;
  const offsetY = padding - minY * scale;

  // CAD Y-up to Canvas Y-down: canvasY = canvasHeight - (y*scale + offsetY)
  const toCanvasX = (x) => x * scale + offsetX;
  const toCanvasY = (y) => canvasHeight - (y * scale + offsetY);

  // helper to create closed polygon path string (Fabric Path expects SVG path)
  function polygonPathFromPoints(pointsArray) {
    if (!pointsArray.length) return "";
    return (
      pointsArray
        .map(
          (p, i) =>
            `${i === 0 ? "M" : "L"} ${toCanvasX(p[0])} ${toCanvasY(p[1])}`
        )
        .join(" ") + " Z"
    );
  }

  // Draw frames
  (geometry.frames || []).forEach((f) => {
    const pathStr = polygonPathFromPoints(f.points);
    if (!pathStr) return;
    const p = new fabric.Path(pathStr, {
      fill: "",
      stroke: "#0b6394",
      strokeWidth: Math.max(1, 2),
      selectable: false,
      evented: false,
    });
    canvas.add(p);
  });

  // Draw cutouts
  (geometry.cutouts || []).forEach((c) => {
    const pathStr = polygonPathFromPoints(c.points);
    if (!pathStr) return;
    const p = new fabric.Path(pathStr, {
      fill: "#ffffff",
      stroke: "#e85",
      strokeWidth: Math.max(0.8, 1.2),
      selectable: false,
      evented: false,
    });
    canvas.add(p);
  });

  // Draw holes
  (geometry.holes || []).forEach((h) => {
    const cx = toCanvasX(h.center[0]);
    const cy = toCanvasY(h.center[1]);
    const r = Math.max(1, h.radius * scale);
    const c = new fabric.Circle({
      left: cx,
      top: cy,
      radius: r,
      originX: "center",
      originY: "center",
      fill: "#333",
      selectable: false,
      evented: false,
    });
    canvas.add(c);
  });

  // Labels (center_label)
  (geometry.labels || []).forEach((l) => {
    if (l.type === "center_label" && l.position === "center") {
      const txt = new fabric.Text(l.text, {
        left: canvasWidth / 2,
        top: canvasHeight / 2 - 10,
        originX: "center",
        originY: "center",
        // Choose a font size that scales with our computed drawing scale but
        // keep a sensible minimum for small screens so annotations remain legible.
        fontSize: Math.max(10, Math.round(14 * (scale / 4 + 0.5))),
        fill: "#222",
        selectable: false,
        evented: false,
      });
      canvas.add(txt);
    }
  });

  // === draw width/height dimensions for first two frames (replicates previous behaviour) ===
  function drawDimLineFabric(x1, y1, x2, y2, label, opts = {}) {
    const { tick = 6, textSize = 12, color = "#c0392b" } = opts;
    // main line
    const line = new fabric.Line([x1, y1, x2, y2], {
      stroke: color,
      strokeWidth: 1.2,
      selectable: false,
      evented: false,
    });
    canvas.add(line);

    // ticks
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len = Math.hypot(dx, dy) || 1;
    let px = (-dy / len) * tick;
    let py = (dx / len) * tick;

    const midx = (x1 + x2) / 2;
    const midy = (y1 + y2) / 2;
    const dirSign =
      (midx - canvasWidth / 2) * px + (midy - canvasHeight / 2) * py >= 0
        ? 1
        : -1;
    px *= dirSign;
    py *= dirSign;

    const t1 = new fabric.Line([x1, y1, x1 + px, y1 + py], {
      stroke: color,
      strokeWidth: 1.2,
      selectable: false,
      evented: false,
    });
    const t2 = new fabric.Line([x2, y2, x2 + px, y2 + py], {
      stroke: color,
      strokeWidth: 1.2,
      selectable: false,
      evented: false,
    });
    canvas.add(t1);
    canvas.add(t2);

    // endpoint markers
    const m1 = new fabric.Circle({
      left: x1,
      top: y1,
      radius: 2.2,
      fill: color,
      originX: "center",
      originY: "center",
      selectable: false,
      evented: false,
    });
    const m2 = new fabric.Circle({
      left: x2,
      top: y2,
      radius: 2.2,
      fill: color,
      originX: "center",
      originY: "center",
      selectable: false,
      evented: false,
    });
    canvas.add(m1);
    canvas.add(m2);

    // label background rect + text
    const labelX = midx + px * 2.5;
    const labelY = midy + py * 2.5;
    const txt = new fabric.Text(label, {
      left: labelX,
      top: labelY,
      originX: "center",
      originY: "center",
      fontSize: textSize,
      fill: "#000",
      selectable: false,
      evented: false,
    });
    // approximate width
    const approxWidth = Math.max(40, label.length * (textSize * 0.6));
    const rect = new fabric.Rect({
      left: labelX - approxWidth / 2 - 6,
      top: labelY - textSize / 1.6 - 4,
      width: approxWidth + 12,
      height: textSize * 1.6 + 6,
      fill: "#fff",
      stroke: "#ddd",
      rx: 3,
      ry: 3,
      originX: "left",
      originY: "top",
      selectable: false,
      evented: false,
    });
    // rectify rect position because we used center coords for txt
    rect.left = rect.left;
    rect.top = rect.top;
    canvas.add(rect);
    canvas.add(txt);
  }

  const fs = geometry.frames || [];
  if (fs.length >= 1) {
    const f = fs[0];
    const xsF = f.points.map((p) => p[0]);
    const ysF = f.points.map((p) => p[1]);
    const minXF = Math.min(...xsF),
      maxXF = Math.max(...xsF);
    const minYF = Math.min(...ysF),
      maxYF = Math.max(...ysF);
    // compute a dynamic offset for dimension lines so labels remain inside
    // the canvas on small screens; clamp to reasonable min/max values.
    const defaultDim = 40;
    const dimOffset = Math.min(
      defaultDim,
      Math.max(12, Math.round(canvasWidth * 0.06))
    );
    // bottom dimension (width)
    const bx1 = toCanvasX(minXF);
    const by = toCanvasY(maxYF) + dimOffset;
    const bx2 = toCanvasX(maxXF);
    const widthVal = Math.round(maxXF - minXF);
    drawDimLineFabric(bx1, by, bx2, by, `${widthVal} mm`, { tick: 6 });
    // right dimension (height)
    const rx = toCanvasX(maxXF) + dimOffset;
    const ry1 = toCanvasY(minYF);
    const ry2 = toCanvasY(maxYF);
    const heightVal = Math.round(maxYF - minYF);
    drawDimLineFabric(rx, ry1, rx, ry2, `${heightVal} mm`, { tick: 6 });
  }

  if (fs.length >= 2) {
    const f = fs[1];
    const xs2 = f.points.map((p) => p[0]);
    const ys2 = f.points.map((p) => p[1]);
    const minX2 = Math.min(...xs2),
      maxX2 = Math.max(...xs2);
    const minY2 = Math.min(...ys2),
      maxY2 = Math.max(...ys2);
    // dynamic dim offset for second frame as well
    const defaultDim2 = 40;
    const dimOffset = Math.min(
      defaultDim2,
      Math.max(12, Math.round(canvasWidth * 0.06))
    );
    // top dimension (width) - above the box
    const tx1 = toCanvasX(minX2);
    let ty = toCanvasY(minY2) - dimOffset;
    const tx2 = toCanvasX(maxX2);
    const widthVal = Math.round(maxX2 - minX2);
    drawDimLineFabric(tx1, ty, tx2, ty, `${widthVal} mm`, { tick: 6 });
    // left dimension (height)
    let lx = toCanvasX(minX2) - dimOffset;
    const ly1 = toCanvasY(minY2);
    const ly2 = toCanvasY(maxY2);
    const heightVal = Math.round(maxY2 - minY2);
    // clamp vertical dimension lines to remain within canvas bounds
    const edgePad = 6;
    if (lx < edgePad) lx = edgePad;
    if (ty < edgePad) ty = edgePad;
    drawDimLineFabric(tx1, ty, tx2, ty, `${widthVal} mm`, { tick: 6 });
    drawDimLineFabric(lx, ly1, lx, ly2, `${heightVal} mm`, { tick: 6 });
  }

  // Zoom & Pan handlers (mouse wheel and ALT + drag for panning)
  canvas.off && canvas.off("mouse:wheel"); // remove previous handlers (if any)
  canvas.on("mouse:wheel", function (opt) {
    let delta = opt.e.deltaY;
    let zoom = canvas.getZoom();
    zoom *= 0.999 ** delta;
    if (zoom > 4) zoom = 4;
    if (zoom < 0.2) zoom = 0.2;
    canvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
    opt.e.preventDefault();
    opt.e.stopPropagation();
  });

  // panning
  let panning = false;
  canvas.off && canvas.off("mouse:down");
  canvas.off && canvas.off("mouse:move");
  canvas.off && canvas.off("mouse:up");

  canvas.on("mouse:down", (opt) => {
    if (opt.e.altKey) panning = true;
  });
  canvas.on("mouse:move", (opt) => {
    if (panning) {
      const e = opt.e;
      const vpt = canvas.viewportTransform;
      vpt[4] += e.movementX;
      vpt[5] += e.movementY;
      canvas.requestRenderAll();
    }
  });
  canvas.on("mouse:up", () => (panning = false));

  canvas.requestRenderAll();
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
