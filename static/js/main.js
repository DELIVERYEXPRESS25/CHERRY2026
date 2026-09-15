document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Format currency inputs
    const currencyInputs = document.querySelectorAll('input[type="number"][step="0.01"]');
    currencyInputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value) {
                this.value = parseFloat(this.value).toFixed(2);
            }
        });
    });

    // Confirm delete actions
    const deleteButtons = document.querySelectorAll('[onclick*="confirm"]');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('¿Está seguro de realizar esta acción?')) {
                e.preventDefault();
            }
        });
    });

    // Active menu item
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-menu a');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

    // Format numbers with thousand separators
    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // Format currency
    function formatCurrency(amount) {
        return 'C$ ' + formatNumber(parseFloat(amount).toFixed(2));
    }

    // Make formatCurrency available globally
    window.formatCurrency = formatCurrency;
    window.formatNumber = formatNumber;

    // Real-time search for tables
    const searchInputs = document.querySelectorAll('.filter-form input[type="text"]');
    searchInputs.forEach(input => {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                this.closest('form').submit();
            }
        });
    });

    // Print functionality
    window.printInvoice = function() {
        window.print();
    };

    // Add loading state to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Procesando...';
            }
        });
    });

    // Tooltip functionality
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(el => {
        el.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.dataset.tooltip;
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + 'px';
            tooltip.style.top = (rect.bottom + 5) + 'px';
        });
        
        el.addEventListener('mouseleave', function() {
            const tooltip = document.querySelector('.tooltip');
            if (tooltip) tooltip.remove();
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + N: New invoice
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/invoices/new';
        }
        
        // Ctrl/Cmd + P: Print
        if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
            e.preventDefault();
            window.print();
        }
    });

    // Auto-refresh dashboard stats
    if (document.querySelector('.stats-grid')) {
        setInterval(() => {
            fetch('/api/dashboard/stats')
                .then(response => response.json())
                .then(data => {
                    // Update chart if exists
                    if (window.salesChart && data.length > 0) {
                        window.salesChart.data.labels = data.map(d => d.date);
                        window.salesChart.data.datasets[0].data = data.map(d => d.total);
                        window.salesChart.update();
                    }
                })
                .catch(error => console.error('Error fetching stats:', error));
        }, 300000); // Every 5 minutes
    }

    // Mobile menu toggle
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && window.innerWidth <= 768) {
        const toggleBtn = document.createElement('button');
        toggleBtn.innerHTML = '<i class="fas fa-bars"></i>';
        toggleBtn.className = 'mobile-menu-btn';
        toggleBtn.style.cssText = 'position:fixed;top:15px;left:15px;z-index:1001;background:var(--primary);color:white;border:none;padding:10px 15px;border-radius:5px;cursor:pointer;';
        document.body.appendChild(toggleBtn);
        
        toggleBtn.addEventListener('click', () => {
            sidebar.style.display = sidebar.style.display === 'block' ? 'none' : 'block';
        });
    }

    // Form validation
    const requiredFields = document.querySelectorAll('[required]');
    requiredFields.forEach(field => {
        field.addEventListener('blur', function() {
            if (!this.value.trim()) {
                this.style.borderColor = '#e74c3c';
            } else {
                this.style.borderColor = '#ddd';
            }
        });
    });

    // Number input validation
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('input', function() {
            if (this.min && parseFloat(this.value) < parseFloat(this.min)) {
                this.value = this.min;
            }
            if (this.max && parseFloat(this.value) > parseFloat(this.max)) {
                this.value = this.max;
            }
        });
    });

    console.log('Cherry Inventario loaded successfully');
});
