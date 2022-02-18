select ecommerce.ts as timestamp, ecommerce.views, ecommerce.revenue, platform.name as platform,
marketplace.name as marketplace from ecommerce, platform, marketplace
where ecommerce.platform = platform.id and ecommerce.marketplace = marketplace.id and ecommerce.ts < dateadd(hour, -1, sysdate)