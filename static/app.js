document.addEventListener('DOMContentLoaded', function() {
    const btnImport = document.getElementById('btn-import');
    const btnActivate = document.getElementById('btn-activate');
    const keysInput = document.getElementById('keys-input');
    const toast = document.getElementById('toast');
    const activeCardSection = document.getElementById('active-card-section');
    const providerSelect = document.getElementById('provider-select');
    const activateProvider = document.getElementById('activate-provider');
    const providerForm = document.getElementById('provider-form');

    let countdownInterval = null;
    let currentCard = null;

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
        if (!panEl || !cvvEl || !expiryEl || !typeEl) return;

        panEl.textContent = formatCardNumber(card.pan);
        cvvEl.textContent = card.cvv || '***';
        expiryEl.textContent =
            (card.exp_month || 'MM') + '/' + (card.exp_year ? card.exp_year.slice(-2) : 'YY');
        typeEl.textContent = (card.card_type || 'CREDIT').toUpperCase();

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
                showToast('激活成功！', 'success');
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

    if (providerForm) {
        providerForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const nameEl = document.getElementById('provider-name');
            const redeemEl = document.getElementById('provider-redeem');
            const queryEl = document.getElementById('provider-query');
            const name = nameEl ? nameEl.value.trim() : '';
            const redeem = redeemEl ? redeemEl.value.trim() : '';
            const query = queryEl ? queryEl.value.trim() : '';

            if (!name || !redeem) {
                showToast('请输入卡商名称和激活接口', 'error');
                return;
            }

            try {
                const resp = await fetch('/api/providers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        redeem_url: redeem,
                        query_url: query
                    })
                });
                const data = await resp.json();
                if (data.success) {
                    showToast('卡商创建成功', 'success');
                    setTimeout(() => location.reload(), 600);
                } else {
                    showToast(data.error || '创建失败', 'error');
                }
            } catch (e) {
                showToast('网络错误', 'error');
            }
        });
    }

    document.querySelectorAll('.copyable').forEach(el => {
        el.addEventListener('click', function() {
            const field = this.dataset.copy;
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
                text = this.textContent.trim();
            }

            if (text) {
                navigator.clipboard.writeText(text);
                showToast('已复制', 'success');
            }
        });
    });
});
