// Global Interactive Frontend Helpers

document.addEventListener('DOMContentLoaded', () => {
    initCardGlowEffects();
    initScrollAnimations();
});

// 1. Mouse-following Radial Glow Effect for Glass Cards
function initCardGlowEffects() {
    document.addEventListener('mousemove', (e) => {
        const cards = document.querySelectorAll('.glass-card, .article-card');
        cards.forEach(card => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });
}

// 2. Scroll Animation Observer (Fade-in on scroll)
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.15
    });

    const animatedElements = document.querySelectorAll('.scroll-reveal');
    animatedElements.forEach(el => observer.observe(el));
}

// 3. Modal Toggles
function toggleModal(modalId, show = true) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    if (show) {
        modal.classList.add('active');
    } else {
        modal.classList.remove('active');
    }
}

// 4. Custom SVG Chart Renderer for Dashboard activity
function renderActivityChart(canvasId, dataPoints) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    
    // Scale for high-resolution displays
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    
    ctx.clearRect(0, 0, width, height);
    
    if (!dataPoints || dataPoints.length === 0) {
        dataPoints = [5, 12, 8, 15, 20, 10, 25]; // Fallback mock values
    }
    
    const maxVal = Math.max(...dataPoints, 10);
    const padding = 30;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;
    const stepX = chartWidth / (dataPoints.length - 1);
    
    // Draw Grid Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + chartHeight * (i / 4);
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }
    
    // Calculate coordinates
    const points = dataPoints.map((val, idx) => {
        const x = padding + idx * stepX;
        const y = padding + chartHeight - (val / maxVal) * chartHeight;
        return { x, y };
    });
    
    // Draw Glow Area Path (Gradient fill)
    const gradient = ctx.createLinearGradient(0, padding, 0, height - padding);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.2)');
    gradient.addColorStop(1, 'rgba(168, 85, 247, 0)');
    
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.moveTo(points[0].x, height - padding);
    
    // Smooth Bezier Curve mapping
    for (let i = 0; i < points.length; i++) {
        if (i === 0) {
            ctx.lineTo(points[i].x, points[i].y);
        } else {
            const cpX1 = points[i-1].x + stepX / 2;
            const cpY1 = points[i-1].y;
            const cpX2 = points[i].x - stepX / 2;
            const cpY2 = points[i].y;
            ctx.bezierCurveTo(cpX1, cpY1, cpX2, cpY2, points[i].x, points[i].y);
        }
    }
    ctx.lineTo(points[points.length - 1].x, height - padding);
    ctx.closePath();
    ctx.fill();
    
    // Draw main stroke line
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 3;
    ctx.shadowColor = 'rgba(6, 182, 212, 0.5)';
    ctx.shadowBlur = 10;
    
    ctx.beginPath();
    for (let i = 0; i < points.length; i++) {
        if (i === 0) {
            ctx.moveTo(points[i].x, points[i].y);
        } else {
            const cpX1 = points[i-1].x + stepX / 2;
            const cpY1 = points[i-1].y;
            const cpX2 = points[i].x - stepX / 2;
            const cpY2 = points[i].y;
            ctx.bezierCurveTo(cpX1, cpY1, cpX2, cpY2, points[i].x, points[i].y);
        }
    }
    ctx.stroke();
    
    // Reset shadow
    ctx.shadowBlur = 0;
    
    // Draw Data Dots
    points.forEach((pt) => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 5, 0, 2 * Math.PI);
        ctx.fillStyle = '#a855f7';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
    });
}
