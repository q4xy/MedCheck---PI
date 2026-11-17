/**
 * MEDCHECK-PI — MAIN DASHBOARD JAVASCRIPT
 * Real-time synchronization, canvas particles, continuous AI scan animation,
 * and high-visibility result presentations.
 */

document.addEventListener("DOMContentLoaded", () => {
  const socket = io({
    transports: ["polling", "websocket"],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
  });

  // DOM Elements
  const livePreview = document.getElementById("live-preview");
  const frozenImage = document.getElementById("frozen-image");
  const aiScanLayer = document.getElementById("ai-scan-layer");
  const aiStatusText = document.getElementById("ai-status-text");
  const btnAnalyze = document.getElementById("btn-analyze-image");
  const resultCard = document.getElementById("result-card");
  const resultTitle = document.getElementById("result-title");
  const resultDesc = document.getElementById("result-desc");
  const btnNewScan = document.getElementById("btn-new-scan");

  // Medicine Details Grid Elements
  const specMedName = document.getElementById("spec-med-name");
  const specMedGeneric = document.getElementById("spec-med-generic");
  const specMedMfr = document.getElementById("spec-med-mfr");
  const specMedBatch = document.getElementById("spec-med-batch");
  const specMedSecurity = document.getElementById("spec-med-security");
  const specGrid = document.getElementById("medicine-spec-grid");

  // Telemetry indicators
  const cameraIndicator = document.getElementById("camera-indicator");
  const esp32Indicator = document.getElementById("esp32-indicator");
  const clockIndicator = document.getElementById("clock-indicator");
  const btnSwitchCam = document.getElementById("btn-switch-cam");

  // Text cycle sequence
  const aiDiagnosticPhrases = [
    "INITIALIZING AI ENGINE...",
    "ANALYZING MEDICINE IMAGE...",
    "SCANNING PACKAGING DETAILS...",
    "EXAMINING VISUAL FEATURES...",
    "AI ANALYSIS IN PROGRESS...",
    "AWAITING VERIFICATION DECISION...",
  ];

  let phraseIndex = 0;
  let textCycleInterval = null;
  let currentCameraIndex = 1;

  // -------------------------------------------------------------
  // 1. Digital Clock
  // -------------------------------------------------------------
  const updateClock = () => {
    const now = new Date();
    if (clockIndicator) {
      clockIndicator.textContent = now.toLocaleTimeString();
    }
  };
  setInterval(updateClock, 1000);
  updateClock();

  // -------------------------------------------------------------
  // 2. Interactive Background Particles Canvas
  // -------------------------------------------------------------
  const canvas = document.getElementById("particle-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    window.addEventListener("resize", () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    const particles = [];
    const particleCount = Math.min(Math.floor((width * height) / 18000), 70);

    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.7,
        vy: (Math.random() - 0.5) * 0.7,
        radius: Math.random() * 2 + 1,
        color: Math.random() > 0.5 ? "rgba(6, 182, 212, " : "rgba(139, 92, 246, ",
        alpha: Math.random() * 0.5 + 0.2,
      });
    }

    const drawParticles = () => {
      ctx.clearRect(0, 0, width, height);

      // Connect near particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 120) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(56, 189, 248, ${0.15 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.8;
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      // Draw particle points
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color + p.alpha + ")";
        ctx.fill();
      });

      requestAnimationFrame(drawParticles);
    };
    drawParticles();
  }

  // -------------------------------------------------------------
  // 3. AI Text Cycling Functions
  // -------------------------------------------------------------
  const startTextCycle = () => {
    stopTextCycle();
    phraseIndex = 0;
    aiStatusText.textContent = aiDiagnosticPhrases[phraseIndex];
    textCycleInterval = setInterval(() => {
      phraseIndex = (phraseIndex + 1) % aiDiagnosticPhrases.length;
      aiStatusText.textContent = aiDiagnosticPhrases[phraseIndex];
    }, 2400);
  };

  const stopTextCycle = () => {
    if (textCycleInterval) {
      clearInterval(textCycleInterval);
      textCycleInterval = null;
    }
  };

  // -------------------------------------------------------------
  // 4. View Transitions
  // -------------------------------------------------------------
  const showScanningState = (imageUrl) => {
    // 1. Freeze image
    if (imageUrl) {
      frozenImage.src = imageUrl;
    } else {
      frozenImage.src = "/captures/current_scan.jpg?t=" + Date.now();
    }
    frozenImage.style.display = "block";
    livePreview.style.display = "none";

    // 2. Activate continuous AI animation overlay
    aiScanLayer.classList.add("active");
    startTextCycle();

    // 3. Hide any previous result card
    resultCard.className = "result-presentation-card";
    resultCard.style.display = "none";

    // 4. Disable button during active scan
    btnAnalyze.disabled = true;
    btnAnalyze.style.opacity = "0.4";
  };

  const showResultState = (result, medicine) => {
    // Stop scanning animation
    aiScanLayer.classList.remove("active");
    stopTextCycle();

    // Configure Result Card theme & typography
    resultCard.className = "result-presentation-card";
    const normalized = (result || "").toUpperCase();

    if (normalized === "REAL") {
      resultCard.classList.add("theme-real");
      resultTitle.textContent = "AUTHENTIC MEDICINE VERIFIED";
      resultDesc.textContent = "Packaging markers, security features, and composition details confirmed authentic.";
    } else if (normalized === "COUNTERFEIT") {
      resultCard.classList.add("theme-counterfeit");
      resultTitle.textContent = "COUNTERFEIT DETECTED";
      resultDesc.textContent = "CRITICAL WARNING: Packaging anomalies detected. This product is flagged as counterfeit.";
    } else {
      // NO MEDICINE FOUND
      resultCard.classList.add("theme-no-medicine");
      resultTitle.textContent = "NO MEDICINE FOUND";
      resultDesc.textContent = "Unable to identify a valid medicine rear-side packaging. Please place packaging back side clearly in frame.";
    }

    if (medicine && normalized !== "NO MEDICINE FOUND") {
      if (specGrid) specGrid.style.display = "grid";
      if (specMedName) specMedName.textContent = medicine.name || "Identified Medicine";
      if (specMedGeneric) specMedGeneric.textContent = medicine.generic || "";
      if (specMedMfr) specMedMfr.textContent = medicine.manufacturer || "";
      if (specMedBatch) specMedBatch.textContent = `${medicine.batch_no || "N/A"} (EXP: ${medicine.exp_date || "N/A"})`;
      if (specMedSecurity) specMedSecurity.textContent = `${medicine.packaging || ""} | ${medicine.security_features || ""}`;
    } else if (specGrid) {
      specGrid.style.display = "none";
    }

    resultCard.style.display = "block";
    btnAnalyze.disabled = true;
    btnAnalyze.style.opacity = "0.4";
  };

  const resetToReadyState = () => {
    // Unfreeze and return to live webcam preview
    frozenImage.style.display = "none";
    livePreview.style.display = "block";
    livePreview.src = "/camera/stream?t=" + Date.now();

    // Stop scanning layer
    aiScanLayer.classList.remove("active");
    stopTextCycle();

    // Hide result card
    resultCard.className = "result-presentation-card";
    resultCard.style.display = "none";

    // Re-enable ANALYZE IMAGE button
    btnAnalyze.disabled = false;
    btnAnalyze.style.opacity = "1";
  };

  // -------------------------------------------------------------
  // 5. User Actions
  // -------------------------------------------------------------
  // Analyze Image Click
  btnAnalyze.addEventListener("click", () => {
    socket.emit("analyze_image");
    showScanningState();
  });

  // Start New Scan Click
  btnNewScan.addEventListener("click", () => {
    socket.emit("reset_scan");
    resetToReadyState();
  });

  // Camera Switch Button Click
  if (btnSwitchCam) {
    btnSwitchCam.addEventListener("click", () => {
      // Toggle between 1 and 0 (or prompt/increment)
      const nextIndex = currentCameraIndex === 1 ? 0 : 1;
      fetch(`/api/camera/switch?index=${nextIndex}`, { method: "POST" })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            currentCameraIndex = data.camera_index;
            btnSwitchCam.textContent = `CAM #${currentCameraIndex}`;
            livePreview.src = "/camera/stream?t=" + Date.now();
          }
        })
        .catch((err) => console.error("Camera switch error:", err));
    });
  }

  // -------------------------------------------------------------
  // 6. Socket.IO Events & State Synchronization
  // -------------------------------------------------------------
  socket.on("connect", () => {
    console.log("[SocketIO] Connected to MedCheck-PI backend.");
  });

  socket.on("scan_started", (data) => {
    showScanningState(data.image_url);
  });

  socket.on("result_selected", (data) => {
    showResultState(data.result, data.medicine);
  });

  socket.on("scan_reset", () => {
    resetToReadyState();
  });

  socket.on("inspection_updated", (state) => {
    if (!state) return;

    // Update Hardware Status Badges
    if (cameraIndicator) {
      if (state.camera_connected) {
        cameraIndicator.className = "telemetry-badge online";
        cameraIndicator.innerHTML = '<span class="pulse-dot"></span> ' + (state.camera_name || "USB CAMERA CONNECTED");
      } else {
        cameraIndicator.className = "telemetry-badge offline";
        cameraIndicator.innerHTML = '<span class="pulse-dot"></span> USB CAMERA OFFLINE';
      }
    }

    if (esp32Indicator) {
      if (state.esp32_connected) {
        esp32Indicator.className = "telemetry-badge online";
        esp32Indicator.innerHTML = '<span class="pulse-dot"></span> ESP32 COM4 ONLINE';
      } else {
        esp32Indicator.className = "telemetry-badge offline";
        esp32Indicator.innerHTML = '<span class="pulse-dot"></span> ESP32 DISCONNECTED';
      }
    }

    if (typeof state.camera_index === "number") {
      currentCameraIndex = state.camera_index;
      if (btnSwitchCam) {
        btnSwitchCam.textContent = `CAM #${currentCameraIndex}`;
      }
    }

    // State routing
    if (state.scan_state === "SCANNING") {
      showScanningState(state.captured_image_url);
    } else if (state.scan_state === "RESULT" && state.selected_result) {
      showResultState(state.selected_result, state.current_medicine);
    } else if (state.scan_state === "READY") {
      resetToReadyState();
    }
  });
});
