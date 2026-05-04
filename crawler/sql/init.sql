-- MySQL 初始化脚本：科技信息采集系统元数据库
-- 数据库: techinfo

USE techinfo;

-- 站点配置表
CREATE TABLE IF NOT EXISTS site_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_name VARCHAR(100) NOT NULL UNIQUE COMMENT '站点名称',
    site_url VARCHAR(500) NOT NULL COMMENT '站点URL',
    spider_name VARCHAR(100) NOT NULL COMMENT 'Scrapy爬虫名',
    cron_expression VARCHAR(50) DEFAULT '0 2 * * *' COMMENT 'Cron表达式',
    use_playwright TINYINT(1) DEFAULT 0 COMMENT '是否使用Playwright',
    enabled TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    selectors JSON COMMENT '页面选择器配置(JSON)',
    headers JSON COMMENT '自定义请求头(JSON)',
    extra_config JSON COMMENT '额外配置',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 爬虫任务日志表
CREATE TABLE IF NOT EXISTS crawl_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    site_name VARCHAR(100) NOT NULL COMMENT '站点名称',
    task_id VARCHAR(255) COMMENT 'Celery任务ID',
    status ENUM('running', 'success', 'failed', 'partial') DEFAULT 'running',
    total_items INT DEFAULT 0 COMMENT '抓取总数',
    new_items INT DEFAULT 0 COMMENT '新增条目数',
    failed_items INT DEFAULT 0 COMMENT '失败条目数',
    error_message TEXT COMMENT '错误信息',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    duration_seconds INT COMMENT '耗时(秒)',
    INDEX idx_site_name (site_name),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 每日统计表
CREATE TABLE IF NOT EXISTS crawl_daily_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stat_date DATE NOT NULL,
    site_name VARCHAR(100) NOT NULL,
    total_crawled INT DEFAULT 0,
    total_new INT DEFAULT 0,
    total_failed INT DEFAULT 0,
    UNIQUE KEY uk_date_site (stat_date, site_name),
    INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入初始站点配置
INSERT INTO site_configs (site_name, site_url, spider_name, cron_expression, use_playwright) VALUES
('ArXiv CS', 'https://arxiv.org/list/cs/recent', 'arxiv', '0 3 * * *', 0),
('GitHub Trending', 'https://github.com/trending', 'github_trending', '0 4 * * *', 0),
('MIT News', 'https://news.mit.edu/topic/artificial-intelligence2', 'mit_news', '0 5 * * *', 0),
('TechCrunch', 'https://techcrunch.com/', 'techcrunch', '0 6 * * *', 1),
('IEEE Spectrum', 'https://spectrum.ieee.org/', 'ieee_spectrum', '0 7 * * *', 0);
