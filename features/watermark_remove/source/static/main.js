// State variables
let videos = [];
let selectedVideo = null;
let originalWidth = 1280;
let originalHeight = 720;
let cropBox = { x: 0, y: 0, width: 0, height: 0 };
let isPinned = false;
let pinnedSnapshot = null;
let fileOverrides = {};
let isDrawing = false;
let startX = 0;
let startY = 0;
let pollInterval = null;

// Batch state
let batchQueue = [];
let isBatchProcessing = false;
let currentBatchIndex = 0;
let cancelBatch = false;

// Shape state
let currentShape = 'rect';        // rect | diamond | ellipse | poly
let lassoPoints = [];             // canvas-buffer coords while drawing
let lassoOrigPoints = [];         // original video coords sent to backend

// Zoom / pan state
let zoomLevel = 1;
let panX = 0, panY = 0;
let isPanning = false;
let spaceDown = false;
let panStartX = 0, panStartY = 0;
let panOriginX = 0, panOriginY = 0;

// DOM Elements
const videoList = document.getElementById('video-list');
const canvasPlaceholder = document.getElementById('canvas-placeholder');
const interactiveContainer = document.getElementById('interactive-container');
const previewImage = document.getElementById('preview-image');
const selectionCanvas = document.getElementById('selection-canvas');
const coordDisplay = document.getElementById('coord-display');
const btnProcess = document.getElementById('btn-process');
const btnProcessBatch = document.getElementById('btn-process-batch');
const btnCancelBatch = document.getElementById('btn-cancel-batch');
const progressBatchText = document.getElementById('progress-batch-text');
const batchActions = document.getElementById('batch-actions');
const btnDetect = document.getElementById('btn-detect');
const detectStatus = document.getElementById('detect-status');
const canvasHint = document.getElementById('canvas-hint');

const btnPreview = document.getElementById('btn-preview');
const smartSettings = document.getElementById('smart-settings');
const inpaintSettings = document.getElementById('inpaint-settings');
const blurSettings = document.getElementById('blur-settings');

// Before/After preview
const baPreview = document.getElementById('ba-preview');
const baLoading = document.getElementById('ba-loading');
const baBefore = document.getElementById('ba-before');
const baAfter = document.getElementById('ba-after');
const baStats = document.getElementById('ba-stats');

// Sliders (id -> value-label id)
const SLIDERS = {
    gain: 'val-gain', floor: 'val-floor', edge: 'val-edge',
    tophat: 'val-tophat', despill: 'val-despill', edge_blur: 'val-edge_blur',
    radius: 'val-radius', blur: 'val-blur'
};
let previewTimer = null;

// Zoom controls
const zoomControls = document.getElementById('zoom-controls');
const zoomLevelLabel = document.getElementById('zoom-level');
const btnZoomIn = document.getElementById('btn-zoom-in');
const btnZoomOut = document.getElementById('btn-zoom-out');
const btnZoomReset = document.getElementById('btn-zoom-reset');

// Modals
const progressModalEl = document.getElementById('progress-modal');
const progressBarFill = document.getElementById('progress-bar-fill');
const progressText = document.getElementById('progress-text');
const progressVideoName = document.getElementById('progress-video-name');

// Context for Canvas
const ctx = selectionCanvas.getContext('2d');

// Current file type
let currentFileType = 'video'; // 'video' | 'image'

// Sensitivity state
let currentSensitivity = 'medium';

// Toast notification system
function showToast(message, type = 'error', duration = 5000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after duration
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Toggle all settings-group elements
function setSettingsDisabled(disabled) {
    document.querySelectorAll('.settings-group').forEach(el => {
        el.classList.toggle('disabled', disabled);
    });
}

// Folder bar elements
const btnRefresh    = document.getElementById('btn-refresh-files');
const btnUpload     = document.getElementById('btn-upload-file');
const fileUploadInput = document.getElementById('file-upload-input');
const btnOpenFolder = document.getElementById('btn-open-folder');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await fetch('/api/reset_tasks', {method: 'POST'});
    } catch(e) { console.error(e); }

    setupFolderBar();
    await loadVideos();
    setupCanvasListeners();
    setupPresetListeners();
    setupShapeListeners();
    setupZoomListeners();

    btnDetect.addEventListener('click', runAutoDetection);
    btnProcess.addEventListener('click', startProcessing);
    if (btnProcessBatch) btnProcessBatch.addEventListener('click', startBatchProcessing);
    if (btnCancelBatch) {
        btnCancelBatch.onclick = () => {
            if (confirm('Bạn có chắc chắn muốn hủy bỏ tiến trình xóa hàng loạt? Các video đã xong sẽ được giữ lại, các video chưa xử lý sẽ bị hủy.')) {
                cancelBatch = true;
                progressModalEl.classList.add('hidden');
                batchActions.style.display = 'none';
                alert('Đã hủy xóa hàng loạt! LƯU Ý: Nếu có 1 video đang chạy dở, nó sẽ chạy ngầm cho xong rồi dừng hẳn.');
            }
        };
    }

    if (btnPreview) btnPreview.addEventListener('click', () => runPreview(false));



    setupSensitivityButtons();
    setupSettingsButtons();
    loadSettings();
    setupSliders();
    document.querySelectorAll('input[name="method"]').forEach(radio => {
        radio.addEventListener('change', updateMethodUI);
    });
    updateMethodUI();

    const btnPin = document.getElementById('btn-pin-bbox');
    if (btnPin) {
        btnPin.addEventListener('click', () => {
            isPinned = !isPinned;
            btnPin.classList.toggle('active', isPinned);
            if (isPinned) {
                btnPin.innerHTML = '<i class="fa-solid fa-thumbtack"></i> Đã Ghim';
                btnPin.classList.replace('btn-secondary', 'btn-primary');
                
                // Lưu lại snapshot hiện tại
                pinnedSnapshot = {
                    cropBox: { ...cropBox },
                    lassoOrigPoints: [...lassoOrigPoints],
                    currentShape: currentShape,
                    settings: {
                        gain: document.getElementById('sld-gain').value,
                        floor: document.getElementById('sld-floor').value,
                        edge: document.getElementById('sld-edge').value,
                        tophat: document.getElementById('sld-tophat').value,
                        despill: document.getElementById('sld-despill').value,
                        edge_blur: document.getElementById('sld-edge_blur').value,
                        radius: document.getElementById('sld-radius').value,
                        blur: document.getElementById('sld-blur').value,
                        method: document.querySelector('input[name="method"]:checked').value
                    }
                };
                
                // Xóa toàn bộ ghi đè lẻ tẻ của từng file để thiết lập gốc mới
                fileOverrides = {};
            } else {
                btnPin.innerHTML = '<i class="fa-solid fa-thumbtack"></i> Ghim';
                btnPin.classList.replace('btn-primary', 'btn-secondary');
                pinnedSnapshot = null;
            }
            if (cropBox.width > 2 || lassoOrigPoints.length > 0) enableActions();
        });
    }
});

function loadSettings() {
    const saved = localStorage.getItem('watermarkSettings');
    if (saved) {
        try {
            const settings = JSON.parse(saved);
            if (settings.gain) document.getElementById('sld-gain').value = settings.gain;
            if (settings.floor) document.getElementById('sld-floor').value = settings.floor;
            if (settings.edge) document.getElementById('sld-edge').value = settings.edge;
            if (settings.tophat) document.getElementById('sld-tophat').value = settings.tophat;
            if (settings.despill) document.getElementById('sld-despill').value = settings.despill;
            if (settings.edge_blur) document.getElementById('sld-edge_blur').value = settings.edge_blur;
        } catch(e) {
            console.error('Error loading settings', e);
        }
    }
}

// ---- Settings Buttons -------------------------------------------------------
function setupSettingsButtons() {
    const btnSave = document.getElementById('btn-save-settings');
    const btnReset = document.getElementById('btn-reset-settings');
    
    if (btnSave) {
        btnSave.addEventListener('click', () => {
            const settings = {
                gain: document.getElementById('sld-gain').value,
                floor: document.getElementById('sld-floor').value,
                edge: document.getElementById('sld-edge').value,
                tophat: document.getElementById('sld-tophat').value,
                despill: document.getElementById('sld-despill').value,
                edge_blur: document.getElementById('sld-edge_blur').value
            };
            localStorage.setItem('watermarkSettings', JSON.stringify(settings));
            alert('Đã lưu tinh chỉnh!');
        });
    }

    if (btnReset) {
        btnReset.addEventListener('click', () => {
            localStorage.removeItem('watermarkSettings');
            // Default values based on HTML
            document.getElementById('sld-gain').value = "1.0";
            document.getElementById('sld-floor').value = "0.015";
            document.getElementById('sld-edge').value = "3";
            document.getElementById('sld-tophat').value = "8";
            document.getElementById('sld-despill').value = "0";
            document.getElementById('sld-edge_blur').value = "0";
            
            // Trigger input events to update UI numbers
            ['gain', 'floor', 'edge', 'tophat', 'despill', 'edge_blur'].forEach(id => {
                document.getElementById(`sld-${id}`).dispatchEvent(new Event('input'));
            });
            alert('Đã khôi phục mặc định!');
        });
    }
}

// ---- Sensitivity buttons ----------------------------------------------------
function setupSensitivityButtons() {
    document.querySelectorAll('.sens-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sens-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentSensitivity = btn.dataset.sens;
            if (!btnProcess.disabled) schedulePreview();
        });
    });
}

// ---- Folder bar -------------------------------------------------------------
function setupFolderBar() {
    if (btnUpload) {
        btnUpload.addEventListener('click', async () => {
            if (window.qtBridge) {
                // Native PySide6 file dialog
                try {
                    btnUpload.disabled = true;
                    btnUpload.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
                    const resStr = await new Promise(resolve => {
                        window.qtBridge.dispatch('/api/open_file_dialog', '{}', resolve);
                    });
                    const data = JSON.parse(resStr);
                    if (data.success && data.saved && data.saved.length > 0) {
                        showToast(`Tải lên thành công ${data.saved.length} file!`, 'success');
                        await loadVideos();
                    }
                } catch (e) {
                    console.error("Native upload error:", e);
                } finally {
                    btnUpload.disabled = false;
                    btnUpload.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Tải File Lên';
                }
            } else if (fileUploadInput) {
                fileUploadInput.click();
            }
        });

        if (fileUploadInput) {
            fileUploadInput.addEventListener('change', async (e) => {
                await handleFileUpload(e, fileUploadInput);
            });
        }
    }

    async function handleFileUpload(e, inputElement) {
        const allFiles = e.target.files;
        if (!allFiles || allFiles.length === 0) return;

        // Filter out files that are not videos or images to prevent uploading entire node_modules or huge unknown files
        const validExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.m4v', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'];
        const files = Array.from(allFiles).filter(file => {
            const name = file.name.toLowerCase();
            return validExtensions.some(ext => name.endsWith(ext));
        });

        if (files.length === 0) {
            alert('Thư mục hoặc danh sách bạn chọn không chứa video/ảnh hợp lệ!');
            inputElement.value = '';
            return;
        }

        if (btnUpload) {
            btnUpload.disabled = true;
            btnUpload.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
        }
        showToast(`Đang tải lên ${files.length} file hợp lệ...`, 'info', 2000);

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                showToast(`Tải lên thành công ${data.saved.length} file!`, 'success');
                await loadVideos();
            } else {
                showToast('Lỗi tải file: ' + data.error);
            }
        } catch (err) {
            showToast('Lỗi mạng khi tải file: ' + err.message);
        } finally {
            if (btnUpload) {
                btnUpload.disabled = false;
                btnUpload.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Tải File Lên';
            }
            inputElement.value = ''; // Reset
        }
    }

    if (btnOpenFolder) {
        const folderUploadInput = document.getElementById('folder-upload-input');
            btnOpenFolder.addEventListener('click', async () => {
                if (window.qtBridge) {
                    try {
                        btnOpenFolder.disabled = true;
                        const resStr = await window.qtBridge.dispatch('/api/open_folder_dialog', '{}');
                        const data = JSON.parse(resStr);
                        if (data.success && data.saved && data.saved.length > 0) {
                            showToast(`Tải lên thành công ${data.saved.length} file từ thư mục!`, 'success');
                            await loadVideos();
                        }
                    } catch (e) {
                        console.error("Native folder upload error:", e);
                    } finally {
                        btnOpenFolder.disabled = false;
                    }
                } else if (folderUploadInput) {
                    folderUploadInput.click();
                }
            });
            
            if (folderUploadInput) {
                folderUploadInput.addEventListener('change', async (e) => {
                    await handleFileUpload(e, folderUploadInput);
                });
            }
        }

    if (btnRefresh) {
        btnRefresh.addEventListener('click', loadVideos);
    }
    
    const btnClearAll = document.getElementById('btn-clear-all');
    if (btnClearAll) {
        btnClearAll.addEventListener('click', async () => {
            if (confirm('Bạn có chắc chắn muốn xóa toàn bộ danh sách?')) {
                const items = fileList.querySelectorAll('.list-group-item');
                for (const item of items) {
                    const name = item.querySelector('.filename').innerText;
                    try {
                        await fetch('/api/delete_file', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ filename: name })
                        });
                    } catch (e) {
                        console.error("Failed to delete", name, e);
                    }
                }
                fileList.innerHTML = '';
                checkEmptyList();
                checkButtonsState();
                showFeedback('Đã xóa danh sách', 'success');
                resetUploadUI();
            }
        });
    }
}

// Show the slider group for the selected method
function updateMethodUI() {
    const method = document.querySelector('input[name="method"]:checked').value;
    smartSettings.style.display = method === 'smart' ? 'block' : 'none';
    inpaintSettings.style.display = method === 'inpaint' ? 'block' : 'none';
    blurSettings.style.display = method === 'blur' ? 'block' : 'none';
    // Re-render preview for the new method if a region is already selected
    if (!btnProcess.disabled) schedulePreview();
}

// Wire all sliders: update their value label and schedule a live preview
function setupSliders() {
    Object.entries(SLIDERS).forEach(([id, labelId]) => {
        const el = document.getElementById('sld-' + id);
        const lbl = document.getElementById(labelId);
        if (!el) return;
        el.addEventListener('input', () => {
            lbl.innerText = el.value;
            schedulePreview();
        });
    });
}

function schedulePreview() {
    if (btnProcess.disabled || !selectedVideo) return;
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(() => runPreview(true), 50);
}

function collectParams() {
    const v = (id) => parseFloat(document.getElementById('sld-' + id).value);
    return {
        gain: v('gain'), floor: v('floor'),
        edge: parseInt(document.getElementById('sld-edge').value, 10),
        tophat: parseInt(document.getElementById('sld-tophat').value, 10),
        despill: v('despill'),
        edge_blur: parseInt(document.getElementById('sld-edge_blur').value, 10),
        radius: parseInt(document.getElementById('sld-radius').value, 10),
        blur: parseInt(document.getElementById('sld-blur').value, 10)
    };
}

async function loadVideos() {
    const icon = btnRefresh ? btnRefresh.querySelector('i') : null;
    if (icon) icon.classList.add('fa-spin');
    const minWait = new Promise(resolve => setTimeout(resolve, 500));
    const fetchCall = fetch(`/api/videos?t=${Date.now()}`);
    try {
        await minWait;
        const res = await fetchCall;
        const data = await res.json();
        if (data.success) {
            videos = data.videos;
            renderVideoList();
        } else {
            videoList.innerHTML = `<li class="loading-item text-danger">Lỗi: ${data.error}</li>`;
        }
    } catch (err) {
        console.error("Lỗi tải danh sách video:", err);
    } finally {
        if (icon) icon.classList.remove('fa-spin');
    }
}

function renderVideoList() {
    videoList.innerHTML = '';
    if (videos.length === 0) {
        videoList.innerHTML = '<li class="loading-item text-muted">Không tìm thấy file nào.<br><small>Chọn thư mục chứa video / ảnh ở trên.</small></li>';
        return;
    }
    
    videos.forEach(video => {
        const li = document.createElement('li');
        li.className = 'video-item';
        if (selectedVideo === video.name) li.classList.add('active');
        
        const isImg = video.type === 'image';
        const icon = isImg ? 'fa-file-image' : 'fa-file-video';
        const badge = isImg ? '<span class="file-type-badge badge-image">IMG</span>' : '<span class="file-type-badge badge-video">VID</span>';
        
        li.innerHTML = `
            <span class="video-name">${video.name}${badge}</span>
            <button class="btn-delete-file" title="Xóa file"><i class="fa-solid fa-trash"></i></button>
            <div class="video-meta">
                <span><i class="fa-solid ${icon}"></i> ${(video.size / (1024 * 1024)).toFixed(1)} MB</span>
            </div>
        `;
        
        li.addEventListener('click', () => selectVideo(video.name, li));
        
        const delBtn = li.querySelector('.btn-delete-file');
        delBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                const res = await fetch('/api/delete_file', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename: video.name})
                });
                const data = await res.json();
                if(data.success) {
                    showToast('Đã xóa ' + video.name, 'success');
                    if (selectedVideo === video.name) {
                        selectedVideo = null;
                        canvasPlaceholder.innerHTML = 'Chọn một file để bắt đầu.';
                        interactiveContainer.classList.add('hidden');
                        if (typeof baPreview !== 'undefined') baPreview.classList.add('hidden');
                        const sideBySide = document.getElementById('side-by-side-result');
                        if (sideBySide) sideBySide.classList.add('hidden');
                        resetSelection();
                    }
                    await loadVideos();
                } else {
                    showToast('Lỗi xóa file: ' + data.error);
                }
            } catch(err) {
                showToast('Lỗi kết nối khi xóa: ' + err.message);
            }
        });

        videoList.appendChild(li);
    });
}

let currentVideoSelectionToken = 0;
// Select video and fetch frame preview
async function selectVideo(videoName, element) {
    if (selectedVideo && selectedVideo !== videoName) {
        // Lưu lại phiên sửa đổi của file hiện tại trước khi chuyển sang file khác
        fileOverrides[selectedVideo] = {
            cropBox: { ...cropBox },
            lassoOrigPoints: [...lassoOrigPoints],
            currentShape: currentShape,
            settings: {
                gain: document.getElementById('sld-gain').value,
                floor: document.getElementById('sld-floor').value,
                edge: document.getElementById('sld-edge').value,
                tophat: document.getElementById('sld-tophat').value,
                despill: document.getElementById('sld-despill').value,
                edge_blur: document.getElementById('sld-edge_blur').value,
                radius: document.getElementById('sld-radius').value,
                blur: document.getElementById('sld-blur').value,
                method: document.querySelector('input[name="method"]:checked') ? document.querySelector('input[name="method"]:checked').value : 'telea'
            }
        };
    }

    document.querySelectorAll('.video-list li').forEach(el => el.classList.remove('active'));
    element.classList.add('active');

    selectedVideo = videoName;
    const token = ++currentVideoSelectionToken;

    canvasPlaceholder.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i><p>Đang trích xuất khung hình từ ${videoName}...</p>`;
    canvasPlaceholder.classList.remove('hidden');
    interactiveContainer.classList.add('hidden');
    zoomControls.classList.add('hidden');
    setSettingsDisabled(true);
    btnProcess.disabled = true;

    // Hide side-by-side result initially when selecting a new video
    const sideBySide = document.getElementById('side-by-side-result');
    if (sideBySide) sideBySide.classList.add('hidden');

    const videoObj = videos.find(v => v.name === videoName);
    if (videoObj && videoObj.has_result) {
        showResultPreview(videoObj.result_name);
    }

    // Lấy thông số cần phục hồi (Ưu tiên ghi đè của file > Cài đặt ghim > Cài đặt mặc định)
    const override = fileOverrides[videoName];
    const snapshotToRestore = override ? override : (isPinned ? pinnedSnapshot : null);

    if (snapshotToRestore) {
        // Phục hồi lại toàn bộ cài đặt từ snapshot đã ghim hoặc phiên đã lưu của file
        cropBox = { ...snapshotToRestore.cropBox };
        lassoOrigPoints = [...snapshotToRestore.lassoOrigPoints];
        currentShape = snapshotToRestore.currentShape;
        
        document.querySelectorAll('.shape-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.shape === currentShape);
        });
        
        const s = snapshotToRestore.settings;
        document.getElementById('sld-gain').value = s.gain;
        document.getElementById('sld-floor').value = s.floor;
        document.getElementById('sld-edge').value = s.edge;
        document.getElementById('sld-tophat').value = s.tophat;
        document.getElementById('sld-despill').value = s.despill;
        document.getElementById('sld-edge_blur').value = s.edge_blur;
        document.getElementById('sld-radius').value = s.radius;
        document.getElementById('sld-blur').value = s.blur;
        
        // Trigger update for UI values
        ['gain', 'floor', 'edge', 'tophat', 'despill', 'edge_blur', 'radius', 'blur'].forEach(id => {
            const el = document.getElementById('sld-' + id);
            if (el) el.dispatchEvent(new Event('input'));
        });
        
        const methodRadio = document.querySelector(`input[name="method"][value="${s.method}"]`);
        if (methodRadio) {
            methodRadio.checked = true;
            methodRadio.dispatchEvent(new Event('change'));
        }
        
        updateCoordDisplay();
    } else {
        resetSelection();
        updateCoordDisplay();
    }
    
    resetZoom();
    if (baPreview) baPreview.classList.add('hidden');
    if (btnPreview) btnPreview.disabled = true;

    try {
        const res = await fetch('/api/extract_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_name: videoName })
        });
        const data = await res.json();

        if (token !== currentVideoSelectionToken) return;

        if (data.success) {
            originalWidth = data.width;
            originalHeight = data.height;
            currentFileType = data.type || 'video';

            // Update process button label
            btnProcess.innerHTML = currentFileType === 'image'
                ? '<i class="fa-solid fa-image"></i> BẮT ĐẦU XÓA WATERMARK (ẢNH)'
                : '<i class="fa-solid fa-play"></i> BẮT ĐẦU XÓA WATERMARK';

            // Hide detect/auto-scan for images (need video frames for variance)
            btnDetect.style.display = currentFileType === 'image' ? 'none' : '';

            const suffix = data.preview_url.startsWith('file:') ? '' : '?t=' + new Date().getTime();
            previewImage.src = data.preview_url + suffix;

            previewImage.onload = () => {
                canvasPlaceholder.classList.add('hidden');
                interactiveContainer.classList.remove('hidden');
                zoomControls.classList.remove('hidden');
                setSettingsDisabled(false);
                resizeCanvas();
                
                if (isPinned && (cropBox.origWidth > 0 || lassoOrigPoints.length > 0)) {
                    enableActions();
                }
            };
        } else {
            canvasPlaceholder.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-danger"></i><p>Lỗi: ${data.error}</p>`;
        }
    } catch (err) {
        canvasPlaceholder.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-danger"></i><p>Lỗi kết nối tới server</p>`;
    }
}

function resetSelection() {
    cropBox = { x: 0, y: 0, width: 0, height: 0 };
    lassoPoints = [];
    lassoOrigPoints = [];
    updateCoordDisplay();
    drawSelection();
}

// Adjust canvas buffer to match the displayed (unscaled) image dimensions
function resizeCanvas() {
    if (!interactiveContainer.classList.contains('hidden')) {
        const wrapperWidth = document.querySelector('.canvas-wrapper').clientWidth;
        const sideBySide = document.getElementById('side-by-side-result');
        const isSideBySide = sideBySide && !sideBySide.classList.contains('hidden');
        
        // Container max bounds
        const maxWidth = isSideBySide ? (wrapperWidth - 15) / 2 : wrapperWidth;
        const maxHeight = 520;
        
        const imgRatio = originalWidth / originalHeight;
        const containerRatio = maxWidth / maxHeight;
        
        let visualWidth, visualHeight;
        if (imgRatio > containerRatio) {
            visualWidth = maxWidth;
            visualHeight = maxWidth / imgRatio;
        } else {
            visualHeight = maxHeight;
            visualWidth = maxHeight * imgRatio;
        }
        
        visualWidth = Math.round(visualWidth);
        visualHeight = Math.round(visualHeight);
        
        previewImage.style.width = visualWidth + 'px';
        previewImage.style.height = visualHeight + 'px';
        selectionCanvas.width = visualWidth;
        selectionCanvas.height = visualHeight;
        selectionCanvas.style.width = visualWidth + 'px';
        selectionCanvas.style.height = visualHeight + 'px';
        
        // Recompute canvas coordinates from the saved original coordinates
        if (cropBox.origWidth > 0 || lassoOrigPoints.length > 0) {
            const scaleX = visualWidth / originalWidth;
            const scaleY = visualHeight / originalHeight;
            cropBox.x = cropBox.origX * scaleX;
            cropBox.y = cropBox.origY * scaleY;
            cropBox.width = cropBox.origWidth * scaleX;
            cropBox.height = cropBox.origHeight * scaleY;
            
            if (currentShape === 'poly' && lassoOrigPoints.length > 0) {
                lassoPoints = lassoOrigPoints.map(p => ({
                    x: p[0] * scaleX, y: p[1] * scaleY
                }));
            }
        }
        
        drawSelection();
    }
}

window.addEventListener('resize', resizeCanvas);

// ---- Zoom & Pan ---------------------------------------------------------
function applyTransform() {
    interactiveContainer.style.transform =
        `scale(${zoomLevel}) translate(${panX}px, ${panY}px)`;
    zoomLevelLabel.innerText = Math.round(zoomLevel * 100) + '%';
}

function resetZoom() {
    zoomLevel = 1; panX = 0; panY = 0;
    applyTransform();
}

function setZoom(z) {
    zoomLevel = Math.max(1, Math.min(5, z));
    if (zoomLevel === 1) { panX = 0; panY = 0; }
    applyTransform();
}

function setupZoomListeners() {
    btnZoomIn.addEventListener('click', () => setZoom(zoomLevel + 0.5));
    btnZoomOut.addEventListener('click', () => setZoom(zoomLevel - 0.5));
    btnZoomReset.addEventListener('click', resetZoom);

    // Space toggles pan mode
    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && !spaceDown) {
            spaceDown = true;
            if (zoomLevel > 1) selectionCanvas.style.cursor = 'grab';
            // prevent page scroll when over the canvas
            if (document.activeElement === document.body) e.preventDefault();
        }
    });
    window.addEventListener('keyup', (e) => {
        if (e.code === 'Space') {
            spaceDown = false;
            isPanning = false;
            selectionCanvas.style.cursor = 'crosshair';
        }
    });
}

// Map a mouse event to canvas-buffer coordinates (handles zoom via rect size).
function getCanvasPoint(e) {
    const rect = selectionCanvas.getBoundingClientRect();
    const sx = selectionCanvas.width / rect.width;
    const sy = selectionCanvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * sx,
        y: (e.clientY - rect.top) * sy
    };
}

// Setup mouse drawing listeners on canvas
function setupCanvasListeners() {
    selectionCanvas.addEventListener('mousedown', (e) => {
        if (!selectedVideo) return;

        // Pan mode (Space held + zoomed in)
        if (spaceDown && zoomLevel > 1) {
            isPanning = true;
            panStartX = e.clientX; panStartY = e.clientY;
            panOriginX = panX; panOriginY = panY;
            selectionCanvas.style.cursor = 'grabbing';
            return;
        }

        isDrawing = true;
        const p = getCanvasPoint(e);
        startX = p.x; startY = p.y;

        if (currentShape === 'poly') {
            lassoPoints = [{ x: startX, y: startY }];
        } else {
            cropBox = { x: startX, y: startY, width: 0, height: 0 };
        }
    });

    selectionCanvas.addEventListener('mousemove', (e) => {
        if (isPanning) {
            // Translate is applied before scale, so divide delta by zoom.
            panX = panOriginX + (e.clientX - panStartX) / zoomLevel;
            panY = panOriginY + (e.clientY - panStartY) / zoomLevel;
            applyTransform();
            return;
        }
        if (!isDrawing) return;
        const p = getCanvasPoint(e);

        if (currentShape === 'poly') {
            lassoPoints.push({ x: p.x, y: p.y });
            drawSelection();
        } else {
            const x = Math.min(startX, p.x);
            const y = Math.min(startY, p.y);
            const width = Math.abs(startX - p.x);
            const height = Math.abs(startY - p.y);
            cropBox = { x, y, width, height };
            drawSelection();
            updateCoordDisplay();
        }
    });

    window.addEventListener('mouseup', () => {
        if (isPanning) {
            isPanning = false;
            selectionCanvas.style.cursor = spaceDown ? 'grab' : 'crosshair';
            return;
        }
        if (!isDrawing) return;
        isDrawing = false;

        if (currentShape === 'poly') {
            finalizeLasso();
        } else {
            convertToOriginalCoords();
            if (cropBox.width > 2 && cropBox.height > 2) {
                enableActions();
            } else {
                disableActions("Chưa chọn (Kích thước quá bé)");
            }
        }
    });
}

function finalizeLasso() {
    if (lassoPoints.length < 3) {
        disableActions("Chưa chọn (Vẽ ít nhất 3 điểm)");
        lassoPoints = [];
        drawSelection();
        return;
    }
    // bbox of lasso in canvas coords
    const xs = lassoPoints.map(p => p.x);
    const ys = lassoPoints.map(p => p.y);
    cropBox.x = Math.min(...xs);
    cropBox.y = Math.min(...ys);
    cropBox.width = Math.max(...xs) - cropBox.x;
    cropBox.height = Math.max(...ys) - cropBox.y;

    // convert bbox + all points to original coords
    convertToOriginalCoords();
    const scaleX = originalWidth / selectionCanvas.width;
    const scaleY = originalHeight / selectionCanvas.height;
    lassoOrigPoints = lassoPoints.map(p => [
        Math.round(p.x * scaleX), Math.round(p.y * scaleY)
    ]);

    drawSelection();
    updateCoordDisplay();
    if (cropBox.width > 2 && cropBox.height > 2) enableActions();
    else disableActions("Chưa chọn (Vùng quá bé)");
}

function enableActions() {
    btnProcess.disabled = false;
    if (btnProcessBatch) btnProcessBatch.disabled = !isPinned;
    if (btnPreview) btnPreview.disabled = false;
    schedulePreview();
}
function disableActions(msg) {
    btnProcess.disabled = true;
    if (btnProcessBatch) btnProcessBatch.disabled = true;
    if (btnPreview) btnPreview.disabled = true;
    if (msg) coordDisplay.innerText = msg;
}

// Convert drawn bbox (canvas-buffer coords) to original video dimensions
function convertToOriginalCoords() {
    const scaleX = originalWidth / selectionCanvas.width;
    const scaleY = originalHeight / selectionCanvas.height;

    cropBox.origX = Math.round(cropBox.x * scaleX);
    cropBox.origY = Math.round(cropBox.y * scaleY);
    cropBox.origWidth = Math.round(cropBox.width * scaleX);
    cropBox.origHeight = Math.round(cropBox.height * scaleY);
}

// Draw the selection (shape-aware)
function drawSelection() {
    ctx.clearRect(0, 0, selectionCanvas.width, selectionCanvas.height);

    const fill = 'rgba(139, 92, 246, 0.3)';
    const stroke = '#8b5cf6';
    ctx.fillStyle = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 2;

    if (currentShape === 'poly') {
        if (lassoPoints.length >= 2) {
            ctx.beginPath();
            ctx.moveTo(lassoPoints[0].x, lassoPoints[0].y);
            for (let i = 1; i < lassoPoints.length; i++) {
                ctx.lineTo(lassoPoints[i].x, lassoPoints[i].y);
            }
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }
        return;
    }

    if (cropBox.width > 0 && cropBox.height > 0) {
        const { x, y, width, height } = cropBox;
        if (currentShape === 'diamond') {
            const cx = x + width / 2, cy = y + height / 2;
            ctx.beginPath();
            ctx.moveTo(cx, y);
            ctx.lineTo(x + width, cy);
            ctx.lineTo(cx, y + height);
            ctx.lineTo(x, cy);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        } else if (currentShape === 'ellipse') {
            ctx.beginPath();
            ctx.ellipse(x + width / 2, y + height / 2, width / 2, height / 2, 0, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        } else { // rect
            ctx.fillRect(x, y, width, height);
            ctx.strokeRect(x, y, width, height);
        }

        // corner dots (bbox)
        ctx.fillStyle = '#06b6d4';
        ctx.fillRect(x - 3, y - 3, 6, 6);
        ctx.fillRect(x + width - 3, y - 3, 6, 6);
        ctx.fillRect(x - 3, y + height - 3, 6, 6);
        ctx.fillRect(x + width - 3, y + height - 3, 6, 6);
    }
}

// Update coordinate representation string
function updateCoordDisplay() {
    if (cropBox.width > 0) {
        const scaleX = originalWidth / (selectionCanvas.width || 1);
        const scaleY = originalHeight / (selectionCanvas.height || 1);

        const ox = Math.round(cropBox.x * scaleX);
        const oy = Math.round(cropBox.y * scaleY);
        const ow = Math.round(cropBox.width * scaleX);
        const oh = Math.round(cropBox.height * scaleY);

        const shapeNames = { rect: 'Vuông', diamond: 'Thoi', ellipse: 'Tròn', poly: 'Custom' };
        coordDisplay.innerText = `[${shapeNames[currentShape]}] ${ox}, ${oy} (${ow}x${oh}px)`;
    } else {
        coordDisplay.innerText = "Chưa chọn";
    }
}

// Shape selector buttons
function setupShapeListeners() {
    document.querySelectorAll('.shape-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.shape-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentShape = btn.dataset.shape;

            // Switching to/from lasso clears the current selection
            resetSelection();
            disableActions(null);

            if (canvasHint) {
                canvasHint.innerText = currentShape === 'poly'
                    ? 'Giữ chuột và vẽ tự do quanh logo, thả chuột để đóng vùng'
                    : 'Kéo thả chuột để vẽ vùng watermark theo hình đã chọn';
            }
        });
    });
}

// Setup listeners for VEO and VieON presets
function setupPresetListeners() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (!selectedVideo) return;
            const preset = btn.dataset.preset;

            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Presets define a rectangle in original coords
            let ox, oy, ow, oh;
            if (preset === 'veo-text') {
                ow = originalWidth * 0.08;
                oh = originalWidth * 0.04;
                ox = originalWidth - ow - (originalWidth * 0.02);
                oy = originalHeight - oh - (originalHeight * 0.02);
            } else { // vieon-star
                ow = originalWidth * 0.08;
                oh = originalWidth * 0.08;
                ox = originalWidth - ow - (originalWidth * 0.02);
                oy = originalHeight - oh - (originalHeight * 0.20);
            }

            // place into canvas-buffer coords
            const scaleX = selectionCanvas.width / originalWidth;
            const scaleY = selectionCanvas.height / originalHeight;
            cropBox.x = ox * scaleX;
            cropBox.y = oy * scaleY;
            cropBox.width = ow * scaleX;
            cropBox.height = oh * scaleY;

            // presets are rectangular regions
            if (currentShape === 'poly') {
                document.querySelector('.shape-btn[data-shape="rect"]').click();
                // re-apply after reset
                cropBox.x = ox * scaleX; cropBox.y = oy * scaleY;
                cropBox.width = ow * scaleX; cropBox.height = oh * scaleY;
            }

            convertToOriginalCoords();
            drawSelection();
            updateCoordDisplay();
            enableActions();
        });
    });
}

// Call API to run auto variance-based watermark detection
async function runAutoDetection() {
    if (!selectedVideo) return;

    detectStatus.classList.remove('hidden');
    btnDetect.disabled = true;

    try {
        const res = await fetch('/api/detect_watermark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_name: selectedVideo })
        });
        const data = await res.json();

        detectStatus.classList.add('hidden');
        btnDetect.disabled = false;

        if (data.success && data.detected && data.detected.length > 0) {
            const wmark = data.detected[0];
            const bbox = wmark.bbox;

            const scaleX = selectionCanvas.width / originalWidth;
            const scaleY = selectionCanvas.height / originalHeight;

            const pad = 5;
            const px1 = Math.max(0, bbox.x - pad);
            const py1 = Math.max(0, bbox.y - pad);
            const px2 = Math.min(originalWidth, bbox.x + bbox.width + pad);
            const py2 = Math.min(originalHeight, bbox.y + bbox.height + pad);

            cropBox.x = px1 * scaleX;
            cropBox.y = py1 * scaleY;
            cropBox.width = (px2 - px1) * scaleX;
            cropBox.height = (py2 - py1) * scaleY;

            convertToOriginalCoords();
            drawSelection();
            updateCoordDisplay();
            enableActions();

            alert(`Đã tự động phát hiện watermark ở ${wmark.corner}!`);
        } else {
            alert("Không tìm thấy watermark tự động. Vui lòng tự vẽ vùng chọn bằng chuột.");
        }
    } catch (err) {
        detectStatus.classList.add('hidden');
        btnDetect.disabled = false;
        alert("Lỗi kết nối tới server khi quét watermark");
    }
}

// Build the shape payload sent to the backend
function buildShapePayload() {
    const method = document.querySelector('input[name="method"]:checked').value;
    const payload = {
        video_name: selectedVideo,
        x: cropBox.origX,
        y: cropBox.origY,
        width: cropBox.origWidth,
        height: cropBox.origHeight,
        shape: currentShape,
        method: method,
        sensitivity: currentSensitivity,
        params: collectParams()
    };
    if (currentShape === 'poly') payload.points = lassoOrigPoints;
    return payload;
}

// Render a before/after preview using the current method + slider params
async function runPreview(silent) {
    if (!selectedVideo || cropBox.width <= 0) return;

    baPreview.classList.remove('hidden');
    baLoading.classList.remove('hidden');
    if (!silent) {
        btnPreview.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang tạo preview...';
        btnPreview.disabled = true;
    }

    try {
        const res = await fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildShapePayload())
        });
        const data = await res.json();

        baLoading.classList.add('hidden');
        btnPreview.innerHTML = '<i class="fa-solid fa-images"></i> Tạo / Cập nhật Preview';
        btnPreview.disabled = false;

        if (data.success) {
            const bustBefore = data.before_url.startsWith('file:') ? '' : '?t=' + Date.now();
            const bustAfter = data.after_url.startsWith('file:') ? '' : '?t=' + Date.now();
            
            const imgBefore = new Image();
            imgBefore.onload = () => baBefore.src = imgBefore.src;
            imgBefore.src = data.before_url + bustBefore;
            
            const imgAfter = new Image();
            imgAfter.onload = () => baAfter.src = imgAfter.src;
            imgAfter.src = data.after_url + bustAfter;
            if (data.stats) {
                baStats.innerText =
                    `Alpha TB: ${data.stats.alpha_mean} · Phủ: ${data.stats.static_percent}%`;
            } else {
                baStats.innerText = '';
            }
        } else if (!silent) {
            showToast(`Lỗi preview: ${data.error}`, 'error', 6000);
        }
    } catch (err) {
        baLoading.classList.add('hidden');
        btnPreview.innerHTML = '<i class="fa-solid fa-images"></i> Tạo / Cập nhật Preview';
        btnPreview.disabled = false;
        if (!silent) alert("Lỗi kết nối tới server khi tạo preview");
    }
}

// Process — route to image (sync) or video (async) endpoint
async function startProcessing() {
    if (!selectedVideo || cropBox.width <= 0) return;

    if (currentFileType === 'image') {
        await processImage();
    } else {
        await processVideo();
    }
}

async function processImage() {
    progressVideoName.innerText = `Ảnh: ${selectedVideo}`;
    progressBarFill.style.width = '60%';
    progressText.innerText = '—';
    progressModalEl.classList.remove('hidden');

    try {
        const res = await fetch('/api/process_image', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildShapePayload())
        });
        const data = await res.json();
        if (data.success) {
            showResultPreview(data.output_name);
            if (isBatchProcessing) {
                runNextBatchItem();
            } else {
                progressModalEl.classList.add('hidden');
                loadVideos();
            }
        } else {
            alert(`Lỗi xử lý ảnh: ${data.error}`);
            if (isBatchProcessing) {
                runNextBatchItem();
            } else {
                progressModalEl.classList.add('hidden');
            }
        }
    } catch (err) {
        alert("Lỗi kết nối tới server");
        if (isBatchProcessing) {
            runNextBatchItem();
        } else {
            progressModalEl.classList.add('hidden');
        }
    }
}

async function processVideo() {
    progressVideoName.innerText = `Video: ${selectedVideo}`;
    progressBarFill.style.width = '0%';
    progressText.innerText = '0';
    progressModalEl.classList.remove('hidden');

    try {
        const payload = buildShapePayload();
        const res = await fetch('/api/process', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            pollStatus(data.task_id);
        } else {
            if (!isBatchProcessing) progressModalEl.classList.add('hidden');
            alert(`Lỗi bắt đầu xử lý: ${data.error}`);
            if (isBatchProcessing) {
                runNextBatchItem();
            }
        }
    } catch (err) {
        if (!isBatchProcessing) progressModalEl.classList.add('hidden');
        alert("Lỗi kết nối tới server khi gửi yêu cầu xử lý");
        if (isBatchProcessing) {
            runNextBatchItem();
        }
    }
}

// Poll processing progress from API
function pollStatus(taskId) {
    console.log("[RUNTIME_HOOK] pollStatus called with taskId:", taskId);
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${taskId}`);
            const data = await res.json();
            console.log("[RUNTIME_HOOK] pollStatus interval, status:", data.success ? data.task.status : "fail");

            if (data.success) {
                const task = data.task;

                if (task.status === 'processing' || task.status === 'analyzing') {
                    progressBarFill.style.width = `${task.progress}%`;
                    progressText.innerText = task.progress;
                } else if (task.status === 'completed') {
                    console.log("[RUNTIME_HOOK] Task completed, calling showResultPreview with:", task.output_name);
                    clearInterval(pollInterval);
                    
                    if (task.output_path) {
                        const pathStr = task.output_path.replace(/\\/g, '/');
                        // FAIL LINE FOUND: Trình duyệt chặn scheme file:/// do lỗi bảo mật CORS/Local Content
                        // Bỏ qua dòng gán file:/// này để hệ thống fallback về '/uploads/' qua HTTP server.
                        // window.NAV_UPLOADS_URL = "file:///" + pathStr.substring(0, pathStr.lastIndexOf('/'));
                    }
                    showResultPreview(task.output_name);
                    runPreview(true);
                    
                    if (isBatchProcessing) {
                        runNextBatchItem();
                    } else {
                        progressVideoName.innerText = 'Đã hoàn thành xử lý!';
                        progressBarFill.style.width = '100%';
                        progressText.innerText = '100';
                        loadVideos();
                        
                        // Create and show a 'Đóng' button if not exists
                        let btnClose = document.getElementById('btn-close-single');
                        if (!btnClose) {
                            const btnGroup = document.createElement('div');
                            btnGroup.style = 'display: flex; justify-content: center; margin-top: 15px;';
                            btnClose = document.createElement('button');
                            btnClose.id = 'btn-close-single';
                            btnClose.className = 'btn btn-primary';
                            btnClose.innerHTML = '<i class="fa-solid fa-check"></i> Đóng';
                            btnClose.onclick = () => {
                                progressModalEl.classList.add('hidden');
                                btnGroup.remove(); // Remove it so it doesn't duplicate
                            };
                            btnGroup.appendChild(btnClose);
                            progressModalEl.querySelector('.modal-card').appendChild(btnGroup);
                        }
                    }
                } else if (task.status === 'failed') {
                    clearInterval(pollInterval);
                    if (!isBatchProcessing) progressModalEl.classList.add('hidden');
                    console.error(`Quá trình xử lý thất bại: ${task.error}`);
                    if (isBatchProcessing) {
                        runNextBatchItem();
                    } else {
                        alert(`Quá trình xử lý thất bại: ${task.error}`);
                    }
                }
            } else {
                clearInterval(pollInterval);
                progressModalEl.classList.add('hidden');
                alert(`Lỗi check tiến độ: ${data.error}`);
            }
        } catch (err) {
            console.error("Polling error", err);
        }
    }, 500);
}

// ---------------------------------------------------------------------------
// Batch Processing Logic
// ---------------------------------------------------------------------------
async function startBatchProcessing() {
    if (videos.length === 0 || cropBox.width <= 0) return;
    
    // Thu thập danh sách các video
    batchQueue = [...videos];
    isBatchProcessing = true;
    currentBatchIndex = 0;
    cancelBatch = false;
    
    if (btnCancelBatch) {
        btnCancelBatch.disabled = false;
        btnCancelBatch.innerHTML = '<i class="fa-solid fa-xmark"></i> Hủy xóa hàng loạt';
    }
    
    runNextBatchItem();
}

async function runNextBatchItem() {
    if (cancelBatch || currentBatchIndex >= batchQueue.length) {
        // Finish batch
        isBatchProcessing = false;
        if (cancelBatch) {
            progressModalEl.classList.add('hidden');
            progressBatchText.style.display = 'none';
            batchActions.style.display = 'none';
            alert('Đã hủy quá trình xóa hàng loạt.');
        } else {
            // Success end of batch
            progressVideoName.innerText = 'Đã hoàn thành toàn bộ danh sách!';
            progressBarFill.style.width = '100%';
            progressText.innerText = '100';
            progressBatchText.style.display = 'none';
            
            if (btnCancelBatch) {
                btnCancelBatch.classList.remove('btn-secondary');
                btnCancelBatch.classList.add('btn-primary');
                btnCancelBatch.innerHTML = '<i class="fa-solid fa-check"></i> Hoàn thành';
                btnCancelBatch.disabled = false;
                
                // Override onclick behavior to just close the modal
                btnCancelBatch.onclick = function() {
                    progressModalEl.classList.add('hidden');
                    batchActions.style.display = 'none';
                    // Reset styling for future uses
                    btnCancelBatch.classList.remove('btn-primary');
                    btnCancelBatch.classList.add('btn-secondary');
                    btnCancelBatch.innerHTML = '<i class="fa-solid fa-xmark"></i> Hủy xóa hàng loạt';
                    btnCancelBatch.onclick = () => {
                        if (confirm('Bạn có chắc chắn muốn hủy bỏ tiến trình xóa hàng loạt? Các video đã xong sẽ được giữ lại, các video chưa xử lý sẽ bị hủy.')) {
                            cancelBatch = true;
                            progressModalEl.classList.add('hidden');
                            batchActions.style.display = 'none';
                            alert('Đã hủy xóa hàng loạt! LƯU Ý: Nếu có 1 video đang chạy dở, nó sẽ chạy ngầm cho xong rồi dừng hẳn.');
                        }
                    };
                };
            }
            loadVideos();
        }
        return;
    }
    
    // Setup UI for current item
    const currentVideo = batchQueue[currentBatchIndex];
    
    // Convert canvas coords back to original to ensure payload has latest
    convertToOriginalCoords();
    
    progressBatchText.style.display = 'block';
    batchActions.style.display = 'flex';
    progressBatchText.innerText = `Đang xử lý file ${currentBatchIndex + 1} / ${batchQueue.length}`;
    
    // Update selected video for the payload builder
    selectedVideo = currentVideo.name;
    
    const ext = currentVideo.name.split('.').pop().toLowerCase();
    const isImg = ['jpg', 'jpeg', 'png', 'webp', 'bmp'].includes(ext);
    currentFileType = isImg ? 'image' : 'video';
    
    // Update the background "Before" preview
    const li = document.querySelector(`.video-list li[data-name="${CSS.escape(currentVideo.name)}"]`);
    if (li) {
        await selectVideo(currentVideo.name, li);
    }
    
    currentBatchIndex++;
    
    // Trigger process
    if (isImg) {
        await processImage();
    } else {
        await processVideo();
    }
}

function showResultPreview(outputName) {
    console.log("[RUNTIME_HOOK] showResultPreview start:", outputName);
    const sideBySide = document.getElementById('side-by-side-result');
    const btnDownload = document.getElementById('btn-download-result');
    
    if (btnDownload) {
        btnDownload.href = `/api/download/${encodeURIComponent(outputName)}`;
    }
    
    if (!sideBySide) return;

    const ext = outputName.split('.').pop().toLowerCase();
    const isVideo = ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext);

    const baseUrl = window.NAV_UPLOADS_URL ? window.NAV_UPLOADS_URL + '/' : '/uploads/';
    const suffix = baseUrl.startsWith('file:') ? '' : `?t=${Date.now()}`;
    const mediaSrc = `${baseUrl}${outputName}${suffix}`;
    console.log("[RUNTIME_HOOK] showResultPreview mediaSrc:", mediaSrc);
    
    if (isVideo) {
        let safeMediaSrc = mediaSrc;
        try { safeMediaSrc = encodeURI(mediaSrc); } catch (e) {}

        // Show loading state to prevent flash of empty video player
        sideBySide.innerHTML = `<div style="display:flex; flex-direction:column; align-items:center; color:var(--text-secondary);"><i class="fa-solid fa-circle-notch fa-spin" style="font-size:2rem; margin-bottom:10px;"></i> Đang tải video kết quả...</div>`;
        sideBySide.classList.remove('hidden');

        const renderFinalVideo = (srcUrl) => {
            sideBySide.innerHTML = `
                <video src="${srcUrl}" controls autoplay loop muted style="max-width:100%; max-height:450px; border-radius:8px;"></video>
                <div style="margin-top: 15px;">
                    <a href="#" onclick="openFolder('${outputName}', this); return false;" class="btn btn-primary" style="display:inline-flex; align-items:center; justify-content:center; padding:10px 20px; font-size:1rem;">
                        <i class="fa-solid fa-folder-open" style="margin-right:8px;"></i> Mở Thư mục
                    </a>
                </div>
            `;
        };

        fetch(safeMediaSrc, { cache: 'no-store' })
            .then(res => {
                if (!res.ok) throw new Error("Fetch failed: " + res.status);
                return res.blob();
            })
            .then(blob => {
                const objUrl = URL.createObjectURL(blob);
                renderFinalVideo(objUrl);
            })
            .catch(err => {
                console.error("Blob fetch error, falling back to direct src:", err);
                renderFinalVideo(safeMediaSrc);
            });
    } else {
        sideBySide.innerHTML = `
            <img src="${mediaSrc}" style="max-width:100%; max-height:450px; object-fit:contain; border-radius:8px;">
            <div style="margin-top: 15px;">
                <a href="#" onclick="openFolder('${outputName}', this); return false;" class="btn btn-primary" style="display:inline-flex; align-items:center; justify-content:center; padding:10px 20px; font-size:1rem;">
                    <i class="fa-solid fa-folder-open" style="margin-right:8px;"></i> Mở Thư mục
                </a>
            </div>
        `;
        sideBySide.classList.remove('hidden');
    }
    
    // Resize canvas to adjust side-by-side view ratio
    setTimeout(resizeCanvas, 100);
}


function openFolder(filename, btnElement = null) {
    if (btnElement) {
        const originalHtml = btnElement.innerHTML;
        btnElement.innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="margin-right:8px;"></i> Đang mở...`;
        btnElement.style.pointerEvents = 'none';
        setTimeout(() => {
            btnElement.innerHTML = originalHtml;
            btnElement.style.pointerEvents = 'auto';
        }, 1000);
    }
    fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: filename || null })
    }).catch(e => console.error(e));
}

document.addEventListener("DOMContentLoaded", function() {
    const btnDownloadAll = document.getElementById("btn-download-all");
    if (btnDownloadAll) {
        btnDownloadAll.addEventListener("click", function(e) {
            e.preventDefault();
            openFolder(null);
        });
    }
});
