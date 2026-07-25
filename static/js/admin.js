// Admin Dashboard & Batch Upload Interactivity

document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const photoInput = document.getElementById('photoInput');
    const fileInfo = document.getElementById('fileInfo');
    const submitUploadBtn = document.getElementById('submitUploadBtn');
    const uploadForm = document.getElementById('uploadForm');
    const processingStatus = document.getElementById('processingStatus');
    const successAlert = document.getElementById('successAlert');
    const successMsg = document.getElementById('successMsg');

    if (!dropzone || !photoInput) return;

    // Drag and Drop Event Listeners
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            photoInput.files = files;
            updateFileInfo(files);
        }
    });

    photoInput.addEventListener('change', () => {
        if (photoInput.files.length > 0) {
            updateFileInfo(photoInput.files);
        }
    });

    function updateFileInfo(files) {
        fileInfo.style.display = 'block';
        fileInfo.innerHTML = `<i class="fa-solid fa-file-image"></i> Selected <strong>${files.length}</strong> photo(s) ready for AI processing.`;
        submitUploadBtn.disabled = false;
    }

    // Submit Upload Handler via AJAX
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(uploadForm);
        
        submitUploadBtn.disabled = true;
        processingStatus.style.display = 'block';
        successAlert.style.display = 'none';

        try {
            const response = await fetch(uploadForm.action, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            processingStatus.style.display = 'none';

            if (response.ok && data.success) {
                successAlert.style.display = 'block';
                successMsg.innerHTML = `Successfully uploaded <strong>${data.uploaded_images}</strong> photographs! AI Face Engine detected & embedded <strong>${data.faces_detected}</strong> human faces.`;
                fileInfo.style.display = 'none';
                photoInput.value = '';
            } else {
                alert(data.error || 'Failed to upload photographs.');
                submitUploadBtn.disabled = false;
            }
        } catch (err) {
            processingStatus.style.display = 'none';
            submitUploadBtn.disabled = false;
            alert('An error occurred during network upload: ' + err.message);
        }
    });
});
