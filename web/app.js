// Base API URL
const API_URL = 'http://127.0.0.1:5000/api/previews';

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    fetchAndRenderMatchCards();
    setupIntersectionObserver();
    setupModal();
});

// Fetch data from API and Render Match Cards
async function fetchAndRenderMatchCards() {
    const container = document.getElementById('match-container');
    
    try {
        const response = await fetch(API_URL);
        const json = await response.json();
        
        if (json.status !== 'success' || !json.data || json.data.length === 0) {
            container.innerHTML = '<p class="text-muted text-center" style="grid-column: 1/-1;">No previews available yet. The AI is analyzing upcoming matches...</p>';
            return;
        }
        
        const matchData = json.data;
        container.innerHTML = ''; // clear loading state
        
        matchData.forEach(match => {
            const card = document.createElement('div');
            card.className = 'match-card fade-in';
            
            // Format time and text snippets
            const matchDate = new Date(match.match_time).toLocaleString('en-GB', {
                weekday: 'short', hour: '2-digit', minute:'2-digit'
            }) !== 'Invalid Date' ? new Date(match.match_time).toLocaleString('en-GB', {weekday: 'short', hour: '2-digit', minute:'2-digit'}) : match.match_time;
            
            // Just extracting a brief summary sentence from the preview text, or using the first 100 chars
            let snippet = match.preview_text;
            if (snippet.length > 120) {
                snippet = snippet.substring(0, 120) + '...';
            }
            
            card.innerHTML = `
                <div class="card-header">
                    <span class="competition">World Cup Qualifiers</span>
                    <span class="date">${matchDate}</span>
                </div>
                <div class="teams">
                    <div class="team">
                        <div class="team-logo">⚽</div>
                        <span class="team-name">${match.home_team}</span>
                    </div>
                    <div class="vs">VS</div>
                    <div class="team">
                        <div class="team-logo">⚽</div>
                        <span class="team-name">${match.away_team}</span>
                    </div>
                </div>
                <div class="preview-snippet">
                    ${snippet}
                </div>
                <div class="card-footer">
                    <button class="btn-card read-preview-btn">Read Full Preview</button>
                </div>
            `;
            
            // Add click listener to the button
            const btn = card.querySelector('.read-preview-btn');
            btn.addEventListener('click', () => {
                openModal(match, matchDate);
            });

            
            container.appendChild(card);
        });
        
        // Re-trigger observer for new elements
        setTimeout(() => {
            document.querySelectorAll('.fade-in').forEach(element => {
                // assume observer is defined globally, or we handle it gracefully if not
                const observerOptions = { root: null, rootMargin: '0px', threshold: 0.1 };
                const observer = new IntersectionObserver((entries, obs) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('visible');
                            obs.unobserve(entry.target);
                        }
                    });
                }, observerOptions);
                observer.observe(element);
            });
        }, 100);
        
    } catch (error) {
        console.error('Error fetching previews:', error);
        container.innerHTML = '<p class="text-muted text-center" style="grid-column: 1/-1;">Could not load match previews. Please check if the API is running.</p>';
    }
}

// Removed static renderMatchCards

// Intersection Observer for scroll animations
function setupIntersectionObserver() {
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe sections and cards
    setTimeout(() => {
        document.querySelectorAll('.fade-in').forEach(element => {
            observer.observe(element);
        });
    }, 100);
}

// Modal Logic
function setupModal() {
    const modal = document.getElementById('preview-modal');
    const closeBtn = document.querySelector('.close-btn');

    // Close on X click
    closeBtn.addEventListener('click', () => {
        modal.classList.remove('show');
    });

    // Close on outside click
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.classList.remove('show');
        }
    });
}

function openModal(match, matchDate) {
    const modal = document.getElementById('preview-modal');
    const title = document.getElementById('modal-match-title');
    const meta = document.getElementById('modal-match-meta');
    const content = document.getElementById('modal-body-content');

    title.textContent = `${match.home_team} vs ${match.away_team}`;
    meta.textContent = matchDate;
    
    // Parse Markdown to HTML
    if (typeof marked !== 'undefined') {
        content.innerHTML = marked.parse(match.preview_text || 'No preview available.');
    } else {
        content.textContent = match.preview_text; // Fallback
    }

    modal.classList.add('show');
}
