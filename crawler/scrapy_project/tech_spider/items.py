import scrapy


class TechArticleItem(scrapy.Item):
    """科技文章数据模型"""

    title = scrapy.Field()
    content = scrapy.Field()
    summary = scrapy.Field()
    source = scrapy.Field()
    url = scrapy.Field()
    published_at = scrapy.Field()
    crawled_at = scrapy.Field()
    category = scrapy.Field()
    tags = scrapy.Field()
    authors = scrapy.Field()
    language = scrapy.Field()
    raw_html = scrapy.Field()
    extra = scrapy.Field()
