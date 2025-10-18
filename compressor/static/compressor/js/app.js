// Функция для получения CSRF токена из cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// Состояние приложения
let selectedFiles = [];
let sessionId = null;
let compressionSettings = {
    quality: null,
    max_dimension: null,
    no_resize: false
};

// DOM элементы
const dropZone = document.getElementById('drop-zone');
const uploadSection = document.getElementById('upload-section');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const fileItems = document.getElementById('file-items');
const fileCount = document.getElementById('file-count');
const totalSize = document.getElementById('total-size');
const settingsSection = document.getElementById('settings-section');
const compressBtn = document.getElementById('compress-btn');
const progressSection = document.getElementById('progress-section');
const resultsSection = document.getElementById('results-section');
const downloadBtn = document.getElementById('download-btn');
const resetBtn = document.getElementById('reset-btn');
const uploadProgressSection = document.getElementById('upload-progress-section');
const uploadProgressBar = document.getElementById('upload-progress-bar');
const uploadProgressPercent = document.getElementById('upload-progress-percent');
const uploadProgressText = document.getElementById('upload-progress-text');
const uploadBytes = document.getElementById('upload-bytes');
const uploadCancelBtn = document.getElementById('upload-cancel-btn');

// Управление состоянием загрузки
let isUploading = false;
let currentUploadXhr = null;
let canceledByUser = false;

// Drag & Drop
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-blue-500', 'bg-blue-50');
});
dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-blue-500', 'bg-blue-50');
});
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-blue-500', 'bg-blue-50');
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

// Обработка выбранных файлов
function handleFiles(files) {
    if (files.length > 30) {
        alert('Maximum 30 files allowed!');
        return;
    }

    selectedFiles = Array.from(files);
    displayFileList();
    settingsSection.classList.remove('hidden');
}

// Отображение списка файлов
function displayFileList() {
    fileItems.innerHTML = '';
    let totalBytes = 0;

    selectedFiles.forEach(file => {
        totalBytes += file.size;
        const div = document.createElement('div');
        div.className = 'flex justify-between items-center text-sm bg-gray-50 p-2 rounded';
        div.innerHTML = `
            <span class="truncate">${file.name}</span>
            <span class="text-gray-500 ml-2">${(file.size / (1024 * 1024)).toFixed(2)} MB</span>
        `;
        fileItems.appendChild(div);
    });

    fileCount.textContent = selectedFiles.length;
    totalSize.textContent = (totalBytes / (1024 * 1024)).toFixed(2);
    fileList.classList.remove('hidden');
}

// Настройки сжатия - Quality
document.querySelectorAll('input[name="quality-mode"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const qualityInput = document.getElementById('quality-input');
        if (e.target.value === 'auto') {
            compressionSettings.quality = null;
            qualityInput.disabled = true;
        } else {
            compressionSettings.quality = parseInt(qualityInput.value);
            qualityInput.disabled = false;
        }
    });
});

document.getElementById('quality-input').addEventListener('input', (e) => {
    compressionSettings.quality = parseInt(e.target.value);
});

// Настройки сжатия - Resolution
document.querySelectorAll('input[name="resize-mode"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const dimensionInput = document.getElementById('dimension-input');
        if (e.target.value === 'auto') {
            compressionSettings.no_resize = false;
            compressionSettings.max_dimension = null;
            dimensionInput.disabled = true;
        } else if (e.target.value === 'custom') {
            compressionSettings.no_resize = false;
            compressionSettings.max_dimension = parseInt(dimensionInput.value);
            dimensionInput.disabled = false;
        } else { // keep-original
            compressionSettings.no_resize = true;
            compressionSettings.max_dimension = null;
            dimensionInput.disabled = true;
        }
    });
});

document.getElementById('dimension-input').addEventListener('input', (e) => {
    compressionSettings.max_dimension = parseInt(e.target.value);
});

// Кнопка сжатия
compressBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) {
        alert('Please select files first!');
        return;
    }

    if (isUploading) {
        return; // игнор повторного нажатия во время загрузки
    }
    isUploading = true;
    compressBtn.disabled = true;
    compressBtn.textContent = 'Uploading...';
    if (uploadSection) uploadSection.classList.add('hidden');
    uploadProgressSection.classList.remove('hidden');
    uploadProgressBar.style.width = '0%';
    uploadProgressPercent.textContent = '0%';
    uploadProgressText.textContent = 'Starting upload...';
    uploadBytes.textContent = '';
    // блокируем выбор файлов на время загрузки
    fileInput.disabled = true;
    dropZone.classList.add('pointer-events-none', 'opacity-60');

    try {
        // Загружаем файлы с прогрессом
        await uploadFiles();

        // Запускаем сжатие
        await startCompression();

        // Показываем прогресс обработки (после загрузки)
        settingsSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        uploadProgressSection.classList.add('hidden');

        // Отображаем настройки
        displayActiveSettings();

        // Мониторим прогресс
        monitorProgress();

    } catch (error) {
        if (error && error.message === '__upload_aborted__') {
            // тишина при отмене пользователем
        } else {
            alert('Error: ' + (error && error.message ? error.message : 'Upload failed'));
        }
        compressBtn.disabled = false;
        compressBtn.textContent = '🗜️ Compress & Download Archive';
        uploadProgressSection.classList.add('hidden');
        if (uploadSection) uploadSection.classList.remove('hidden');
    }
    // снимаем блокировки вне зависимости от результата
    isUploading = false;
    fileInput.disabled = false;
    dropZone.classList.remove('pointer-events-none', 'opacity-60');
    canceledByUser = false;
});

// Отображение активных настроек
function displayActiveSettings() {
    const settingsDisplay = document.getElementById('settings-display');
    let text = 'Settings: ';

    if (compressionSettings.quality !== null) {
        text += `Quality ${compressionSettings.quality}%`;
    } else {
        text += 'Auto quality';
    }

    text += ' | ';

    if (compressionSettings.no_resize) {
        text += 'Original size';
    } else if (compressionSettings.max_dimension !== null) {
        text += `Max ${compressionSettings.max_dimension}px`;
    } else {
        text += 'Auto resize';
    }

    settingsDisplay.textContent = text;
}

// Загрузка файлов с индикацией прогресса
async function uploadFiles() {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        selectedFiles.forEach(file => formData.append('files', file));
        const archiveName = document.getElementById('archive-name').value.trim();
        formData.append('prefix', archiveName);
        formData.append('settings', JSON.stringify(compressionSettings));

        const xhr = new XMLHttpRequest();
        currentUploadXhr = xhr;
        xhr.open('POST', '/api/upload/');
        xhr.setRequestHeader('X-CSRFToken', csrftoken);
        xhr.timeout = 15 * 60 * 1000; // 15 минут на крупные загрузки

        // Предварительно посчитаем общий размер файлов и кумулятивные границы, чтобы показывать текущий файл и счетчик
        const fileSizes = selectedFiles.map(f => f.size);
        const totalFilesBytes = fileSizes.reduce((a, b) => a + b, 0);
        const cumulative = [];
        fileSizes.reduce((sum, s, i) => {
            const next = sum + s;
            cumulative[i] = next;
            return next;
        }, 0);

        xhr.upload.onprogress = (e) => {
            if (!e.lengthComputable) return;
            const percent = Math.round((e.loaded / e.total) * 100);
            uploadProgressBar.style.width = percent + '%';
            uploadProgressPercent.textContent = percent + '%';
            // Оценим текущий файл по сумме загруженных байт, ограничив до суммы файлов (без учета оверхеда multipart)
            const loadedClamped = Math.min(e.loaded, totalFilesBytes);
            let idx = 0;
            while (idx < cumulative.length && loadedClamped > cumulative[idx]) idx++;
            const currentIndex = Math.min(idx, selectedFiles.length - 1);
            const currentName = selectedFiles[currentIndex] ? selectedFiles[currentIndex].name : '';
            uploadProgressText.textContent = `Uploading ${currentIndex + 1}/${selectedFiles.length}: ${currentName}`;
            const loadedMb = (e.loaded / (1024 * 1024)).toFixed(1);
            const totalMb = (e.total / (1024 * 1024)).toFixed(1);
            uploadBytes.textContent = `${loadedMb} MB / ${totalMb} MB`;
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    sessionId = data.session_id;
                    resolve();
                } catch (err) {
                    reject(new Error('Invalid server response'));
                }
            } else {
                try {
                    const data = JSON.parse(xhr.responseText);
                    reject(new Error(data.error || 'Upload failed'));
                } catch (err) {
                    reject(new Error('Upload failed'));
                }
            }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.onabort = () => reject(new Error('__upload_aborted__'));
        xhr.ontimeout = () => reject(new Error('Upload timeout'));
        xhr.onloadend = () => { currentUploadXhr = null; };

        xhr.send(formData);
    });
}

// Отмена загрузки
if (uploadCancelBtn) {
    uploadCancelBtn.addEventListener('click', () => {
        if (currentUploadXhr) {
            try { currentUploadXhr.abort(); } catch (e) { }
        }
        // если уже создана сессия, попросим сервер очистить временные файлы и запись в БД
        if (sessionId) {
            fetch(`/api/session/${sessionId}/cancel/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken }
            }).catch(() => { });
            sessionId = null;
        }
        // Сброс UI
        uploadProgressSection.classList.add('hidden');
        uploadProgressBar.style.width = '0%';
        uploadProgressPercent.textContent = '0%';
        uploadProgressText.textContent = 'Canceled';
        uploadBytes.textContent = '';
        if (uploadSection) uploadSection.classList.remove('hidden');
        compressBtn.disabled = false;
        compressBtn.textContent = '🗜️ Compress & Download Archive';
        isUploading = false;
        fileInput.disabled = false;
        dropZone.classList.remove('pointer-events-none', 'opacity-60');
        // показать список файлов, если был скрыт, и оставить выбранные файлы без очистки
        if (selectedFiles && selectedFiles.length > 0) {
            const fileList = document.getElementById('file-list');
            if (fileList) fileList.classList.remove('hidden');
        }
        canceledByUser = true;
    });
}

// Запуск сжатия
async function startCompression() {
    const response = await fetch(`/api/compress/${sessionId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Compression failed to start');
    }
}

// Мониторинг прогресса
function monitorProgress() {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${sessionId}/`);
            const data = await response.json();

            updateProgressBar(data);

            if (data.stage === 'completed' && data.results) {
                clearInterval(interval);
                // на всякий случай скрываем upload-прогресс
                if (uploadProgressSection) uploadProgressSection.classList.add('hidden');
                showResults(data.results);
            } else if (data.results && data.results.status === 'error') {
                clearInterval(interval);
                alert('Error: ' + data.results.error);
                resetApp();
            }
        } catch (error) {
            console.error('Status check error:', error);
        }
    }, 500);
}

// Обновление прогресс-бара
function updateProgressBar(data) {
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const progressText = document.getElementById('progress-text');
    const currentFile = document.getElementById('current-file');

    const progress = data.progress || 0;
    progressBar.style.width = progress + '%';
    progressPercent.textContent = progress + '%';

    if (data.stage === 'compressing') {
        progressText.textContent = `Processing file ${data.index || 0} of ${data.total || 0}`;
        currentFile.textContent = `Current: ${data.current_file || ''}`;
    } else if (data.stage === 'archiving') {
        progressText.textContent = 'Creating archive...';
        currentFile.textContent = data.current_file || '';
    } else if (data.stage === 'completed') {
        progressText.textContent = 'Complete!';
        currentFile.textContent = '';
    }
}

// Показать результаты
function showResults(results) {
    // скрываем любые загрузочные секции
    if (uploadProgressSection) uploadProgressSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    // по требованию: скрываем секцию выбора файлов после завершения
    if (uploadSection) uploadSection.classList.add('hidden');
    fileList.classList.add('hidden');
    settingsSection.classList.add('hidden');

    const summary = document.getElementById('summary');
    const totalSavings = results.total_original_mb > 0
        ? ((1 - results.total_compressed_mb / results.total_original_mb) * 100).toFixed(1)
        : 0;

    let html = `
        <div class="bg-blue-50 border border-blue-200 rounded p-4">
            <p class="text-gray-700"><strong>Processed:</strong> ${results.successful}/${results.successful + results.failed} files</p>
            <p class="text-gray-700"><strong>Original size:</strong> ${results.total_original_mb.toFixed(1)} MB</p>
            <p class="text-gray-700"><strong>Compressed size:</strong> ${results.total_compressed_mb.toFixed(1)} MB</p>
            <p class="text-green-600 font-semibold"><strong>Total savings:</strong> ${totalSavings}%</p>
        </div>
    `;

    // По категориям
    if (Object.keys(results.categories).length > 0) {
        html += '<div class="mt-4"><p class="font-semibold text-gray-700 mb-2">By category:</p><div class="space-y-1">';
        for (const [category, stats] of Object.entries(results.categories)) {
            const savings = stats.savings || 0;
            html += `<p class="text-sm text-gray-600">• ${category}: ${stats.count} files (${savings.toFixed(1)}% savings)</p>`;
        }
        html += '</div></div>';
    }

    summary.innerHTML = html;
}

// Кнопка скачивания
downloadBtn.addEventListener('click', () => {
    window.location.href = `/api/download/${sessionId}/`;
});

// Кнопка сброса
resetBtn.addEventListener('click', resetApp);

function resetApp() {
    selectedFiles = [];
    sessionId = null;
    compressionSettings = {
        quality: null,
        max_dimension: null,
        no_resize: false
    };

    fileInput.value = '';
    if (uploadSection) uploadSection.classList.remove('hidden');
    fileList.classList.add('hidden');
    settingsSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    uploadProgressSection.classList.add('hidden');

    compressBtn.disabled = false;
    compressBtn.textContent = '🗜️ Compress & Download Archive';

    // Сброс настроек
    document.querySelector('input[name="quality-mode"][value="auto"]').checked = true;
    document.querySelector('input[name="resize-mode"][value="auto"]').checked = true;
    document.getElementById('quality-input').disabled = true;
    document.getElementById('dimension-input').disabled = true;
    document.getElementById('archive-name').value = '';
}