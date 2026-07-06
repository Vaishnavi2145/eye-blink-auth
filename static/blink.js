// static/blink.js
// Eye Aspect Ratio (EAR) blink detection using MediaPipe FaceMesh

window.BlinkAuth = (function () {
    let video, canvas, ctx, countEl, hiddenInput, startBtn, resetBtn;
    let camera, faceMesh;
    let blinkCount = 0;
    let isBlinking = false;

    // Eye landmarks indices (MediaPipe Face Mesh)
    // Left eye: 33, 160, 158, 133, 153, 144
    // Right eye: 263, 387, 385, 362, 380, 373
    const LEFT = [33, 160, 158, 133, 153, 144];
    const RIGHT = [263, 387, 385, 362, 380, 373];

    function dist(a, b) {
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        return Math.hypot(dx, dy);
    }

    function ear(pts) {
        // EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        const p1 = pts[0], p2 = pts[1], p3 = pts[2], p4 = pts[3], p5 = pts[4], p6 = pts[5];
        const v1 = dist(p2, p6);
        const v2 = dist(p3, p5);
        const h = dist(p1, p4);
        return (v1 + v2) / (2.0 * h);
    }

    function drawLandmarks(landmarks) {
        if (!ctx || !canvas) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.lineWidth = 2;
        ctx.strokeStyle = "white";
        ctx.globalAlpha = 0.8;

        function drawEye(indices) {
            ctx.beginPath();
            indices.forEach((idx, i) => {
                const p = landmarks[idx];
                const x = p.x * canvas.width;
                const y = p.y * canvas.height;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.closePath();
            ctx.stroke();
        }

        drawEye(LEFT);
        drawEye(RIGHT);
    }

    async function onResults(results) {
        if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
            return;
        }
        const landmarks = results.multiFaceLandmarks[0];

        drawLandmarks(landmarks);

        const leftPts = LEFT.map(i => landmarks[i]);
        const rightPts = RIGHT.map(i => landmarks[i]);

        const leftEAR = ear(leftPts);
        const rightEAR = ear(rightPts);
        const avgEAR = (leftEAR + rightEAR) / 2;

        // Thresholds (tweak if needed)
        const BLINK_THRESHOLD = 0.21;  // lower => stricter
        const OPEN_THRESHOLD = 0.26;   // hysteresis to avoid jitter

        if (!isBlinking && avgEAR < BLINK_THRESHOLD) {
            isBlinking = true;
        } else if (isBlinking && avgEAR > OPEN_THRESHOLD) {
            isBlinking = false;
            blinkCount += 1;
            updateUI();
        }
    }

    function updateUI() {
        if (countEl) countEl.textContent = String(blinkCount);
        if (hiddenInput) hiddenInput.value = String(blinkCount);
    }

    function resetCounter() {
        blinkCount = 0;
        updateUI();
    }

    function attachEvents() {
        if (resetBtn) resetBtn.addEventListener("click", resetCounter);
        if (startBtn) startBtn.addEventListener("click", startCamera);
    }

    async function startCamera() {
        if (camera) return; // already running
        if (!video) return;

        // ✅ FIX: remove the "FaceMesh." prefix
        faceMesh = new FaceMesh({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
        });
        faceMesh.setOptions({
            maxNumFaces: 1,
            refineLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });
        faceMesh.onResults(onResults);

        camera = new Camera(video, {
            onFrame: async () => {
                await faceMesh.send({ image: video });
            },
            width: 640,
            height: 480
        });
        camera.start();

        // Match canvas to video size
        setTimeout(() => {
            if (!canvas) return;
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
        }, 500);
    }


    function init(opts) {
        video = document.getElementById(opts.videoId);
        canvas = document.getElementById(opts.canvasId);
        ctx = canvas.getContext("2d");
        countEl = document.getElementById(opts.countElId);
        hiddenInput = document.getElementById(opts.hiddenInputId);
        startBtn = document.getElementById(opts.startBtnId);
        resetBtn = document.getElementById(opts.resetBtnId);
        attachEvents();
        resetCounter();
    }

    function captureFaceFrame() {
        if (!video || video.readyState < 2) return null;

        const tempCanvas = document.createElement("canvas");
        tempCanvas.width = video.videoWidth;
        tempCanvas.height = video.videoHeight;

        const ctx = tempCanvas.getContext("2d");
        ctx.drawImage(video, 0, 0);

        return tempCanvas.toDataURL("image/jpeg");
    }

    function stopCamera() {
        if (camera) {
            camera.stop();
            camera = null;
        }
        if (video && video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
    }


    return { init, stopCamera, captureFaceFrame };

})();
