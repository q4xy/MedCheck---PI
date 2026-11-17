document.addEventListener("DOMContentLoaded", () => {
  const socket = io();
  const analyzeButton = document.getElementById("analyze-button");
  const decisionButtons = document.querySelectorAll(".decision");
  const selectedResult = document.getElementById("selected-result");
  const scanStatus = document.getElementById("scan-status");
  const cameraState = document.getElementById("camera-state");
  const capturedImage = document.getElementById("captured-image");
  const analysisStatus = document.getElementById("analysis-status");
  const analysisMessage = document.getElementById("analysis-message");

  const updateView = (payload) => {
    if (!payload) return;

    const selected = payload.selected_result || "WAITING";
    selectedResult.textContent = selected;
    scanStatus.textContent = payload.current_status || "SYSTEM ONLINE";
    cameraState.textContent = payload.camera_connected ? "USB ONLINE" : "USB OFFLINE";
    cameraState.classList.toggle("ok", !!payload.camera_connected);
    cameraState.classList.toggle("neutral", !payload.camera_connected);

    analysisStatus.textContent = payload.analysis_status || "WAITING FOR CAPTURE";
    analysisMessage.textContent = payload.analysis_message || "Awaiting a valid rear-side medicine image.";

    const accepted = Boolean(payload.image_accepted);
    decisionButtons.forEach((button) => {
      button.disabled = !accepted;
    });

    if (payload.latest_image_url) {
      capturedImage.src = payload.latest_image_url;
    }
  };

  analyzeButton.addEventListener("click", () => {
    socket.emit("analyze_image");
  });

  decisionButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const result = button.dataset.result;
      socket.emit("select_result", { result });
      button.classList.add("pressed");
      setTimeout(() => button.classList.remove("pressed"), 250);
    });
  });

  socket.on("inspection_updated", updateView);
  socket.on("result_selected", (payload) => {
    selectedResult.textContent = payload.result || "WAITING";
    scanStatus.textContent = payload.status || "RESULT SELECTED";
  });
});
