document.addEventListener("DOMContentLoaded", () => {
  const socket = io({ reconnection: true, reconnectionDelay: 1000 });
  const analyzeButton = document.getElementById("analyze-button");
  const decisions = document.querySelectorAll(".decision");
  const image = document.getElementById("operator-image");
  const imageEmpty = document.getElementById("operator-image-empty");
  const scanOverlay = document.getElementById("operator-scan-overlay");
  const cameraDot = document.getElementById("camera-dot");

  const updateState = (payload) => {
    if (!payload) return;
    document.getElementById("camera-status").textContent = payload.camera_connected
      ? "USB WEBCAM CONNECTED"
      : "USB WEBCAM DISCONNECTED";
    cameraDot.classList.toggle("connected", Boolean(payload.camera_connected));
    document.getElementById("operator-classification").textContent =
      payload.classification || "WAITING FOR CAPTURE";
    const confidence = document.getElementById("operator-confidence");
    if (Number.isFinite(payload.analysis_confidence) && payload.analysis_confidence_label) {
      confidence.textContent = `${payload.analysis_confidence_label}: ${Math.round(payload.analysis_confidence * 100)}%`;
      confidence.hidden = false;
    } else {
      confidence.textContent = "";
      confidence.hidden = true;
    }
    document.getElementById("operator-message").textContent =
      payload.analysis_message || "Capture the rear side using the laptop keyboard, then analyze it.";
    document.getElementById("operator-observation").textContent = payload.red_mark_detected
      ? (payload.red_mark_observation || "Red-colored marking detected near the lower printed information area.")
      : "";
    document.getElementById("operator-result").textContent = payload.selected_result || "NOT SELECTED";
    scanOverlay.classList.toggle("hidden", payload.scan_state !== "ANALYZING");

    const hasCapture = Boolean(payload.captured_image_url);
    analyzeButton.disabled = !hasCapture || Boolean(payload.analysis_running);
    const accepted = Boolean(payload.image_accepted) && payload.classification === "SUPPORTED MEDICINE FOUND";
    decisions.forEach((button) => { button.disabled = !accepted; });
    if (hasCapture) {
      image.src = `${payload.captured_image_url}?t=${payload.last_update_ts || Date.now()}`;
      image.hidden = false;
      imageEmpty.hidden = true;
    } else {
      image.removeAttribute("src");
      image.hidden = true;
      imageEmpty.hidden = false;
    }
  };

  analyzeButton.addEventListener("click", () => {
    if (!analyzeButton.disabled) socket.emit("analyze_image");
  });
  decisions.forEach((button) => {
    button.addEventListener("click", () => {
      if (!button.disabled) socket.emit("select_result", { result: button.dataset.result });
    });
  });

  socket.on("inspection_updated", updateState);
  socket.on("capture_completed", updateState);
  socket.on("analysis_started", updateState);
  socket.on("analysis_completed", updateState);
  socket.on("operator_decision", updateState);
  socket.on("connect", () => { document.getElementById("socket-status").textContent = "Connected to laptop"; });
  socket.on("disconnect", () => { document.getElementById("socket-status").textContent = "Reconnecting…"; });
  socket.on("connect_error", () => { document.getElementById("socket-status").textContent = "Cannot connect to laptop"; });
});
