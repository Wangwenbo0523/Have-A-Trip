-- Have-A-Trip · 景点配图的种子数据
--
-- 本文件由 scripts/make_attraction_covers.py 生成, **不要手改**。
-- 改图或加景点请改那个脚本再重跑, 否则 CI 的 --check 会拦下来。
--
-- 封面是自绘的 SVG, 出处就是仓库里的脚本本身, 许可与仓库一致(MIT)。
-- 为什么不用第三方照片: 见 docs/LICENSE-AUDIT.md 第五节。
--
-- 幂等: 用 upsert, 重跑会把 caption / credit / license 同步成本文件的版本。
--
-- 执行:
--   psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/images.sql

BEGIN;

INSERT INTO attraction_image (attraction_id, url, caption, credit, license, sort) VALUES
    ((SELECT id FROM attraction WHERE slug = 'west-lake'), '/images/covers/west-lake.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'huangshan'), '/images/covers/huangshan.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'jiuzhaigou'), '/images/covers/jiuzhaigou.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'zhangjiajie'), '/images/covers/zhangjiajie.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'taishan'), '/images/covers/taishan.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'huashan'), '/images/covers/huashan.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'lijiang-river'), '/images/covers/lijiang-river.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'qinghai-lake'), '/images/covers/qinghai-lake.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'daocheng-yading'), '/images/covers/daocheng-yading.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'changbai-mountain'), '/images/covers/changbai-mountain.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'hulunbuir'), '/images/covers/hulunbuir.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'kanas'), '/images/covers/kanas.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'terracotta-army'), '/images/covers/terracotta-army.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'badaling-great-wall'), '/images/covers/badaling-great-wall.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'mogao-caves'), '/images/covers/mogao-caves.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'yungang-grottoes'), '/images/covers/yungang-grottoes.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'longmen-grottoes'), '/images/covers/longmen-grottoes.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'pingyao'), '/images/covers/pingyao.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'ming-xiaoling'), '/images/covers/ming-xiaoling.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'huaqing-palace'), '/images/covers/huaqing-palace.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'yinxu'), '/images/covers/yinxu.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'liangzhu'), '/images/covers/liangzhu.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'palace-museum'), '/images/covers/palace-museum.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'national-museum'), '/images/covers/national-museum.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'shanghai-museum'), '/images/covers/shanghai-museum.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'shaanxi-history-museum'), '/images/covers/shaanxi-history-museum.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'sanxingdui-museum'), '/images/covers/sanxingdui-museum.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'suzhou-museum'), '/images/covers/suzhou-museum.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'the-bund'), '/images/covers/the-bund.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'oriental-pearl-tower'), '/images/covers/oriental-pearl-tower.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'canton-tower'), '/images/covers/canton-tower.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'temple-of-heaven'), '/images/covers/temple-of-heaven.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'summer-palace'), '/images/covers/summer-palace.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'orange-isle'), '/images/covers/orange-isle.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'lingyin-temple'), '/images/covers/lingyin-temple.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'potala-palace'), '/images/covers/potala-palace.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'mount-emei'), '/images/covers/mount-emei.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'leshan-buddha'), '/images/covers/leshan-buddha.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'wudang-mountain'), '/images/covers/wudang-mountain.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'wuzhen'), '/images/covers/wuzhen.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'zhouzhuang'), '/images/covers/zhouzhuang.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'xitang'), '/images/covers/xitang.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'hongcun'), '/images/covers/hongcun.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'lijiang-old-town'), '/images/covers/lijiang-old-town.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'fenghuang'), '/images/covers/fenghuang.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'shanghai-disney'), '/images/covers/shanghai-disney.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'chimelong-ocean-kingdom'), '/images/covers/chimelong-ocean-kingdom.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'universal-beijing'), '/images/covers/universal-beijing.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'window-of-the-world'), '/images/covers/window-of-the-world.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0),
    ((SELECT id FROM attraction WHERE slug = 'hangzhou-songcheng'), '/images/covers/hangzhou-songcheng.svg', '自绘示意图', 'Have-A-Trip 自绘', 'MIT', 0)
ON CONFLICT (attraction_id, url) DO UPDATE SET
    caption = EXCLUDED.caption,
    credit  = EXCLUDED.credit,
    license = EXCLUDED.license,
    sort    = EXCLUDED.sort;

COMMIT;
