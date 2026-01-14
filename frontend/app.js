/* ============================================================================
   Wall Clock - Ambient Theme with Sunrise/Sunset
   ============================================================================ */

// Configuration
const API_BASE = '';
const WS_URL = `ws://${window.location.host}/ws`;

// Default location (Creston, Iowa) - used if geolocation unavailable
const DEFAULT_LAT = 41.0586;
const DEFAULT_LNG = -94.3614;

// State
const state = {
    weather: null,
    calendar: { today: [], upcoming: [] },
    notes: null,
    todayCycleIndex: 1,      // Start at 1 (index 0 is pinned)
    upcomingCycleIndex: 1,   // Start at 1 (index 0 is pinned)
    theme: 'auto',           // Day/night theme
    bgTheme: 'flowcean',     // Background style theme
    holiday: null,           // Current holiday theme
    weatherFxEnabled: true,  // Weather particle effects
    currentWeatherEffect: 'none',
    isDaytime: true,
    sunTimes: null,
    location: { lat: DEFAULT_LAT, lng: DEFAULT_LNG },
    orientation: 'landscape', // Screen orientation mode
    touchMode: false,         // Kiosk touch mode (hides cursor)
    glassOpacity: 20,         // Glass panel opacity (0-100)
    glassMode: 'classic',     // Glass style: 'classic' or 'apple'
    // Spotify Connect (controls Raspotify/other devices)
    spotify: {
        connected: false,
        configured: false,
        isPlaying: false,
        track: null,
        error: null,
        deviceId: null,        // Active device ID
        volume: 0.5,           // Volume (0-1)
        position: 0,           // Current position in ms
        duration: 0,           // Track duration in ms
        progressInterval: null, // Interval for updating progress bar
        pollingInterval: null   // Interval for polling now playing
    }
};

// Spotify Connect mode - control Raspotify or other devices
// (Web Playback SDK removed - requires HTTPS which we don't have)

// ============================================================================
// Background Theme Management
// ============================================================================

function initBgTheme() {
    const saved = localStorage.getItem('clockie-bg-theme');
    if (saved) {
        state.bgTheme = saved;
    }
    applyBgTheme();
}

function setBgTheme(theme) {
    state.bgTheme = theme;
    localStorage.setItem('clockie-bg-theme', theme);
    applyBgTheme();
}

function applyBgTheme() {
    document.documentElement.setAttribute('data-bg-theme', state.bgTheme);
    console.log('Background theme:', state.bgTheme);
    
    // Handle photos theme
    if (state.bgTheme === 'photos') {
        initPhotoSlideshow();
    } else {
        stopPhotoSlideshow();
    }
}

// ============================================================================
// Photo Slideshow System
// ============================================================================

const photoState = {
    photos: [],
    currentIndex: 0,
    activeLayer: 1,
    slideshowInterval: null,
    preloadedImages: new Map(),
    intervalSeconds: 30  // Change photo every 30 seconds
};

async function initPhotoSlideshow() {
    console.log('Initializing photo slideshow...');
    
    try {
        const response = await fetch('/api/photos');
        const data = await response.json();
        photoState.photos = data.photos || [];
        
        const noPhotosMsg = document.getElementById('noPhotosMsg');
        
        if (photoState.photos.length === 0) {
            // Show no photos message
            if (noPhotosMsg) noPhotosMsg.style.display = 'flex';
            return;
        }
        
        if (noPhotosMsg) noPhotosMsg.style.display = 'none';
        
        // Shuffle photos for variety
        shuffleArray(photoState.photos);
        
        // Preload first few images
        preloadPhotos(0, 3);
        
        // Show first photo immediately
        photoState.currentIndex = 0;
        await showPhoto(photoState.currentIndex);
        
        // Start slideshow interval
        if (photoState.slideshowInterval) {
            clearInterval(photoState.slideshowInterval);
        }
        photoState.slideshowInterval = setInterval(nextPhoto, photoState.intervalSeconds * 1000);
        
        console.log(`Photo slideshow started with ${photoState.photos.length} photos`);
        
    } catch (error) {
        console.error('Error loading photos:', error);
    }
}

function stopPhotoSlideshow() {
    if (photoState.slideshowInterval) {
        clearInterval(photoState.slideshowInterval);
        photoState.slideshowInterval = null;
    }
    
    // Clear photo layers
    const layer1 = document.getElementById('photoLayer1');
    const layer2 = document.getElementById('photoLayer2');
    if (layer1) {
        layer1.style.backgroundImage = '';
        layer1.classList.remove('active', 'ken-burns');
    }
    if (layer2) {
        layer2.style.backgroundImage = '';
        layer2.classList.remove('active', 'ken-burns');
    }
}

function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

function preloadPhotos(startIndex, count) {
    for (let i = 0; i < count; i++) {
        const index = (startIndex + i) % photoState.photos.length;
        const photo = photoState.photos[index];
        if (photo && !photoState.preloadedImages.has(photo.url)) {
            const img = new Image();
            img.src = photo.url;
            photoState.preloadedImages.set(photo.url, img);
        }
    }
}

async function showPhoto(index) {
    if (photoState.photos.length === 0) return;
    
    const photo = photoState.photos[index];
    if (!photo) return;
    
    // Get the layers
    const layer1 = document.getElementById('photoLayer1');
    const layer2 = document.getElementById('photoLayer2');
    
    // Determine which layer to use
    const activeLayer = photoState.activeLayer === 1 ? layer1 : layer2;
    const inactiveLayer = photoState.activeLayer === 1 ? layer2 : layer1;
    
    // Set the new image on the inactive layer
    inactiveLayer.style.backgroundImage = `url('${photo.url}')`;
    inactiveLayer.classList.add('ken-burns');
    
    // Small delay for image to load
    await new Promise(resolve => setTimeout(resolve, 50));
    
    // Crossfade
    activeLayer.classList.remove('active');
    inactiveLayer.classList.add('active');
    
    // Swap active layer for next time
    photoState.activeLayer = photoState.activeLayer === 1 ? 2 : 1;
    
    // Preload next photos
    preloadPhotos(index + 1, 2);
}

function nextPhoto() {
    photoState.currentIndex = (photoState.currentIndex + 1) % photoState.photos.length;
    showPhoto(photoState.currentIndex);
}

// ============================================================================
// Glass Opacity Slider
// ============================================================================

function initGlassOpacitySlider() {
    const toggle = document.getElementById('glassSliderToggle');
    const panel = document.getElementById('glassSliderPanel');
    const slider = document.getElementById('glassOpacitySlider');
    const valueDisplay = document.getElementById('glassOpacityValue');
    const classicBtn = document.getElementById('glassModeClassic');
    const appleBtn = document.getElementById('glassModeApple');
    
    if (!toggle || !panel || !slider) return;
    
    // Load saved opacity value
    const savedOpacity = localStorage.getItem('clockie-glass-opacity');
    if (savedOpacity !== null) {
        state.glassOpacity = parseInt(savedOpacity);
        slider.value = state.glassOpacity;
    }
    
    // Load saved glass mode
    const savedMode = localStorage.getItem('clockie-glass-mode');
    if (savedMode) {
        state.glassMode = savedMode;
    }
    
    // Apply initial values
    applyGlassOpacity(state.glassOpacity);
    applyGlassMode(state.glassMode);
    if (valueDisplay) valueDisplay.textContent = state.glassOpacity;
    updateGlassModeButtons();
    
    // Toggle panel visibility
    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        panel.classList.toggle('visible');
    });
    
    // Close panel when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.glass-slider-container')) {
            panel.classList.remove('visible');
        }
    });
    
    // Handle slider changes
    slider.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        state.glassOpacity = value;
        if (valueDisplay) valueDisplay.textContent = value;
        applyGlassOpacity(value);
    });
    
    // Save opacity on change end
    slider.addEventListener('change', (e) => {
        localStorage.setItem('clockie-glass-opacity', state.glassOpacity);
    });
    
    // Handle glass mode toggle
    if (classicBtn) {
        classicBtn.addEventListener('click', () => {
            state.glassMode = 'classic';
            applyGlassMode('classic');
            updateGlassModeButtons();
            localStorage.setItem('clockie-glass-mode', 'classic');
        });
    }
    
    const liquidBtn = document.getElementById('glassModeLiquid');
    if (liquidBtn) {
        liquidBtn.addEventListener('click', () => {
            state.glassMode = 'liquid';
            applyGlassMode('liquid');
            updateGlassModeButtons();
            localStorage.setItem('clockie-glass-mode', 'liquid');
        });
    }
}

function updateGlassModeButtons() {
    const classicBtn = document.getElementById('glassModeClassic');
    const liquidBtn = document.getElementById('glassModeLiquid');
    
    if (classicBtn && liquidBtn) {
        classicBtn.classList.toggle('active', state.glassMode === 'classic');
        liquidBtn.classList.toggle('active', state.glassMode === 'liquid');
    }
}

function applyGlassMode(mode) {
    document.documentElement.setAttribute('data-glass-mode', mode);
}

function applyGlassOpacity(percent) {
    // Convert 0-100 to 0-0.5 for opacity (0% = transparent, 100% = 50% opaque)
    const opacity = (percent / 100) * 0.5;
    // Blur scales from 4px to 20px
    const blur = 4 + (percent / 100) * 16;
    
    document.documentElement.style.setProperty('--glass-opacity', opacity.toFixed(3));
    document.documentElement.style.setProperty('--glass-blur', `${blur.toFixed(0)}px`);
}

// ============================================================================
// Holiday Theme System
// ============================================================================

const HOLIDAYS = {
    // Fixed date holidays
    '01-01': { name: 'newyear', label: "Happy New Year! 🎉" },
    '02-14': { name: 'valentine', label: "Happy Valentine's Day 💕" },
    '03-17': { name: 'stpatricks', label: "Happy St. Patrick's Day ☘️" },
    '07-04': { name: 'july4th', label: "Happy 4th of July! 🇺🇸" },
    '10-31': { name: 'halloween', label: "Happy Halloween! 🎃" },
    '12-24': { name: 'christmas-eve', label: "Christmas Eve ✨" },
    '12-25': { name: 'christmas', label: "Merry Christmas! 🎄" },
    '12-31': { name: 'newyears-eve', label: "Happy New Year's Eve! 🥂" },
};

function getEasterDate(year) {
    // Anonymous Gregorian algorithm for Easter
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const month = Math.floor((h + l - 7 * m + 114) / 31);
    const day = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(year, month - 1, day);
}

function getThanksgivingDate(year) {
    // 4th Thursday of November
    const nov1 = new Date(year, 10, 1);
    const dayOfWeek = nov1.getDay();
    const firstThursday = dayOfWeek <= 4 ? 4 - dayOfWeek + 1 : 11 - dayOfWeek + 4 + 1;
    return new Date(year, 10, firstThursday + 21);
}

function getMemorialDayDate(year) {
    // Last Monday of May
    const may31 = new Date(year, 4, 31);
    const dayOfWeek = may31.getDay();
    const lastMonday = dayOfWeek === 0 ? 25 : 31 - dayOfWeek + 1;
    return new Date(year, 4, lastMonday);
}

function getLaborDayDate(year) {
    // First Monday of September
    const sep1 = new Date(year, 8, 1);
    const dayOfWeek = sep1.getDay();
    const firstMonday = dayOfWeek === 0 ? 2 : dayOfWeek === 1 ? 1 : 9 - dayOfWeek;
    return new Date(year, 8, firstMonday);
}

function checkHoliday() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const dateKey = `${month}-${day}`;
    
    // Check fixed holidays first
    if (HOLIDAYS[dateKey]) {
        return HOLIDAYS[dateKey];
    }
    
    // Check variable holidays
    const easter = getEasterDate(year);
    if (now.getMonth() === easter.getMonth() && now.getDate() === easter.getDate()) {
        return { name: 'easter', label: "Happy Easter! 🐰" };
    }
    
    const thanksgiving = getThanksgivingDate(year);
    if (now.getMonth() === thanksgiving.getMonth() && now.getDate() === thanksgiving.getDate()) {
        return { name: 'thanksgiving', label: "Happy Thanksgiving! 🦃" };
    }
    
    const memorial = getMemorialDayDate(year);
    if (now.getMonth() === memorial.getMonth() && now.getDate() === memorial.getDate()) {
        return { name: 'memorial', label: "Memorial Day 🇺🇸" };
    }
    
    const labor = getLaborDayDate(year);
    if (now.getMonth() === labor.getMonth() && now.getDate() === labor.getDate()) {
        return { name: 'labor', label: "Happy Labor Day!" };
    }
    
    return null;
}

function initHolidayTheme() {
    // Check for preview parameter first
    const urlParams = new URLSearchParams(window.location.search);
    const previewHoliday = urlParams.get('preview_holiday') || localStorage.getItem('clockie-holiday-preview');
    
    if (previewHoliday) {
        console.log('Holiday preview:', previewHoliday);
        document.documentElement.setAttribute('data-holiday', previewHoliday);
        createHolidayEffects(previewHoliday);
        state.holiday = { name: previewHoliday, label: 'Preview Mode' };
        // Clear preview after 60 seconds
        setTimeout(() => {
            localStorage.removeItem('clockie-holiday-preview');
        }, 60000);
        return;
    }
    
    // Normal holiday detection
    const holiday = checkHoliday();
    state.holiday = holiday;
    
    if (holiday) {
        console.log('Holiday detected:', holiday.name);
        document.documentElement.setAttribute('data-holiday', holiday.name);
        createHolidayEffects(holiday.name);
    } else {
        document.documentElement.removeAttribute('data-holiday');
    }
}

function createHolidayEffects(holidayName) {
    const container = document.getElementById('holidayEffects');
    if (!container) return;
    
    container.innerHTML = '';
    
    const particleConfigs = {
        'christmas': { count: 50, class: 'snowflake', content: ['❄', '❅', '❆', '✧'] },
        'christmas-eve': { count: 40, class: 'snowflake', content: ['❄', '❅', '✧', '⭐'] },
        'newyear': { count: 60, class: 'confetti', content: ['🎉', '✨', '🎊', '⭐', '💫'] },
        'newyears-eve': { count: 50, class: 'sparkle', content: ['✨', '🥂', '🎆', '⭐', '💫'] },
        'valentine': { count: 40, class: 'heart', content: ['❤', '💕', '💖', '💗', '💓'] },
        'stpatricks': { count: 35, class: 'clover', content: ['☘️', '🍀', '✨', '💚'] },
        'easter': { count: 30, class: 'easter', content: ['🐰', '🥚', '🌸', '🌷', '✨'] },
        'july4th': { count: 50, class: 'firework', content: ['✨', '🎆', '⭐', '💫', '🇺🇸'] },
        'halloween': { count: 40, class: 'spooky', content: ['🎃', '👻', '🦇', '🕷️', '✨'] },
        'thanksgiving': { count: 30, class: 'autumn', content: ['🍂', '🍁', '🦃', '🌾', '✨'] },
        'memorial': { count: 25, class: 'patriot', content: ['🇺🇸', '⭐', '✨', '🎖️'] },
        'labor': { count: 25, class: 'sparkle', content: ['⭐', '✨', '💪', '🎉'] },
    };
    
    const config = particleConfigs[holidayName];
    if (!config) return;
    
    for (let i = 0; i < config.count; i++) {
        const particle = document.createElement('div');
        particle.className = `holiday-particle ${config.class}`;
        particle.textContent = config.content[Math.floor(Math.random() * config.content.length)];
        particle.style.left = `${Math.random() * 100}%`;
        particle.style.animationDelay = `${Math.random() * 15}s`;
        particle.style.animationDuration = `${10 + Math.random() * 20}s`;
        particle.style.fontSize = `${12 + Math.random() * 20}px`;
        particle.style.opacity = 0.3 + Math.random() * 0.5;
        container.appendChild(particle);
    }
}

// ============================================================================
// Orientation & Touch Mode
// ============================================================================

function initOrientationAndTouch() {
    // Load saved orientation
    const savedOrientation = localStorage.getItem('clockie-orientation');
    if (savedOrientation) {
        state.orientation = savedOrientation;
    }
    applyOrientation();
    
    // Load saved touch mode
    const savedTouchMode = localStorage.getItem('clockie-touch-mode');
    state.touchMode = savedTouchMode === 'true';
    applyTouchMode();
    
    // Set up orientation toggle buttons
    document.querySelectorAll('.orientation-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            setOrientation(btn.dataset.orientation);
        });
    });
    
    // Touch mode switch
    const touchSwitch = document.getElementById('touchModeSwitch');
    if (touchSwitch) {
        touchSwitch.addEventListener('click', toggleTouchMode);
    }
    
    updateOrientationButtons();
    updateTouchModeSwitch();
}

function setOrientation(orientation) {
    state.orientation = orientation;
    localStorage.setItem('clockie-orientation', orientation);
    applyOrientation();
    updateOrientationButtons();
}

function applyOrientation() {
    document.documentElement.setAttribute('data-orientation', state.orientation);
    console.log('Orientation:', state.orientation);
}

function updateOrientationButtons() {
    document.querySelectorAll('.orientation-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.orientation === state.orientation);
    });
}

function toggleTouchMode() {
    state.touchMode = !state.touchMode;
    localStorage.setItem('clockie-touch-mode', state.touchMode);
    applyTouchMode();
    updateTouchModeSwitch();
}

function applyTouchMode() {
    document.documentElement.setAttribute('data-touch-mode', state.touchMode);
    console.log('Touch mode:', state.touchMode);
}

function updateTouchModeSwitch() {
    const switchEl = document.getElementById('touchModeSwitch');
    if (switchEl) {
        switchEl.classList.toggle('active', state.touchMode);
    }
}

// ============================================================================
// Quick Add Event Panel
// ============================================================================

function initQuickAddEvent() {
    const overlay = document.getElementById('quickAddOverlay');
    const closeBtn = document.getElementById('quickAddClose');
    const fab = document.getElementById('fabAddEvent');
    const form = document.getElementById('quickAddForm');
    const handle = document.querySelector('.quick-add-handle');
    
    // Open panel with FAB
    fab?.addEventListener('click', () => openQuickAdd());
    
    // Close button
    closeBtn?.addEventListener('click', closeQuickAdd);
    
    // Close on overlay click
    overlay?.addEventListener('click', (e) => {
        if (e.target === overlay) closeQuickAdd();
    });
    
    // Touch to drag down to close
    let startY = 0;
    let currentY = 0;
    
    handle?.addEventListener('touchstart', (e) => {
        startY = e.touches[0].clientY;
    }, { passive: true });
    
    handle?.addEventListener('touchmove', (e) => {
        currentY = e.touches[0].clientY;
        const delta = currentY - startY;
        if (delta > 0) {
            const panel = document.querySelector('.quick-add-panel');
            panel.style.transform = `translateY(${delta}px)`;
        }
    }, { passive: true });
    
    handle?.addEventListener('touchend', () => {
        const panel = document.querySelector('.quick-add-panel');
        const delta = currentY - startY;
        if (delta > 100) {
            closeQuickAdd();
        } else {
            panel.style.transform = '';
        }
        startY = 0;
        currentY = 0;
    });
    
    // Quick time preset buttons
    document.querySelectorAll('.quick-time-btn').forEach(btn => {
        btn.addEventListener('click', () => applyTimePreset(btn.dataset.preset));
    });
    
    // Form submission
    form?.addEventListener('submit', handleQuickAddSubmit);
    
    // Set default date to today
    const dateInput = document.getElementById('eventDate');
    if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }
}

function openQuickAdd() {
    const overlay = document.getElementById('quickAddOverlay');
    overlay?.classList.add('open');
    
    // Reset form
    document.getElementById('quickAddForm')?.reset();
    document.getElementById('quickAddStatus').textContent = '';
    
    // Set today's date
    const dateInput = document.getElementById('eventDate');
    if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }
    
    // Focus title input after animation
    setTimeout(() => {
        document.getElementById('eventTitle')?.focus();
    }, 400);
}

function closeQuickAdd() {
    const overlay = document.getElementById('quickAddOverlay');
    const panel = document.querySelector('.quick-add-panel');
    overlay?.classList.remove('open');
    if (panel) panel.style.transform = '';
}

function applyTimePreset(preset) {
    const dateInput = document.getElementById('eventDate');
    const timeInput = document.getElementById('eventTime');
    const today = new Date();
    
    // Clear active states
    document.querySelectorAll('.quick-time-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.quick-time-btn[data-preset="${preset}"]`)?.classList.add('active');
    
    switch (preset) {
        case 'today':
            dateInput.value = today.toISOString().split('T')[0];
            break;
        case 'tomorrow':
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.value = tomorrow.toISOString().split('T')[0];
            break;
        case 'next-week':
            const nextWeek = new Date(today);
            nextWeek.setDate(nextWeek.getDate() + 7);
            dateInput.value = nextWeek.toISOString().split('T')[0];
            break;
        case 'all-day':
            timeInput.value = '';
            break;
    }
}

async function handleQuickAddSubmit(e) {
    e.preventDefault();
    
    const statusEl = document.getElementById('quickAddStatus');
    const submitBtn = document.querySelector('.quick-add-submit');
    
    const title = document.getElementById('eventTitle')?.value?.trim();
    const date = document.getElementById('eventDate')?.value;
    const time = document.getElementById('eventTime')?.value;
    const notes = document.getElementById('eventNotes')?.value?.trim();
    
    if (!title || !date) {
        statusEl.textContent = 'Please enter a title and date';
        statusEl.className = 'quick-add-status error';
        return;
    }
    
    try {
        submitBtn.disabled = true;
        statusEl.textContent = 'Adding event...';
        statusEl.className = 'quick-add-status';
        
        const eventData = {
            title,
            date,
            time: time || null,
            notes: notes || null,
            all_day: !time
        };
        
        const response = await fetch('/api/events/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(eventData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusEl.textContent = '✓ Event added!';
            statusEl.className = 'quick-add-status success';
            
            // Refresh calendar data
            setTimeout(() => {
                fetchCalendar();
                closeQuickAdd();
            }, 1200);
        } else {
            statusEl.textContent = '✗ ' + (result.error || 'Failed to add event');
            statusEl.className = 'quick-add-status error';
        }
    } catch (err) {
        console.error('Failed to add event:', err);
        statusEl.textContent = '✗ Network error';
        statusEl.className = 'quick-add-status error';
    } finally {
        submitBtn.disabled = false;
    }
}

// ============================================================================
// Settings Panel
// ============================================================================

let calendarAccountCount = 0;

function initSettings() {
    const gear = document.getElementById('settingsGear');
    const overlay = document.getElementById('settingsOverlay');
    const closeBtn = document.getElementById('settingsClose');
    
    // Open settings
    if (gear) {
        gear.addEventListener('click', () => {
            overlay?.classList.add('open');
            loadConfig(); // Load config when opening
        });
    }
    
    // Close settings
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            overlay?.classList.remove('open');
        });
    }
    
    // Close on overlay click (outside panel)
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('open');
            }
        });
    }
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay?.classList.contains('open')) {
            overlay.classList.remove('open');
        }
    });
    
    // Theme options in settings
    document.querySelectorAll('.settings-option[data-theme]').forEach(btn => {
        btn.addEventListener('click', () => {
            setTheme(btn.dataset.theme);
            updateSettingsThemeButtons();
        });
    });
    
    // Weather switch in settings
    const weatherSwitch = document.getElementById('weatherFxSwitch');
    if (weatherSwitch) {
        weatherSwitch.addEventListener('click', toggleWeatherEffects);
    }
    
    // Accordion headers
    document.querySelectorAll('.accordion-header').forEach(header => {
        header.addEventListener('click', () => {
            const accordionId = header.dataset.accordion;
            const content = document.getElementById(`${accordionId}Accordion`);
            header.classList.toggle('open');
            content?.classList.toggle('open');
        });
    });
    
    // Add calendar account button
    const addAccountBtn = document.getElementById('addCalendarAccount');
    if (addAccountBtn) {
        addAccountBtn.addEventListener('click', () => addCalendarAccountCard());
    }
    
    // Save config button
    const saveBtn = document.getElementById('saveConfigBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveConfig);
    }
    
    // Initialize button states
    updateSettingsThemeButtons();
}

function updateSettingsThemeButtons() {
    document.querySelectorAll('.settings-option[data-theme]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === state.theme);
    });
}

// Add a calendar account card to the list
function addCalendarAccountCard(account = null) {
    const list = document.getElementById('calendarAccountsList');
    if (!list) return;
    
    const index = calendarAccountCount++;
    const card = document.createElement('div');
    card.className = 'account-card';
    card.dataset.index = index;
    
    card.innerHTML = `
        <button class="account-remove" title="Remove account">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
        </button>
        <div class="form-group">
            <label>Account Name</label>
            <input type="text" class="cfg-account-name" placeholder="Personal" value="${account?.name || ''}">
        </div>
        <div class="form-group">
            <label>CalDAV URL</label>
            <input type="text" class="cfg-account-url" placeholder="https://caldav.icloud.com" value="${account?.url || 'https://caldav.icloud.com'}">
        </div>
        <div class="form-group">
            <label>Username (Email)</label>
            <input type="text" class="cfg-account-username" placeholder="you@icloud.com" value="${account?.username || ''}">
        </div>
        <div class="form-group">
            <label>App-Specific Password</label>
            <input type="password" class="cfg-account-password" placeholder="xxxx-xxxx-xxxx-xxxx" value="${account?.password || ''}" autocomplete="new-password">
        </div>
    `;
    
    // Remove button handler
    card.querySelector('.account-remove').addEventListener('click', () => {
        card.remove();
    });
    
    list.appendChild(card);
}

// Load configuration from backend
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) return;
        
        const config = await response.json();
        
        // Weather settings
        if (config.weather) {
            const w = config.weather;
            document.getElementById('cfgWeatherApiKey').value = w.api_key || '';
            document.getElementById('cfgWeatherCity').value = w.city || '';
            document.getElementById('cfgWeatherState').value = w.state || '';
            document.getElementById('cfgWeatherCountry').value = w.country || '';
            document.getElementById('cfgWeatherUnits').value = w.units || 'imperial';
        }
        
        // Calendar settings
        if (config.calendar) {
            const c = config.calendar;
            document.getElementById('cfgCalendarInterval').value = c.update_interval ? Math.floor(c.update_interval / 60) : '';
            document.getElementById('cfgCalendarMaxEvents').value = c.max_events || '';
            
            // Clear and repopulate accounts
            const list = document.getElementById('calendarAccountsList');
            if (list) {
                list.innerHTML = '';
                calendarAccountCount = 0;
                
                if (c.accounts && c.accounts.length > 0) {
                    c.accounts.forEach(account => addCalendarAccountCard(account));
                }
            }
        }
        
        // Spotify settings
        if (config.spotify) {
            const s = config.spotify;
            document.getElementById('cfgSpotifyClientId').value = s.client_id || '';
            document.getElementById('cfgSpotifyClientSecret').value = s.client_secret || '';
            document.getElementById('cfgSpotifyRedirectUri').value = s.redirect_uri || `http://${window.location.host}/api/spotify/callback`;
        }
        
    } catch (err) {
        console.error('Failed to load config:', err);
    }
}

// Save configuration to backend
async function saveConfig() {
    const statusEl = document.getElementById('saveStatus');
    const saveBtn = document.getElementById('saveConfigBtn');
    
    try {
        saveBtn.disabled = true;
        statusEl.textContent = 'Saving...';
        statusEl.className = 'save-status';
        
        // Gather weather config
        const weather = {
            api_key: document.getElementById('cfgWeatherApiKey').value.trim(),
            city: document.getElementById('cfgWeatherCity').value.trim(),
            state: document.getElementById('cfgWeatherState').value.trim().toUpperCase(),
            country: document.getElementById('cfgWeatherCountry').value.trim().toUpperCase(),
            units: document.getElementById('cfgWeatherUnits').value
        };
        
        // Gather calendar config
        const accounts = [];
        document.querySelectorAll('.account-card').forEach(card => {
            const name = card.querySelector('.cfg-account-name').value.trim();
            const url = card.querySelector('.cfg-account-url').value.trim();
            const username = card.querySelector('.cfg-account-username').value.trim();
            const password = card.querySelector('.cfg-account-password').value.trim();
            
            if (name && username && password) {
                accounts.push({ name, url, username, password });
            }
        });
        
        const intervalMin = parseInt(document.getElementById('cfgCalendarInterval').value) || 5;
        const maxEvents = parseInt(document.getElementById('cfgCalendarMaxEvents').value) || 15;
        
        const calendar = {
            accounts,
            update_interval: intervalMin * 60, // Convert to seconds
            max_events: maxEvents
        };
        
        // Gather Spotify config
        const spotify = {
            client_id: document.getElementById('cfgSpotifyClientId').value.trim(),
            client_secret: document.getElementById('cfgSpotifyClientSecret').value.trim(),
            redirect_uri: document.getElementById('cfgSpotifyRedirectUri').value.trim() || `http://${window.location.host}/api/spotify/callback`
        };
        
        // Send to backend
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ weather, calendar, spotify })
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusEl.textContent = '✓ Configuration saved! Reloading data...';
            statusEl.className = 'save-status success';
            
            // Refresh data
            setTimeout(() => {
                fetchWeather();
                fetchCalendar();
                updateSpotifyStatus(); // Refresh Spotify status
                statusEl.textContent = '';
            }, 1500);
        } else {
            statusEl.textContent = '✗ ' + (result.error || 'Failed to save');
            statusEl.className = 'save-status error';
        }
        
    } catch (err) {
        console.error('Failed to save config:', err);
        statusEl.textContent = '✗ Error: ' + err.message;
        statusEl.className = 'save-status error';
    } finally {
        saveBtn.disabled = false;
    }
}

// ============================================================================
// Weather Effects System
// ============================================================================

function initWeatherEffects() {
    // Load saved preference
    const saved = localStorage.getItem('clockie-weather-fx');
    state.weatherFxEnabled = saved !== 'false';
    
    // Update toggle state
    updateWeatherFxToggle();
    
    // Check for weather effect preview in URL
    const urlParams = new URLSearchParams(window.location.search);
    const previewWeather = urlParams.get('preview_weather');
    if (previewWeather) {
        console.log('Weather effect preview:', previewWeather);
        // Force enable and create effect after DOM is ready
        setTimeout(() => setWeatherEffect(previewWeather, true), 500);
    }
}

function toggleWeatherEffects() {
    state.weatherFxEnabled = !state.weatherFxEnabled;
    localStorage.setItem('clockie-weather-fx', state.weatherFxEnabled);
    updateWeatherFxToggle();
    
    if (state.weatherFxEnabled && state.currentWeatherEffect !== 'none') {
        createWeatherEffects(state.currentWeatherEffect);
    } else {
        clearWeatherEffects();
    }
}

function updateWeatherFxToggle() {
    const switchEl = document.getElementById('weatherFxSwitch');
    const container = document.getElementById('weatherEffects');
    
    if (switchEl) {
        switchEl.classList.toggle('active', state.weatherFxEnabled);
    }
    
    if (container) {
        container.classList.toggle('disabled', !state.weatherFxEnabled);
    }
}

function setWeatherEffect(effectType, forceEnable = false) {
    state.currentWeatherEffect = effectType;
    
    // If force enabled (for previews), temporarily enable effects
    if (forceEnable) {
        state.weatherFxEnabled = true;
        updateWeatherFxToggle();
    }
    
    if (!state.weatherFxEnabled || effectType === 'none') {
        clearWeatherEffects();
        return;
    }
    
    createWeatherEffects(effectType);
    console.log('Weather effect created:', effectType);
}

function clearWeatherEffects() {
    const container = document.getElementById('weatherEffects');
    if (container) {
        container.innerHTML = '';
        container.removeAttribute('data-effect');
    }
}

function createWeatherEffects(effectType) {
    const container = document.getElementById('weatherEffects');
    if (!container) return;
    
    // Clear existing effects
    container.innerHTML = '';
    container.setAttribute('data-effect', effectType);
    
    const configs = {
        'rain': { count: 100, class: 'rain', minDuration: 0.8, maxDuration: 1.5 },
        'drizzle': { count: 50, class: 'drizzle', minDuration: 1.5, maxDuration: 3 },
        'storm': { count: 150, class: 'storm', minDuration: 0.5, maxDuration: 1 },
        'snow': { count: 80, class: 'snow', minDuration: 5, maxDuration: 15 },
        'wind': { count: 20, class: 'wind', minDuration: 4, maxDuration: 8, content: ['🍃', '🍂', '🌿', '🌾'] },
        'fog': { count: 0 } // Fog uses CSS only
    };
    
    const config = configs[effectType];
    if (!config) return;
    
    // Add lightning flash for storms
    if (effectType === 'storm') {
        const lightning = document.createElement('div');
        lightning.className = 'lightning';
        container.appendChild(lightning);
    }
    
    // Create particles
    for (let i = 0; i < config.count; i++) {
        const particle = document.createElement('div');
        particle.className = `weather-particle ${config.class}`;
        
        // Position randomly across width
        particle.style.left = `${Math.random() * 100}%`;
        
        // Random animation timing
        const duration = config.minDuration + Math.random() * (config.maxDuration - config.minDuration);
        particle.style.animationDuration = `${duration}s`;
        particle.style.animationDelay = `${Math.random() * duration}s`;
        
        // For wind effect, use leaf emojis
        if (config.content) {
            particle.textContent = config.content[Math.floor(Math.random() * config.content.length)];
            particle.style.top = `${20 + Math.random() * 40}%`;
        }
        
        // Vary size slightly for depth
        if (effectType === 'snow') {
            const size = 4 + Math.random() * 8;
            particle.style.width = `${size}px`;
            particle.style.height = `${size}px`;
        } else if (effectType === 'rain' || effectType === 'storm') {
            const height = 15 + Math.random() * 20;
            particle.style.height = `${height}px`;
        }
        
        container.appendChild(particle);
    }
    
    console.log(`Weather effect: ${effectType} (${config.count} particles)`);
}

// ============================================================================
// Sunrise/Sunset Calculations
// ============================================================================

function calculateSunTimes(lat, lng, date = new Date()) {
    // Simple sunrise/sunset calculation
    // Based on NOAA Solar Calculator algorithms (simplified)
    
    const rad = Math.PI / 180;
    const dayOfYear = getDayOfYear(date);
    
    // Fractional year (radians)
    const gamma = (2 * Math.PI / 365) * (dayOfYear - 1 + (date.getHours() - 12) / 24);
    
    // Equation of time (minutes)
    const eqTime = 229.18 * (0.000075 + 0.001868 * Math.cos(gamma) 
        - 0.032077 * Math.sin(gamma) - 0.014615 * Math.cos(2 * gamma) 
        - 0.040849 * Math.sin(2 * gamma));
    
    // Solar declination (radians)
    const decl = 0.006918 - 0.399912 * Math.cos(gamma) + 0.070257 * Math.sin(gamma)
        - 0.006758 * Math.cos(2 * gamma) + 0.000907 * Math.sin(2 * gamma)
        - 0.002697 * Math.cos(3 * gamma) + 0.00148 * Math.sin(3 * gamma);
    
    // Hour angle for sunrise/sunset
    const latRad = lat * rad;
    const zenith = 90.833 * rad; // Official zenith for sunrise/sunset
    
    const cosHA = (Math.cos(zenith) / (Math.cos(latRad) * Math.cos(decl))) 
        - Math.tan(latRad) * Math.tan(decl);
    
    // Check for polar day/night
    if (cosHA > 1) {
        // Sun never rises (polar night)
        return { sunrise: null, sunset: null, polarNight: true };
    } else if (cosHA < -1) {
        // Sun never sets (polar day)
        return { sunrise: null, sunset: null, polarDay: true };
    }
    
    const ha = Math.acos(cosHA) / rad;
    
    // Calculate sunrise and sunset times
    const timezone = -date.getTimezoneOffset() / 60;
    
    const sunriseMinutes = 720 - 4 * (lng + ha) - eqTime + timezone * 60;
    const sunsetMinutes = 720 - 4 * (lng - ha) - eqTime + timezone * 60;
    
    const sunrise = new Date(date);
    sunrise.setHours(0, 0, 0, 0);
    sunrise.setMinutes(sunriseMinutes);
    
    const sunset = new Date(date);
    sunset.setHours(0, 0, 0, 0);
    sunset.setMinutes(sunsetMinutes);
    
    return { sunrise, sunset };
}

function getDayOfYear(date) {
    const start = new Date(date.getFullYear(), 0, 0);
    const diff = date - start;
    const oneDay = 1000 * 60 * 60 * 24;
    return Math.floor(diff / oneDay);
}

function isDaytime() {
    const now = new Date();
    
    if (!state.sunTimes || !state.sunTimes.sunrise || !state.sunTimes.sunset) {
        // Fallback: 6 AM to 6 PM
        const hour = now.getHours();
        return hour >= 6 && hour < 18;
    }
    
    return now >= state.sunTimes.sunrise && now < state.sunTimes.sunset;
}

// ============================================================================
// Theme Management
// ============================================================================

function initTheme() {
    // Load saved preference
    const saved = localStorage.getItem('wallclock-theme');
    if (saved && ['auto', 'light', 'dark'].includes(saved)) {
        state.theme = saved;
    }
    
    // Try to get user location for accurate sun times
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                state.location.lat = pos.coords.latitude;
                state.location.lng = pos.coords.longitude;
                updateSunTimes();
            },
            () => {
                // Use default location
                updateSunTimes();
            },
            { timeout: 5000 }
        );
    } else {
        updateSunTimes();
    }
    
    // Initialize settings panel
    initSettings();
    
    // Update theme immediately
    applyTheme();
    
    // Check theme every minute
    setInterval(checkTheme, 60000);
}

function updateSunTimes() {
    state.sunTimes = calculateSunTimes(state.location.lat, state.location.lng);
    console.log('Sun times:', {
        sunrise: state.sunTimes.sunrise?.toLocaleTimeString(),
        sunset: state.sunTimes.sunset?.toLocaleTimeString()
    });
}

function setTheme(theme) {
    state.theme = theme;
    localStorage.setItem('wallclock-theme', theme);
    applyTheme(true); // true = with transition
}

function checkTheme() {
    // Recalculate sun times at midnight
    const now = new Date();
    if (now.getHours() === 0 && now.getMinutes() === 0) {
        updateSunTimes();
    }
    
    // Check if we need to transition
    if (state.theme === 'auto') {
        const wasDay = state.isDaytime;
        state.isDaytime = isDaytime();
        
        if (wasDay !== state.isDaytime) {
            applyTheme(true, true); // Slow natural transition for sunrise/sunset
        }
    }
}

function applyTheme(withTransition = false, isSunriseOrSunset = false) {
    const html = document.documentElement;
    
    // Update settings panel buttons
    updateSettingsThemeButtons();
    
    // Set theme attribute
    html.setAttribute('data-theme', state.theme);
    
    // For auto theme, add day/night class
    if (state.theme === 'auto') {
        state.isDaytime = isDaytime();
        html.classList.toggle('is-day', state.isDaytime);
        html.classList.toggle('is-night', !state.isDaytime);
    } else {
        html.classList.remove('is-day', 'is-night');
    }
    
    // Apply transitions
    if (withTransition) {
        // Clear any existing transition classes
        html.classList.remove('theme-transitioning-slow', 'theme-transitioning-fast');
        
        if (isSunriseOrSunset) {
            // Slow 60-second transition for natural sunrise/sunset
            html.classList.add('theme-transitioning-slow');
            setTimeout(() => html.classList.remove('theme-transitioning-slow'), 60000);
        } else {
            // Fast 1.5-second transition for manual switching
            html.classList.add('theme-transitioning-fast');
            setTimeout(() => html.classList.remove('theme-transitioning-fast'), 2000);
        }
    }
}

// ============================================================================
// Time Display
// ============================================================================

function updateTime() {
    const now = new Date();

    const hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;

    document.getElementById('timeDisplay').textContent = `${displayHours}:${minutes}`;
    document.getElementById('secondsDisplay').textContent = seconds;
    document.getElementById('periodDisplay').textContent = ampm;
    
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('dateDisplay').textContent = now.toLocaleDateString('en-US', options);
}

// ============================================================================
// Weather
// ============================================================================

function updateWeather(data) {
    if (!data) return;
    state.weather = data;

    const els = {
        icon: document.getElementById('weatherIcon'),
        temp: document.getElementById('weatherTemp'),
        desc: document.getElementById('weatherDesc'),
        feels: document.getElementById('weatherFeels'),
        humidity: document.getElementById('weatherHumidity'),
        location: document.getElementById('weatherLocation')
    };
    
    // Update weather display
    if (els.icon) els.icon.textContent = data.icon || '🌡️';
    if (els.temp) els.temp.textContent = data.temp ?? '--';
    if (els.desc) {
        // Add moon phase info if night and clear
        let description = data.description || 'Unavailable';
        if (data.is_night && data.moon_phase && data.weather_id === 800) {
            description = `Clear • ${data.moon_phase.name}`;
        }
        els.desc.textContent = description;
    }
    if (els.feels) els.feels.textContent = `Feels ${data.feels_like ?? '--'}°`;
    if (els.humidity) els.humidity.textContent = `${data.humidity ?? '--'}%`;
    if (els.location) els.location.textContent = data.location || 'Unknown';
    
    // Update weather particle effects
    if (data.weather_effect && data.weather_effect !== state.currentWeatherEffect) {
        setWeatherEffect(data.weather_effect);
    }
    
    console.log(`Weather: ${data.description}, Night: ${data.is_night}, Effect: ${data.weather_effect}`);
    
    document.querySelector('.weather-card')?.classList.remove('loading');
}

// ============================================================================
// Calendar - Two Cards with Pinned First + Cycling Rest
// ============================================================================

function updateCalendar(data) {
    if (!data) return;

    // Extract today and upcoming events
    if (data.today !== undefined) {
        state.calendar.today = (data.today || []).sort((a, b) => 
            new Date(a.datetime) - new Date(b.datetime)
        );
        state.calendar.upcoming = (data.upcoming || []).sort((a, b) => 
            new Date(a.datetime) - new Date(b.datetime)
        );
    } else if (Array.isArray(data)) {
        state.calendar.today = data.filter(e => e.is_today).sort((a, b) => 
            new Date(a.datetime) - new Date(b.datetime)
        );
        state.calendar.upcoming = data.filter(e => e.is_upcoming).sort((a, b) => 
            new Date(a.datetime) - new Date(b.datetime)
        );
    }
    
    // Reset cycle indexes
    state.todayCycleIndex = 1;
    state.upcomingCycleIndex = 1;
    
    // Display both cards
    displayTodayEvents();
    displayUpcomingEvents();
    
    // Update mini calendar
    if (typeof updateCalendarEvents === "function") {
 updateCalendarEvents(data);
 }
    
    document.querySelectorAll('.event-card').forEach(c => c.classList.remove('loading'));
}

function displayTodayEvents() {
    const title = document.getElementById('todayTitle');
    const time = document.getElementById('todayTime');
    const cycleContainer = document.getElementById('todayCycle');
    const indicator = document.getElementById('todayIndicator');
    
    const events = state.calendar.today;
    
    if (events.length > 0) {
        // Pinned: first (soonest) event
        const first = events[0];
        if (title) title.textContent = first.title || 'Event';
        if (time) time.textContent = first.time || '';
        
        // Cycle container: show if more than 1 event
        if (events.length > 1) {
            if (cycleContainer) cycleContainer.classList.remove('hidden');
            displayTodayCycleEvent();
            updateIndicators(indicator, events.length);
        } else {
            if (cycleContainer) cycleContainer.classList.add('hidden');
            if (indicator) indicator.innerHTML = '';
        }
    } else {
        if (title) title.textContent = 'No events today';
        if (time) time.textContent = '';
        if (cycleContainer) cycleContainer.classList.add('hidden');
        if (indicator) indicator.innerHTML = '';
    }
}

function displayTodayCycleEvent() {
    const title = document.getElementById('todayCycleTitle');
    const time = document.getElementById('todayCycleTime');
    const container = document.getElementById('todayCycle');
    
    const events = state.calendar.today.slice(1); // Skip pinned event
    if (events.length === 0) return;
    
    const idx = (state.todayCycleIndex - 1) % events.length;
    const event = events[idx];
    
    if (title) title.textContent = event.title || 'Event';
    if (time) time.textContent = event.time || '';
    
    // Animate
    animateCycleItem(container);
}

function displayUpcomingEvents() {
    const title = document.getElementById('upcomingTitle');
    const time = document.getElementById('upcomingTime');
    const cycleContainer = document.getElementById('upcomingCycle');
    const indicator = document.getElementById('upcomingIndicator');
    
    const events = state.calendar.upcoming;
    
    if (events.length > 0) {
        // Pinned: first (soonest) event
        const first = events[0];
        if (title) title.textContent = first.title || 'Event';
        if (time) time.textContent = `${first.date || ''} ${first.time || ''}`.trim();
        
        // Cycle container: show if more than 1 event
        if (events.length > 1) {
            if (cycleContainer) cycleContainer.classList.remove('hidden');
            displayUpcomingCycleEvent();
            updateIndicators(indicator, events.length);
        } else {
            if (cycleContainer) cycleContainer.classList.add('hidden');
            if (indicator) indicator.innerHTML = '';
        }
    } else {
        if (title) title.textContent = 'No upcoming events';
        if (time) time.textContent = '';
        if (cycleContainer) cycleContainer.classList.add('hidden');
        if (indicator) indicator.innerHTML = '';
    }
}

function displayUpcomingCycleEvent() {
    const title = document.getElementById('upcomingCycleTitle');
    const time = document.getElementById('upcomingCycleTime');
    const container = document.getElementById('upcomingCycle');
    
    const events = state.calendar.upcoming.slice(1); // Skip pinned event
    if (events.length === 0) return;
    
    const idx = (state.upcomingCycleIndex - 1) % events.length;
    const event = events[idx];
    
    if (title) title.textContent = event.title || 'Event';
    if (time) time.textContent = `${event.date || ''} ${event.time || ''}`.trim();
    
    // Animate
    animateCycleItem(container);
}

function animateCycleItem(container) {
    const item = container?.querySelector('.event-cycle-item');
    if (item) {
        item.style.animation = 'none';
        item.offsetHeight; // Force reflow
        item.style.animation = 'fadeSlide 0.4s ease-out';
    }
}

function cycleTodayEvents() {
    const events = state.calendar.today.slice(1);
    if (events.length > 0) {
        state.todayCycleIndex++;
        if (state.todayCycleIndex > events.length) {
            state.todayCycleIndex = 1;
        }
        displayTodayCycleEvent();
        updateIndicatorActive('todayIndicator', state.todayCycleIndex - 1, events.length);
    }
}

function cycleUpcomingEvents() {
    const events = state.calendar.upcoming.slice(1);
    if (events.length > 0) {
        state.upcomingCycleIndex++;
        if (state.upcomingCycleIndex > events.length) {
            state.upcomingCycleIndex = 1;
        }
        displayUpcomingCycleEvent();
        updateIndicatorActive('upcomingIndicator', state.upcomingCycleIndex - 1, events.length);
    }
}

function updateIndicators(el, totalCount) {
    if (!el) return;
    el.innerHTML = '';
    
    // Show dots for additional events (not counting the pinned one)
    const cycleCount = Math.min(totalCount - 1, 5);
    if (cycleCount > 0) {
        for (let i = 0; i < cycleCount; i++) {
            const dot = document.createElement('span');
            if (i === 0) dot.classList.add('active');
            el.appendChild(dot);
        }
    }
}

function updateIndicatorActive(id, activeIndex, totalCycleCount) {
    const el = document.getElementById(id);
    if (!el) return;
    
    const dots = el.querySelectorAll('span');
    const displayCount = Math.min(totalCycleCount, 5);
    
    dots.forEach((dot, i) => {
        dot.classList.toggle('active', i === (activeIndex % displayCount));
    });
}

// ============================================================================
// Notes
// ============================================================================

function updateStickyNote(data) {
    if (!data) return;
    state.notes = data;

    const el = document.getElementById('stickyNoteText');
    if (!el) return;

    if (data.content && data.content.trim()) {
        el.textContent = data.content;
    } else {
        el.textContent = 'Add notes to ClockNote.txt';
    }
    
    document.querySelector('.notes-card')?.classList.remove('loading');
}

// ============================================================================
// Jarvis AI Agent
// ============================================================================

let jarvisState = {
    lastMessage: '',
    isOnline: true,
    lastUpdate: null
};

function updateJarvis(data) {
    if (!data) return;
    
    const messageEl = document.getElementById('jarvisMessage');
    const statusEl = document.getElementById('jarvisStatus');
    
    if (!messageEl) return;
    
    // Update status indicator
    if (statusEl) {
        statusEl.classList.remove('offline', 'thinking');
        if (data.source === 'ferretbox') {
            statusEl.classList.add('online');
            jarvisState.isOnline = true;
        } else if (data.source === 'fallback') {
            statusEl.classList.add('offline');
            jarvisState.isOnline = false;
        } else if (data.source === 'initializing') {
            statusEl.classList.add('thinking');
        }
    }
    
    // Only animate if message actually changed
    const newMessage = data.message || '';
    if (newMessage && newMessage !== jarvisState.lastMessage) {
        jarvisState.lastMessage = newMessage;
        jarvisState.lastUpdate = new Date();
        
        // Animate message change
        messageEl.classList.remove('visible');
        messageEl.classList.add('updating');
        
        setTimeout(() => {
            messageEl.textContent = newMessage;
            messageEl.classList.remove('updating');
            messageEl.classList.add('visible');
        }, 300);
    }
}

async function fetchJarvisBriefing(force = false) {
    try {
        const statusEl = document.getElementById('jarvisStatus');
        if (statusEl) {
            statusEl.classList.add('thinking');
        }
        
        const url = force 
            ? `${API_BASE}/api/jarvis/briefing?force=true` 
            : `${API_BASE}/api/jarvis/briefing`;
        const res = await fetch(url);
        
        if (res.ok) {
            const data = await res.json();
            updateJarvis(data);
        }
    } catch (e) {
        console.error('Jarvis fetch error:', e);
        const statusEl = document.getElementById('jarvisStatus');
        if (statusEl) {
            statusEl.classList.add('offline');
        }
    }
}

function initJarvis() {
    // Initial fetch
    fetchJarvisBriefing();
    
    // Add initial visible class after a short delay
    setTimeout(() => {
        const messageEl = document.getElementById('jarvisMessage');
        if (messageEl) {
            messageEl.classList.add('visible');
        }
    }, 500);
}

// ============================================================================
// API
// ============================================================================

async function fetchWeather() {
    try {
        const res = await fetch(`${API_BASE}/api/weather`);
        if (res.ok) updateWeather(await res.json());
    } catch (e) {
        console.error('Weather fetch error:', e);
    }
}

// ============================================================================
// Nest Thermostat
// ============================================================================

let nestConnected = false;

async function checkNestStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/integrations/nest/status`);
        if (res.ok) {
            const data = await res.json();
            nestConnected = data.connected;
            
            const nestSection = document.getElementById('nestSection');
            if (nestSection) {
                if (nestConnected) {
                    nestSection.classList.remove('hidden');
                    fetchNestData();
                } else {
                    nestSection.classList.add('hidden');
                }
            }
        }
    } catch (e) {
        console.error('Nest status check error:', e);
        nestConnected = false;
    }
}

async function fetchNestData() {
    if (!nestConnected) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/integrations/nest/thermostat`);
        if (res.ok) {
            const data = await res.json();
            updateNestDisplay(data);
        }
    } catch (e) {
        console.error('Nest fetch error:', e);
    }
}

function updateNestDisplay(data) {
    if (!data || !data.connected || !data.thermostats || data.thermostats.length === 0) {
        const nestSection = document.getElementById('nestSection');
        if (nestSection) nestSection.classList.add('hidden');
        return;
    }
    
    // Use first thermostat (typically there's only one)
    const t = data.thermostats[0];
    
    const els = {
        section: document.getElementById('nestSection'),
        label: document.getElementById('nestLabel'),
        temp: document.getElementById('nestTemp'),
        mode: document.getElementById('nestMode'),
        hvac: document.getElementById('nestHvac'),
        humidity: document.getElementById('nestHumidity'),
        setpoint: document.getElementById('nestSetpoint')
    };
    
    if (els.section) els.section.classList.remove('hidden');
    if (els.label) els.label.textContent = t.display_name || 'Thermostat';
    if (els.temp) els.temp.textContent = t.ambient_temperature_f ?? '--';
    if (els.humidity) els.humidity.textContent = t.humidity_percent ? `${t.humidity_percent}%` : '--%';
    
    // Mode display
    if (els.mode) {
        const modeMap = {
            'HEAT': 'Heat',
            'COOL': 'Cool',
            'HEATCOOL': 'Auto',
            'OFF': 'Off'
        };
        els.mode.textContent = modeMap[t.hvac_mode] || t.hvac_mode || '--';
    }
    
    // HVAC status (what it's doing now)
    if (els.hvac) {
        els.hvac.className = 'nest-hvac';
        if (t.hvac_status === 'HEATING') {
            els.hvac.textContent = 'Heating';
            els.hvac.classList.add('heating');
        } else if (t.hvac_status === 'COOLING') {
            els.hvac.textContent = 'Cooling';
            els.hvac.classList.add('cooling');
        } else {
            els.hvac.textContent = 'Idle';
            els.hvac.classList.add('off');
        }
    }
    
    // Setpoint
    if (els.setpoint) {
        if (t.eco_mode === 'MANUAL_ECO') {
            els.setpoint.textContent = 'Eco';
        } else if (t.hvac_mode === 'HEAT' && t.heat_setpoint_f) {
            els.setpoint.textContent = `Set ${t.heat_setpoint_f}°`;
        } else if (t.hvac_mode === 'COOL' && t.cool_setpoint_f) {
            els.setpoint.textContent = `Set ${t.cool_setpoint_f}°`;
        } else if (t.hvac_mode === 'HEATCOOL') {
            const heat = t.heat_setpoint_f || '--';
            const cool = t.cool_setpoint_f || '--';
            els.setpoint.textContent = `${heat}°-${cool}°`;
        } else {
            els.setpoint.textContent = '--';
        }
    }
    
    console.log(`Nest: ${t.ambient_temperature_f}°F, Mode: ${t.hvac_mode}, Status: ${t.hvac_status}`);
}

async function fetchCalendar() {
    try {
        const res = await fetch(`${API_BASE}/api/calendar`);
        if (res.ok) updateCalendar(await res.json());
    } catch (e) {
        console.error('Calendar fetch error:', e);
    }
}

async function fetchNotes() {
    try {
        const res = await fetch(`${API_BASE}/api/notes`);
        if (res.ok) updateStickyNote(await res.json());
    } catch (e) {
        console.error('Notes fetch error:', e);
    }
}

// ============================================================================
// WebSocket
// ============================================================================

let ws = null;
let reconnectTimeout = null;

function connectWebSocket() {
    if (ws?.readyState === WebSocket.OPEN) return;

    try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('WebSocket connected');
        clearTimeout(reconnectTimeout);
    };

        ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                if (msg.type === 'weather') updateWeather(msg.data);
                else if (msg.type === 'calendar') updateCalendar(msg.data);
                else if (msg.type === 'notes') updateStickyNote(msg.data);
                else if (msg.type === 'jarvis') updateJarvis(msg.data);
            } catch (err) {
                console.error('WS message error:', err);
            }
    };

    ws.onclose = () => {
            console.log('WebSocket closed, reconnecting...');
            reconnectTimeout = setTimeout(connectWebSocket, 5000);
        };
        
        ws.onerror = (err) => console.error('WS error:', err);
    } catch (e) {
        console.error('WS connect error:', e);
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
    }
}

// ============================================================================
// Spotify Integration
// ============================================================================

async function initSpotify() {
    // Check for OAuth callback parameters
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('spotify_connected')) {
        console.log('Spotify connected successfully!');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    if (urlParams.get('spotify_error')) {
        console.error('Spotify connection error:', urlParams.get('spotify_error'));
        showSpotifyError(getSpotifyErrorMessage(urlParams.get('spotify_error')));
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Check Spotify status
    await updateSpotifyStatus();
    
    // Set up event listeners for settings panel
    document.getElementById('spotifyConnectBtn')?.addEventListener('click', connectSpotify);
    document.getElementById('spotifyDisconnectBtn')?.addEventListener('click', disconnectSpotify);
    document.getElementById('spotifySubmitCallback')?.addEventListener('click', submitSpotifyCallback);
    document.getElementById('spotifyCancelAuth')?.addEventListener('click', cancelSpotifyAuth);
    document.getElementById('spotifyResetBtn')?.addEventListener('click', resetSpotifyConnection);
    
    // Set up ghost player controls (Spotify Connect - controls Raspotify/other devices)
    document.getElementById('ghostPlayPauseBtn')?.addEventListener('click', toggleSpotifyPlayback);
    document.getElementById('ghostNextBtn')?.addEventListener('click', spotifyNext);
    document.getElementById('ghostPrevBtn')?.addEventListener('click', spotifyPrev);
    
    // Start polling for now playing if connected
    if (state.spotify.connected) {
        startNowPlayingPolling();
    }
}

function startNowPlayingPolling() {
    // Poll every 3 seconds for now playing updates
    fetchNowPlaying();
    if (!state.spotify.pollingInterval) {
        state.spotify.pollingInterval = setInterval(fetchNowPlaying, 3000);
    }
}

function stopNowPlayingPolling() {
    if (state.spotify.pollingInterval) {
        clearInterval(state.spotify.pollingInterval);
        state.spotify.pollingInterval = null;
    }
}

// Spotify Connect mode - fetch devices and control playback via API
async function fetchSpotifyDevices() {
    try {
        const response = await fetch('/api/spotify/devices');
        const data = await response.json();
        
        if (data.error) {
            console.log('Devices fetch error:', data.error);
            return [];
        }
        
        return data.devices || [];
    } catch (err) {
        console.error('Failed to fetch devices:', err);
        return [];
    }
}

// Transfer playback to Raspotify (Wall Clock device)
async function transferToWallClock() {
    try {
        const devices = await fetchSpotifyDevices();
        const wallClock = devices.find(d => 
            d.name.toLowerCase().includes('wall clock') || 
            d.name.toLowerCase().includes('raspotify') ||
            d.name.toLowerCase().includes('librespot')
        );
        
        if (wallClock) {
            const response = await fetch('/api/spotify/transfer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: wallClock.id })
            });
            const data = await response.json();
            
            if (data.success) {
                console.log('Playback transferred to Wall Clock');
                const statusEl = document.getElementById('spotifyPlayerStatus');
                if (statusEl) statusEl.textContent = 'Playing on Wall Clock';
                setTimeout(fetchNowPlaying, 1000);
            }
        } else {
            console.log('WallClock device not found. Available:', devices.map(d => d.name));
            showSpotifyError('WallClock not found. Open Spotify on your phone → Connect to "WallClock" device → Then try again.');
        }
    } catch (err) {
        console.error('Failed to transfer playback:', err);
    }
}

// Progress bar updates
// Progress/volume tracking removed - Ghost Player is minimal
function startProgressUpdates() {
    // No-op: Ghost player doesn't show progress
}

function stopProgressUpdates() {
    // No-op: Ghost player doesn't show progress
}

function updateProgressBar() {
    // No-op: Ghost player doesn't have a progress bar
}

function getSpotifyErrorMessage(errorCode) {
    const messages = {
        'not_connected': 'Spotify is not connected. Please connect your account in Settings.',
        'needs_reauth': 'Spotify authorization expired. Please reconnect your account.',
        'no_device': 'No active Spotify device found. Start playing on any device first.',
        'playback_unavailable': 'Playback not available. You may need Spotify Premium.',
        'token_expired': 'Session expired. Please try again.',
        'invalid_state': 'Invalid authorization. Please try connecting again.',
        'token_exchange_failed': 'Failed to connect. Please try again.',
        'no_code': 'Authorization was cancelled or failed.',
    };
    return messages[errorCode] || `Connection error: ${errorCode}`;
}

async function updateSpotifyStatus() {
    try {
        const response = await fetch('/api/spotify/status');
        const status = await response.json();
        
        state.spotify.configured = status.configured;
        state.spotify.connected = status.connected;
        
        const notConnectedEl = document.getElementById('spotifyNotConnected');
        const connectedEl = document.getElementById('spotifyConnected');
        const notConfiguredEl = document.getElementById('spotifyNotConfigured');
        
        // Update settings panel UI
        if (!status.configured) {
            notConnectedEl?.classList.add('hidden');
            connectedEl?.classList.add('hidden');
            notConfiguredEl?.classList.remove('hidden');
        } else if (status.connected) {
            notConnectedEl?.classList.add('hidden');
            connectedEl?.classList.remove('hidden');
            notConfiguredEl?.classList.add('hidden');
            
            // Update user info
            if (status.user) {
                const nameEl = document.getElementById('spotifyUserName');
                const avatarEl = document.getElementById('spotifyUserAvatar');
                if (nameEl) nameEl.textContent = status.user.display_name || status.user.id;
                if (avatarEl && status.user.image) avatarEl.src = status.user.image;
            }
            
            // Start polling for now playing
            fetchNowPlaying();
        } else {
            notConnectedEl?.classList.remove('hidden');
            connectedEl?.classList.add('hidden');
            notConfiguredEl?.classList.add('hidden');
        }
        
        // Show/hide the Now Playing card based on connection status
        updateSpotifyCardVisibility();
        
    } catch (err) {
        console.error('Failed to get Spotify status:', err);
    }
}

async function connectSpotify() {
    try {
        const response = await fetch('/api/spotify/connect');
        const data = await response.json();
        
        if (data.error) {
            showSpotifyError(data.message || 'Failed to start connection');
            return;
        }
        
        if (data.auth_url) {
            // Show manual flow UI instead of redirecting
            const manualFlow = document.getElementById('spotifyManualFlow');
            const authLink = document.getElementById('spotifyAuthLink');
            const connectBtn = document.getElementById('spotifyConnectBtn');
            
            if (manualFlow && authLink) {
                authLink.href = data.auth_url;
                manualFlow.classList.remove('hidden');
                if (connectBtn) connectBtn.classList.add('hidden');
            }
        }
    } catch (err) {
        console.error('Failed to connect Spotify:', err);
        showSpotifyError('Network error. Please try again.');
    }
}

function cancelSpotifyAuth() {
    const manualFlow = document.getElementById('spotifyManualFlow');
    const connectBtn = document.getElementById('spotifyConnectBtn');
    const statusEl = document.getElementById('spotifyManualStatus');
    const callbackInput = document.getElementById('spotifyCallbackUrl');
    
    if (manualFlow) manualFlow.classList.add('hidden');
    if (connectBtn) connectBtn.classList.remove('hidden');
    if (statusEl) statusEl.textContent = '';
    if (callbackInput) callbackInput.value = '';
}

async function submitSpotifyCallback() {
    const callbackUrl = document.getElementById('spotifyCallbackUrl')?.value?.trim();
    const statusEl = document.getElementById('spotifyManualStatus');
    
    if (!callbackUrl) {
        if (statusEl) {
            statusEl.textContent = 'Please paste the callback URL';
            statusEl.className = 'spotify-manual-status error';
        }
        return;
    }
    
    // Validate it looks like a callback URL
    if (!callbackUrl.includes('code=')) {
        if (statusEl) {
            statusEl.textContent = 'URL doesn\'t appear to contain an authorization code. Make sure you copied the full URL.';
            statusEl.className = 'spotify-manual-status error';
        }
        return;
    }
    
    if (statusEl) {
        statusEl.textContent = 'Processing...';
        statusEl.className = 'spotify-manual-status';
    }
    
    try {
        const response = await fetch('/api/spotify/manual-callback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ callback_url: callbackUrl })
        });
        const data = await response.json();
        
        if (data.error) {
            if (statusEl) {
                statusEl.textContent = data.message || 'Failed to complete authorization';
                statusEl.className = 'spotify-manual-status error';
            }
            return;
        }
        
        if (data.success) {
            if (statusEl) {
                statusEl.textContent = 'Connected successfully!';
                statusEl.className = 'spotify-manual-status success';
            }
            
            // Reset the manual flow UI
            setTimeout(async () => {
                cancelSpotifyAuth();
                // Refresh Spotify status
                state.spotify.connected = true;
                await updateSpotifyStatus();
                updateSpotifyCardVisibility();
                // Start polling for now playing (Spotify Connect mode)
                startNowPlayingPolling();
            }, 1500);
        }
    } catch (err) {
        console.error('Failed to submit callback:', err);
        if (statusEl) {
            statusEl.textContent = 'Network error. Please try again.';
            statusEl.className = 'spotify-manual-status error';
        }
    }
}

async function disconnectSpotify() {
    try {
        // Stop polling
        stopNowPlayingPolling();
        stopProgressUpdates();
        
        const response = await fetch('/api/spotify/disconnect', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            state.spotify.connected = false;
            state.spotify.track = null;
            state.spotify.deviceId = null;
            state.spotify.isPlaying = false;
            await updateSpotifyStatus();
            updateSpotifyCardVisibility();
        }
    } catch (err) {
        console.error('Failed to disconnect Spotify:', err);
    }
}

async function resetSpotifyConnection() {
    // Force disconnect everything and clear state
    console.log('Resetting Spotify connection...');
    
    // Stop polling and progress updates
    stopNowPlayingPolling();
    stopProgressUpdates();
    
    // Clear local state
    state.spotify.connected = false;
    state.spotify.configured = false;
    state.spotify.track = null;
    state.spotify.deviceId = null;
    state.spotify.isPlaying = false;
    state.spotify.error = null;
    
    // Call backend disconnect
    try {
        await fetch('/api/spotify/disconnect', { method: 'POST' });
    } catch (e) {
        console.log('Backend disconnect error (ignoring):', e);
    }
    
    // Update UI
    await updateSpotifyStatus();
    updateSpotifyCardVisibility();
    
    // Hide manual flow if visible
    cancelSpotifyAuth();
    
    // Show confirmation
    alert('Spotify connection reset. You can now reconnect.');
}

async function fetchNowPlaying() {
    if (!state.spotify.connected) return;
    
    try {
        const response = await fetch('/api/spotify/now-playing');
        const data = await response.json();
        
        if (data.error) {
            if (data.error.code === 'not_connected' || data.error.code === 'needs_reauth') {
                state.spotify.connected = false;
                stopNowPlayingPolling();
                updateSpotifyCardVisibility();
                return;
            }
            // Don't show error for "no device" - just means nothing is playing
            if (data.error.code !== 'no_device') {
                state.spotify.error = data.error;
            }
            return;
        }
        
        state.spotify.error = null;
        state.spotify.isPlaying = data.is_playing || false;
        state.spotify.position = data.progress_ms || 0;
        
        if (data.track) {
            state.spotify.track = data.track;
            state.spotify.duration = data.track.duration_ms || 0;
        } else {
            state.spotify.track = null;
        }
        
        // Update device info if available
        if (data.device) {
            state.spotify.deviceId = data.device.id;
            const statusEl = document.getElementById('spotifyPlayerStatus');
            if (statusEl) {
                // Use device name, fallback to WallClock if Unknown or empty
                const deviceName = (data.device.name && data.device.name !== 'Unknown') 
                    ? data.device.name 
                    : 'WallClock';
                statusEl.textContent = `Playing on ${deviceName}`;
            }
        }
        
        updateNowPlayingUI();
        updatePlayPauseButton();
        updateProgressBar();
        updateSpotifyCardVisibility();
        
        // Start/stop progress simulation based on play state
        if (state.spotify.isPlaying) {
            startProgressUpdates();
        } else {
            stopProgressUpdates();
        }
        
    } catch (err) {
        console.error('Failed to fetch now playing:', err);
    }
}

function updateNowPlayingUI() {
    const ghostPlayer = document.getElementById('ghostPlayer');
    const albumArt = document.getElementById('ghostAlbumArt');
    const trackTitle = document.getElementById('ghostTrackTitle');
    const trackArtist = document.getElementById('ghostTrackArtist');
    
    if (!state.spotify.track || !state.spotify.isPlaying) {
        // Hide ghost player when nothing is playing
        ghostPlayer?.classList.add('hidden');
        return;
    }
    
    // Show ghost player
    ghostPlayer?.classList.remove('hidden');
    
    // Update album art
    if (albumArt) {
        albumArt.src = state.spotify.track.image || '';
    }
    
    // Update track info (simple text, no scrolling for ghost player)
    if (trackTitle) {
        trackTitle.textContent = state.spotify.track.name || '';
    }
    
    if (trackArtist) {
        trackArtist.textContent = state.spotify.track.artist || '';
    }
}

function updatePlayPauseButton() {
    // Update ghost player buttons
    const playIcon = document.querySelector('#ghostPlayer .play-icon');
    const pauseIcon = document.querySelector('#ghostPlayer .pause-icon');
    
    if (state.spotify.isPlaying) {
        playIcon?.classList.add('hidden');
        pauseIcon?.classList.remove('hidden');
    } else {
        playIcon?.classList.remove('hidden');
        pauseIcon?.classList.add('hidden');
    }
}

function updateGhostPlayerVisibility() {
    const ghostPlayer = document.getElementById('ghostPlayer');
    if (!ghostPlayer) return;
    
    // Show ghost player only when connected AND playing
    if (state.spotify.connected && state.spotify.isPlaying && state.spotify.track) {
        ghostPlayer.classList.remove('hidden');
    } else {
        ghostPlayer.classList.add('hidden');
    }
}

// Alias for backwards compatibility
function updateSpotifyCardVisibility() {
    updateGhostPlayerVisibility();
}

function showSpotifyError(message) {
    // Ghost player is minimal - just log errors to console
    // Errors can be seen in the settings panel or browser console
    console.warn('Spotify:', message);
}

async function toggleSpotifyPlayback() {
    if (!state.spotify.connected) {
        showSpotifyError('Spotify not connected');
        return;
    }
    
    try {
        const endpoint = state.spotify.isPlaying ? '/api/spotify/pause' : '/api/spotify/play';
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();
        
        if (data.error) {
            // If no device, try to transfer to Wall Clock first
            if (data.error.code === 'no_device') {
                showSpotifyError('No active device. Transferring to Wall Clock...');
                await transferToWallClock();
                return;
            }
            showSpotifyError(data.error.message || 'Playback failed');
            return;
        }
        
        // Toggle state optimistically
        state.spotify.isPlaying = !state.spotify.isPlaying;
        updatePlayPauseButton();
        
        // Fetch actual state
        setTimeout(fetchNowPlaying, 500);
    } catch (err) {
        console.error('Playback toggle error:', err);
        showSpotifyError('Failed to toggle playback');
    }
}

async function spotifyNext() {
    if (!state.spotify.connected) return;
    
    try {
        await fetch('/api/spotify/next', { method: 'POST' });
        setTimeout(fetchNowPlaying, 500);
    } catch (err) {
        console.error('Skip next error:', err);
    }
}

async function spotifyPrev() {
    if (!state.spotify.connected) return;
    
    try {
        await fetch('/api/spotify/previous', { method: 'POST' });
        setTimeout(fetchNowPlaying, 500);
    } catch (err) {
        console.error('Skip prev error:', err);
    }
}

// ============================================================================
// Initialize
// ============================================================================

async function init() {
    console.log('Initializing Wall Clock...');

    // Start clock
    updateTime();
    setInterval(updateTime, 1000);

    // Initialize theme systems
    initTheme();
    initBgTheme();
    initGlassOpacitySlider();
    initHolidayTheme();
    initWeatherEffects();
    
    // Initialize orientation and touch mode
    initOrientationAndTouch();
    
    // Initialize quick add event panel
    initQuickAddEvent();
    
    // Initialize Spotify
    initSpotify();
    
    // Initialize Jarvis AI Agent
    initJarvis();
    
    // Initialize mini calendar
    if (typeof initMiniCalendar === "function") {
 initMiniCalendar();
 }
    
    // Add loading states
    document.querySelectorAll('.card').forEach(c => c.classList.add('loading'));
    
    // Fetch initial data
    await Promise.all([fetchWeather(), fetchCalendar(), fetchNotes()]);
    
    // Check Nest status and fetch data if connected
    checkNestStatus();
    
    // Connect WebSocket
    connectWebSocket();

    // Calendar event cycling (every 5 seconds for each card)
    setInterval(cycleTodayEvents, 5000);
    setInterval(cycleUpcomingEvents, 5000);
    
    // Periodic refresh (every 5 minutes)
    setInterval(() => {
        fetchWeather();
        fetchCalendar();
        fetchNotes();
        checkNestStatus();  // Re-check Nest connection
    }, 300000);
    
    // Nest data refresh (every 60 seconds when connected)
    setInterval(() => {
        if (nestConnected) fetchNestData();
    }, 60000);
    
    console.log('Wall Clock ready');
}

// Start
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Visibility change handler
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        fetchWeather();
        fetchCalendar();
        fetchNotes();
        fetchJarvisBriefing();
        checkNestStatus();
        checkTheme();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'F11') {
        e.preventDefault();
        document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
    }
    if (e.key === 'r' || e.key === 'R') {
        fetchWeather();
        fetchCalendar();
        fetchNotes();
        checkNestStatus();
    }
    if (e.key === 't' || e.key === 'T') {
        // Cycle day/night themes
        const themes = ['auto', 'light', 'dark'];
        const next = themes[(themes.indexOf(state.theme) + 1) % themes.length];
        setTheme(next);
    }
    if (e.key === 'b' || e.key === 'B') {
        // Cycle background themes
        const bgThemes = ['flowcean', 'aurora', 'nebula', 'lava', 'forest', 'sunset', 'ocean', 'neon', 'minimal', 'candy'];
        const next = bgThemes[(bgThemes.indexOf(state.bgTheme) + 1) % bgThemes.length];
        setBgTheme(next);
    }
});

// Manual holiday setter for testing
function setHoliday(holidayName) {
    if (holidayName === null || holidayName === 'none') {
        document.documentElement.removeAttribute('data-holiday');
        document.getElementById('holidayEffects').innerHTML = '';
        state.holiday = null;
        console.log('Holiday theme cleared');
    } else {
        document.documentElement.setAttribute('data-holiday', holidayName);
        createHolidayEffects(holidayName);
        state.holiday = { name: holidayName };
        console.log('Holiday theme set to:', holidayName);
    }
}

// Export for debugging
window.wallClock = {
    state,
    setTheme,
    setBgTheme,
    setHoliday,  // Test holidays: wallClock.setHoliday('christmas')
    setWeatherEffect,  // Test weather: wallClock.setWeatherEffect('rain')
    toggleWeatherEffects,
    setOrientation,    // wallClock.setOrientation('portrait')
    toggleTouchMode,   // wallClock.toggleTouchMode()
    openQuickAdd,      // wallClock.openQuickAdd()
    refresh: () => { fetchWeather(); fetchCalendar(); fetchNotes(); checkNestStatus(); }
};
// ============================================================================
// Mini Calendar System
// ============================================================================

// Comprehensive emoji mapping for event keywords
const EVENT_EMOJI_MAP = {
    // Work & Professional
    'work': '💼',
    'office': '🏢',
    'meeting': '🤝',
    'conference': '📊',
    'presentation': '📽️',
    'interview': '🎤',
    'deadline': '⏰',
    'project': '📋',
    'client': '👔',
    'call': '📞',
    'zoom': '💻',
    'teams': '💻',
    'webinar': '🖥️',
    
    // Health & Medical
    'doctor': '👨‍⚕️',
    'dentist': '🦷',
    'appointment': '📅',
    'hospital': '🏥',
    'therapy': '🧠',
    'checkup': '🩺',
    'vaccine': '💉',
    'pharmacy': '💊',
    'optometrist': '👓',
    'vet': '🐾',
    
    // Fitness & Sports
    'gym': '💪',
    'workout': '🏋️',
    'exercise': '🏃',
    'yoga': '🧘',
    'swimming': '🏊',
    'swim': '🏊',
    'pool': '🏊',
    'tennis': '🎾',
    'golf': '⛳',
    'basketball': '🏀',
    'football': '🏈',
    'soccer': '⚽',
    'baseball': '⚾',
    'hockey': '🏒',
    'running': '🏃',
    'run': '🏃',
    'marathon': '🏃',
    'bike': '🚴',
    'cycling': '🚴',
    'hike': '🥾',
    'hiking': '🥾',
    'ski': '⛷️',
    'skiing': '⛷️',
    'snowboard': '🏂',
    
    // Celebrations & Social
    'birthday': '🎂',
    'bday': '🎂',
    'party': '🎉',
    'celebration': '🎊',
    'anniversary': '💍',
    'wedding': '💒',
    'shower': '🎀',
    'graduation': '🎓',
    'reunion': '👨‍👩‍👧‍👦',
    
    // Food & Dining
    'dinner': '🍽️',
    'lunch': '🍴',
    'breakfast': '🥞',
    'brunch': '🥂',
    'restaurant': '🍽️',
    'coffee': '☕',
    'drinks': '🍻',
    'bar': '🍺',
    'bbq': '🍖',
    'barbecue': '🍖',
    'picnic': '🧺',
    'potluck': '🥘',
    
    // Travel & Transportation
    'flight': '✈️',
    'fly': '✈️',
    'airport': '✈️',
    'travel': '🧳',
    'trip': '🗺️',
    'vacation': '🏖️',
    'hotel': '🏨',
    'cruise': '🚢',
    'road trip': '🚗',
    'camping': '⛺',
    'beach': '🏖️',
    
    // Education & Learning
    'school': '📚',
    'class': '📖',
    'lecture': '🎓',
    'exam': '📝',
    'test': '📝',
    'study': '📖',
    'homework': '✏️',
    'tutor': '👨‍🏫',
    'lesson': '📕',
    'course': '📚',
    'training': '🎯',
    
    // Entertainment
    'movie': '🎬',
    'cinema': '🎬',
    'theater': '🎭',
    'theatre': '🎭',
    'concert': '🎵',
    'show': '🎪',
    'game': '🎮',
    'gaming': '🎮',
    'museum': '🏛️',
    'zoo': '🦁',
    'aquarium': '🐠',
    'amusement': '🎢',
    'park': '🌳',
    
    // Shopping & Errands
    'shopping': '🛒',
    'groceries': '🛒',
    'store': '🏪',
    'mall': '🛍️',
    'haircut': '💇',
    'salon': '💅',
    'spa': '🧖',
    'car': '🚗',
    'mechanic': '🔧',
    'repair': '🔨',
    'bank': '🏦',
    'post office': '📮',
    'dmv': '🪪',
    
    // Home & Family
    'home': '🏠',
    'house': '🏡',
    'move': '📦',
    'moving': '📦',
    'clean': '🧹',
    'cleaning': '🧹',
    'laundry': '🧺',
    'garden': '🌱',
    'gardening': '🌻',
    'pet': '🐕',
    'dog': '🐕',
    'cat': '🐱',
    'babysit': '👶',
    'kids': '👧',
    'family': '👨‍👩‍👧',
    'playdate': '🧸',
    
    // Holidays & Special Days
    'christmas': '🎄',
    'xmas': '🎄',
    'thanksgiving': '🦃',
    'easter': '🐰',
    'halloween': '🎃',
    'new year': '🎆',
    'valentine': '💝',
    'mothers day': '💐',
    'fathers day': '👔',
    'memorial': '🇺🇸',
    'independence': '🎆',
    '4th of july': '🎇',
    'labor day': '🛠️',
    
    // Religious & Spiritual
    'church': '⛪',
    'mass': '⛪',
    'service': '🙏',
    'bible': '📖',
    'temple': '🛕',
    'mosque': '🕌',
    'synagogue': '🕍',
    'prayer': '🙏',
    'meditation': '🧘',
    
    // Finance & Legal
    'tax': '📑',
    'taxes': '📑',
    'accountant': '🧮',
    'lawyer': '⚖️',
    'court': '⚖️',
    'insurance': '📋',
    'mortgage': '🏦',
    
    // Tech & Creative
    'photo': '📸',
    'photography': '📷',
    'video': '🎥',
    'podcast': '🎙️',
    'stream': '📡',
    'art': '🎨',
    'paint': '🖌️',
    'craft': '✂️',
    'music': '🎵',
    'piano': '🎹',
    'guitar': '🎸',
    'band': '🎸',
    'dance': '💃',
    'ballet': '🩰',
    
    // Weather-related activities
    'rain': '🌧️',
    'snow': '❄️',
    'sunny': '☀️',
    
    // Miscellaneous
    'reminder': '🔔',
    'important': '⭐',
    'urgent': '🚨',
    'todo': '✅',
    'follow up': '📌',
    'review': '🔍',
    'sign': '✍️',
    'pickup': '📦',
    'drop off': '📬',
    'delivery': '📦',
    'volunteer': '🤲',
    'charity': '❤️',
    'donate': '💝',
    'vote': '🗳️',
    'election': '🗳️'
};

// Default emoji for events that don't match any keyword
const DEFAULT_EVENT_EMOJI = '📌';

// Calendar state
let calendarState = {
    currentMonth: new Date().getMonth(),
    currentYear: new Date().getFullYear(),
    allEvents: [] // Will store all calendar events
};

/**
 * Get emoji(s) for an event based on its title
 */
function getEventEmoji(eventTitle) {
    if (!eventTitle) return DEFAULT_EVENT_EMOJI;
    
    const titleLower = eventTitle.toLowerCase();
    const matchedEmojis = [];
    
    // Check each keyword in the map
    for (const [keyword, emoji] of Object.entries(EVENT_EMOJI_MAP)) {
        if (titleLower.includes(keyword)) {
            if (!matchedEmojis.includes(emoji)) {
                matchedEmojis.push(emoji);
            }
        }
    }
    
    // Return matched emoji(s) or default
    return matchedEmojis.length > 0 ? matchedEmojis[0] : DEFAULT_EVENT_EMOJI;
}

/**
 * Get all emojis for multiple events on a day
 */
function getDayEmojis(events) {
    const emojis = new Set();
    events.forEach(event => {
        emojis.add(getEventEmoji(event.title));
    });
    return Array.from(emojis);
}

/**
 * Get events for a specific date
 */
function getEventsForDate(year, month, day) {
    const targetDate = new Date(year, month, day);
    const targetDateStr = targetDate.toDateString();
    
    return calendarState.allEvents.filter(event => {
        const eventDate = new Date(event.datetime || event.date);
        return eventDate.toDateString() === targetDateStr;
    });
}

/**
 * Generate the mini calendar
 */
function generateMiniCalendar() {
    const container = document.getElementById('calendarDays');
    const monthYearEl = document.getElementById('calMonthYear');
    
    if (!container || !monthYearEl) return;
    
    const year = calendarState.currentYear;
    const month = calendarState.currentMonth;
    
    // Update month/year display
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'];
    monthYearEl.textContent = `${monthNames[month]} ${year}`;
    
    // Get first day of month and total days
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrevMonth = new Date(year, month, 0).getDate();
    
    // Today's date for highlighting
    const today = new Date();
    const isCurrentMonth = today.getMonth() === month && today.getFullYear() === year;
    
    // Clear container
    container.innerHTML = '';
    
    // Add days from previous month
    for (let i = firstDay - 1; i >= 0; i--) {
        const dayNum = daysInPrevMonth - i;
        const dayEl = createDayElement(dayNum, year, month - 1, true);
        container.appendChild(dayEl);
    }
    
    // Add days of current month
    for (let day = 1; day <= daysInMonth; day++) {
        const isToday = isCurrentMonth && day === today.getDate();
        const dayEl = createDayElement(day, year, month, false, isToday);
        container.appendChild(dayEl);
    }
    
    // Add days from next month to complete the grid
    const totalCells = container.children.length;
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    
    for (let i = 1; i <= remainingCells; i++) {
        const dayEl = createDayElement(i, year, month + 1, true);
        container.appendChild(dayEl);
    }
}

/**
 * Create a day element for the calendar
 */
function createDayElement(day, year, month, isOtherMonth = false, isToday = false) {
    const dayEl = document.createElement('div');
    dayEl.className = 'calendar-day';
    
    if (isOtherMonth) {
        dayEl.classList.add('other-month');
    }
    
    if (isToday) {
        dayEl.classList.add('today');
    }
    
    // Check for events on this day
    const events = getEventsForDate(year, month, day);
    
    if (events.length > 0) {
        dayEl.classList.add('has-events');
    }
    
    // Day number
    const dayNumber = document.createElement('span');
    dayNumber.className = 'day-number';
    dayNumber.textContent = day;
    dayEl.appendChild(dayNumber);
    
    // Event emoji indicators
    if (events.length > 0) {
        const emojis = getDayEmojis(events);
        
        if (emojis.length <= 3) {
            const emojisContainer = document.createElement('div');
            emojisContainer.className = 'day-emojis';
            emojis.slice(0, 3).forEach(emoji => {
                const emojiSpan = document.createElement('span');
                emojiSpan.className = 'day-emoji';
                emojiSpan.textContent = emoji;
                emojisContainer.appendChild(emojiSpan);
            });
            dayEl.appendChild(emojisContainer);
        } else {
            // Too many events - show count
            const countEl = document.createElement('span');
            countEl.className = 'event-count';
            countEl.textContent = `${events.length}`;
            dayEl.appendChild(countEl);
        }
    }
    
    // Click handler
    dayEl.addEventListener('click', () => {
        if (!isOtherMonth || events.length > 0) {
            showDayPopup(year, month, day, events);
        }
    });
    
    return dayEl;
}

/**
 * Show popup with events for a specific day
 */
function showDayPopup(year, month, day, events) {
    const overlay = document.getElementById('dayPopupOverlay');
    const titleEl = document.getElementById('dayPopupTitle');
    const contentEl = document.getElementById('dayPopupContent');
    
    if (!overlay || !titleEl || !contentEl) return;
    
    // Format date for title
    const date = new Date(year, month, day);
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    titleEl.textContent = date.toLocaleDateString('en-US', options);
    
    // Clear content
    contentEl.innerHTML = '';
    
    if (events.length === 0) {
        // No events message
        const noEvents = document.createElement('div');
        noEvents.className = 'popup-no-events';
        noEvents.innerHTML = `
            <div class="popup-no-events-emoji">📭</div>
            <div class="popup-no-events-text">No events scheduled</div>
        `;
        contentEl.appendChild(noEvents);
    } else {
        // List events
        events.forEach(event => {
            const eventEl = document.createElement('div');
            eventEl.className = 'popup-event';
            
            const emoji = getEventEmoji(event.title);
            const time = event.time || 'All Day';
            
            eventEl.innerHTML = `
                <span class="popup-event-emoji">${emoji}</span>
                <div class="popup-event-details">
                    <p class="popup-event-title">${event.title || 'Untitled Event'}</p>
                    <p class="popup-event-time">${time}</p>
                </div>
            `;
            contentEl.appendChild(eventEl);
        });
    }
    
    // Show overlay
    overlay.classList.add('open');
}

/**
 * Close the day popup
 */
function closeDayPopup() {
    const overlay = document.getElementById('dayPopupOverlay');
    if (overlay) {
        overlay.classList.remove('open');
    }
}

/**
 * Navigate to previous month
 */
function prevMonth() {
    calendarState.currentMonth--;
    if (calendarState.currentMonth < 0) {
        calendarState.currentMonth = 11;
        calendarState.currentYear--;
    }
    generateMiniCalendar();
}

/**
 * Navigate to next month
 */
function nextMonth() {
    calendarState.currentMonth++;
    if (calendarState.currentMonth > 11) {
        calendarState.currentMonth = 0;
        calendarState.currentYear++;
    }
    generateMiniCalendar();
}

/**
 * Update calendar with new events data
 */
function updateCalendarEvents(events) {
    // Combine today and upcoming events
    calendarState.allEvents = [];
    
    if (Array.isArray(events)) {
        calendarState.allEvents = events;
    } else if (events && typeof events === 'object') {
        if (events.today) {
            calendarState.allEvents = calendarState.allEvents.concat(events.today);
        }
        if (events.upcoming) {
            calendarState.allEvents = calendarState.allEvents.concat(events.upcoming);
        }
    }
    
    // Regenerate calendar with new data
    generateMiniCalendar();
}

/**
 * Initialize the mini calendar
 */
function initMiniCalendar() {
    // Set up navigation buttons
    const prevBtn = document.getElementById('calPrevMonth');
    const nextBtn = document.getElementById('calNextMonth');
    
    if (prevBtn) prevBtn.addEventListener('click', prevMonth);
    if (nextBtn) nextBtn.addEventListener('click', nextMonth);
    
    // Set up popup close handlers
    const closeBtn = document.getElementById('dayPopupClose');
    const overlay = document.getElementById('dayPopupOverlay');
    
    if (closeBtn) closeBtn.addEventListener('click', closeDayPopup);
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeDayPopup();
        });
    }
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDayPopup();
    });
    
    // Generate initial calendar
    generateMiniCalendar();
}

