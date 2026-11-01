/**
 * TailorPro — Client-side JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {

    // -----------------------------------------------------------------
    // Sidebar toggle (mobile)
    // -----------------------------------------------------------------
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (sidebarToggle && sidebar && overlay) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            overlay.classList.toggle('active');
        });

        overlay.addEventListener('click', function () {
            sidebar.classList.remove('show');
            overlay.classList.remove('active');
        });
    }

    // -----------------------------------------------------------------
    // Auto-dismiss flash alerts after 6 seconds
    // -----------------------------------------------------------------
    const alerts = document.querySelectorAll('.flash-container .alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 6000);
    });

    // -----------------------------------------------------------------
    // Confirm dangerous actions
    // -----------------------------------------------------------------
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm(form.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // -----------------------------------------------------------------
    // Prevent double submission on forms
    // -----------------------------------------------------------------
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            const btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) {
                btn.disabled = true;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Processing...';
                // Re-enable after 5 seconds as a fallback
                setTimeout(function () {
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }, 5000);
            }
        });
    });

    // -----------------------------------------------------------------
    // Active link highlighting (fallback)
    // -----------------------------------------------------------------
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(function (link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});
