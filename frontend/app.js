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
  } else {
    singleInputsDiv.classList.remove("hidden");
    singleInputsDiv.classList.add("fade-in");
    bulkInputsDiv.classList.add("hidden");
    excelInput.required = false;
    toggleHint.textContent = "Enter parameters below";
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
          width_measurement: Number(data.width_measurement) || 0,
          height_measurement: Number(data.height_measurement) || 0,
          left_side_allowance_width:
            Number(data.left_side_allowance_width) || 25,
          right_side_allowance_width:
            Number(data.right_side_allowance_width) || 25,
          top_side_allowance_height:
            Number(data.top_side_allowance_height) || 25,
          bottom_side_allowance_height:
            Number(data.bottom_side_allowance_height) || 25,
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

function showToast(msg, type = "success") {
  const toast = document.createElement("div");
  toast.textContent = msg;
  toast.style.cssText = `
    position: fixed; bottom: 30px; right: 20px;
    background: ${'${type === "success" ? "#16a34a" : "#dc2626"}'};
    color: white; padding: 10px 16px; border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3); z-index: 9999;
    animation: fadeInOut 3s forwards;
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

document.querySelector("h2").addEventListener("click", () => {
  showToast("Developed by Jinesh 🧠", "success");
});
