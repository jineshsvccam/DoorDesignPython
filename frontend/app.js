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
        value: "standard",
        label: "Standard Fire Door (Top 150 / Bottom 240 / L-R 190)",
      },
      {
        value: "fourglass",
        label: "Four glass with centre aligned from top and bottom",
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
      // draw into SVG preview
      try {
        drawGeometryToSVG(json.geometry);
      } catch (err) {
        console.error("SVG draw error", err);
      }
    } catch (err) {
      previewBox.textContent = "Error: " + err.message;
    }
  });
}

// Render geometry object into svg#svgPreview
function drawGeometryToSVG(geometry) {
  const svg = document.getElementById("svgPreview");
  if (!svg) return;
  // clear
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  // find bounding box of all points to scale to viewBox
  const points = [];
  (geometry.frames || []).forEach((f) =>
    f.points.forEach((p) => points.push(p))
  );
  (geometry.cutouts || []).forEach((c) =>
    c.points.forEach((p) => points.push(p))
  );
  (geometry.holes || []).forEach((h) => points.push(h.center));

  // default view if nothing
  if (points.length === 0) {
    // draw placeholder
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", 100);
    rect.setAttribute("y", 100);
    rect.setAttribute("width", 800);
    rect.setAttribute("height", 800);
    rect.setAttribute("fill", "none");
    rect.setAttribute("stroke", "#ccc");
    svg.appendChild(rect);
    return;
  }

  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs);
  const minY = Math.min(...ys),
    maxY = Math.max(...ys);

  const padding = 20; // px inside viewBox
  const vbW = Math.max(1, maxX - minX);
  const vbH = Math.max(1, maxY - minY);

  // compute scale to fit into 1000x1000 minus padding
  const targetW = 1000 - padding * 2;
  const targetH = 1000 - padding * 2;
  const scale = Math.min(targetW / vbW, targetH / vbH);

  const offsetX = (1000 - vbW * scale) / 2 - minX * scale;
  // For SVG we flip Y (SVG y increases downward). Map CAD y-up to SVG y-down so
  // CAD maxY maps to top padding and CAD minY maps to bottom padding.
  const paddingY = (1000 - vbH * scale) / 2;

  function toSvgX(x) {
    return x * scale + offsetX;
  }

  function toSvgY(y) {
    // flip Y: place maxY at top padding, minY at bottom padding
    return paddingY + (maxY - y) * scale;
  }

  // helper to create svg elements
  function create(name, attrs) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  }

  // draw frames (outer rectangle etc.)
  (geometry.frames || []).forEach((f) => {
    const path =
      f.points
        .map(
          (p, i) =>
            `${i === 0 ? "M" : "L"} ${toSvgX(p[0]).toFixed(2)} ${toSvgY(
              p[1]
            ).toFixed(2)}`
        )
        .join(" ") + " Z";
    const el = create("path", {
      d: path,
      fill: "none",
      stroke: "#0b6394",
      "stroke-width": 2,
    });
    svg.appendChild(el);
  });

  // draw cutouts
  (geometry.cutouts || []).forEach((c) => {
    const path =
      c.points
        .map(
          (p, i) =>
            `${i === 0 ? "M" : "L"} ${toSvgX(p[0]).toFixed(2)} ${toSvgY(
              p[1]
            ).toFixed(2)}`
        )
        .join(" ") + " Z";
    const el = create("path", {
      d: path,
      fill: "#ffffff",
      stroke: "#e85",
      "stroke-width": 1.5,
    });
    svg.appendChild(el);
  });

  // draw holes
  (geometry.holes || []).forEach((h) => {
    const cx = toSvgX(h.center[0]);
    const cy = toSvgY(h.center[1]);
    const r = Math.max(1, h.radius * scale);
    const circle = create("circle", { cx: cx, cy: cy, r: r, fill: "#333" });
    svg.appendChild(circle);
  });

  // center label if provided
  (geometry.labels || []).forEach((l) => {
    if (l.type === "center_label" && l.position === "center") {
      const txt = create("text", {
        x: 500,
        y: 500,
        "text-anchor": "middle",
        "dominant-baseline": "middle",
        fill: "#222",
        "font-size": 14,
      });
      txt.textContent = l.text;
      svg.appendChild(txt);
    }
  });
}
// draw width/height dimensions for first two frames
function drawDimLine(x1, y1, x2, y2, label, opts = {}) {
  const { tick = 6, textSize = 14, color = "#c0392b" } = opts; // brighter color
  // main line
  const line = create("line", {
    x1: x1,
    y1: y1,
    x2: x2,
    y2: y2,
    stroke: color,
    "stroke-width": 1.6,
  });
  svg.appendChild(line);
  // ticks at ends (perpendicular)
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  let px = (-dy / len) * tick;
  let py = (dx / len) * tick;
  // choose outward direction for ticks relative to svg center (500,500)
  const midx = (x1 + x2) / 2;
  const midy = (y1 + y2) / 2;
  const dirSign = (midx - 500) * px + (midy - 500) * py >= 0 ? 1 : -1;
  px *= dirSign;
  py *= dirSign;
  const t1 = create("line", {
    x1: x1,
    y1: y1,
    x2: x1 + px,
    y2: y1 + py,
    stroke: color,
    "stroke-width": 1.6,
  });
  svg.appendChild(t1);
  const t2 = create("line", {
    x1: x2,
    y1: y2,
    x2: x2 + px,
    y2: y2 + py,
    stroke: color,
    "stroke-width": 1.6,
  });
  svg.appendChild(t2);
  // endpoint markers for visibility
  const m1 = create("circle", { cx: x1, cy: y1, r: 2.2, fill: color });
  svg.appendChild(m1);
  const m2 = create("circle", { cx: x2, cy: y2, r: 2.2, fill: color });
  svg.appendChild(m2);
  // label
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  // prefer horizontal label with small white background for contrast
  const labelX = mx + px * 2.5;
  const labelY = my + py * 2.5;
  const txt = create("text", {
    x: labelX,
    y: labelY,
    fill: "#000",
    "font-size": textSize,
    "text-anchor": "middle",
    "dominant-baseline": "middle",
  });
  txt.textContent = label;
  // add background rect behind text for readability
  // approximate text width
  const approxWidth = Math.max(40, label.length * (textSize * 0.6));
  const rect = create("rect", {
    x: labelX - approxWidth / 2 - 6,
    y: labelY - textSize / 1.6 - 4,
    width: approxWidth + 12,
    height: textSize * 1.6 + 6,
    fill: "#fff",
    stroke: "#ddd",
    rx: 3,
    ry: 3,
  });
  svg.appendChild(rect);
  svg.appendChild(txt);
}

const fs = geometry.frames || [];
if (fs.length >= 1) {
  const f = fs[0];
  const xs = f.points.map((p) => p[0]);
  const ys = f.points.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs);
  const minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const dimOffset = 40; // px (increased so dims sit further from box)
  // bottom dimension (width)
  const bx1 = toSvgX(minX),
    by = toSvgY(maxY) + dimOffset;
  const bx2 = toSvgX(maxX);
  const widthVal = Math.round(maxX - minX);
  drawDimLine(bx1, by, bx2, by, `${widthVal} mm`, { tick: 6 });
  // right dimension (height)
  const rx = toSvgX(maxX) + dimOffset;
  const ry1 = toSvgY(minY),
    ry2 = toSvgY(maxY);
  const heightVal = Math.round(maxY - minY);
  // draw vertical line and rotated text
  drawDimLine(rx, ry1, rx, ry2, `${heightVal} mm`, { tick: 6 });
}

if (fs.length >= 2) {
  const f = fs[1];
  const xs = f.points.map((p) => p[0]);
  const ys = f.points.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs);
  const minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const dimOffset = 40; // px
  // top dimension (width) - above the box
  const tx1 = toSvgX(minX),
    ty = toSvgY(minY) - dimOffset;
  const tx2 = toSvgX(maxX);
  const widthVal = Math.round(maxX - minX);
  drawDimLine(tx1, ty, tx2, ty, `${widthVal} mm`, { tick: 6 });
  // left dimension (height)
  const lx = toSvgX(minX) - dimOffset;
  const ly1 = toSvgY(minY),
    ly2 = toSvgY(maxY);
  const heightVal = Math.round(maxY - minY);
  drawDimLine(lx, ly1, lx, ly2, `${heightVal} mm`, { tick: 6 });
}

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
