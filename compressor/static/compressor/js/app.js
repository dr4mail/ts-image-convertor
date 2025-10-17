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
            <span class="text-gray-500 ml-2">${(file.size / (1024*1024)).toFixed(2)} MB</span>
        `;
        fileItems.appendChild(div);
    });
    
    fileCount.textContent = selectedFiles.length;
    totalSize.textContent = (totalBytes / (1024*1024)).toFixed(2);
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
    
    compressBtn.disabled = true;
    compressBtn.textContent = 'Uploading...';
    
    try {
        // Загружаем файлы
        await uploadFiles();
        
        // Запускаем сжатие
        await startCompression();
        
        // Показываем прогресс
        settingsSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        
        // Отображаем настройки
        displayActiveSettings();
        
        // Мониторим прогресс
        monitorProgress();
        
    } catch (error) {
        alert('Error: ' + error.message);
        compressBtn.disabled = false;
        compressBtn.textContent = '🗜️ Compress & Download Archive';
    }
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

// Загрузка файлов
async function uploadFiles() {
    const formData = new FormData();
    
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });
    
    const archiveName = document.getElementById('archive-name').value.trim();
    formData.append('prefix', archiveName);
    formData.append('settings', JSON.stringify(compressionSettings));
    
    const response = await fetch('/api/upload/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken
        },
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Upload failed');
    }
    
    const data = await response.json();
    sessionId = data.session_id;
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
    progressSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    
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
    fileList.classList.add('hidden');
    settingsSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    
    compressBtn.disabled = false;
    compressBtn.textContent = '🗜️ Compress & Download Archive';
    
    // Сброс настроек
    document.querySelector('input[name="quality-mode"][value="auto"]').checked = true;
    document.querySelector('input[name="resize-mode"][value="auto"]').checked = true;
    document.getElementById('quality-input').disabled = true;
    document.getElementById('dimension-input').disabled = true;
    document.getElementById('archive-name').value = '';
}