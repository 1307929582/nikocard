document.addEventListener('DOMContentLoaded', function() {
    const btnImport = document.getElementById('btn-import');
    const btnActivate = document.getElementById('btn-activate');
    const keysInput = document.getElementById('keys-input');
    const toast = document.getElementById('toast');
    const activeCardSection = document.getElementById('active-card-section');
    const providerSelect = document.getElementById('provider-select');
    const activateProvider = document.getElementById('activate-provider');
    const keysBody = document.getElementById('keys-body');
    const keysProvider = document.getElementById('keys-provider');
    const keysStatus = document.getElementById('keys-status');
    const keysSearch = document.getElementById('keys-search');
    const keysRefresh = document.getElementById('keys-refresh');
    const keysDelete = document.getElementById('keys-delete');
    const keysSelectAll = document.getElementById('keys-select-all');
    const keysPrev = document.getElementById('keys-prev');
    const keysNext = document.getElementById('keys-next');
    const keysPage = document.getElementById('keys-page');
    const keysSummary = document.getElementById('keys-summary');

    let countdownInterval = null;
    let currentCard = null;
    let keysState = {
        page: 1,
        perPage: 200,
        total: 0,
        loading: false
    };

    if (window.activeCard && window.activeCard.pan) {
        currentCard = window.activeCard;
        displayCard(currentCard);
    }

    function showToast(message, type = 'info') {
        if (!toast) return;
        toast.textContent = message;
        toast.className = 'toast show ' + type;
        setTimeout(() => {
            toast.className = 'toast';
        }, 3000);
    }

    function updateStats(stats) {
        const unusedEl = document.getElementById('stat-unused');
        const usedEl = document.getElementById('stat-used');
        const totalEl = document.getElementById('stat-total');
        if (!unusedEl || !usedEl || !totalEl) return;
        unusedEl.textContent = stats.unused;
        usedEl.textContent = stats.used;
        totalEl.textContent = stats.total;
    }

    function formatDate(value) {
        if (!value) return '-';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return value;
        return d.toLocaleString();
    }

    function renderKeys(keys) {
        if (!keysBody) return;
        if (!keys || keys.length === 0) {
            keysBody.innerHTML = '<tr><td colspan="7" class="keys-empty">暂无数据</td></tr>';
            return;
        }
        const statusMap = {
            unused: '未使用',
            used: '已使用',
            failed: '失败'
        };
        keysBody.innerHTML = keys.map(item => {
            const status = item.status || 'unknown';
            const statusLabel = statusMap[status] || status;
            return `
                <tr>
                    <td><input type="checkbox" class="keys-checkbox" data-id="${item.id}"></td>
                    <td class="copyable" data-copy="key">${item.key_id || ''}</td>
                    <td>${item.provider_name || '-'}</td>
                    <td><span class="keys-status ${status}">${statusLabel}</span></td>
                    <td>${formatDate(item.created_at)}</td>
                    <td>${formatDate(item.used_at)}</td>
                    <td><button class="btn-danger keys-delete-one" data-id="${item.id}">删除</button></td>
                </tr>
            `;
        }).join('');
    }

    function updateKeysSummary() {
        if (!keysSummary) return;
        const total = keysState.total || 0;
        const totalPages = Math.max(1, Math.ceil(total / keysState.perPage));
        keysSummary.textContent = `共 ${total} 条，当前第 ${keysState.page} / ${totalPages} 页`;
        if (keysPage) {
            keysPage.textContent = `${keysState.page} / ${totalPages}`;
        }
        if (keysPrev) keysPrev.disabled = keysState.page <= 1;
        if (keysNext) keysNext.disabled = keysState.page >= totalPages;
    }

    function updateDeleteButtonState() {
        if (!keysDelete) return;
        const checked = document.querySelectorAll('.keys-checkbox:checked');
        keysDelete.disabled = checked.length === 0;
    }

    async function loadKeys() {
        if (!keysBody || keysState.loading) return;
        keysState.loading = true;
        const providerId = keysProvider ? keysProvider.value : '';
        const status = keysStatus ? keysStatus.value : 'all';
        const keyword = keysSearch ? keysSearch.value.trim() : '';

        const params = new URLSearchParams({
            provider_id: providerId,
            status: status,
            q: keyword,
            page: String(keysState.page),
            per_page: String(keysState.perPage)
        });

        try {
            const resp = await fetch(`/api/keys?${params.toString()}`);
            const data = await resp.json();
            if (data.success) {
                keysState.total = data.total || 0;
                renderKeys(data.keys || []);
                updateKeysSummary();
            } else {
                showToast(data.error || '加载失败', 'error');
            }
        } catch (e) {
            showToast('网络错误', 'error');
        } finally {
            keysState.loading = false;
            if (keysSelectAll) keysSelectAll.checked = false;
            updateDeleteButtonState();
        }
    }

    function formatCardNumber(pan) {
        if (!pan) return '**** **** **** ****';
        return pan.replace(/(.{4})/g, '$1 ').trim();
    }

    function displayCard(card) {
        if (!activeCardSection) return;
        currentCard = card;
        activeCardSection.style.display = 'block';

        const panEl = document.getElementById('card-pan');
        const cvvEl = document.getElementById('card-cvv');
        const expiryEl = document.getElementById('card-expiry');
        const typeEl = document.getElementById('card-type');
        const addressEl = document.getElementById('card-address');
        if (!panEl || !cvvEl || !expiryEl || !typeEl || !addressEl) return;

        panEl.textContent = formatCardNumber(card.pan);
        cvvEl.textContent = card.cvv || '***';
        expiryEl.textContent =
            (card.exp_month || 'MM') + '/' + (card.exp_year ? card.exp_year.slice(-2) : 'YY');
        typeEl.textContent = (card.card_type || 'CREDIT').toUpperCase();
        addressEl.textContent = card.address || '未配置地址';

        startCountdown(card.expire_time);
    }

    function startCountdown(expireTime) {
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }

        const expireDate = new Date(expireTime);
        const countdownEl = document.getElementById('countdown');
        if (!countdownEl) return;

        function updateCountdown() {
            const now = new Date();
            const diff = expireDate - now;

            if (diff <= 0) {
                countdownEl.textContent = '已过期';
                clearInterval(countdownInterval);
                return;
            }

            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            countdownEl.textContent =
                String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
        }

        updateCountdown();
        countdownInterval = setInterval(updateCountdown, 1000);
    }

    if (btnImport && keysInput) {
        btnImport.addEventListener('click', async function() {
            const keys = keysInput.value.trim();
            if (!keys) {
                showToast('请输入卡密', 'error');
                return;
            }
            if (!providerSelect || !providerSelect.value) {
                showToast('请选择卡商', 'error');
                return;
            }

            btnImport.disabled = true;
            btnImport.textContent = '导入中...';

            try {
                const resp = await fetch('/api/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        keys: keys,
                        provider_id: providerSelect.value
                    })
                });
                const data = await resp.json();

                if (data.success) {
                    let message = `成功导入 ${data.added} 个卡密`;
                    if (data.invalid) {
                        message += `，无效 ${data.invalid} 个`;
                    }
                    if (data.unchecked) {
                        message += `，校验失败 ${data.unchecked} 个`;
                    }
                    showToast(message, 'success');
                    keysInput.value = '';
                    updateStats(data.stats);
                } else {
                    showToast(data.error || '导入失败', 'error');
                }
            } catch (e) {
                showToast('网络错误', 'error');
            }

            btnImport.disabled = false;
            btnImport.textContent = '导入卡密';
        });
    }

    if (btnActivate) {
        btnActivate.addEventListener('click', async function() {
            if (!activateProvider || !activateProvider.value) {
                showToast('请选择卡商', 'error');
                return;
            }
            btnActivate.disabled = true;
            btnActivate.innerHTML = '<span class="loading">激活中...</span>';

            try {
                const resp = await fetch('/api/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider_id: activateProvider.value
                    })
                });
                const data = await resp.json();

                if (data.success) {
                    if (data.skipped_used) {
                        showToast(`激活成功，已跳过 ${data.skipped_used} 张已使用卡密`, 'success');
                    } else {
                        showToast('激活成功！', 'success');
                    }
                    displayCard(data.card);
                    if (data.stats) updateStats(data.stats);
                    setTimeout(() => location.reload(), 500);
                } else {
                    console.error('激活失败', data);
                    showToast(data.error || '激活失败', 'error');
                    if (data.stats) updateStats(data.stats);
                }
            } catch (e) {
                console.error('激活请求异常', e);
                showToast('网络错误', 'error');
            }

            btnActivate.disabled = false;
            btnActivate.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
                激活卡片
            `;
        });
    }

    if (keysBody) {
        loadKeys();
    }

    if (keysProvider) {
        keysProvider.addEventListener('change', () => {
            keysState.page = 1;
            loadKeys();
        });
    }
    if (keysStatus) {
        keysStatus.addEventListener('change', () => {
            keysState.page = 1;
            loadKeys();
        });
    }
    if (keysSearch) {
        keysSearch.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                keysState.page = 1;
                loadKeys();
            }
        });
    }
    if (keysRefresh) {
        keysRefresh.addEventListener('click', () => {
            loadKeys();
        });
    }
    if (keysSelectAll) {
        keysSelectAll.addEventListener('change', () => {
            const boxes = document.querySelectorAll('.keys-checkbox');
            boxes.forEach(box => {
                box.checked = keysSelectAll.checked;
            });
            updateDeleteButtonState();
        });
    }
    if (keysBody) {
        keysBody.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('keys-checkbox')) {
                updateDeleteButtonState();
            }
        });
        keysBody.addEventListener('click', async (e) => {
            const target = e.target;
            if (!(target instanceof HTMLElement)) return;
            if (target.classList.contains('keys-delete-one')) {
                const id = target.dataset.id;
                if (!id) return;
                if (!confirm('确定删除该卡密吗？')) return;
                try {
                    const resp = await fetch('/api/keys/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ids: [id] })
                    });
                    const data = await resp.json();
                    if (data.success) {
                        showToast('已删除', 'success');
                        updateStats(data.stats);
                        loadKeys();
                    } else {
                        showToast(data.error || '删除失败', 'error');
                    }
                } catch (err) {
                    showToast('网络错误', 'error');
                }
            }
        });
    }
    if (keysDelete) {
        keysDelete.addEventListener('click', async () => {
            const checked = Array.from(document.querySelectorAll('.keys-checkbox:checked')).map(item => item.dataset.id);
            if (checked.length === 0) return;
            if (!confirm(`确定删除 ${checked.length} 条卡密吗？`)) return;
            try {
                const resp = await fetch('/api/keys/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids: checked })
                });
                const data = await resp.json();
                if (data.success) {
                    showToast(`已删除 ${data.deleted} 条`, 'success');
                    updateStats(data.stats);
                    loadKeys();
                } else {
                    showToast(data.error || '删除失败', 'error');
                }
            } catch (err) {
                showToast('网络错误', 'error');
            }
        });
    }
    if (keysPrev) {
        keysPrev.addEventListener('click', () => {
            if (keysState.page > 1) {
                keysState.page -= 1;
                loadKeys();
            }
        });
    }
    if (keysNext) {
        keysNext.addEventListener('click', () => {
            const totalPages = Math.max(1, Math.ceil(keysState.total / keysState.perPage));
            if (keysState.page < totalPages) {
                keysState.page += 1;
                loadKeys();
            }
        });
    }


    document.addEventListener('click', function(e) {
        const target = e.target;
        if (!(target instanceof HTMLElement)) return;
        const el = target.closest('.copyable');
        if (!el) return;
        const field = el.dataset.copy;
        let text = '';
        if (field === 'pan' && currentCard) {
            text = currentCard.pan || '';
        } else if (field === 'cvv' && currentCard) {
            text = currentCard.cvv || '';
        } else if (field === 'expiry' && currentCard) {
            const month = currentCard.exp_month || '';
            const year = currentCard.exp_year || '';
            text = month && year ? `${month}/${year}` : '';
        } else if (field === 'address') {
            text = el.textContent.trim();
        } else if (field === 'key') {
            text = el.textContent.trim();
        }

        if (text) {
            navigator.clipboard.writeText(text);
            showToast('已复制', 'success');
        }
    });
});
