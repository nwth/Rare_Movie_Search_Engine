/**
 * CineSeeker - Rare Movie Search Engine Frontend
 * Phase 1: MVP Search Interface
 */

class CineSeeker {
    constructor() {
        this.elements = {
            form: document.getElementById('searchForm'),
            input: document.getElementById('searchInput'),
            searchBtn: document.getElementById('searchBtn'),
            hero: document.getElementById('hero'),
            loading: document.getElementById('loadingState'),
            results: document.getElementById('resultsSection'),
            resultsList: document.getElementById('resultsList'),
            resultsCount: document.getElementById('resultsCount'),
            searchTime: document.getElementById('searchTime'),
            sourcesList: document.getElementById('sourcesList'),
            emptyState: document.getElementById('emptyState'),
            errorState: document.getElementById('errorState'),
            errorMessage: document.getElementById('errorMessage'),
            retryBtn: document.getElementById('retryBtn'),
            filterBar: document.getElementById('filterBar'),
            toast: document.getElementById('toast'),
        };

        this.currentQuery = '';
        this.currentResults = [];
        this.activeFilter = 'all';

        this.init();
    }

    init() {
        this.elements.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSearch();
        });

        this.elements.retryBtn.addEventListener('click', () => {
            this.handleSearch();
        });

        // Hint chips
        document.querySelectorAll('.hint-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                this.elements.input.value = chip.dataset.query;
                this.handleSearch();
            });
        });

        // Filter buttons
        this.elements.filterBar.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;
            this.activeFilter = btn.dataset.filter;
            this.elements.filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            this.renderResults();
        });

        // Enter key triggers search
        this.elements.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleSearch();
            }
        });
    }

    async handleSearch() {
        const query = this.elements.input.value.trim();
        if (!query) {
            this.showToast('请输入电影名称');
            return;
        }

        this.currentQuery = query;
        this.currentResults = [];
        this.activeFilter = 'all';

        // Reset UI
        this.elements.results.classList.remove('active');
        this.elements.emptyState.classList.remove('active');
        this.elements.errorState.classList.remove('active');
        this.elements.loading.classList.add('active');
        this.elements.searchBtn.disabled = true;

        // Reset filter bar
        this.elements.filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('.filter-btn[data-filter="all"]')?.classList.add('active');

        try {
            const data = await this.fetchResults(query);
            this.currentResults = data.results;
            this.renderResults(data);
            this.showResults(data);
        } catch (err) {
            this.showError(err.message || '搜索请求失败，请检查网络连接');
        } finally {
            this.elements.loading.classList.remove('active');
            this.elements.searchBtn.disabled = false;
        }
    }

    async fetchResults(query) {
        const url = `/api/search?q=${encodeURIComponent(query)}&max_results=30`;
        const response = await fetch(url);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }

    showResults(data) {
        this.elements.results.classList.add('active');

        // Summary
        this.elements.resultsCount.textContent = data.total_count;
        this.elements.searchTime.textContent = `${data.search_time_ms}ms`;

        // Sources
        const sourceNames = {
            google_dork: 'Google Dork',
            the_pirate_bay: 'TPB',
            '1337x': '1337x',
            yts: 'YTS',
            btdigg: 'BTDigg',
            rarbg: 'RARBG',
        };
        this.elements.sourcesList.textContent = data.sources_used
            .map(s => sourceNames[s] || s)
            .join(', ');

        // Scroll to results
        this.elements.results.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    renderResults() {
        const list = this.elements.resultsList;
        list.innerHTML = '';

        const filtered = this.activeFilter === 'all'
            ? this.currentResults
            : this.currentResults.filter(r => r.resource_type === this.activeFilter);

        if (filtered.length === 0) {
            this.elements.emptyState.classList.add('active');
            return;
        }

        this.elements.emptyState.classList.remove('active');

        filtered.forEach(result => {
            const card = this.createResultCard(result);
            list.appendChild(card);
        });
    }

    createResultCard(result) {
        const card = document.createElement('div');
        card.className = 'result-card';

        // Resource type label
        const typeLabels = {
            magnet: '磁力',
            torrent: '种子',
            cloud_drive: '网盘',
            stream: '在线',
            ed2k: 'ED2K',
        };

        const sourceNames = {
            google_dork: 'Google',
            the_pirate_bay: 'TPB',
            '1337x': '1337x',
            yts: 'YTS',
            btdigg: 'BTDigg',
            rarbg: 'RARBG',
        };

        // Badges
        let badgesHtml = `<span class="badge badge-${result.resource_type}">${typeLabels[result.resource_type] || result.resource_type}</span>`;
        if (result.resolution) {
            badgesHtml += `<span class="badge badge-resolution">${result.resolution}</span>`;
        }

        // Meta info
        let metaHtml = '';
        if (result.seeders !== null && result.seeders !== undefined) {
            metaHtml += `<span class="meta-item"><span class="icon">⬆</span> ${result.seeders} 做种</span>`;
        }
        if (result.size) {
            metaHtml += `<span class="meta-item"><span class="icon">💾</span> ${result.size}</span>`;
        }
        metaHtml += `<span class="meta-item"><span class="icon">📡</span> ${sourceNames[result.source] || result.source}</span>`;

        // Stars for quality score
        const stars = result.quality_score > 0
            ? `<span class="quality-score">★ ${result.quality_score.toFixed(1)}</span>`
            : '';

        const displayUrl = result.url.length > 80
            ? result.url.substring(0, 80) + '...'
            : result.url;

        card.innerHTML = `
            <div class="result-card-header">
                <div class="result-title">${this.escapeHtml(result.title)} ${stars}</div>
                <div class="result-badges">${badgesHtml}</div>
            </div>
            <div class="result-card-meta">${metaHtml}</div>
            <div class="result-card-meta" style="font-size:0.75rem;color:var(--text-muted);word-break:break-all;font-family:monospace;">${this.escapeHtml(displayUrl)}</div>
            <div class="result-card-actions">
                <button class="copy-btn" data-url="${this.escapeHtml(result.url)}">📋 复制链接</button>
                <button class="open-btn" data-url="${this.escapeHtml(result.url)}">🔗 打开链接</button>
            </div>
        `;

        // Event listeners
        card.querySelector('.copy-btn').addEventListener('click', () => {
            this.copyToClipboard(result.url);
        });

        card.querySelector('.open-btn').addEventListener('click', () => {
            if (result.url.startsWith('magnet:')) {
                window.location.href = result.url;
            } else {
                window.open(result.url, '_blank');
            }
        });

        return card;
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('链接已复制到剪贴板');
        }).catch(() => {
            // Fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            this.showToast('链接已复制到剪贴板');
        });
    }

    showError(message) {
        this.elements.errorState.classList.add('active');
        this.elements.errorMessage.textContent = message;
        this.elements.results.classList.remove('active');
    }

    showToast(message) {
        const toast = this.elements.toast;
        toast.textContent = message;
        toast.classList.add('show');
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            toast.classList.remove('show');
        }, 2500);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new CineSeeker();
});
