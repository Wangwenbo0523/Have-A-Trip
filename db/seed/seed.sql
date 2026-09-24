-- Have-A-Trip · 种子数据
--
-- 只放**自采的公开事实信息**, 不引入任何第三方数据集, 便于「将来可闭源」。
-- 每条 attraction 都必须写清 source 与 license(S0 已把它设为 NOT NULL)。
--
-- 幂等性: 全部 ON CONFLICT DO NOTHING, 可重复执行。
--
-- 刻意不造假的数据:
--   * rating_avg / rating_count 一律为 0 —— 评分只能由 behavior_log 聚合得出,
--     种子里写死一个好看的分数就是在骗人。前端需处理「暂无评分」。
--   * attraction_image 这里不插 —— 图片素材在 S7 补齐, 届时每条都带 credit 与 license。
--   * ticket_price 是易变信息, S7 上线前需逐条复核。
--
-- 执行:
--   psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/seed.sql

BEGIN;

-- ---------------------------------------------------------------- 分类

INSERT INTO category (slug, name, sort) VALUES
    ('nature',       '自然风光',   10),
    ('history',      '历史古迹',   20),
    ('museum',       '博物馆',     30),
    ('landmark',     '城市地标',   40),
    ('religion',     '宗教场所',   50),
    ('ancient-town', '古镇村落',   60),
    ('theme-park',   '主题乐园',   70)
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------- 标签

INSERT INTO tag (slug, name) VALUES
    ('world-heritage', '世界遗产'),
    ('free',           '免票'),
    ('family',         '亲子'),
    ('sunrise',        '日出'),
    ('night-view',     '夜景'),
    ('photography',    '摄影'),
    ('hiking',         '徒步'),
    ('indoor',         '适合雨天')
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------- 景点

INSERT INTO attraction (
    slug, name, name_en, summary, description,
    category_id, country_code, province, city, address, lat, lon,
    best_season, suggested_hours, ticket_price,
    status, source, license, source_url
) VALUES
(
    'west-lake', '西湖', 'West Lake',
    '三面环山的淡水湖, 以「一山二塔三岛三堤五湖」的格局和南宋流传至今的十景著称。',
    '位于杭州城西, 湖面约 6.4 平方公里。苏堤、白堤把湖面分成若干区域, 沿岸可步行或骑行环湖。'
    || '苏堤春晓、断桥残雪、雷峰夕照等「西湖十景」自南宋起沿用至今, 2011 年以文化景观列入世界遗产名录。'
    || '环湖大部分区域全天开放且不收费, 个别园中园单独售票。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '浙江省', '杭州市', '浙江省杭州市西湖区龙井路 1 号',
    30.248900, 120.141700,
    '四季皆宜, 春季与秋季最佳', 4.0, 0.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'palace-museum', '故宫博物院', 'Palace Museum',
    '明清两代皇宫, 世界上现存规模最大的木质结构宫殿建筑群, 1925 年建院。',
    '又称紫禁城, 始建于明永乐年间, 占地约 72 万平方米, 现存建筑约 9000 余间。'
    || '中轴线由午门、太和殿、乾清宫、神武门等构成, 现藏文物逾 186 万件, 分书画、陶瓷、钟表、'
    || '宫廷器物等多个门类。参观通常由午门入、神武门出, 单向通行。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '北京市', '北京市', '北京市东城区景山前街 4 号',
    39.916300, 116.397200,
    '春秋两季, 避开暑期与节假日', 4.0, 60.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'terracotta-army', '秦始皇兵马俑', 'Terracotta Army',
    '秦始皇陵的陪葬坑, 1974 年发现, 出土陶俑陶马数千件, 1987 年列入世界遗产。',
    '位于西安市临潼区, 已发掘三个俑坑: 一号坑规模最大, 以步兵与战车方阵为主; '
    || '二号坑为多兵种混编; 三号坑被认为是统帅机构。陶俑面部各不相同, 出土时原有彩绘, '
    || '因接触空气而脱落。坑上建有保护大厅, 可沿参观廊道观看。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '陕西省', '西安市', '陕西省西安市临潼区秦陵北路',
    34.384100, 109.278500,
    '春秋两季', 3.0, 120.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
)
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------- 景点标签

INSERT INTO attraction_tag (attraction_id, tag_id)
SELECT a.id, t.id
FROM attraction a
JOIN tag t ON t.slug IN ('world-heritage', 'free', 'photography', 'night-view')
WHERE a.slug = 'west-lake'
ON CONFLICT DO NOTHING;

INSERT INTO attraction_tag (attraction_id, tag_id)
SELECT a.id, t.id
FROM attraction a
JOIN tag t ON t.slug IN ('world-heritage', 'family', 'indoor')
WHERE a.slug = 'palace-museum'
ON CONFLICT DO NOTHING;

INSERT INTO attraction_tag (attraction_id, tag_id)
SELECT a.id, t.id
FROM attraction a
JOIN tag t ON t.slug IN ('world-heritage', 'family', 'indoor')
WHERE a.slug = 'terracotta-army'
ON CONFLICT DO NOTHING;

COMMIT;