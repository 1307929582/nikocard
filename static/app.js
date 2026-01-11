document.addEventListener('DOMContentLoaded', function() {
    const btnImport = document.getElementById('btn-import');
    const btnActivate = document.getElementById('btn-activate');
    const keysInput = document.getElementById('keys-input');
    const toast = document.getElementById('toast');
    const activeCardSection = document.getElementById('active-card-section');

    let countdownInterval = null;
    let currentCard = null;

    if (window.activeCard && window.activeCard.pan) {
        currentCard = window.activeCard;
        displayCard(currentCard);
    }

    function showToast(message, type = 'info') {
        toast.textContent = message;
        toast.className = 'toast show ' + type;
        setTimeout(() => {
            toast.className = 'toast';
        }, 3000);
    }

    function updateStats(stats) {
        document.getElementById('stat-unused').textContent = stats.unused;
        document.getElementById('stat-used').textContent = stats.used;
        document.getElementById('stat-total').textContent = stats.total;
    }

    function formatCardNumber(pan) {
        if (!pan) return '**** **** **** ****';
        return pan.replace(/(.{4})/g, '$1 ').trim();
    }

    function displayCard(card) {
        currentCard = card;
        activeCardSection.style.display = 'block';

        document.getElementById('card-pan').textContent = formatCardNumber(card.pan);
        document.getElementById('card-cvv').textContent = card.cvv || '***';
        document.getElementById('card-expiry').textContent =
            (card.exp_month || 'MM') + '/' + (card.exp_year ? card.exp_year.slice(-2) : 'YY');
        document.getElementById('card-type').textContent = (card.card_type || 'CREDIT').toUpperCase();

        startCountdown(card.expire_time);
    }

    function startCountdown(expireTime) {
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }

        const expireDate = new Date(expireTime);

        function updateCountdown() {
            const now = new Date();
            const diff = expireDate - now;

            if (diff <= 0) {
                document.getElementById('countdown').textContent = '已过期';
                clearInterval(countdownInterval);
                return;
            }

            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            document.getElementById('countdown').textContent =
                String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
        }

        updateCountdown();
        countdownInterval = setInterval(updateCountdown, 1000);
    }

    btnImport.addEventListener('click', async function() {
        const keys = keysInput.value.trim();
        if (!keys) {
            showToast('请输入卡密', 'error');
            return;
        }

        btnImport.disabled = true;
        btnImport.textContent = '导入中...';

        try {
            const resp = await fetch('/api/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keys: keys })
            });
            const data = await resp.json();

            if (data.success) {
                showToast(`成功导入 ${data.added} 个卡密`, 'success');
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

    btnActivate.addEventListener('click', async function() {
        btnActivate.disabled = true;
        btnActivate.innerHTML = '<span class="loading">激活中...</span>';

        try {
            const resp = await fetch('/api/activate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();

            if (data.success) {
                showToast('激活成功！', 'success');
                displayCard(data.card);
                if (data.stats) updateStats(data.stats);
                setTimeout(() => location.reload(), 500);
            } else {
                showToast(data.error || '激活失败', 'error');
                if (data.stats) updateStats(data.stats);
            }
        } catch (e) {
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

    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const field = this.dataset.copy;
            let text = '';
            if (field === 'cvv' && currentCard) {
                text = currentCard.cvv;
            }
            if (text) {
                navigator.clipboard.writeText(text);
                showToast('已复制', 'success');
            }
        });
    });

    const copyAllBtn = document.getElementById('copy-all');
    if (copyAllBtn) {
        copyAllBtn.addEventListener('click', function() {
            if (!currentCard) return;
            const text = `卡号: ${currentCard.pan}\nCVV: ${currentCard.cvv}\n有效期: ${currentCard.exp_month}/${currentCard.exp_year}`;
            navigator.clipboard.writeText(text);
            showToast('已复制全部信息', 'success');
        });
    }
});
