/**
 * MEDCHECK-PI — ADMIN CONTROL PANEL JAVASCRIPT
 * Black & White, Transparent/Visible, Pre-set Medicine Profile Management.
 */

document.addEventListener("DOMContentLoaded", () => {
  const socket = io({
    transports: ["polling", "websocket"],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
  });

  const statusDisplay = document.getElementById("admin-status-display");
  const toastMessage = document.getElementById("admin-toast");
  const chipsRow = document.getElementById("med-chips-row");

  // Medicine profile elements
  const medName = document.getElementById("admin-med-name");
  const medGeneric = document.getElementById("admin-med-generic");
  const medMfr = document.getElementById("admin-med-mfr");
  const medBatch = document.getElementById("admin-med-batch");
  const medComp = document.getElementById("admin-med-comp");
  const medSecurity = document.getElementById("admin-med-security");

  // Buttons
  const btnCounterfeit = document.getElementById("btn-counterfeit");
  const btnReal = document.getElementById("btn-real");
  const btnNoMedicine = document.getElementById("btn-no-medicine");

  let activeMedicineId = "dolo650";
  let presetMedicines = [];

  const triggerHaptic = () => {
    if ("vibrate" in navigator) {
      try {
        navigator.vibrate(35);
      } catch (e) {}
    }
  };

  const showToast = (msg) => {
    if (toastMessage) {
      toastMessage.textContent = msg;
      setTimeout(() => {
        if (toastMessage.textContent === msg) {
          toastMessage.textContent = "";
        }
      }, 3000);
    }
  };

  const updateStatusDisplay = (status, result) => {
    if (!statusDisplay) return;

    statusDisplay.className = "admin-status-display";

    if (result === "COUNTERFEIT") {
      statusDisplay.textContent = "VERDICT: COUNTERFEIT";
      statusDisplay.classList.add("active-result");
    } else if (result === "REAL") {
      statusDisplay.textContent = "VERDICT: REAL";
      statusDisplay.classList.add("active-result");
    } else if (result === "NO MEDICINE FOUND") {
      statusDisplay.textContent = "VERDICT: NO MEDICINE FOUND";
      statusDisplay.classList.add("active-result");
    } else if (status === "SCANNING") {
      statusDisplay.textContent = "AI SCANNING IN PROGRESS...";
      statusDisplay.classList.add("scanning");
    } else {
      statusDisplay.textContent = "SYSTEM READY";
    }
  };

  const renderMedicineDetails = (med) => {
    if (!med) return;
    activeMedicineId = med.id;

    if (medName) medName.textContent = med.name || "Medicine";
    if (medGeneric) medGeneric.textContent = med.generic || "";
    if (medMfr) medMfr.textContent = med.manufacturer || "N/A";
    if (medBatch) medBatch.textContent = `${med.batch_no || "N/A"} (EXP: ${med.exp_date || "N/A"})`;
    if (medComp) medComp.textContent = med.composition || "N/A";
    if (medSecurity) medSecurity.textContent = `${med.packaging || ""} | ${med.security_features || ""}`;

    // Highlight active chip
    document.querySelectorAll(".med-chip-btn").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.id === med.id);
    });
  };

  const buildMedicineChips = (medList, currentMed) => {
    if (!chipsRow || !medList || !medList.length) return;
    presetMedicines = medList;
    chipsRow.innerHTML = "";

    medList.forEach((med) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "med-chip-btn";
      chip.dataset.id = med.id;
      chip.textContent = med.name;

      if (currentMed && currentMed.id === med.id) {
        chip.classList.add("active");
      }

      chip.addEventListener("click", () => {
        triggerHaptic();
        activeMedicineId = med.id;
        renderMedicineDetails(med);
        socket.emit("select_medicine", { id: med.id });
        showToast(`Profile set to ${med.name}`);
      });

      chipsRow.appendChild(chip);
    });
  };

  // Button 1: COUNTERFEIT
  btnCounterfeit.addEventListener("click", () => {
    triggerHaptic();
    socket.emit("select_result", { result: "COUNTERFEIT", medicine_id: activeMedicineId });
    updateStatusDisplay("RESULT", "COUNTERFEIT");
    showToast("Submitted: COUNTERFEIT");
  });

  // Button 2: REAL
  btnReal.addEventListener("click", () => {
    triggerHaptic();
    socket.emit("select_result", { result: "REAL", medicine_id: activeMedicineId });
    updateStatusDisplay("RESULT", "REAL");
    showToast("Submitted: REAL");
  });

  // Button 3: NO MEDICINE FOUND
  btnNoMedicine.addEventListener("click", () => {
    triggerHaptic();
    socket.emit("select_result", { result: "NO MEDICINE FOUND", medicine_id: activeMedicineId });
    updateStatusDisplay("RESULT", "NO MEDICINE FOUND");
    showToast("Submitted: NO MEDICINE FOUND");
  });

  // Socket state listeners
  socket.on("inspection_updated", (state) => {
    if (!state) return;

    if (state.preset_medicines && state.preset_medicines.length) {
      if (!chipsRow.children.length) {
        buildMedicineChips(state.preset_medicines, state.current_medicine);
      }
    }

    if (state.current_medicine) {
      renderMedicineDetails(state.current_medicine);
    }

    if (state.scan_state === "SCANNING") {
      updateStatusDisplay("SCANNING", null);
    } else if (state.scan_state === "RESULT" && state.selected_result) {
      updateStatusDisplay("RESULT", state.selected_result);
    } else {
      updateStatusDisplay("READY", null);
    }
  });

  socket.on("scan_started", (data) => {
    updateStatusDisplay("SCANNING", null);
    if (data.medicine) {
      renderMedicineDetails(data.medicine);
    }
    showToast("Scan active: Select verification decision");
  });

  socket.on("result_selected", (data) => {
    updateStatusDisplay("RESULT", data.result);
    if (data.medicine) {
      renderMedicineDetails(data.medicine);
    }
  });

  socket.on("scan_reset", () => {
    updateStatusDisplay("READY", null);
  });
});
