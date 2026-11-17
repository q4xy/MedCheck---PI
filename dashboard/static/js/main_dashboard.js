document.addEventListener("DOMContentLoaded", () => {
  const socket = io({ reconnection: true, reconnectionDelay: 1000 });
  const $ = (id) => document.getElementById(id);
  const livePreview = $("live-preview");
  const capturedImage = $("captured-image");
  const emptyImage = $("image-empty");
  const scanOverlay = $("scan-overlay");
  const historyList = $("history-list");
  const cameraIndicator = $("camera-indicator");
  const cameraName = $("camera-name");
  const esp32Indicator = $("esp32-indicator");
  const clock = $("clock-indicator");

  const updateClock = () => { clock.textContent = new Date().toLocaleTimeString(); };
  updateClock();
  setInterval(updateClock, 1000);

  const renderHistory = (items) => {
    historyList.replaceChildren();
    if (!items || items.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty-history";
      empty.textContent = "No inspection history yet.";
      historyList.appendChild(empty);
      return;
    }
    items.slice(0, 8).forEach((record) => {
      const row = document.createElement("article");
      row.className = "history-item";
      const classification = document.createElement("strong");
      classification.textContent = record.classification || "NEEDS MANUAL REVIEW";
      const decision = document.createElement("span");
      decision.textContent = record.operator_decision
        ? `OPERATOR: ${record.operator_decision}`
        : "NO OPERATOR DECISION";
      const observation = document.createElement("span");
      observation.textContent = record.red_mark_detected ? "RED MARK OBSERVED" : "NO RED MARK OBSERVED";
      const time = document.createElement("time");
      time.textContent = record.timestamp || "";
      row.append(classification, decision, observation, time);
      historyList.appendChild(row);
    });
  };

  const updateState = (payload) => {
    if (!payload) return;
    cameraIndicator.textContent = payload.camera_connected ? "USB WEBCAM CONNECTED" : "USB WEBCAM DISCONNECTED";
    cameraName.textContent = payload.camera_name || cameraIndicator.textContent;
    esp32Indicator.textContent = payload.esp32_connected ? "ESP32 CONNECTED" : "ESP32 DISCONNECTED";
    $("system-state").textContent = "SYSTEM ONLINE";
    $("counterfeit-count").textContent = payload.summary_counts?.counterfeit ?? 0;
    $("real-count").textContent = payload.summary_counts?.real ?? 0;
    $("no-medicine-count").textContent = payload.summary_counts?.no_medicine_found ?? 0;
    $("classification").textContent = payload.classification || "WAITING FOR CAPTURE";
    const confidence = $("analysis-confidence");
    if (Number.isFinite(payload.analysis_confidence) && payload.analysis_confidence_label) {
      confidence.textContent = `${payload.analysis_confidence_label}: ${Math.round(payload.analysis_confidence * 100)}%`;
      confidence.hidden = false;
    } else {
      confidence.textContent = "";
      confidence.hidden = true;
    }
    $("analysis-message").textContent = payload.analysis_message || "";
    $("operator-result").textContent = payload.selected_result || "NOT SELECTED";
    $("inspection-time").textContent = payload.captured_image_name
      ? payload.captured_image_name.replace(/^scan_/, "").replace(/\.jpg$/, "").replaceAll("_", " ")
      : "AWAITING CAPTURE";
    $("red-observation").textContent = payload.red_mark_detected
      ? (payload.red_mark_observation || "Red-colored marking detected near the lower printed information area.")
      : "No red marking observation detected.";
    scanOverlay.classList.toggle("hidden", payload.scan_state !== "ANALYZING");

    if (payload.captured_image_url) {
      capturedImage.src = `${payload.captured_image_url}?t=${payload.last_update_ts || Date.now()}`;
      capturedImage.hidden = false;
      emptyImage.hidden = true;
    } else {
      capturedImage.removeAttribute("src");
      capturedImage.hidden = true;
      emptyImage.hidden = false;
    }
    renderHistory(payload.history);
  };

  socket.on("inspection_updated", updateState);
  socket.on("connect", () => { $("system-state").textContent = "SYSTEM ONLINE"; });
  socket.on("disconnect", () => { $("system-state").textContent = "RECONNECTING"; });
  socket.on("analysis_started", updateState);
  socket.on("analysis_completed", updateState);
  socket.on("capture_completed", updateState);

  const localLaptop = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  if (localLaptop) {
    document.addEventListener("keydown", (event) => {
      if (event.repeat || event.ctrlKey || event.altKey || event.metaKey) return;
      if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
      const key = event.key.toLowerCase();
      if (key === "s") {
        event.preventDefault();
        socket.emit("capture_image");
      } else if (key === "r") {
        event.preventDefault();
        socket.emit("retake_scan");
      }
    });
  }

  livePreview.addEventListener("error", () => {
    cameraIndicator.textContent = "USB WEBCAM DISCONNECTED";
  });
});
