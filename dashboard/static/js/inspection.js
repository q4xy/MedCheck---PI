document.addEventListener("DOMContentLoaded", () => {
  const socket = io();
  const resultBadge = document.getElementById("result-badge");
  const scanStatus = document.getElementById("scan-status");
  const cameraIndicator = document.getElementById("camera-indicator");
  const cameraName = document.getElementById("camera-name");
  const cameraText = document.getElementById("camera-text");
  const esp32Indicator = document.getElementById("esp32-indicator");
  const esp32Text = document.getElementById("esp32-text");
  const scanTime = document.getElementById("scan-time");
  const inspectionText = document.getElementById("inspection-text");
  const capturedImage = document.getElementById("captured-image");
  const scanOverlay = document.getElementById("scan-overlay");
  const historyList = document.getElementById("history-list");
  const analysisStatus = document.getElementById("analysis-status");
  const analysisMessage = document.getElementById("analysis-message");
  const startInspectionButton = document.getElementById("start-inspection-button");

  const updateClock = () => {
    const now = new Date();
    document.getElementById("clock-indicator").textContent = now.toLocaleTimeString();
  };

  const renderHistory = (history = []) => {
    historyList.innerHTML = "";
    if (!history.length) {
      historyList.innerHTML = "<div class='history-empty'>No inspection results yet.</div>";
      return;
    }

    history.slice(0, 6).forEach((entry) => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <div class="history-image-wrap">
          <img src="${entry.image_url || ""}" alt="${entry.result || "inspection"}" />
        </div>
        <div class="history-meta">
          <strong>${entry.result || "WAITING"}</strong>
          <span>${entry.analysis_status || "RESULT"}</span>
          <small>${entry.timestamp || ""}</small>
        </div>
      `;
      historyList.appendChild(item);
    });
  };

  const applyState = (payload) => {
    if (!payload) return;

    const isReal = payload.selected_result === "REAL";
    const isCounterfeit = payload.selected_result === "COUNTERFEIT";
    const waiting = !isReal && !isCounterfeit;

    resultBadge.textContent = payload.selected_result ? payload.selected_result : "WAITING FOR CAPTURE";
    resultBadge.classList.toggle("real", isReal);
    resultBadge.classList.toggle("counterfeit", isCounterfeit);
    resultBadge.classList.toggle("waiting", waiting);

    scanStatus.textContent = payload.current_status || "SYSTEM ONLINE";
    cameraIndicator.textContent = payload.camera_connected ? "USB CAMERA CONNECTED" : "USB CAMERA DISCONNECTED";
    cameraIndicator.classList.toggle("connected", !!payload.camera_connected);
    cameraName.textContent = payload.camera_connected ? (payload.camera_name || "USB CAMERA CONNECTED") : "USB CAMERA OFFLINE";
    cameraText.textContent = payload.camera_connected ? "USB CONNECTED" : "USB DISCONNECTED";
    esp32Indicator.textContent = payload.esp32_connected ? "ESP32 ONLINE" : "ESP32 OFFLINE";
    esp32Text.textContent = payload.esp32_connected ? "ONLINE" : "OFFLINE";
    scanTime.textContent = payload.latest_scan_time || "N/A";
    inspectionText.textContent = payload.selected_result || "WAITING";
    analysisStatus.textContent = payload.analysis_status || "WAITING FOR CAPTURE";
    analysisMessage.textContent = payload.analysis_message || "Awaiting a valid rear-side medicine image.";

    if (payload.latest_image_url) {
      capturedImage.src = payload.latest_image_url;
    }

    renderHistory(payload.history || []);
  };

  socket.on("inspection_updated", applyState);
  socket.on("scan_started", (payload) => {
    scanStatus.textContent = payload.status || "SCANNING REAR PACKAGE";
    scanOverlay.classList.remove("hidden");
  });
  socket.on("scan_completed", (payload) => {
    scanStatus.textContent = payload.status || "IMAGE CAPTURED";
    scanOverlay.classList.add("hidden");
    if (payload.image_url) {
      capturedImage.src = payload.image_url;
    }
  });

  startInspectionButton.addEventListener("click", () => {
    socket.emit("trigger_scan");
    scanOverlay.classList.remove("hidden");
  });

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    if (key === "s") {
      socket.emit("trigger_scan");
    }
    if (key === "r") {
      socket.emit("retake_scan");
    }
  });

  updateClock();
  setInterval(updateClock, 1000);
});
