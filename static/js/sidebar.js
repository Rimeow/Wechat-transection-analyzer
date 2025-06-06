document.addEventListener('DOMContentLoaded', function() {
    // 侧边栏切换功能
    const toggleSidebar = document.getElementById('toggle-sidebar');
    const refreshReports = document.getElementById('refresh-reports');
    const loadingReports = document.getElementById('loading-reports');

    // 初始加载报告列表
    loadReportList();

    // 刷新报告列表
    if (refreshReports) {
        refreshReports.addEventListener('click', function() {
            loadReportList();
        });
    }

    // 切换侧边栏
    if (toggleSidebar) {
        toggleSidebar.addEventListener('click', function() {
            document.body.classList.toggle('sidebar-hidden');
        });
    }

    // 在小屏幕上默认隐藏侧边栏
    if (window.innerWidth <= 768) {
        document.body.classList.add('sidebar-hidden');
    }

    // 加载历史报告列表
    function loadReportList() {
        const reportList = document.getElementById('report-list');
        if (!reportList) return;

        // 显示加载图标
        if (loadingReports) {
            loadingReports.style.display = 'inline-block';
        }

        // 获取报告列表
        fetch('/api/reports')
            .then(response => response.json())
            .then(data => {
                // 隐藏加载图标
                if (loadingReports) {
                    loadingReports.style.display = 'none';
                }

                // 清空报告列表
                reportList.innerHTML = '';

                if (data.length === 0) {
                    // 如果没有报告，显示提示信息
                    reportList.innerHTML = '<li class="no-reports">还没有分析过的报告</li>';
                    return;
                }

                // 添加报告到列表
                data.forEach(report => {
                    const reportItem = document.createElement('li');
                    const taskClass = report.type === 'pdf' ? 'pdf-task' : 'zip-task';
                    reportItem.className = `report-item ${taskClass}`;

                    // 格式化日期
                    let formattedDate = '';
                    if (report.timestamp) {
                        const date = new Date(report.timestamp);
                        formattedDate = date.toLocaleString('zh-CN', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                    }

                    const taskTypeLabel = report.type === 'pdf' ? 'PDF' : 'ZIP';
                    const taskTypeClass = report.type === 'pdf' ? 'pdf' : 'zip';

                    // 创建报告HTML，为每个文件添加预览和下载链接
                    reportItem.innerHTML = `
                        <div class="report-name">
                        ${report.name}
                        <span class="task-type-tag ${taskTypeClass}">${taskTypeLabel}</span>
                        </div>
                        <div class="report-date">${formattedDate}</div>
                        <div class="report-files">
                            ${report.files.map(file => `
                                <div class="file-item">
                                    <div class="file-info">
                                        <span class="file-icon">📄</span>
                                        <span class="file-name" title="${file.name}">${file.name}</span>
                                    </div>
                                    <div class="file-actions">
                                        <a href="${file.preview_url}" class="file-action preview-action" title="预览">
                                            <span class="action-icon">🔍️</span>
                                        </a>
                                        <a href="/download/report/${encodeURIComponent(report.name)}/${encodeURIComponent(file.name)}"
                                           class="file-action download-action" title="下载" download>
                                            <span class="action-icon">⬇️</span>
                                        </a>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;

                    reportList.appendChild(reportItem);
                });
            })
            .catch(error => {
                if (loadingReports) {
                    loadingReports.style.display = 'none';
                }
                reportList.innerHTML = `<li class="no-reports">加载失败: ${error.message}</li>`;
                console.error('Error loading reports:', error);
            });
    }
});
