// Participant Live Face Scan — with Secure Context detection & camera fallback

document.addEventListener('DOMContentLoaded', () => {
    const searchForm        = document.getElementById('searchForm');
    const searchBtn         = document.getElementById('searchBtn');
    const selfiePreviewArea = document.getElementById('selfiePreviewArea');
    const selfiePreviewImg  = document.getElementById('selfiePreviewImg');
    const thresholdRange    = document.getElementById('thresholdRange');
    const thresholdVal      = document.getElementById('thresholdVal');

    const startWebcamBtn    = document.getElementById('startWebcamBtn');
    const startCameraPrompt = document.getElementById('startCameraPrompt');
    const videoWrapper      = document.getElementById('videoWrapper');
    const webcamVideo       = document.getElementById('webcamVideo');
    const webcamCanvas      = document.getElementById('webcamCanvas');
    const captureWebcamBtn  = document.getElementById('captureWebcamBtn');
    const rescanFaceBtn     = document.getElementById('rescanFaceBtn');
    const httpsWarning      = document.getElementById('httpsWarning');

    const resultsSection    = document.getElementById('resultsSection');
    const galleryGrid       = document.getElementById('galleryGrid');
    const resultsMeta       = document.getElementById('resultsMeta');
    const downloadZipBtn    = document.getElementById('downloadZipBtn');

    let currentSelfieBlob  = null;
    let stream             = null;
    let currentMatchedPaths = [];

    // --- Check secure context first ---
    // navigator.mediaDevices is only available on HTTPS or localhost
    const isSecureCtx = window.isSecureContext ||
                        location.hostname === 'localhost' ||
                        location.hostname === '127.0.0.1';

    if (!isSecureCtx || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        // Show warning, hide scanner
        if (httpsWarning) httpsWarning.style.display = 'block';
        if (startWebcamBtn) {
            startWebcamBtn.disabled = true;
            startWebcamBtn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Camera Unavailable (HTTP)';
            startWebcamBtn.style.opacity = '0.5';
            startWebcamBtn.style.cursor = 'not-allowed';
        }
        return; // Stop further init — camera cannot be used
    }

    // --- Threshold slider ---
    if (thresholdRange) {
        thresholdRange.addEventListener('input', e => {
            thresholdVal.textContent = parseFloat(e.target.value).toFixed(2);
        });
    }

    // --- Start camera ---
    if (startWebcamBtn) {
        startWebcamBtn.addEventListener('click', async () => {
            await initCameraStream();
        });
    }

    async function initCameraStream() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            });
            webcamVideo.srcObject = stream;
            startCameraPrompt.style.display   = 'none';
            videoWrapper.style.display        = 'block';
            captureWebcamBtn.style.display    = 'inline-flex';
            searchBtn.style.display           = 'none';
            selfiePreviewArea.style.display   = 'none';
        } catch (err) {
            let msg = 'Camera access was denied or unavailable.';
            if (err.name === 'NotAllowedError')
                msg = 'Camera permission denied. Please allow camera access in your browser settings and try again.';
            else if (err.name === 'NotFoundError')
                msg = 'No camera device found on this device.';
            else if (err.name === 'NotReadableError')
                msg = 'Camera is already in use by another application.';

            startCameraPrompt.innerHTML = `
                <i class="fa-solid fa-circle-exclamation" style="font-size:3rem; color:#fca5a5; margin-bottom:1rem;"></i>
                <h4 style="color:#fca5a5; margin-bottom:0.5rem;">Camera Error</h4>
                <p style="color:var(--text-muted); font-size:0.9rem; max-width:400px; margin:0 auto 1.5rem auto;">${msg}</p>
                <button type="button" class="btn btn-primary" onclick="location.reload()">
                    <i class="fa-solid fa-rotate-right"></i> Retry
                </button>
            `;
        }
    }

    // --- Capture snapshot ---
    if (captureWebcamBtn) {
        captureWebcamBtn.addEventListener('click', () => {
            if (!webcamVideo.videoWidth) return;

            const ctx = webcamCanvas.getContext('2d');
            webcamCanvas.width  = webcamVideo.videoWidth  || 640;
            webcamCanvas.height = webcamVideo.videoHeight || 480;

            // Mirror to match live preview
            ctx.translate(webcamCanvas.width, 0);
            ctx.scale(-1, 1);
            ctx.drawImage(webcamVideo, 0, 0, webcamCanvas.width, webcamCanvas.height);

            webcamCanvas.toBlob(blob => {
                currentSelfieBlob = new File([blob], 'scanned_face.jpg', { type: 'image/jpeg' });
                selfiePreviewImg.src = webcamCanvas.toDataURL('image/jpeg');
                stopCameraStream();

                videoWrapper.style.display       = 'none';
                captureWebcamBtn.style.display   = 'none';
                selfiePreviewArea.style.display  = 'block';
                searchBtn.style.display          = 'inline-flex';
                searchBtn.disabled               = false;
            }, 'image/jpeg', 0.95);
        });
    }

    // --- Re-scan ---
    if (rescanFaceBtn) {
        rescanFaceBtn.addEventListener('click', () => {
            currentSelfieBlob = null;
            selfiePreviewArea.style.display = 'none';
            searchBtn.style.display         = 'none';
            initCameraStream();
        });
    }

    function stopCameraStream() {
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
            stream = null;
        }
    }

    // --- Submit search ---
    if (searchForm) {
        searchForm.addEventListener('submit', async e => {
            e.preventDefault();
            if (!currentSelfieBlob) {
                alert('Please scan your face first.');
                return;
            }

            const eventId   = document.getElementById('event_id').value;
            const threshold = thresholdRange.value;

            const formData = new FormData();
            formData.append('event_id',  eventId);
            formData.append('threshold', threshold);
            formData.append('selfie',    currentSelfieBlob);

            searchBtn.disabled   = true;
            searchBtn.innerHTML  = '<i class="fa-solid fa-spinner fa-spin"></i> Matching Embeddings...';
            resultsSection.style.display = 'none';

            try {
                const res  = await fetch('/api/search', { method: 'POST', body: formData });
                const data = await res.json();

                searchBtn.disabled  = false;
                searchBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Search My Photos';

                if (res.ok && data.success) {
                    displayResults(data);
                } else {
                    alert(data.error || 'Face search failed. Please try again.');
                }
            } catch (err) {
                searchBtn.disabled  = false;
                searchBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Search My Photos';
                alert('Network error: ' + err.message);
            }
        });
    }

    function displayResults(data) {
        resultsSection.style.display = 'block';
        galleryGrid.innerHTML        = '';
        currentMatchedPaths          = [];

        resultsMeta.innerHTML = `Retrieved <strong>${data.total_matches}</strong> photo(s) in <strong>${data.processing_time_ms} ms</strong>.`;

        if (!data.matches.length) {
            galleryGrid.innerHTML = `
                <div style="grid-column:1/-1; text-align:center; padding:3rem 1rem; color:var(--text-muted);">
                    <i class="fa-solid fa-face-frown" style="font-size:3rem; color:var(--text-subtle); margin-bottom:1rem;"></i>
                    <h4>No Matching Photos Found</h4>
                    <p style="font-size:0.9rem; margin-top:0.5rem;">Try lowering the sensitivity slider or re-scanning with better lighting.</p>
                </div>`;
            if (downloadZipBtn) downloadZipBtn.style.display = 'none';
            return;
        }

        if (downloadZipBtn) downloadZipBtn.style.display = 'inline-flex';

        data.matches.forEach(item => {
            const relPath = item.image_path;
            currentMatchedPaths.push(item.image_path);

            const card = document.createElement('div');
            card.className = 'photo-card';
            card.innerHTML = `
                <div class="photo-overlay"><i class="fa-solid fa-bolt"></i> ${item.confidence_percentage}% Match</div>
                <img src="${relPath}" class="photo-img" alt="Event Photo" loading="lazy">
                <div class="photo-actions">
                    <span style="font-size:0.8rem; color:var(--text-muted); overflow:hidden; white-space:nowrap; max-width:130px; text-overflow:ellipsis;">
                        ${item.filename}
                    </span>
                    <a href="${relPath}" download="${item.filename}" class="btn btn-secondary" style="padding:0.4rem 0.8rem; font-size:0.8rem;">
                        <i class="fa-solid fa-download"></i> Save
                    </a>
                </div>`;
            galleryGrid.appendChild(card);
        });

        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    // --- ZIP download ---
    if (downloadZipBtn) {
        downloadZipBtn.addEventListener('click', async () => {
            if (!currentMatchedPaths.length) return;

            downloadZipBtn.disabled = true;
            downloadZipBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Archiving...';

            try {
                const res = await fetch('/api/download_zip', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_paths: currentMatchedPaths })
                });

                if (res.ok) {
                    const blob = await res.blob();
                    const url  = URL.createObjectURL(blob);
                    const a    = document.createElement('a');
                    a.href     = url;
                    a.download = 'My_Event_Photos.zip';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                } else {
                    alert('Failed to generate ZIP. Please try again.');
                }
            } catch (err) {
                alert('ZIP error: ' + err.message);
            } finally {
                downloadZipBtn.disabled = false;
                downloadZipBtn.innerHTML = '<i class="fa-solid fa-file-zipper"></i> Download All as ZIP';
            }
        });
    }
});
