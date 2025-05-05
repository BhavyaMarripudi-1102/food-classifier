// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // ======================
    // 1. Tab Switching
    // ======================
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Activate clicked tab
            btn.classList.add('active');
            const tabId = btn.dataset.tab + '-tab';
            document.getElementById(tabId).classList.add('active');
            
            // Initialize camera if on camera tab
            if (btn.dataset.tab === 'camera') {
                initializeCamera();
            }
        });
    });

    // ======================
    // 2. Camera Functionality
    // ======================
    let stream = null;
    
    function initializeCamera() {
        const video = document.getElementById('camera-feed');
        const canvas = document.getElementById('camera-canvas');
        const captureBtn = document.getElementById('capture-btn');
        
        // Check if already initialized
        if (stream) return;
        
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(s => {
                stream = s;
                video.srcObject = stream;
                captureBtn.style.display = 'block';
            })
            .catch(err => {
                console.error("Camera error:", err);
                document.getElementById('camera-tab').innerHTML = `
                    <div class="camera-error">
                        <p>Camera access denied. Please use upload or URL instead.</p>
                    </div>
                `;
            });
    }

    // Capture photo from camera
    document.getElementById('capture-btn')?.addEventListener('click', function() {
        const video = document.getElementById('camera-feed');
        const canvas = document.getElementById('camera-canvas');
        const form = document.getElementById('classifier-form');
        
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        
        // Convert to blob and submit
        canvas.toBlob(blob => {
            const file = new File([blob], 'capture.jpg', { type: 'image/jpeg' });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            
            // Replace file input
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.name = 'image_file';
            fileInput.files = dataTransfer.files;
            fileInput.style.display = 'none';
            
            form.appendChild(fileInput);
            form.submit();
        }, 'image/jpeg', 0.9);
    });

    // ======================
    // 3. Theme Switching
    // ======================
    const themeSwitch = document.querySelector('input[name="dark_mode"]');
    if (themeSwitch) {
        // Initialize from session
        themeSwitch.checked = document.documentElement.dataset.theme === 'dark';
        
        themeSwitch.addEventListener('change', function() {
            const isDark = this.checked;
            document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
            
            // Persist preference
            fetch('/update_theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dark_mode: isDark })
            });
        });
    }

    // ======================
    // 4. Form Handling
    // ======================
    const classifierForm = document.getElementById('classifier-form');
    if (classifierForm) {
        classifierForm.addEventListener('submit', function(e) {
            const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
            
            // Validate based on active tab
            if (activeTab === 'url') {
                const urlInput = this.elements['image_url'];
                if (!urlInput.value.startsWith('http')) {
                    e.preventDefault();
                    alert('Please enter a valid URL starting with http/https');
                }
            } else if (activeTab === 'upload') {
                if (!this.elements['image_file'].value) {
                    e.preventDefault();
                    alert('Please select an image file');
                }
            }
        });
    }

    // ======================
    // 5. History Actions
    // ======================
    // Confirm before clearing history
    document.querySelector('.btn.danger')?.addEventListener('click', function(e) {
        if (!confirm('Are you sure you want to clear all history?')) {
            e.preventDefault();
        }
    });

    // ======================
    // 6. Dynamic Nutrition Display
    // ======================
    function updateNutritionDisplay() {
        const portionSelect = document.getElementById('portion-size');
        if (!portionSelect) return;
        
        portionSelect.addEventListener('change', function() {
            const size = this.value;
            document.querySelectorAll('[data-nutrition]').forEach(el => {
                const nutrition = JSON.parse(el.dataset.nutrition);
                el.textContent = nutrition[size] || 'N/A';
            });
        });
    }
    updateNutritionDisplay();
});

// ======================
// 7. Utility Functions
// ======================
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        toast.addEventListener('transitionend', () => toast.remove());
    }, 3000);
}

// Initialize tooltips
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(el => {
        el.addEventListener('mouseenter', () => {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = el.dataset.tooltip;
            document.body.appendChild(tooltip);
            
            const rect = el.getBoundingClientRect();
            tooltip.style.left = `${rect.left + rect.width/2 - tooltip.offsetWidth/2}px`;
            tooltip.style.top = `${rect.top - tooltip.offsetHeight - 5}px`;
            
            el.addEventListener('mouseleave', () => tooltip.remove(), { once: true });
        });
    });
}
initTooltips();