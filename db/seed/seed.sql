-- Have-A-Trip · 种子数据
--
-- 140 个景点: 100 个中国境内 + 40 个境外(覆盖六大洲), 全部为自采的公开事实信息,
-- 不引入任何第三方数据集, 以便「将来可闭源」。判断见 docs/LICENSE-AUDIT.md 第三节。
-- 境内的 100 条见「中国城市的馆 · 园 · 地标」与「中国城市巡礼」两节; 境外的 40 条见「世界景点」分节。
-- 每条 attraction 都必须写清 source 与 license(S0 已把它设为 NOT NULL)。
--
-- 幂等性: 可重复执行。
--   * 分类 / 标签 / 景点 用 upsert, 重跑会把内容列同步成本文件里的版本;
--   * 景点标签先按 source 认领后删除再重建, 所以删标签、换标签也能同步;
--   * 有意不放进 DO UPDATE 的列: rating_avg / rating_count —— 那两个值只能由
--     behavior_log 聚合得出, 重跑种子不能把它们抹掉。
--
-- 刻意不造假的数据:
--   * rating_avg / rating_count 一律为 0 —— 种子里写死一个好看的分数就是在骗人。
--     前端需处理「暂无评分」。
--   * lat / lon 一律为 NULL —— 种子数据不编造坐标; 一期不做地图与定位, 也用不到。
--   * ticket_price 只在**确定免费**时写 0, 其余为 NULL —— 票价是易变信息,
--     写进种子的数字迟早会过期, 应由导入或运营流程维护。
--   * attraction_image 不在这里 —— 配图连同 credit 与 license 都在 db/seed/images.sql,
--     由 scripts/make_attraction_covers.py 生成(自绘 SVG, 与仓库同许可)。
--   * a_level / heritage 只填能核实的。**留空表示「未核实」, 不是「没有等级」**。
--     景区名录与世界遗产名录都会调整, 宁可空着也不猜。
--   * attraction_plan / attraction_plan_step 是本仓库自采的行程建议, 不是官方或旅行社线路;
--     只给花费档次(budget_level)不给金额, 理由同 ticket_price。
--
-- 执行:
--   psql -d attraction_atlas -v ON_ERROR_STOP=1 -f db/seed/seed.sql

BEGIN;

-- ---------------------------------------------------------------- 分类

INSERT INTO category (slug, name, sort) VALUES
    ('nature',        '自然风光',  10),
    ('history',       '历史古迹',  20),
    ('museum',        '博物馆',    30),
    ('landmark',      '城市地标',  40),
    ('religion',      '宗教场所',  50),
    ('ancient-town',  '古镇村落',  60),
    ('theme-park',    '主题乐园',  70),
    ('palace',        '宫殿城堡',  80),
    ('archaeology',   '考古遗址',  90)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    sort = EXCLUDED.sort;

-- ---------------------------------------------------------------- 标签

INSERT INTO tag (slug, name) VALUES
    ('world-heritage',        '世界遗产'  ),
    ('free',                  '免票'      ),
    ('family',                '亲子'      ),
    ('sunrise',               '日出'      ),
    ('night-view',            '夜景'      ),
    ('photography',           '摄影'      ),
    ('hiking',                '徒步'      ),
    ('indoor',                '适合雨天'  ),
    ('must-see',              '必打卡'    ),
    ('ancient-architecture',  '古建筑'    ),
    ('water-town',            '水乡'      ),
    ('lake',                  '湖泊'      ),
    ('grassland',             '草原'      ),
    ('grottoes',              '石窟'      ),
    ('cruise',                '游船'      ),
    ('garden',                '园林'      ),
    ('park',                  '公园'      ),
    ('city-view',             '城市观景'  ),
    ('amusement',             '游乐项目'  ),
    ('sunset',                 '日落'),
    ('architecture',           '建筑'),
    ('ruins',                  '遗址'),
    ('island',                 '海岛'),
    ('waterfall',              '瀑布'),
    ('desert',                 '沙漠'),
    ('wildlife',               '野生动物'),
    ('ancient-civilization',   '古文明'),
    ('canyon',                 '峡谷'),
    ('glacier',                '冰川'),
    ('reef',                   '珊瑚礁'),
    ('art',                    '艺术')
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name;

-- ---------------------------------------------------------------- 景点
--
-- 每条都带 source 与 license; 不带坐标与票价(见文件头的口径说明)。

INSERT INTO attraction (
    slug, name, name_en, summary, description,
    category_id, country_code, province, city, address, lat, lon,
    best_season, suggested_hours, ticket_price,
    status, source, license, source_url
) VALUES
(
    'west-lake', '西湖', 'West Lake',
    '三面环山的淡水湖，以「一山二塔三岛三堤五湖」的格局和南宋流传至今的十景著称。',
    '位于杭州城西，湖面约 6.4 平方公里。苏堤、白堤把湖面分成若干区域，沿岸可步行或骑行环湖。'
    || '苏堤春晓、断桥残雪、雷峰夕照等「西湖十景」自南宋起沿用至今，2011 年以文化景观列入世界遗产名录。'
    || '环湖大部分区域全天开放且不收费，个别园中园单独售票。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '浙江省', '杭州市', '浙江省杭州市西湖区',
    NULL, NULL,
    '四季皆宜，春季与秋季最佳', 4.0, 0.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'huangshan', '黄山', 'Mount Huang',
    '以奇松、怪石、云海、温泉「四绝」闻名的山岳，1990 年列入世界文化与自然双重遗产。',
    '主峰莲花峰海拔 1864 米。'
    || '前山（慈光阁方向）与后山（云谷寺方向）各有一条主线路，多数行程安排为前山上、后山下或反之。'
    || '看日出与云海通常需要在山上住宿，光明顶、始信峰、丹霞峰是常见观景位置。山上气温比山下低约 8 至 10 摄氏度。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '安徽省', '黄山市', '安徽省黄山市黄山区',
    NULL, NULL,
    '4 月至 11 月，冬季雪景另有看点', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'jiuzhaigou', '九寨沟', 'Jiuzhaigou Valley',
    '由一百多个高山湖泊与多层瀑布组成的沟谷，钙化景观是主要特色。',
    '景区呈 Y 字形，由树正沟、日则沟、则查洼沟三条沟组成，靠观光车在沟内接驳。'
    || '五花海、诺日朗瀑布、长海、五彩池是常见停留点。海拔在 2000 至 3100 米之间，游览节奏宜慢。'
    || '1992 年列入世界自然遗产名录。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '四川省', '阿坝藏族羌族自治州', '四川省阿坝州九寨沟县漳扎镇',
    NULL, NULL,
    '9 月至 11 月秋色最好', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'zhangjiajie', '张家界国家森林公园', 'Zhangjiajie National Forest Park',
    '以石英砂岩峰林地貌著称，数千座石柱直立成群，是武陵源风景名胜区的核心。',
    '园内峰林由石英砂岩经流水切割与重力崩塌形成，金鞭溪、袁家界、天子山是主要片区，各片区之间靠缆车与环保车连接。'
    || '雨后云雾中的峰林是最常见的拍摄场景。武陵源 1992 年列入世界自然遗产名录。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '湖南省', '张家界市', '湖南省张家界市武陵源区',
    NULL, NULL,
    '4 月至 10 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'taishan', '泰山', 'Mount Tai',
    '五岳之首，自秦汉起为历代帝王封禅之地，1987 年列入世界文化与自然双重遗产。',
    '主峰玉皇顶海拔 1545 米。'
    || '登山主路自红门经中天门、十八盘至南天门，全程石阶约七千级，也可由天外村乘中巴至中天门再步行或乘索道。'
    || '沿途碑刻、庙宇密集，岱庙在泰安市区、登山起点之外。看日出多在玉皇顶与日观峰。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '山东省', '泰安市', '山东省泰安市泰山区',
    NULL, NULL,
    '4 月至 10 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'huashan', '华山', 'Mount Hua',
    '五岳之西，以险峻的花岗岩山体与崖壁栈道著称。',
    '由东、西、南、北、中五峰组成，南峰落雁峰海拔 2154 米为最高。'
    || '北峰索道与西峰索道各通往一处峰下，常见的走法是西峰上、北峰下或反之。'
    || '长空栈道、鹞子翻身等路段需要单独的安全装备与排队，恐高者慎行。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '陕西省', '渭南市', '陕西省渭南市华阴市',
    NULL, NULL,
    '4 月至 10 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'lijiang-river', '桂林漓江', 'Li River',
    '喀斯特峰丛夹岸的江段，桂林至阳朔一段约 83 公里，是最典型的山水景致。',
    '游览方式以竹筏与游船为主，全程水路通常四到五小时，兴坪一带是二十元人民币背面图案的取景处。'
    || '枯水期水位偏低，部分航段会调整或改用其他码头。沿江的杨堤、兴坪也可分段乘竹筏。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '广西壮族自治区', '桂林市', '广西桂林市至阳朔县沿江',
    NULL, NULL,
    '4 月至 10 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'qinghai-lake', '青海湖', 'Qinghai Lake',
    '中国面积最大的内陆咸水湖，湖面海拔约 3200 米。',
    '环湖公路全长约 360 公里，常见走法为自驾或骑行环湖，两天左右。'
    || '每年夏季湖畔油菜花与湖水相接是主要拍摄场景，鸟岛等区域在繁殖期会限流或关闭。海拔较高，初到者宜留出适应时间。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '青海省', '海北藏族自治州', '青海省海北州与海南州环湖地区',
    NULL, NULL,
    '6 月至 8 月', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'daocheng-yading', '稻城亚丁', 'Yading Nature Reserve',
    '以三座雪山与高山湖泊为核心的自然保护区，海拔普遍在 4000 米以上。',
    '三座雪山为仙乃日、央迈勇、夏诺多吉，山下分布着牛奶海、五色海、珍珠海等湖泊。'
    || '景区入口在香格里拉镇，需换乘观光车再步行或骑马。高海拔徒步强度较大，需按自身状况安排并预留适应时间。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '四川省', '甘孜藏族自治州', '四川省甘孜州稻城县香格里拉镇',
    NULL, NULL,
    '9 月至 10 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'changbai-mountain', '长白山', 'Changbai Mountain',
    '中朝界山，山顶天池是火山口湖，也是松花江等水系的源头。',
    '北坡、西坡、南坡各有上山路线，北坡设施最完备、西坡台阶最多。天池能否看到取决于天气，云雾常年较重。'
    || '景区内另有长白瀑布、聚龙温泉与地下森林等停留点，冬季有雪凇与滑雪场。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '吉林省', '延边朝鲜族自治州', '吉林省延边州安图县二道白河镇',
    NULL, NULL,
    '7 月至 9 月，冬季看雪', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hulunbuir', '呼伦贝尔草原', 'Hulunbuir Grassland',
    '中国保存较完整的大面积草甸草原，夏季牧草与河曲是主要景致。',
    '草原面积辽阔，公共交通不便，通常以自驾或包车方式游览，海拉尔、额尔古纳、恩和、室韦一线是常见线路。'
    || '莫日格勒河、额尔古纳湿地在夏季与初秋最为上镜，昼夜温差大，需带外套。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '内蒙古自治区', '呼伦贝尔市', '内蒙古呼伦贝尔市境内',
    NULL, NULL,
    '6 月至 9 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'kanas', '喀纳斯', 'Kanas Lake',
    '阿尔泰山深处的湖泊与河谷，湖水会随季节与光线呈现不同颜色。',
    '湖区由喀纳斯湖、卧龙湾、月亮湾、神仙湾等景点串联，靠区间车接驳。'
    || '周边有图瓦人村落（禾木、白哈巴），常与喀纳斯一并安排。距离主要城市较远，往返通常需要三到四天。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '新疆维吾尔自治区', '阿勒泰地区', '新疆阿勒泰地区布尔津县',
    NULL, NULL,
    '6 月至 9 月，9 月下旬秋色最好', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'terracotta-army', '秦始皇兵马俑', 'Terracotta Army',
    '秦始皇陵的陪葬坑，1974 年发现，出土陶俑陶马数千件，1987 年列入世界遗产。',
    '位于西安市临潼区，已发掘三个俑坑：一号坑规模最大，以步兵与战车方阵为主；二号坑为多兵种混编；三号坑被认为是统帅机构。'
    || '陶俑面部各不相同，出土时原有彩绘，因接触空气而脱落。坑上建有保护大厅，可沿参观廊道观看。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '陕西省', '西安市', '陕西省西安市临潼区',
    NULL, NULL,
    '春季与秋季', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'badaling-great-wall', '八达岭长城', 'Badaling Great Wall',
    '明长城保存最完整、开放最早的段落之一，1987 年作为长城的一部分列入世界遗产。',
    '位于北京西北方向约 70 公里处，关城与南北两侧城墙沿山脊延伸。'
    || '北段坡度较陡、八达岭至北八楼是多数人走的路线；南段人流相对少。'
    || '可乘市郊铁路或缆车、滑车上下，节假日客流集中，建议早到。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '北京市', '北京市', '北京市延庆区八达岭镇',
    NULL, NULL,
    '4 月至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'mogao-caves', '敦煌莫高窟', 'Mogao Caves',
    '始建于十六国的石窟群，现存洞窟数百个，壁画与彩塑规模居中国石窟之首。',
    '位于敦煌城东南约 25 公里的鸣沙山东麓，1987 年列入世界遗产名录。'
    || '为控制洞窟内温湿度，参观采用预约制，由讲解员带队分组进入，每个团队当天开放的洞窟不同。洞窟内禁止拍照。'
    || '园区另有数字展示中心，先看影片再进窟通常体验更好。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '甘肃省', '敦煌市', '甘肃省敦煌市鸣沙山东麓',
    NULL, NULL,
    '5 月至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'yungang-grottoes', '云冈石窟', 'Yungang Grottoes',
    '北魏时期开凿的石窟群，2001 年列入世界遗产，以大型佛像与犍陀罗风格著称。',
    '位于大同城西约 16 公里的武州山南麓，主要洞窟编号至 45 窟。'
    || '第 20 窟的露天大佛是标志性的造像，第 5、6 窟以整体雕刻与彩色装饰见长。与敦煌、龙门并称中国三大石窟。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '山西省', '大同市', '山西省大同市云冈区',
    NULL, NULL,
    '5 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'longmen-grottoes', '龙门石窟', 'Longmen Grottoes',
    '开凿于北魏至唐代的窟龛群，沿伊河两岸崖壁分布，2000 年列入世界遗产。',
    '位于洛阳城南的伊河两岸，西山与东山相对，另有香山寺、白园等附属景点。奉先寺的卢舍那大佛是唐代造像的代表。'
    || '西山窟龛最集中，傍晚有夜游时段，灯光下的造像与白天观感不同。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '河南省', '洛阳市', '河南省洛阳市洛龙区',
    NULL, NULL,
    '4 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'pingyao', '平遥古城', 'Ancient City of Pingyao',
    '保存完整的明清县城格局，1997 年列入世界遗产，晋商票号的发源地之一。',
    '城墙周长约 6 公里，城内街巷保持明清走向，日昇昌票号、县衙、文庙是主要看点。'
    || '城内有居民生活，南大街与东大街商铺集中，早晚客流较少。进出古城本身不收费，参观各景点通常需要通票。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '山西省', '晋中市', '山西省晋中市平遥县',
    NULL, NULL,
    '4 月至 10 月', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'ming-xiaoling', '明孝陵', 'Ming Xiaoling Mausoleum',
    '明太祖朱元璋的陵寝，明清皇家陵寝中规模较大的一座，2003 年列入世界遗产。',
    '位于紫金山南麓，神道自下马坊起，经石象路、翁仲路折向陵宫，石象路两侧的石兽与秋色是南京常见的取景处。'
    || '陵宫主体建筑保留基址与部分复原，方城明楼可登。与中山陵、灵谷寺同在钟山风景区内，可一并安排。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '江苏省', '南京市', '江苏省南京市玄武区紫金山南麓',
    NULL, NULL,
    '10 月至 11 月，2 月赏梅', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'huaqing-palace', '华清宫', 'Huaqing Palace',
    '唐代皇家温泉离宫遗址，与骊山、兵马俑同在临潼一线。',
    '园内保留唐代汤池遗址与部分建筑基址，另有西安事变发生地五间厅。骊山可乘索道上山，山上有兵谏亭、老母殿等处。'
    || '晚间有以园林为背景的实景演出，需另行购票。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '陕西省', '西安市', '陕西省西安市临潼区骊山北麓',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'yinxu', '殷墟', 'Yin Xu',
    '商代晚期都城遗址，甲骨文与青铜器的主要出土地，2006 年列入世界遗产。',
    '位于安阳市西北的洹河两岸，包括宫殿宗庙区、王陵区与作坊遗址等。'
    || '出土的甲骨刻辞是汉字的早期形态，司母戊鼎（后母戊鼎）即出自此处。'
    || '园区内有车马坑与妇好墓等展示，配合博物馆一起看理解更完整。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '河南省', '安阳市', '河南省安阳市殷都区小屯村',
    NULL, NULL,
    '4 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'liangzhu', '良渚古城遗址', 'Liangzhu Archaeological Site',
    '距今约五千年的大型史前城址，以水利系统与玉器著称，2019 年列入世界遗产。',
    '遗址由古城、水利系统与外围聚落组成，公园内以展示性与复原性场景为主，可乘观光车在城址与湿地之间移动。'
    || '良渚博物院在瓶窑镇另址，馆藏玉琮、玉璧等器物，建议与遗址公园先后安排。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '浙江省', '杭州市', '浙江省杭州市余杭区瓶窑镇',
    NULL, NULL,
    '3 月至 11 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'palace-museum', '故宫博物院', 'Palace Museum',
    '明清两代皇宫，世界上现存规模最大的木质结构宫殿建筑群，1925 年建院。',
    '又称紫禁城，始建于明永乐年间，占地约 72 万平方米，现存建筑约 9000 余间。'
    || '中轴线由午门、太和殿、乾清宫、神武门等构成，现藏文物逾 186 万件，分书画、陶瓷、钟表、宫廷器物等多个门类。'
    || '参观通常由午门入、神武门出，单向通行。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '北京市', '北京市', '北京市东城区景山前街 4 号',
    NULL, NULL,
    '春季与秋季，避开暑期与节假日', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'national-museum', '中国国家博物馆', 'National Museum of China',
    '位于天安门广场东侧的综合博物馆，馆藏逾一百四十万件，常设「古代中国」基本陈列。',
    '由原中国历史博物馆与中国革命博物馆合并组建，建筑面积近 20 万平方米，是世界上单体建筑面积较大的博物馆之一。'
    || '「古代中国」基本陈列按年代铺开，从旧石器时代一直到清末，看完约需三小时。'
    || '免费参观但需提前实名预约，馆内一层有多处寄存与休息区域。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '北京市', '北京市', '北京市东城区东长安街 16 号',
    NULL, NULL,
    '四季皆宜', 4.0, 0.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shanghai-museum', '上海博物馆', 'Shanghai Museum',
    '以中国古代青铜器、陶瓷与书画收藏著称，人民广场馆与东馆两处。',
    '人民广场馆外形取「天圆地方」之意，青铜、陶瓷、书法、绘画四个门类的收藏在国内外都有分量。'
    || '浦东的东馆规模更大，设有中国古代青铜馆、陶瓷馆等展区与开放式库房。两馆内容侧重不同，可按兴趣选择，也需分别预约。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '上海市', '上海市', '上海市黄浦区人民大道 201 号',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shaanxi-history-museum', '陕西历史博物馆', 'Shaanxi History Museum',
    '以周秦汉唐文物为主线的省级博物馆，唐代金银器与壁画是重点。',
    '位于大雁塔西北侧，基本陈列按史前、周、秦、汉、魏晋南北朝、隋唐、宋元明清铺开，唐代部分器物最集中。'
    || '另有唐代壁画珍品馆等专题馆需单独购票。馆内人流较大，建议预约并尽量在开馆时段入馆。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '陕西省', '西安市', '陕西省西安市雁塔区小寨东路 91 号',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'sanxingdui-museum', '三星堆博物馆', 'Sanxingdui Museum',
    '展示古蜀国祭祀坑出土文物的专题博物馆，青铜纵目面具与神树是标志性器物。',
    '遗址的年代大致相当于中原的商代，出土的青铜器、金器与象牙造型与中原风格差异明显。'
    || '新馆开放后展陈面积大幅增加，青铜大立人、青铜神树、金杖等依次陈列。遗址区与博物馆相邻，可一并参观。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '四川省', '德阳市', '四川省德阳市广汉市鸭子河南岸',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'suzhou-museum', '苏州博物馆', 'Suzhou Museum',
    '由贝聿铭设计的新馆与太平天国忠王府相连，建筑本身即看点。',
    '新馆以「中而新、苏而新」为思路，用几何体量、白墙灰瓦与水院表达江南意趣，片石假山与主庭院的取景角度常被拍照。'
    || '馆藏以吴地文物、书画与工艺品为主，忠王府部分保留原有格局。免费参观需预约，紧邻拙政园与狮子林。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '江苏省', '苏州市', '江苏省苏州市姑苏区东北街 204 号',
    NULL, NULL,
    '四季皆宜', 2.0, 0.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'the-bund', '外滩', 'The Bund',
    '黄浦江西岸的历史建筑群，对岸是陆家嘴天际线，是上海最典型的城市景观。',
    '沿江步道全长约 1.5 公里，一侧是二十世纪初的各国风格建筑，另一侧隔江可见东方明珠与上海中心。'
    || '日落后亮灯，从外白渡桥向南走视角较完整。节假日与晚间人流集中，观景平台分上下两层，上层视野更开阔且不收费。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '上海市', '上海市', '上海市黄浦区中山东一路一带',
    NULL, NULL,
    '四季皆宜', 2.0, 0.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'oriental-pearl-tower', '东方明珠广播电视塔', 'Oriental Pearl Tower',
    '陆家嘴的球体串珠形电视塔，建成时为中国最高的建筑。',
    '塔高约 468 米，观光层分布在下球体、上球体与太空舱等位置，其中有一段玻璃观景廊道可俯瞰地面。'
    || '可看到外滩与黄浦江转弯处，夜景比白天更值得上。塔下即为陆家嘴环形天桥，可与上海中心、金茂大厦串联游览。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '上海市', '上海市', '上海市浦东新区世纪大道 1 号',
    NULL, NULL,
    '四季皆宜', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'canton-tower', '广州塔', 'Canton Tower',
    '珠江边的细腰形电视塔，塔高 600 米，是广州的标识性建筑。',
    '塔身中部收细，得名「小蛮腰」。观光层在 400 米以上，另设有摩天轮与极速云霄等高空项目。'
    || '塔下是珠江夜游的主要码头之一，可把登塔与夜游安排在同一个晚上。隔江北望是珠江新城的花城广场与广州大剧院。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '广东省', '广州市', '广东省广州市海珠区阅江西路 222 号',
    NULL, NULL,
    '四季皆宜', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'temple-of-heaven', '天坛', 'Temple of Heaven',
    '明清两代皇帝祭天祈谷的建筑群，祈年殿的三重檐圆形殿身是北京的名片之一，1998 年列入世界遗产。',
    '主要建筑沿南北轴线分布：圜丘坛在南，用于祭天；祈年殿在北，用于祈谷；两者之间由丹陛桥相连。'
    || '回音壁、三音石在皇穹宇一带。园内古柏成片，清晨有大量市民在园中活动，氛围与其他景区不同。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '北京市', '北京市', '北京市东城区天坛路甲 1 号',
    NULL, NULL,
    '4 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'summer-palace', '颐和园', 'Summer Palace',
    '以昆明湖与万寿山为骨架的皇家园林，1998 年列入世界遗产。',
    '全园面积约 290 公顷，水面约占四分之三。'
    || '长廊、佛香阁、十七孔桥、石舫是主要看点，沿昆明湖东堤往西可看到西山与玉泉山的借景。'
    || '环湖步行一圈约三小时，也可乘园内游船。旺季从东宫门入最方便。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '北京市', '北京市', '北京市海淀区新建宫门路 19 号',
    NULL, NULL,
    '4 月至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'orange-isle', '橘子洲', 'Orange Isle',
    '湘江中的沙洲，洲头有青年毛泽东雕像，隔江与岳麓山相对。',
    '洲长约五公里，地铁可直达洲上，园内有观光小火车串联洲头与洲尾。'
    || '周六晚间常有焰火表演（以当年公告为准），江两岸是常见的观景位置。'
    || '与岳麓山、岳麓书院在同一片区，可通过橘子洲大桥步行往返。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '湖南省', '长沙市', '湖南省长沙市岳麓区湘江中',
    NULL, NULL,
    '四季皆宜，秋季可观橘', 3.0, 0.00,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'lingyin-temple', '灵隐寺', 'Lingyin Temple',
    '始建于东晋的江南名刹，背靠北高峰，对面的飞来峰造像同为看点。',
    '寺院位于飞来峰与北高峰之间，中轴线上有天王殿、大雄宝殿、药师殿、藏经楼等。'
    || '飞来峰崖壁上分布着五代至宋元的石刻造像三百余尊。进入景区与进入寺院需分别购票，飞来峰景区在前。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '浙江省', '杭州市', '浙江省杭州市西湖区法云弄 1 号',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'potala-palace', '布达拉宫', 'Potala Palace',
    '依红山而建的宫堡式建筑群，藏式建筑的集大成者，1994 年列入世界遗产。',
    '分为红宫与白宫两部分，主体高 100 余米，房间数量众多，殿内壁画与灵塔是重点。'
    || '参观按预约时段分批进入，宫内步行距离长且台阶多，海拔约 3700 米，行程不宜排得太紧。宫内多数区域禁止拍照。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '西藏自治区', '拉萨市', '西藏拉萨市城关区北京中路 35 号',
    NULL, NULL,
    '5 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'mount-emei', '峨眉山', 'Mount Emei',
    '中国佛教四大名山之一，主峰万佛顶海拔 3099 米，1996 年列入世界文化与自然双重遗产。',
    '山脚报国寺一带海拔约 500 米，与金顶高差悬殊，通常以「观光车 + 索道 + 徒步」组合上山。'
    || '金顶有十方普贤像与日出、云海、佛光等景观，能否看到取决于天气。山中猴群活动频繁，食物与塑料袋需收好。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '四川省', '乐山市', '四川省乐山市峨眉山市',
    NULL, NULL,
    '4 月至 10 月，冬季看雪与日出', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'leshan-buddha', '乐山大佛', 'Leshan Giant Buddha',
    '依凌云山崖壁凿成的弥勒坐像，通高 71 米，开凿于唐代，1996 年列入世界遗产。',
    '大佛面向岷江、大渡河与青衣江的汇流处，头部与山齐平，脚背可容多人并立。'
    || '参观方式有两种：沿九曲栈道从佛头步行至佛脚，或乘船在江上远观全貌。陆路栈道排队时间较长，节假日建议优先考虑乘船。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '四川省', '乐山市', '四川省乐山市市中区凌云路',
    NULL, NULL,
    '4 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'wudang-mountain', '武当山', 'Wudang Mountains',
    '道教名山与武当武术的发源地，明代建筑群1994 年列入世界遗产。',
    '主要建筑沿中轴线分布：太子坡、紫霄宫、南岩宫一路向上，金顶为终点。金顶太和宫为铜铸鎏金建筑，可步行或乘索道到达。'
    || '山体高差大、景点分散，通常需要一整天，也可在山上住一晚看日出。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '湖北省', '十堰市', '湖北省十堰市丹江口市',
    NULL, NULL,
    '4 月至 10 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'wuzhen', '乌镇', 'Wuzhen Water Town',
    '京杭大运河畔的水乡古镇，分东栅与西栅两片，西栅夜景是主要看点。',
    '东栅保留较多原住民生活场景，街巷较窄、白天热闹；西栅由统一运营，河道、石桥与灯影在入夜后连成一片，适合住一晚慢慢逛。'
    || '东西栅之间有免费班车，多数行程安排为白天东栅、傍晚之后西栅。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '浙江省', '嘉兴市', '浙江省嘉兴市桐乡市乌镇镇',
    NULL, NULL,
    '3 月至 5 月、9 月至 11 月', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'zhouzhuang', '周庄', 'Zhouzhuang',
    '四面环水的水乡古镇，双桥与沈厅、张厅是主要看点。',
    '镇内河道呈「井」字形，居民依水而居，桥多且形式各异，双桥由一座石拱桥与一座石梁桥相连。'
    || '沈厅、张厅为明清宅院，砖雕门楼与厅堂格局保存较好。摇橹船可从水面看沿河民居，早晚游客较少。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '江苏省', '苏州市', '江苏省苏州市昆山市周庄镇',
    NULL, NULL,
    '3 月至 5 月、9 月至 11 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'xitang', '西塘', 'Xitang',
    '以长廊与众多石桥著称的水乡古镇，沿河廊棚可遮雨。',
    '镇内河边多建有带顶棚的廊棚，总长近千米，雨天也方便步行。石桥密度较高，送子来凤桥、五福桥是常见取景点。'
    || '入夜后沿河灯笼亮起，与乌镇西栅的氛围不同，更贴近居民生活。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '浙江省', '嘉兴市', '浙江省嘉兴市嘉善县西塘镇',
    NULL, NULL,
    '3 月至 5 月、9 月至 11 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hongcun', '宏村', 'Hongcun',
    '以水系与徽派民居著称的村落，村中半月形水塘是标志性画面，2000 年列入世界遗产。',
    '村落由人工水系贯穿，水从村北引入，经月沼、南湖流出，兼作消防与生活用水。'
    || '月沼四周是白墙黛瓦的民居，清晨水面平静时倒影最完整。南湖书院、承志堂等宅院的木雕与砖雕值得细看。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '安徽省', '黄山市', '安徽省黄山市黟县宏村镇',
    NULL, NULL,
    '3 月至 4 月、10 月至 11 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'lijiang-old-town', '丽江古城', 'Lijiang Old Town',
    '纳西族聚居的高原古城，以不设城墙与三河穿城的水系布局著称，1997 年列入世界遗产。',
    '又称大研古城，玉泉水自北引入后分三股穿街过巷，形成「家家流水」的格局。'
    || '四方街是全城中心，木府、五凤楼、万古楼等分布其间。'
    || '海拔约 2400 米，古城内为石板路，行李多时建议用客栈的接送服务。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '云南省', '丽江市', '云南省丽江市古城区',
    NULL, NULL,
    '3 月至 5 月、9 月至 11 月', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'fenghuang', '凤凰古城', 'Fenghuang Ancient Town',
    '沱江穿城而过的苗族与土家族聚居古城，临江吊脚楼是主要景致。',
    '城内的石板街与沿江吊脚楼保存较好，虹桥、跳岩、万名塔沿沱江一线分布。入夜后江边灯影与吊脚楼倒影是常见的拍摄画面。'
    || '进入古城本身不收费，参观沈从文故居等具体景点通常需要另行购票。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '湖南省', '湘西土家族苗族自治州', '湖南省湘西州凤凰县沱江镇',
    NULL, NULL,
    '4 月至 10 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shanghai-disney', '上海迪士尼度假区', 'Shanghai Disney Resort',
    '中国大陆首座迪士尼乐园，含七个主题园区与两座主题酒店。',
    '园区包括米奇大街、奇想花园、梦幻世界、探险岛、宝藏湾、明日世界与玩具总动员等区域，创极速光轮与加勒比海盗是常被提到的项目。'
    || '开园前排队入园可省不少时间，烟花表演通常在闭园前举行。门票按日期分档，需提前在官方渠道预约。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '上海市', '上海市', '上海市浦东新区申迪西路 753 号',
    NULL, NULL,
    '四季皆宜', 10.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'chimelong-ocean-kingdom', '珠海长隆海洋王国', 'Chimelong Ocean Kingdom',
    '以海洋动物展示与机动游戏为主的乐园，鲸鲨馆是规模较大的水族馆之一。',
    '园区分为海洋大街、海豚湾、雨林飞翔、海洋奇观、极地探险等区域，鲸鲨馆的巨型展缸与前后的观赏廊道是主要看点，另有海豚、白鲸等剧场表演。'
    || '傍晚有花车巡游与焰火表演。邻接横琴口岸，可与澳门行程衔接。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '广东省', '珠海市', '广东省珠海市横琴新区富祥湾',
    NULL, NULL,
    '四季皆宜', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'universal-beijing', '北京环球度假区', 'Universal Beijing Resort',
    '含哈利·波特的魔法世界、变形金刚基地等主题园区的度假区。',
    '园区由环球影城主题公园、城市大道与度假酒店组成，哈利·波特的魔法世界、小黄人乐园、功夫熊猫盖世之地、变形金刚基地、侏罗纪世界等是主要分区。'
    || '热门项目排队时间长，园区提供付费的快速通行产品。城市大道可单独进入，夜间餐饮与商店营业到较晚。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '北京市', '北京市', '北京市通州区京哈高速与东六环交汇处',
    NULL, NULL,
    '四季皆宜', 10.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'window-of-the-world', '深圳世界之窗', 'Window of the World',
    '把世界知名建筑按比例微缩复制的主题公园，1994 年开园。',
    '园内按亚洲、欧洲、美洲、非洲、大洋洲等区域布置微缩景观，埃菲尔铁塔、金字塔、悉尼歌剧院等按比例缩小后集中呈现。'
    || '晚间有灯光秀与巡游，节假日另有专场演出。园区面积较大，靠步行与园内交通结合更省力。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '广东省', '深圳市', '广东省深圳市南山区深南大道 9037 号',
    NULL, NULL,
    '四季皆宜', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hangzhou-songcheng', '杭州宋城', 'Hangzhou Songcheng',
    '以宋代市井风貌为主题的园区，主打室内大型演出。',
    '园区按宋代街市复建，街上有杂技、木偶、皮影等定时演出与手作店铺，核心是室内大型歌舞演出，时长约一小时，需按场次入场。'
    || '演出票与园区门票的搭配方式按季节调整，购票时需看清包含内容。园区紧邻之江路，与西湖景区南线相距不远。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '浙江省', '杭州市', '浙江省杭州市西湖区之江路 148 号',
    NULL, NULL,
    '四季皆宜', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),

-- ---------------------------------------- 中国城市的馆 · 园 · 地标（24 条）
-- 这一批补的是各城市的博物馆、游乐场与地标性建筑: 博物馆 8(含科技馆 1)、
-- 主题乐园 8(含海洋公园与迪士尼各 1)、城市地标 8(含超高层 3、古楼 2、摩天轮 1)。
-- 口径与上面完全一致: 不带坐标, 评分一律 0, 票价一律留空(不写拿不准的免费),
-- a_level 只填能核实的(广州长隆旅游度假区、黄鹤楼), 其余留空表示「未核实」。
(
    'shanghai-natural-history-museum', '上海自然博物馆', 'Shanghai Natural History Museum',
    '以「自然·人·和谐」为主题的自然科学博物馆，从古生物、矿物到现生动植物都有陈列。',
    '新馆 2015 年在静安雕塑公园内开放，建筑外形取自鹦鹉螺的螺旋，屋顶绿化与公园连成一片。'
    || '展厅按起源之谜、生命长河、演化之道、大地探珍等主题划分，恐龙骨架、大型鲸类与矿物标本是常见停留点。'
    || '展项以可动手操作为主，带孩子参观的比例较高，展线为单向，中途折返要走回头路。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '上海市', '上海市', '上海市静安区山海关路 399 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'nanjing-museum', '南京博物院', 'Nanjing Museum',
    '中国最早创建的博物馆之一，分六馆陈列，从史前一直铺到民国。',
    '前身是 1933 年筹建的国立中央博物院，院内大殿为仿辽代式样的建筑，位于中山门内。'
    || '分历史馆、特展馆、数字馆、艺术馆、民国馆与非遗馆六部分；历史馆按年代陈列江苏一带的出土文物。'
    || '民国馆做成街景式展陈，节奏可以放慢；各馆之间步行有距离，整体参观量不小。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '江苏省', '南京市', '江苏省南京市玄武区中山东路 321 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hubei-museum', '湖北省博物馆', 'Hubei Provincial Museum',
    '以东周曾侯乙墓与越王勾践剑等出土文物著称的省级博物馆，馆内有编钟演奏。',
    '坐落在武昌东湖之滨，由主展馆与相邻的专题馆组成一片院落。'
    || '曾侯乙墓出土的编钟、尊盘与九鼎八簋是核心展品，另有越王勾践剑、郧县人头骨化石与元青花四爱图梅瓶。'
    || '编钟演奏按场次在馆内进行，进馆先记下当天的场次时间更从容。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '湖北省', '武汉市', '湖北省武汉市武昌区东湖路 160 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'henan-museum', '河南博物院', 'Henan Museum',
    '以中原地区出土文物为主线的省级博物馆，史前到宋元的青铜、陶瓷与玉器是主体。',
    '位于郑州市区北部，主展馆取「九鼎定中原」的寓意，中庭方形，四面为展厅。'
    || '贾湖骨笛、莲鹤方壶、妇好鸮尊、云纹铜禁等常被列为镇院之宝，年代自新石器时代延续到汉代。'
    || '按朝代顺序布置的展厅适合自上而下走一遍，馆内另设专题展与临时展。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '河南省', '郑州市', '河南省郑州市金水区农业路 8 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hunan-museum', '湖南博物院', 'Hunan Museum',
    '以马王堆汉墓出土文物为核心的省级博物馆，帛画、丝织品与简牍是主要看点。',
    '位于长沙市开福区，前身为湖南省博物馆，2022 年更名为湖南博物院。'
    || '马王堆汉墓的 T 形帛画、素纱襌衣与大量漆器集中展出，墓葬结构在展厅内做了复原。'
    || '另有商周青铜器与长沙窑瓷器等专题陈列，整体参观时间通常控制在半天内。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '湖南省', '长沙市', '湖南省长沙市开福区东风路 50 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'jinsha-site-museum', '金沙遗址博物馆', 'Jinsha Site Museum',
    '建在商周古蜀都邑遗址上的博物馆，太阳神鸟金饰出土于此。',
    '位于成都市区西部，由遗迹馆与陈列馆两部分组成。'
    || '遗迹馆保留祭祀区的考古现场做原状展示；陈列馆按主题陈列出土文物，太阳神鸟金饰、金面具与成堆象牙是核心展品。'
    || '太阳神鸟图案后来被用作中国文化遗产标志；两馆之间有园区绿地相连，全程以步行为主。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '四川省', '成都市', '四川省成都市青羊区金沙遗址路 2 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'guangdong-museum', '广东省博物馆', 'Guangdong Museum',
    '珠江新城的省级综合博物馆，外观为镂空方盒，以广东历史与工艺美术陈列为主。',
    '2010 年在珠江新城落成开放，外立面覆镂空金属板，夜间透光。'
    || '常设展包括广东历史文化陈列、潮州木雕、端砚与历代陶瓷，另设自然与艺术专题。'
    || '与广州图书馆、广州大剧院同处一片文化建筑群，可以跟周边行程串起来。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '广东省', '广州市', '广东省广州市天河区珠江东路 2 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'china-science-technology-museum', '中国科学技术馆', 'China Science and Technology Museum',
    '以互动体验为主的科普场馆，展厅覆盖物理、机械、生命与航天等内容。',
    '位于北京奥林匹克公园内，与鸟巢、水立方相距不远。'
    || '常设展厅按华夏之光、探索与发现、科技与生活、挑战与未来等主题分布，多数展项可以手动操作。'
    || '另有球幕与巨幕影院按场次放映；儿童科学乐园面向年龄较小的观众，需要单独安排时间。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '北京市', '北京市', '北京市朝阳区北辰东路 5 号',
    NULL, NULL,
    '四季皆宜，室内为主', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'guangzhou-chimelong', '广州长隆旅游度假区', 'Chimelong Resort',
    '由野生动物世界、欢乐世界与水乐园等多个园区组成的度假区。',
    '园区集中在广州番禺，各园单独售票，园与园之间有穿梭巴士接驳。'
    || '野生动物世界以乘车观赏与缆车结合的路线为主，欢乐世界以过山车等大型游乐设施为主。'
    || '单园面积都不小，一天通常只够玩一园，节假日排队时间会更长。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '广东省', '广州市', '广东省广州市番禺区大石街道',
    NULL, NULL,
    '四季皆宜，夏季注意防晒', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'happy-valley-beijing', '北京欢乐谷', 'Happy Valley Beijing',
    '东四环旁的大型主题公园，以大型游乐设施与演艺为主要内容。',
    '园区按主题分区布置，项目以过山车一类的机械游乐设施为主，另有剧场与巡游演出。'
    || '夏季开放水上项目，园区内餐饮与商店分布在各片区。'
    || '节假日排队时间较长，开园即入园能多玩几个热门项目。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '北京市', '北京市', '北京市朝阳区东四环小武基北路',
    NULL, NULL,
    '4 月至 10 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shanghai-haichang-park', '上海海昌海洋公园', 'Shanghai Haichang Ocean Park',
    '浦东临港的海洋主题公园，大型展缸、海洋动物与游乐设施兼有。',
    '位于浦东临港，与滴水湖一带相距不远。'
    || '园内分为人鱼海湾、极地小镇、海底奇域等区域，既有观赏展馆，也有过山车一类的设施。'
    || '鲸鲨、虎鲸与企鹅展区是常见停留点，各类演艺按场次开演，入园后先看时间表更省事。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '上海市', '上海市', '上海市浦东新区南汇新城镇银飞路 166 号',
    NULL, NULL,
    '四季皆宜，室内外结合', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'happy-valley-shenzhen', '深圳欢乐谷', 'Happy Valley Shenzhen',
    '华侨城片区的大型主题公园，以过山车与季节性水上项目为主。',
    '与深圳世界之窗同在华侨城一带，两园相距不远，一天通常二选一。'
    || '园区按主题分区，既有大型机械项目，也有面向低龄观众的亲子区域。'
    || '部分时段开放夜场，夏季项目排队时间较长。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '广东省', '深圳市', '广东省深圳市南山区侨城西街 18 号',
    NULL, NULL,
    '四季皆宜，夏季注意防晒', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'happy-valley-wuhan', '武汉欢乐谷', 'Happy Valley Wuhan',
    '东湖片区的大型主题公园，以大型游乐设施与季节性水上项目为主。',
    '位于东湖北岸一带，与玛雅海滩水公园相邻。'
    || '园区按主题分区，项目以大型机械游乐与演艺为主。'
    || '夏季水公园与主园区分别运营，购票时需看清包含范围。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '湖北省', '武汉市', '湖北省武汉市洪山区欢乐大道 196 号',
    NULL, NULL,
    '4 月至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'happy-valley-chengdu', '成都欢乐谷', 'Happy Valley Chengdu',
    '成都城西的大型主题公园，以大型游乐设施与节庆活动为主。',
    '位于成都西北三环附近，园区按主题分区布置。'
    || '既有面向成人的大型项目，也有面向儿童的区域与剧场演出。'
    || '节假日与暑期人流量大，部分时段开放夜场。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '四川省', '成都市', '四川省成都市金牛区西华大道 16 号',
    NULL, NULL,
    '4 月至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'happy-valley-chongqing', '重庆欢乐谷', 'Happy Valley Chongqing',
    '两江新区的大型主题公园，项目以大型机械游乐设施为主。',
    '位于嘉陵江以北的礼嘉一带，园区按主题分区。'
    || '过山车等大型项目集中在几处片区，另有室内项目与演艺，雨天可玩的选择相对多一些。'
    || '与市区之间以轨道交通和自驾衔接，出行前先看清当日的开放时间。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '重庆市', '重庆市', '重庆市两江新区礼嘉街道',
    NULL, NULL,
    '4 月至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hongkong-disneyland', '香港迪士尼乐园', 'Hong Kong Disneyland',
    '大屿山的迪士尼主题乐园，以园区巡游、剧场演出与城堡夜景为主要内容。',
    '位于大屿山竹篙湾，可由东涌线转乘度假区专线前往。'
    || '园区分为美国小镇大街、幻想世界、明日世界等区域，整体规模小于其他迪士尼乐园，一天可以走完。'
    || '巡游与夜间演出按当日时间表安排，门票按日期分档，需提前在官方渠道购买。',
    (SELECT id FROM category WHERE slug = 'theme-park'),
    'CN', '香港特别行政区', '香港', '香港大屿山竹篙湾',
    NULL, NULL,
    '四季皆宜', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shanghai-tower', '上海中心大厦', 'Shanghai Tower',
    '陆家嘴的超高层建筑，楼体螺旋收分，观光层可俯瞰黄浦江两岸。',
    '高 632 米、118 层，2016 年建成启用，是中国已建成建筑中最高的。'
    || '楼体每层相对下层旋转一个小角度，外立面因此呈螺旋上升的形态，双层幕墙之间形成中庭。'
    || '观光层设在高区，电梯直达；与金茂大厦、上海环球金融中心相邻，三座塔楼在同一片街区内。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '上海市', '上海市', '上海市浦东新区银城中路 501 号',
    NULL, NULL,
    '四季皆宜，晴天视野更好', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'citic-tower', '中信大厦（中国尊）', 'CITIC Tower',
    '北京国贸一带的超高层建筑，外形取礼器「尊」的轮廓，是北京最高的建筑。',
    '高 528 米、108 层，2018 年建成，位于朝阳区国贸中央商务区。'
    || '楼体自下而上收分，底部宽、上部窄，轮廓取自古代礼器「尊」。'
    || '建筑以办公为主，从国贸一带的街道与邻近楼宇可以看到它的轮廓，入夜后与周边建筑形成一组天际线。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '北京市', '北京市', '北京市朝阳区光华路 10 号',
    NULL, NULL,
    '四季皆宜', 1.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'ping-an-finance-center', '平安金融中心', 'Ping An Finance Centre',
    '福田 CBD 的超高层建筑，塔尖直上，是深圳最高的建筑。',
    '高约 600 米、118 层，2017 年落成，位于福田中心区。'
    || '楼体为矩形平面，立面以竖向线条强调高度，顶部收成塔尖。'
    || '设有对外观光的云际观光层，可俯瞰福田中心区与香港方向，具体开放安排以现场公告为准。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '广东省', '深圳市', '广东省深圳市福田区益田路 5033 号',
    NULL, NULL,
    '四季皆宜，晴天视野更好', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hongya-cave', '洪崖洞', 'Hongya Cave',
    '嘉陵江边的吊脚楼样建筑群，依崖壁分层而建，夜景是主要看点。',
    '位于渝中区嘉陵江畔，建筑自上而下分多层，上层临沧白路、下层临江，各层由街道与步道连通。'
    || '是依山就势建造的吊脚楼样式街区，入夜亮灯后，楼体与江面倒影是常见的拍摄场景。'
    || '区域内以商业与餐饮为主，人流集中在晚间，节假日常常限流。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '重庆市', '重庆市', '重庆市渝中区嘉陵江滨江路 88 号',
    NULL, NULL,
    '四季皆宜，傍晚与夜间最佳', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'yellow-crane-tower', '黄鹤楼', 'Yellow Crane Tower',
    '江南三大名楼之一，坐落于蛇山之上，可俯瞰长江与武汉长江大桥。',
    '现楼为 1985 年重建，五层攒尖顶，通高约 51 米，位于武昌蛇山西端。'
    || '楼名因历代题咏而著名，各层陈列相关碑刻与楹联，登楼后向东可望长江与武汉长江大桥。'
    || '园区内另有白云阁等建筑，整体步行量不大。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '湖北省', '武汉市', '湖北省武汉市武昌区蛇山西山坡特 1 号',
    NULL, NULL,
    '四季皆宜', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'tianjin-eye', '天津之眼', 'Tianjin Eye',
    '跨海河而建的摩天轮，轮体架在桥上，夜间灯光是主要看点。',
    '位于永乐桥上，横跨海河，轮体直径约 110 米。'
    || '座舱为封闭式，转一圈约半小时，最高处可俯瞰海河两岸的市区。'
    || '靠近三岔河口一带，周边是步行可达的河岸区域，晚间灯光效果更明显。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '天津市', '天津市', '天津市河北区永乐桥',
    NULL, NULL,
    '四季皆宜，夜间最佳', 1.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'xian-bell-tower', '西安钟楼', 'Xian Bell Tower',
    '明代修建的楼阁式钟楼，位于西安城墙内四条大街的交汇点。',
    '建于明洪武年间，后世有过迁移与重修，现存楼体为砖木结构，重檐三滴水，四角攒尖顶。'
    || '楼内陈列钟与鼓，登楼可以看到四条大街以钟楼为中心向四方延伸。'
    || '与鼓楼相距不远，夜间亮灯后是城墙内常见的拍摄对象。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '陕西省', '西安市', '陕西省西安市碑林区东西南北四条大街交汇处',
    NULL, NULL,
    '四季皆宜，夜间最佳', 1.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'macau-tower', '澳门旅游塔', 'Macau Tower',
    '澳门半岛南端的观光塔，塔身细高，设有观景层与户外活动项目。',
    '塔高约 338 米，2001 年投入使用，位于南湾湖畔的填海区。'
    || '观景层设在高区，可俯瞰澳门半岛、氹仔与珠海方向。'
    || '塔上另设高飞跳与空中漫步等户外项目，需另行预约，具体安排以现场公告为准。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '澳门特别行政区', '澳门', '澳门观光塔前地',
    NULL, NULL,
    '四季皆宜', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),

-- ---------------------------------------- 中国城市巡礼（26 条）
-- 补的是还没进库的城市: 沈阳、长春、哈尔滨、呼和浩特、太原、石家庄、济南、青岛、
-- 合肥、南昌、福州、厦门、昆明、贵阳、南宁、兰州、银川、西宁、乌鲁木齐、宁波、
-- 温州、无锡、佛山、泉州。以博物馆(10)、宗教场所(4)、自然(4)、地标(3)、
-- 宫殿 / 历史 / 古镇 / 考古(各 1) 为主。口径与前面几节完全一致。
(
    'shenyang-imperial-palace', '沈阳故宫', 'Shenyang Imperial Palace',
    '清入关前的皇宫，大政殿与十王亭的布局与北京故宫不同，2004 年作为「明清皇宫」的扩展项目列入世界遗产。',
    '始建于 1625 年，是清太祖、清太宗时期的宫殿，1644 年清迁都北京后成为陪都宫殿。'
    || '中路为大政殿与十王亭，八旗与左右翼王亭分列两侧；东路有崇政殿与凤凰楼，西路是文溯阁等建筑。'
    || '与北京故宫同为「明清皇宫」世界遗产的组成部分，但规模小得多，半天可以走完。',
    (SELECT id FROM category WHERE slug = 'palace'),
    'CN', '辽宁省', '沈阳市', '辽宁省沈阳市沈河区沈阳路 171 号',
    NULL, NULL,
    '四季皆宜', 2.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'palace-museum-of-manchukuo', '伪满皇宫博物院', 'Palace Museum of Manchukuo',
    '溥仪在长春的宫廷旧址，现为博物馆，展出伪满洲国时期的建筑原状与史料。',
    '位于长春市宽城区，由勤民楼、缉熙楼、同德殿等建筑组成。'
    || '建筑是中式与日式混合的样式，室内按当时的办公与居住原状布置，另设专题陈列说明那段历史。'
    || '参观以建筑与原状陈列为主，馆内的史料部分内容较重，适合留出完整时间慢慢看。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '吉林省', '长春市', '吉林省长春市宽城区光复北路 5 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'harbin-saint-sophia-cathedral', '哈尔滨圣索菲亚教堂', 'Harbin Saint Sophia Cathedral',
    '拜占庭样式的教堂建筑，红砖墙体与绿色穹顶，现为建筑艺术馆。',
    '建于 20 世纪初，1932 年重建后形成现在的砖砌结构，曾长期作为宗教场所。'
    || '平面为拉丁十字，中央是大型穹顶，四角有帐篷顶式的塔楼，立面以红砖砌出装饰线脚。'
    || '教堂前的广场是常见的拍摄点，内部现用作展览空间，展出与哈尔滨城市历史相关的图片。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '黑龙江省', '哈尔滨市', '黑龙江省哈尔滨市道里区透笼街 88 号',
    NULL, NULL,
    '四季皆宜，夜间亮灯另有看点', 1.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'inner-mongolia-museum', '内蒙古博物院', 'Inner Mongolia Museum',
    '以草原文化为主线的自治区博物馆，古生物化石与民族文物是两大部分。',
    '位于呼和浩特市区东部，常设陈列包括远古世界、草原雄风、草原天骄等主题。'
    || '恐龙与哺乳动物化石是自然部分的主要内容，民族部分陈列游牧生活的器具、服饰与宗教用品。'
    || '馆内展厅按楼层分布，整体步行量不大，适合与市区的其他行程串起来。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '内蒙古自治区', '呼和浩特市', '内蒙古呼和浩特市新城区新华东街 27 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shanxi-museum', '山西博物院', 'Shanxi Museum',
    '以晋国与北朝文物为主的省级博物馆，晋侯鸟尊是常被提及的一件。',
    '位于太原汾河西岸，主馆外形取斗与鼎的轮廓，展厅围绕「晋魂」这条主线布置。'
    || '青铜器是核心，晋侯墓地出土的器物成组陈列；另有北朝壁画、佛教造像与晋商文物等专题。'
    || '展厅按主题分列，走完一遍需要半天，馆内休息区与文创店集中在一层。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '山西省', '太原市', '山西省太原市万柏林区滨河西路北段 13 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hebei-museum', '河北博物院', 'Hebei Museum',
    '满城汉墓出土文物是这里的重点，金缕玉衣与长信宫灯都在常设陈列中。',
    '位于石家庄市中心，常设陈列包括战国中山、满城汉墓、燕赵故事等部分。'
    || '满城汉墓展区集中展出刘胜与窦绾墓的随葬品，金缕玉衣与长信宫灯是其中的代表。'
    || '另设石刻、陶瓷与近现代专题，展厅之间以楼层相连，整体以室内参观为主。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '河北省', '石家庄市', '河北省石家庄市长安区东大街 4 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'zhaozhou-bridge', '赵州桥', 'Zhaozhou Bridge',
    '隋代建成的敞肩石拱桥，是现存最早采用敞肩式构造的石拱桥。',
    '位于石家庄东南的赵县，横跨洨河，由隋代工匠李春主持建造。'
    || '桥身主拱两端各有两个小拱，既减重又便于泄洪，这种敞肩式构造在桥梁史上出现得很早。'
    || '桥面现为步行通道，两侧有栏杆与雕刻，与桥旁的陈列馆可以一并参观。',
    (SELECT id FROM category WHERE slug = 'history'),
    'CN', '河北省', '石家庄市', '河北省石家庄市赵县赵州镇',
    NULL, NULL,
    '四季皆宜', 1.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'shandong-museum', '山东博物馆', 'Shandong Museum',
    '以龙山文化黑陶、汉画像石与甲骨为主的省级博物馆。',
    '位于济南经十路沿线，常设陈列按时间顺序梳理山东一带的考古发现。'
    || '龙山文化的蛋壳黑陶器壁极薄，是常被提到的代表性器物；另有商周青铜器与汉代画像石。'
    || '另有佛教造像与书画专题，展厅集中在主馆内，半天可以走完主要部分。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '山东省', '济南市', '山东省济南市历下区经十路 11899 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'baotu-spring', '趵突泉', 'Baotu Spring',
    '济南城内的名泉，泉水自地下涌出，与周边的泉池、园林组成一片园区。',
    '位于济南老城西南，泉池中的三股水常年涌出，水位随季节变化。'
    || '园内除趵突泉外还有金线泉、漱玉泉等多处泉池，另有李清照纪念堂等建筑。'
    || '与大明湖、五龙潭相距不远，可以步行串起来，园内以平坦步道为主。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '山东省', '济南市', '山东省济南市历下区趵突泉南路 1 号',
    NULL, NULL,
    '四季皆宜，秋季水位较稳', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'zhanqiao-pier', '栈桥', 'Zhanqiao Pier',
    '伸入海中的长栈桥，尽头是回澜阁，是青岛老城的标志性一处。',
    '始建于 19 世纪末，从太平路一侧伸向海中，全长数百米。'
    || '栈桥尽头的八角亭为回澜阁，两侧是青岛湾，退潮时桥旁露出礁石与沙滩。'
    || '桥北端接老城的中山路一带，可以步行串起周边建筑，冬季海鸥聚集时人尤其多。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '山东省', '青岛市', '山东省青岛市市南区太平路 12 号',
    NULL, NULL,
    '四季皆宜', 1.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'anhui-museum', '安徽博物院', 'Anhui Museum',
    '以青铜器与徽州文化为主的省级博物馆，楚大鼎是其中的代表器物。',
    '位于合肥市蜀山区，常设陈列包括安徽文明史、徽州古建筑、文房四宝等部分。'
    || '青铜部分是重点，楚大鼎体量大，与蔡侯墓等出土器物成组陈列；徽州部分以砖木雕件与原状构件为主。'
    || '另设书画与文房专题，展厅集中在主馆内。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '安徽省', '合肥市', '安徽省合肥市蜀山区怀宁路 268 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'tengwang-pavilion', '滕王阁', 'Tengwang Pavilion',
    '江南三大名楼之一，临赣江而立，因《滕王阁序》而著名。',
    '最早建于唐代，历代屡毁屡建，现楼为 1989 年重建，主阁明三层暗七层。'
    || '各层陈列与滕王阁相关的诗文、碑刻与图画，登到高层可以望赣江与南昌城的轮廓。'
    || '与黄鹤楼、岳阳楼并称江南三大名楼，园区内另有附属建筑与庭院。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '江西省', '南昌市', '江西省南昌市东湖区仿古街 58 号',
    NULL, NULL,
    '四季皆宜，夜间亮灯另有看点', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'three-lanes-seven-alleys', '三坊七巷', 'Three Lanes and Seven Alleys',
    '福州老城的明清坊巷格局，三条坊、七条巷与一条主街组成棋盘般的街巷。',
    '街区自唐宋形成，现存建筑多为明清与民国时期，白墙黛瓦、马鞍墙是常见的形式。'
    || '沿主街南后街两侧分布着多处名人故居与祠堂，部分宅院对外开放，可以看到天井与厅堂的布局。'
    || '街区内以步行为主，也会遇到仍在使用的民居与商铺，参观时注意不要打扰住户。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '福建省', '福州市', '福建省福州市鼓楼区南后街',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'gulangyu-island', '鼓浪屿', 'Gulangyu Island',
    '岛上的历史国际社区，各国风格的老建筑与街巷并存，2017 年列入世界遗产。',
    '位于厦门岛西南海面，全岛以步行为主，没有机动车通行。'
    || '岛上保存了大量 19 世纪末至 20 世纪初的住宅、领事馆与教堂建筑，样式混杂了南洋与欧洲的作法。'
    || '日光岩与菽庄花园是常见的停留点，岛上另有钢琴博物馆等展馆，渡轮是唯一的进出方式。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'CN', '福建省', '厦门市', '福建省厦门市思明区鼓浪屿',
    NULL, NULL,
    '四季皆宜', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'stone-forest', '石林', 'Stone Forest',
    '喀斯特石柱群，密集的石峰连成一片「石头森林」，2007 年作为「中国南方喀斯特」列入世界自然遗产。',
    '位于昆明东南的石林彝族自治县，石柱由石灰岩经长期溶蚀与切割形成。'
    || '景区分大石林、小石林等片区，大石林石峰最高最密，小石林一带草地与石峰相间，常见的那座「阿诗玛」石峰在此。'
    || '片区之间靠步道与摆渡车连接，园内步行量不小，日晒强时宜早进园。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '云南省', '昆明市', '云南省昆明市石林彝族自治县',
    NULL, NULL,
    '四季皆宜，春季与秋季更舒适', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'jiaxiu-pavilion', '甲秀楼', 'Jiaxiu Pavilion',
    '南明河上鳌矶石上的三层楼阁，是贵阳老城的标志。',
    '始建于明代，历代重修，楼下以石桥与两岸相连，楼体为三层三重檐。'
    || '楼前的浮玉桥横跨南明河，桥上有涵碧亭，与楼体组成一组临水建筑。'
    || '夜间亮灯后楼体与河面倒影相衬，周边是步行可达的河岸步道。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CN', '贵州省', '贵阳市', '贵州省贵阳市南明区翠微巷 8 号',
    NULL, NULL,
    '四季皆宜，夜间最佳', 1.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'guangxi-museum-of-nationalities', '广西民族博物馆', 'Guangxi Museum of Nationalities',
    '以广西各民族生活与铜鼓文化为主题的博物馆。',
    '位于南宁青秀山一带，主馆外形取自铜鼓的轮廓。'
    || '常设陈列按民族分列，展出服饰、织锦、建筑构件与生产工具，铜鼓单独成一部分，数量较多。'
    || '馆外有民族村寨式的建筑与原状民居，室内外结合，适合安排半天。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '广西壮族自治区', '南宁市', '广西南宁市青秀区青环路 11 号',
    NULL, NULL,
    '四季皆宜，室内外结合', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'gansu-provincial-museum', '甘肃省博物馆', 'Gansu Provincial Museum',
    '铜奔马（马踏飞燕）与彩陶是这里的重点，另有一条丝绸之路的陈列线。',
    '位于兰州市七里河区，常设陈列包括甘肃丝绸之路文明、彩陶、古生物化石等部分。'
    || '武威雷台汉墓出土的铜奔马是常被提及的一件，同出的铜车马仪仗队成组陈列。'
    || '彩陶部分按年代排列，从大地湾到马家窑的器物连成一条线。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '甘肃省', '兰州市', '甘肃省兰州市七里河区西津西路 3 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'western-xia-tombs', '西夏陵', 'Western Xia Imperial Tombs',
    '贺兰山东麓的西夏帝王陵墓群，夯土陵塔散布在戈壁滩上。',
    '陵区南北绵延数公里，包含多座帝陵与陪葬墓，每座陵园都有神道、碑亭与陵城的遗迹。'
    || '陵塔为夯土筑成，形制与中原帝陵不同，经数百年风蚀后成为现在的锥形土丘。'
    || '陵区内有博物馆与陈列馆，各陵之间距离较远，通常乘车在主要几处停留。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'CN', '宁夏回族自治区', '银川市', '宁夏银川市西夏区贺兰山东麓',
    NULL, NULL,
    '4 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'kumbum-monastery', '塔尔寺', 'Kumbum Monastery',
    '藏传佛教格鲁派的重要寺院，酥油花、壁画与堆绣被称为「艺术三绝」。',
    '位于西宁西南的湟中区鲁沙尔镇，寺院依山而建，由众多殿堂与僧舍组成。'
    || '大金瓦殿是核心建筑，殿前有供信徒叩拜的区域；酥油花馆内展出用彩色酥油塑成的造像与故事场景。'
    || '寺内有多处殿堂需要按指示单向参观，宗教场所内注意着装与拍摄规定。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '青海省', '西宁市', '青海省西宁市湟中区鲁沙尔镇',
    NULL, NULL,
    '5 月至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'xinjiang-regional-museum', '新疆维吾尔自治区博物馆', 'Xinjiang Regional Museum',
    '以丝绸之路文物与古代干尸陈列为主的自治区博物馆。',
    '位于乌鲁木齐市区，常设陈列包括西域历史、民族风情与古代干尸等部分。'
    || '干尸陈列保存了出土于吐鲁番、罗布泊一带的古代遗体及相关随葬品，年代跨度较大。'
    || '丝路部分展出织锦、文书与钱币等，展品说明较细，适合按顺序看。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '新疆维吾尔自治区', '乌鲁木齐市', '新疆乌鲁木齐市沙依巴克区西北路 581 号',
    NULL, NULL,
    '四季皆宜，室内为主', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'tianyi-pavilion', '天一阁', 'Tianyi Pavilion',
    '中国现存最早的私家藏书楼，明代建成，院落里另有园林与碑廊。',
    '由明代范钦于 16 世纪创建，藏书楼为两层硬山顶建筑，楼下六间、楼上通为一间。'
    || '院落中有水池与假山，池边布置了碑廊与近现代移入的亭台，园内还设有麻将等专题陈列。'
    || '与月湖一带相距不远，参观以建筑、园林与藏书史料为主，步行量不大。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'CN', '浙江省', '宁波市', '浙江省宁波市海曙区天一街 10 号',
    NULL, NULL,
    '四季皆宜', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'yandang-mountain', '雁荡山', 'Yandang Mountain',
    '以流纹岩地貌著称的山岳，岩峰与洞壑在云雾中形态多变。',
    '位于温州乐清一带，分灵峰、灵岩、大龙湫、雁湖等片区，各片区之间需要乘车。'
    || '岩体为流纹岩，经断裂与风化后形成柱状、叠嶂状的峰群，大龙湫是一处落差较大的瀑布。'
    || '灵峰夜景是当地常见的安排，同一处岩峰在不同角度看形态差别很大。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '浙江省', '温州市', '浙江省温州市乐清市雁荡镇',
    NULL, NULL,
    '4 月至 10 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'yuantouzhu', '鼋头渚', 'Yuantouzhu',
    '太湖边的一处半岛，樱花与湖景是主要看点。',
    '位于无锡西南的太湖之滨，因半岛形似鼋头而得名，园区包含充山、鹿顶山与若干小岛。'
    || '春季樱花成片开放，是园内最集中的时段；平时以湖景、芦苇与山坡步道为主。'
    || '园内有游船可到太湖中的岛上，整体步行量中等，环湖一带路况平缓。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CN', '江苏省', '无锡市', '江苏省无锡市滨湖区鼋渚路 1 号',
    NULL, NULL,
    '3 月至 5 月，樱花期最佳', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'foshan-ancestral-temple', '佛山祖庙', 'Foshan Ancestral Temple',
    '供奉北帝的明代庙宇，砖雕、木雕与陶塑脊饰集中，旁边是黄飞鸿纪念馆。',
    '始建于北宋，现存建筑多为明代重建，沿中轴依次为万福台、灵应牌坊与正殿。'
    || '建筑上的砖雕、木雕、石雕与灰塑、陶塑脊饰是主要看点，正殿屋顶的瓦脊上排列着陶塑人物。'
    || '与黄飞鸿纪念馆、叶问堂在同一片区域内，可以看到醒狮与武术相关的陈列。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '广东省', '佛山市', '广东省佛山市禅城区祖庙路 21 号',
    NULL, NULL,
    '四季皆宜', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'quanzhou-kaiyuan-temple', '泉州开元寺', 'Kaiyuan Temple',
    '唐代始建的佛寺，东西两座石塔是泉州老城的天际线。',
    '位于泉州西街，寺院始建于唐代，现存建筑布局为明代以后重修。'
    || '大雄宝殿的柱础与廊柱中有印度教石刻构件，殿前月台须弥座上有狮身人面浮雕，是海上贸易留下的痕迹。'
    || '东西两座石塔为宋代所建，五层八角，塔身浮雕保存较好；2021 年泉州以「宋元中国的世界海洋商贸中心」列入世界遗产，开元寺是其中一处。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'CN', '福建省', '泉州市', '福建省泉州市鲤城区西街 176 号',
    NULL, NULL,
    '四季皆宜', 1.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),

-- ------------------------------------------------ 世界景点（40 条）
-- 覆盖六大洲: 亚洲 9 / 欧洲 12 / 非洲 5 / 北美洲 6 / 南美洲 5 / 大洋洲 3。
-- 口径与上面一致: 不带坐标, 票价只在确定免费时写 0, 评分一律 0。

(
    'angkor-wat', '吴哥窟', 'Angkor Wat',
    '9 至 15 世纪高棉帝国的寺庙群，以五塔轮廓和回廊浮雕著称，是现存规模最大的宗教建筑群之一。',
    '位于暹粒市北郊，现存寺庙、水库与道路构成一座面积数百平方公里的古代都城遗址。中心建筑吴哥寺建于 12 世纪，三层台基之上立五座塔，回廊墙面刻有长达数百米的浮雕，题材取自印度史诗与征战场景。1992 年列入世界文化遗产名录，此后由多国团队参与修复。旱季日出时西侧水池会映出五塔剪影，是最常被拍摄的机位。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'KH', '暹粒省', '暹粒', '柬埔寨暹粒市北郊',
    NULL, NULL,
    '11 月至次年 3 月（旱季）', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'taj-mahal', '泰姬陵', 'Taj Mahal',
    '莫卧儿皇帝沙贾汗为纪念亡妻所建的白色大理石陵墓，以完全对称的布局与镶嵌工艺闻名。',
    '坐落在阿格拉亚穆纳河南岸，1630 年代动工，历时约二十年建成。主体陵墓立于方形台基之上，四角立宣礼塔，中央穹顶高约 35 米，墙面镶嵌彩色石材组成花卉纹样。1983 年列入世界文化遗产名录。陵墓与两侧的清真寺、迎宾楼构成严格的轴对称构图，从正门望去的框景是最经典的视角。',
    (SELECT id FROM category WHERE slug = 'palace'),
    'IN', '北方邦', '阿格拉', '印度阿格拉市亚穆纳河南岸',
    NULL, NULL,
    '10 月至次年 3 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'mount-fuji', '富士山', 'Mount Fuji',
    '日本最高峰，海拔 3776 米的层状火山，近乎完美的圆锥形山体长期是绘画与诗歌的题材。',
    '横跨静冈与山梨两县，山顶终年气候严酷，登山道只在夏季开山期间开放。2013 年以「信仰的对象与艺术的源泉」列入世界文化遗产名录。观赏不必登山：河口湖、山中湖一侧的水面倒影，以及新干线上远望的侧影，都是常见视角。登山道分吉田、须走、御殿场、富士宫四条，吉田口设施最全。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'JP', '静冈县 / 山梨县', '富士宫', '日本静冈县与山梨县交界',
    NULL, NULL,
    '登山限夏季；远观秋冬能见度最好', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'petra', '佩特拉', 'Petra',
    '纳巴泰人在岩壁上凿出的古城，入口是一条狭窄的峡谷，尽头正对凿岩而成的卡兹尼神殿。',
    '位于约旦南部，公元前 4 世纪至公元 1 世纪间为纳巴泰王国的都城，后来因商路转移而废弃。建筑多为直接在砂岩崖壁上开凿，外立面带希腊化风格的柱式与山花。进入古城要步行穿过约 1.2 公里长的蛇道，谷壁高耸、仅见一线天，走到尽头时神殿立面突然出现在正前方。1985 年列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'JO', '马安省', '瓦迪穆萨', '约旦瓦迪穆萨镇东侧',
    NULL, NULL,
    '3 至 5 月、9 至 11 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'borobudur', '婆罗浮屠', 'Borobudur',
    '9 世纪的阶梯式石构佛塔，以层层回廊浮雕和顶部钟形舍利塔组成的立体曼荼罗闻名。',
    '位于爪哇岛中部，整座建筑用约两百万块火山岩砌成，形制为方形基座逐层收分至圆形顶层。回廊墙面与栏杆刻有大量叙事浮雕，内容为本生故事与善财童子参访。顶层立数十座钟形塔，塔身开菱形孔，其中一座塔内可见未完成的佛像。1991 年列入世界文化遗产名录，日出时段常需单独购票并由指定入口进入。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'ID', '中爪哇省', '马格朗', '印度尼西亚中爪哇省马格朗县',
    NULL, NULL,
    '5 至 9 月（旱季）', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'hagia-sophia', '圣索菲亚大教堂', 'Hagia Sophia',
    '6 世纪建成的穹顶建筑，先为教堂、后为清真寺、今为清真寺与参观地并存，是拜占庭建筑的代表。',
    '位于伊斯坦布尔老城，查士丁尼一世时期建成，中央穹顶直径约 31 米，依靠帆拱与半穹顶逐级传递重量，穹顶基座一圈开窗形成「悬空」的观感。奥斯曼时期在外侧增建四座宣礼塔并覆盖部分马赛克，部分拜占庭镶嵌画在近代修复后重新显露。老城历史区域于 1985 年列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'TR', '伊斯坦布尔省', '伊斯坦布尔', '土耳其伊斯坦布尔老城区',
    NULL, NULL,
    '4 至 6 月、9 至 11 月', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'ha-long-bay', '下龙湾', 'Ha Long Bay',
    '一千多座石灰岩岛屿与礁柱立在海面上，属喀斯特地貌被海水淹没后的形态。',
    '位于越南北部湾西部，海面上散布约一千六百座岛屿与岩柱，多数为孤立的小岛，岛体内部有溶洞。成因是石灰岩长期溶蚀后海侵淹没。1994 年列入世界自然遗产名录，后续又扩展了包括吉婆群岛在内的范围。常规玩法是乘船过夜或一日游，途中安排登岛观景与进溶洞。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'VN', '广宁省', '下龙', '越南广宁省下龙市海域',
    NULL, NULL,
    '10 至 4 月', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'kinkakuji', '金阁寺', 'Kinkaku-ji',
    '京都北山的临济宗寺院，三层楼阁的两层覆以金箔，与池面倒影构成固定视角。',
    '正式名称为鹿苑寺，始于 14 世纪足利义满的北山山庄，其后改为禅寺。舍利殿三层形制各异，一层为寝殿造、二层为武家造、三层为禅宗佛殿，外墙与二层以上覆金箔。1950 年舍利殿曾遭纵火焚毁，现建筑为 1955 年重建。寺院不大，游览路线为单向环池一周，读作「金阁」的倒影视角在池南侧。1994 年作为「古都京都的文化财」之一列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'JP', '京都府', '京都', '日本京都市北区',
    NULL, NULL,
    '四季皆宜', 1.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'gyeongbokgung', '景福宫', 'Gyeongbokgung',
    '朝鲜王朝的正宫，前朝后寝布局，正门光化门与勤政殿构成纵深轴线。',
    '始建于 14 世纪末，多次毁于战火并在 19 世纪重建，日据时期多数殿宇被拆，近代按史料陆续复原。中轴线上依次为光化门、兴礼门、勤政门、勤政殿，两侧有庆会楼与修政殿等。宫殿背后是北岳山，轴线对景是选址时的考量。每日固定时段在光化门与兴礼门之间进行守门将换岗仪式。',
    (SELECT id FROM category WHERE slug = 'palace'),
    'KR', '首尔特别市', '首尔', '韩国首尔市钟路区',
    NULL, NULL,
    '4 至 5 月、10 至 11 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'eiffel-tower', '埃菲尔铁塔', 'Eiffel Tower',
    '1889 年建成的铁构塔，高约 330 米，从战神广场到塞纳河形成对称的观赏轴线。',
    '为巴黎世界博览会而建，由约一万八千个金属构件用数百万铆钉连接。塔身分三层平台，二层与顶层可乘电梯或走楼梯上行，顶层能俯瞰塞纳河与巴黎的放射状街区。建成时曾被批评为破坏城市景观，后来成为城市的标志。夜间整点有持续数分钟的灯光闪烁。塞纳河沿岸区域于 1991 年列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'FR', '法兰西岛大区', '巴黎', '法国巴黎塞纳河畔战神广场',
    NULL, NULL,
    '4 至 6 月、9 至 10 月', 2.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'colosseum', '罗马斗兽场', 'Colosseum',
    '公元 1 世纪的椭圆形竞技场，可容纳数万观众，看台与地下通道结构保存至今。',
    '位于罗马老城东南，公元 72 年前后动工，80 年落成。平面为椭圆，外墙原分四层，底层为多立克柱式、其上依次为爱奥尼、科林斯与实墙，每层开八十个拱券。看台按身份分区，地下部分有供人员与动物升降的通道。中世纪后曾被当作采石场，部分石料被拆去建其他建筑，所以西侧外墙有明显缺口。1980 年作为「罗马历史中心」的一部分列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'IT', '拉齐奥大区', '罗马', '意大利罗马市老城东南',
    NULL, NULL,
    '4 至 6 月、9 至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'sagrada-familia', '圣家堂', 'Sagrada Familia',
    '高迪主持设计的大教堂，把自然形态与几何曲面结合，至今仍在按原方案施工。',
    '1882 年动工，高迪自 1883 年起主持设计直至去世，此后依其模型与图纸继续建造。建筑有诞生立面、受难立面与尚未完成的荣耀立面三组主题立面，内部立柱分叉成树状，穹顶与侧窗共同控制进入的光线。2005 年作为「安东尼·高迪的作品」之一列入世界文化遗产名录。塔楼参观需另购票并乘电梯上行，下楼走螺旋楼梯。',
    (SELECT id FROM category WHERE slug = 'religion'),
    'ES', '加泰罗尼亚', '巴塞罗那', '西班牙巴塞罗那市扩展区',
    NULL, NULL,
    '3 至 6 月、9 至 11 月', 2.5, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'versailles', '凡尔赛宫', 'Palace of Versailles',
    '17 世纪的法兰西王宫，以镜厅与对称的法式园林著称，中轴线一直延伸到运河尽头。',
    '由路易十四扩建为宫廷所在，此后长期是法国政治中心。宫殿以国王与王后套房、镜厅为核心，镜厅一侧为十七扇拱窗、另一侧对应十七面镜子。园林由勒诺特设计，中轴线自宫殿向西延伸到运河，两侧布置林园、水池与喷泉。宫外还有大小特里亚农宫。1979 年列入世界文化遗产名录。宫殿与园林需分别购票。',
    (SELECT id FROM category WHERE slug = 'palace'),
    'FR', '法兰西岛大区', '凡尔赛', '法国凡尔赛镇西侧',
    NULL, NULL,
    '4 至 9 月（园林喷泉开放期）', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'neuschwanstein', '新天鹅堡', 'Neuschwanstein Castle',
    '19 世纪巴伐利亚国王修建的城堡，白色石墙与尖塔立在阿尔卑斯山北麓的岩脊上。',
    '位于德国南部菲森附近，由巴伐利亚国王路德维希二世下令修建，参照中世纪骑士城堡与瓦格纳歌剧中的意象设计，内部大量使用壁画与木雕，并装了在当时属新技术的供暖与自来水系统。国王 1886 年去世时城堡尚未完工，此后即对公众开放。城堡内参观按编号分组限时进入，票面上印有入场时段。',
    (SELECT id FROM category WHERE slug = 'palace'),
    'DE', '巴伐利亚州', '菲森', '德国巴伐利亚州菲森附近',
    NULL, NULL,
    '5 至 9 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'acropolis', '雅典卫城', 'Acropolis of Athens',
    '建于石灰岩高台上的古希腊圣地，帕特农神庙的柱廊与山花是古典建筑的基准。',
    '位于雅典市中心的高约 150 米的岩台上，公元前 5 世纪在伯里克利主持下大规模营建。帕特农神庙为多立克柱式，柱身有微妙的收分与卷杀，台基与横梁也带弧线校正，用以修正视觉变形。卫城前门、胜利神庙与伊瑞克提翁神庙同在一组。1687 年神庙曾被用作火药库并因爆炸受损。1987 年列入世界文化遗产名录。山脚有卫城博物馆陈列原有构件与雕塑。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'GR', '阿提卡大区', '雅典', '希腊雅典市中心岩台',
    NULL, NULL,
    '4 至 6 月、9 至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'santorini', '圣托里尼', 'Santorini',
    '爱琴海上的火山岛，破火山口边缘的悬崖上建着白墙蓝顶的村落，正对海湾与日落。',
    '属基克拉泽斯群岛，现存轮廓来自史前一次大型火山喷发形成的破火山口。岛屿西侧的悬崖带集中了费拉、伊亚等村落，房屋沿崖壁层层堆叠，多为白墙配蓝色圆顶。伊亚的日落方向正对海湾与小岛，是全岛人流最密集的时段。岛的东侧地势平缓，有黑沙与红沙海滩。岛本身无门票，村内交通靠步行、巴士或缆车。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'GR', '南爱琴大区', '费拉', '希腊爱琴海基克拉泽斯群岛',
    NULL, NULL,
    '4 至 6 月、9 至 10 月', 24.0, 0.0,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'stonehenge', '巨石阵', 'Stonehenge',
    '新石器时代晚期的巨石圆阵，外围环沟与立石为同心布局，朝向夏至日出方向。',
    '位于英格兰南部索尔兹伯里平原，约公元前 2500 年前后形成现今的巨石布局。外围是环形土沟与土堤，内部为若干吨重的砂岩立石与横梁组成的三石结构，并有来自威尔士的较小蓝砂岩。中轴线上有一座被称为「脚跟石」的立石，夏至日出方向与它对齐。1986 年列入世界文化遗产名录。参观需沿指定路线绕行，不能进入石阵内部。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'GB', '威尔特郡', '埃姆斯伯里', '英国威尔特郡索尔兹伯里平原',
    NULL, NULL,
    '5 至 9 月', 2.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'pompeii', '庞贝古城', 'Pompeii',
    '公元 79 年被火山灰掩埋的罗马城市，街道、民居与壁画在封闭状态下保存下来。',
    '位于那不勒斯湾东岸，公元 79 年维苏威火山喷发后被火山灰与碎屑覆盖，城市结构因此得以完整保存。现存街道呈网格状，有广场、神庙、浴场、剧场与作坊，多处民居墙面留有壁画，地面有车辙与过街石。部分遇难者遗骸被火山灰包裹后形成空腔，近代灌注石膏得以呈现原形。1997 年列入世界文化遗产名录。遗址范围很大，需大量步行。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'IT', '坎帕尼亚大区', '那不勒斯', '意大利那不勒斯湾东岸',
    NULL, NULL,
    '4 至 6 月、9 至 10 月', 5.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'louvre', '卢浮宫', 'Louvre Museum',
    '由王宫改建的博物馆，藏品跨越古代文明到 19 世纪，以玻璃金字塔为现入口。',
    '始建于 12 世纪末的城堡，后逐步扩建为王宫，1793 年起作为博物馆开放。藏品覆盖古埃及、古希腊罗马、古代近东与欧洲绘画雕塑，名作如《蒙娜丽莎》《米洛的维纳斯》《萨莫色雷斯的胜利女神》分布在德农馆与叙利馆。1989 年在主庭院建成玻璃金字塔作为主入口。塞纳河沿岸区域于 1991 年列入世界文化遗产名录。展线极长，一次很难看完，按馆区取舍比按顺序走更实际。',
    (SELECT id FROM category WHERE slug = 'museum'),
    'FR', '法兰西岛大区', '巴黎', '法国巴黎塞纳河右岸',
    NULL, NULL,
    '四季皆宜（雨天更佳）', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'jungfrau', '少女峰', 'Jungfrau',
    '伯尔尼高地的一座雪峰，山肩处有欧洲海拔最高的火车站，可近观阿莱奇冰川。',
    '海拔 4158 米，属伯尔尼阿尔卑斯。1890 年代建成齿轨铁路，终点站建在山肩的岩体内部，出站即达观景平台与冰宫。列车全程在隧道中爬升，途中设两处短暂停留，可下车透过岩壁窗口看冰川。2001 年「瑞士阿尔卑斯山少女峰—阿莱奇」列入世界自然遗产名录。山下有格林德瓦与劳特布龙嫩两条上山的换乘路线，天气不佳时山顶常被云遮住。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CH', '伯尔尼州', '因特拉肯', '瑞士伯尔尼高地',
    NULL, NULL,
    '6 至 9 月上山；冬季为滑雪季', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'charles-bridge', '查理大桥', 'Charles Bridge',
    '横跨伏尔塔瓦河的石桥，两侧立三十尊雕像，连接老城与布拉格城堡一侧。',
    '始建于 14 世纪，由查理四世下令修建，替代此前被洪水冲毁的旧桥。桥身由砂岩砌成，两侧石栏上陆续立起三十尊巴洛克风格的圣像，多为 17 至 18 世纪作品，现多为复制品，原件部分存于博物馆。桥塔分居两端，老城一侧的桥塔可登顶。布拉格历史中心于 1992 年列入世界文化遗产名录。桥面仅供步行，清晨与夜间人流差别很大。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'CZ', '布拉格', '布拉格', '捷克布拉格伏尔塔瓦河上',
    NULL, NULL,
    '4 至 10 月', 1.5, 0.0,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'pyramids-of-giza', '吉萨金字塔群', 'Pyramids of Giza',
    '古王国时期的三座大金字塔与狮身人面像，以正方向基与四面对称的几何精度著称。',
    '位于开罗西南的吉萨高原，三座主要金字塔分别属胡夫、哈夫拉与孟卡拉。胡夫金字塔原高约 146 米，用数百万块石灰岩砌筑，内部有上升通道与墓室；哈夫拉金字塔顶部仍保留部分原外包石，轮廓更完整。狮身人面像由整块岩体就地雕成。1979 年作为「孟菲斯及其墓地」的一部分列入世界文化遗产名录。石阵周边可步行绕行，进入金字塔内部需另行购票并弯腰通过低矮通道。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'EG', '吉萨省', '吉萨', '埃及开罗西南吉萨高原',
    NULL, NULL,
    '10 月至次年 4 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'victoria-falls', '维多利亚瀑布', 'Victoria Falls',
    '赞比西河上的宽幅瀑布，水雾在远处即可看见，旱季与丰水季形态差别很大。',
    '位于赞比亚与津巴布韦交界，赞比西河在此落入约百米深的玄武岩裂隙。瀑布宽约 1700 米，被几个岛屿分成数段，其中主瀑布一段最宽。丰水季水量大，水雾腾起可达数百米高，部分观景步道会被水雾打湿；旱季水量小，反而更容易看清崖壁与裂隙结构。1989 年列入世界自然遗产名录。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'ZM', '南部省', '利文斯顿', '赞比亚与津巴布韦界河赞比西河上',
    NULL, NULL,
    '6 至 8 月（水量适中）', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'serengeti', '塞伦盖蒂', 'Serengeti National Park',
    '东非的大型草原保护区，角马与斑马按雨季循环迁徙，是迁徙现象最完整的保存地。',
    '位于坦桑尼亚北部，南接恩戈罗恩戈罗保护区，北连肯尼亚马赛马拉。降水随季节在南北之间推移，食草动物随之循环移动，形成每年一度的大规模迁徙。保护区内以草原为主，间有金合欢散生林与岩丘。1981 年列入世界自然遗产名录。游览需乘越野车由向导带领，园区内通行多为土路，雨季部分路段难行。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'TZ', '马拉区', '塞罗内拉', '坦桑尼亚北部草原',
    NULL, NULL,
    '6 至 10 月（旱季观赏条件最好）', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'marrakech-medina', '马拉喀什老城', 'Medina of Marrakesh',
    '红土城墙环绕的老城，巷道如迷宫，广场夜间集中了说书、乐手与小吃摊。',
    '马拉喀什建于 11 世纪，老城被长约数公里的红褐色土墙环绕，墙内巷弄密集，民居外墙多为土红色，内部围合成天井。主要建筑包括库图比亚清真寺、巴西亚宫与萨阿德王朝陵墓。老城中心的广场白天相对安静，入夜后摆满摊位与演出，被列为非物质文化遗产的广场演出即在此。1985 年列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'ancient-town'),
    'MA', '马拉喀什-萨菲大区', '马拉喀什', '摩洛哥马拉喀什市老城区',
    NULL, NULL,
    '3 至 5 月、10 至 11 月', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'table-mountain', '桌山', 'Table Mountain',
    '顶部平坦如桌面的砂岩山体，紧邻开普敦市区，山顶可俯瞰海湾与半岛。',
    '海拔约 1085 米，顶部因水平岩层与长期侵蚀而成平顶，常有云层沿山脊铺展后从崖顶垂下，当地人称之为「桌布」。上山可乘旋转缆车，也可步行沿数条步道上山，其中普拉特克利普峡谷路线最常见。2004 年作为「开普植物区保护区」的一部分列入世界自然遗产名录。山顶风大且天气变化快，缆车在风大时停运。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'ZA', '西开普省', '开普敦', '南非开普敦市西侧',
    NULL, NULL,
    '11 月至次年 3 月（南半球夏季）', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'grand-canyon', '科罗拉多大峡谷', 'Grand Canyon',
    '科罗拉多河切割出的巨型峡谷，水平岩层完整暴露，断面记录近二十亿年地质历史。',
    '位于美国亚利桑那州北部，由科罗拉多河长期下切形成，谷长约 446 公里，最深处超过 1800 米。谷壁岩层自下而上依次为深变质岩到年轻沉积岩，层理清晰，是地质学的经典剖面。南缘全年开放且设施集中，北缘海拔更高、冬季封闭。1979 年列入世界自然遗产名录。谷内徒步落差大，往返需按体力严格规划。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'US', '亚利桑那州', '图萨扬', '美国亚利桑那州北部',
    NULL, NULL,
    '3 至 5 月、9 至 11 月', 8.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'statue-of-liberty', '自由女神像', 'Statue of Liberty',
    '立在纽约港小岛上的铜像，由内部钢架支撑薄铜皮，落成时是法国赠予美国的礼物。',
    '位于纽约港的自由岛上，1886 年落成，由法国雕塑家巴托尔迪设计，内部钢架由埃菲尔设计。铜皮厚仅数毫米，靠内部骨架成形，表面因氧化呈青绿色。基座内设博物馆，登冠冕需单独预约且不设电梯，须走狭窄旋转楼梯。1984 年列入世界文化遗产名录。上岛只能乘渡轮，渡轮码头位于曼哈顿南端的炮台公园。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'US', '纽约州', '纽约', '美国纽约港自由岛',
    NULL, NULL,
    '4 至 10 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'yellowstone', '黄石国家公园', 'Yellowstone National Park',
    '以间歇泉、热泉与峡谷为主的保护区，也是北美野牛与狼等种群的重要栖息地。',
    '横跨怀俄明、蒙大拿与爱达荷三州，坐落在一处超级火山之上，地热活动集中，间歇泉、热泉与泥浆池数量众多，其中一处间歇泉喷发高度可达数十米且周期较稳定。黄石大峡谷的岩壁因热液蚀变呈黄褐色，公园名称即由此而来。园区为野牛与狼等种群提供栖息地，路边常可见成群野牛。1978 年列入世界自然遗产名录。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'US', '怀俄明州', '西黄石', '美国怀俄明州西北部',
    NULL, NULL,
    '6 至 9 月（其余多数道路封闭）', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'chichen-itza', '奇琴伊察', 'Chichen Itza',
    '玛雅后古典期的城邦遗址，中央金字塔在春秋分日会出现沿阶而下的光影。',
    '位于尤卡坦半岛北部，是玛雅文明的重要城邦之一，建筑融合了玛雅与中部墨西哥的风格。中央的金字塔四面各设阶梯，春秋分前后日落时，塔身阶梯的投影会形成沿阶而下的连续三角形光影。场内还有大球场、武士神庙与天文观测建筑。1988 年列入世界文化遗产名录。遗址地势平坦，全程步行，正午日晒很强。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'MX', '尤卡坦州', '巴利亚多利德', '墨西哥尤卡坦半岛北部',
    NULL, NULL,
    '11 月至次年 3 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'banff', '班夫国家公园', 'Banff National Park',
    '加拿大落基山脉东麓的保护区，冰川湖、雪峰与针叶林连成一片。',
    '位于阿尔伯塔省，是加拿大最早设立的国家公园，园区以冰川侵蚀形成的湖泊与谷地为主，湖水因悬浮的岩粉呈蓝绿色。路易斯湖与梦莲湖是最常被拍摄的两处，后者需在特定时段乘接驳车进入。园内公路沿线设有多处观景点与步道，野生动物包括麋鹿、山羊与熊。1984 年作为「加拿大落基山脉公园群」的一部分列入世界自然遗产名录。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CA', '阿尔伯塔省', '班夫', '加拿大阿尔伯塔省落基山脉东麓',
    NULL, NULL,
    '6 至 9 月（冬季为滑雪季）', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'niagara-falls', '尼亚加拉瀑布', 'Niagara Falls',
    '横跨美加边境的三段瀑布，以马蹄瀑布水量最大，水雾常年可见。',
    '位于安大略湖与伊利湖之间的尼亚加拉河上，由马蹄瀑布、美国瀑布与新娘面纱瀑布组成。河水在石灰岩崖壁处跌落约五十米，马蹄瀑布一段承担了绝大部分水量。两侧分属加拿大与美国，均可乘观光船靠近瀑布底部，也有步行隧道通到瀑布后方。瀑布本身不在世界遗产名录内，但作为自然景观长期是北美最知名的景点之一。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'CA', '安大略省', '尼亚加拉瀑布城', '加拿大安大略省与美国纽约州界河上',
    NULL, NULL,
    '6 至 9 月', 4.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'machu-picchu', '马丘比丘', 'Machu Picchu',
    '海拔约 2400 米的山脊城址，梯田与石构沿地形层层展开，四周为陡峭山谷。',
    '位于秘鲁南部安第斯山区，约建于 15 世纪，属印加时期的城址，由神庙区、王宫区与梯田区组成，石构不用灰浆，靠精确切割的石块密合。其中「拴日石」与太阳神庙均与太阳运行方位有关。1911 年被重新发现。1983 年以「马丘比丘历史圣地」列入世界文化与自然双重遗产名录。每日入场人数受限，需提前预约时段并按指定路线通行。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'PE', '库斯科大区', '库斯科', '秘鲁南部安第斯山区',
    NULL, NULL,
    '5 至 9 月（旱季）', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'christ-the-redeemer', '里约基督像', 'Christ the Redeemer',
    '立在科尔科瓦多山顶的张开双臂的巨大石像，从城中多数位置都能望见。',
    '位于里约热内卢的科尔科瓦多山顶，高约 30 米，基座另高约 8 米，用钢筋混凝土外覆皂石薄片，1931 年落成。塑像双臂张开，正面朝向瓜纳巴拉湾。所立的山峰属蒂茹卡国家公园范围。城市与山海之间的整体景观于 2012 年列入世界文化遗产名录，塑像位于该遗产范围内。登顶可乘齿轨小火车或面包车，也可徒步。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'BR', '里约热内卢州', '里约热内卢', '巴西里约热内卢科尔科瓦多山顶',
    NULL, NULL,
    '5 至 10 月', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'iguazu-falls', '伊瓜苏瀑布', 'Iguazu Falls',
    '由两百多条小瀑布组成的瀑布群，中央的「魔鬼咽喉」落差集中、水声轰鸣。',
    '位于巴西与阿根廷交界，伊瓜苏河在玄武岩台地上跌落后汇入巴拉那河。瀑布群长约 2.7 公里，被岛屿与岩脊分成众多细流，多数时段水量稳定。核心的一段呈马蹄形，落差约 80 米，观景栈道可接近到水雾范围内。两侧国家公园分别于 1984 年与 1986 年列入世界自然遗产名录，合为同一处遗产。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'BR', '巴拉那州', '福斯-杜伊瓜苏', '巴西与阿根廷界河伊瓜苏河上',
    NULL, NULL,
    '3 至 5 月、8 至 10 月', 6.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'galapagos', '加拉帕戈斯群岛', 'Galapagos Islands',
    '太平洋上的火山群岛，物种随岛屿隔离而分化，是演化生物学的重要现场。',
    '属厄瓜多尔，位于南美大陆以西约一千公里的太平洋上，由十余座主要岛屿与众多小岛组成。岛屿均为火山成因，植被随海拔与岛屿年龄差异明显。岛上有象龟、海鬣蜥与多种不会远飞的鸟类，因长期与大陆隔离而各自分化。1978 年列入世界自然遗产名录。进入群岛需在机场办理管理手续，登岛一般需持证向导带领，各岛停留须按许可路线行走。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'EC', '加拉帕戈斯省', '阿约拉港', '厄瓜多尔以西太平洋海域',
    NULL, NULL,
    '全年（12 至 5 月温暖多雨，6 至 11 月凉爽干燥）', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'easter-island', '复活节岛', 'Easter Island',
    '太平洋上的孤立火山岛，岛上散布数百尊巨石人像，多数背朝大海立于祭台之上。',
    '属智利，位于太平洋东南部，距最近的大陆三千多公里。岛上现存约九百尊巨石人像，多为凝灰岩或玄武岩雕成，多数立在与祭祀相关的石台之上，背向大海、面向村落。人像的运输与竖立方式长期是研究课题。岛民曾创制一种刻在木板上的文字符号，至今未完全解读。1995 年作为「拉帕努伊国家公园」列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'archaeology'),
    'CL', '瓦尔帕莱索大区', '安加罗阿', '智利以西太平洋上的火山岛',
    NULL, NULL,
    '10 月至次年 3 月', 24.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'sydney-opera-house', '悉尼歌剧院', 'Sydney Opera House',
    '由球面壳体拼成的剧院建筑，屋面覆白色瓷砖，坐落在海港大桥旁的半岛上。',
    '位于悉尼港的贝内朗角，1973 年落成，由丹麦建筑师约恩·乌松设计。屋面由一组取自同一球面的壳体构成，施工中为解决壳体几何问题，最终统一为球面分段，使构件可以标准化预制。表面覆以百万余块白色与米色瓷砖。内部有音乐厅、歌剧院等多个厅室，可参加导览参观后台与厅内。2007 年列入世界文化遗产名录。',
    (SELECT id FROM category WHERE slug = 'landmark'),
    'AU', '新南威尔士州', '悉尼', '澳大利亚悉尼港贝内朗角',
    NULL, NULL,
    '四季皆宜', 3.0, NULL,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'great-barrier-reef', '大堡礁', 'Great Barrier Reef',
    '由珊瑚与钙质骨骼堆积形成的巨大礁群，沿海岸线延伸两千余公里。',
    '位于澳大利亚东北外海，由数千个独立礁体与岛屿组成，是现存规模最大的珊瑚礁系统。礁体由造礁珊瑚的钙质骨骼长期堆积而成，为大量鱼类与无脊椎动物提供栖息环境。1981 年列入世界自然遗产名录。观赏方式包括浮潜、深潜与玻璃底船，水质与珊瑚状况受海水温度影响，不同区域的状况差别较大。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'AU', '昆士兰州', '凯恩斯', '澳大利亚昆士兰州东北外海',
    NULL, NULL,
    '6 至 10 月（干季，能见度较好）', 8.0, 0.0,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    'milford-sound', '米尔福德峡湾', 'Milford Sound',
    '冰川侵蚀而成的深峡湾，两侧崖壁近乎垂直，常年有瀑布沿崖面跌落。',
    '位于新西兰南岛峡湾国家公园内，由冰期冰川下切后海水侵入形成。峡湾两侧为近乎垂直的岩壁，其中一处山峰自水面算起高逾一千米，是世界上较高的临海崖壁之一。区域内降水丰沛，崖壁上常年可见临时瀑布，雨后数量明显增加。1990 年作为「蒂瓦希普纳穆」的一部分列入世界自然遗产名录。进入峡湾需从陆路经隧道或乘船，峡湾内通常乘船游览。',
    (SELECT id FROM category WHERE slug = 'nature'),
    'NZ', '南地大区', '米尔福德峡湾', '新西兰南岛峡湾国家公园',
    NULL, NULL,
    '11 月至次年 3 月', 8.0, 0.0,
    'published', 'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
)
ON CONFLICT (slug) DO UPDATE SET
    name            = EXCLUDED.name,
    name_en         = EXCLUDED.name_en,
    summary         = EXCLUDED.summary,
    description     = EXCLUDED.description,
    category_id     = EXCLUDED.category_id,
    country_code    = EXCLUDED.country_code,
    province        = EXCLUDED.province,
    city            = EXCLUDED.city,
    address         = EXCLUDED.address,
    lat             = EXCLUDED.lat,
    lon             = EXCLUDED.lon,
    best_season     = EXCLUDED.best_season,
    suggested_hours = EXCLUDED.suggested_hours,
    ticket_price    = EXCLUDED.ticket_price,
    status          = EXCLUDED.status,
    source          = EXCLUDED.source,
    license         = EXCLUDED.license,
    source_url      = EXCLUDED.source_url;

-- ------------------------------------------------- 景区等级与世界遗产 (v2.0)
--
-- 这两列不放进上面的 INSERT: 加进列清单会让每条老记录都要改一遍, 而且
-- 它们的口径不同 —— **留空表示「未核实」, 不是「没有等级」**, 单独一块更好核对。
-- a_level 用 GB/T 17775 的说法, 只适用于中国大陆景区; 境外景点一律留空,
-- 它们的「等级」看 heritage(UNESCO 世界遗产类别)。
-- 这一段每次重跑都无条件覆盖, 所以手工在库里改过的值会被修回来。

UPDATE attraction a
SET a_level = m.a_level, heritage = m.heritage
FROM (VALUES
    ('west-lake',             '5A',  'cultural'),
    ('huangshan',             '5A',  'mixed'),
    ('jiuzhaigou',            '5A',  'natural'),
    ('zhangjiajie',           '5A',  'natural'),
    ('lijiang-old-town',      '5A',  'cultural'),
    ('pingyao',               '5A',  'cultural'),
    ('yungang-grottoes',      '5A',  'cultural'),
    ('longmen-grottoes',      '5A',  'cultural'),
    ('mogao-caves',           NULL,  'cultural'),
    ('potala-palace',         '5A',  'cultural'),
    ('mount-emei',            '5A',  'mixed'),
    ('leshan-buddha',         '5A',  'mixed'),
    ('wudang-mountain',       '5A',  'cultural'),
    ('taishan',               '5A',  'mixed'),
    ('hongcun',               '5A',  'cultural'),
    ('ming-xiaoling',         '5A',  'cultural'),
    ('temple-of-heaven',      '5A',  'cultural'),
    ('summer-palace',         '5A',  'cultural'),
    ('palace-museum',         '5A',  'cultural'),
    ('terracotta-army',       '5A',  'cultural'),
    ('huaqing-palace',        '5A',  NULL),
    ('huashan',               '5A',  NULL),
    ('badaling-great-wall',   '5A',  'cultural'),
    ('wuzhen',                '5A',  NULL),
    ('zhouzhuang',            '5A',  NULL),
    ('xitang',                '5A',  NULL),
    ('changbai-mountain',     '5A',  NULL),
    ('kanas',                 '5A',  NULL),
    ('yinxu',                 '5A',  'cultural'),
    ('orange-isle',           '5A',  NULL),
    ('hangzhou-songcheng',    '5A',  NULL),
    ('daocheng-yading',       '5A',  NULL),
    ('oriental-pearl-tower',  '5A',  NULL),
    ('liangzhu',              '4A',  'cultural'),
    ('fenghuang',             '4A',  NULL),
    ('sanxingdui-museum',     '4A',  NULL),
    ('shaanxi-history-museum', '4A',  NULL),
    ('national-museum',       '4A',  NULL),
    ('shanghai-museum',       '4A',  NULL),
    ('suzhou-museum',         '4A',  NULL),
    ('canton-tower',          '4A',  NULL),
    ('lingyin-temple',        NULL,  NULL),
    ('the-bund',              NULL,  NULL),
    ('hulunbuir',             NULL,  NULL),
    ('shanghai-disney',       NULL,  NULL),
    ('chimelong-ocean-kingdom', NULL,  NULL),
    ('universal-beijing',     NULL,  NULL),
    ('window-of-the-world',   NULL,  NULL),
    ('angkor-wat',            NULL,  'cultural'),
    ('taj-mahal',             NULL,  'cultural'),
    ('mount-fuji',            NULL,  'cultural'),
    ('petra',                 NULL,  'cultural'),
    ('borobudur',             NULL,  'cultural'),
    ('hagia-sophia',          NULL,  'cultural'),
    ('ha-long-bay',           NULL,  'natural'),
    ('kinkakuji',             NULL,  'cultural'),
    ('gyeongbokgung',         NULL,  NULL),
    ('eiffel-tower',          NULL,  'cultural'),
    ('colosseum',             NULL,  'cultural'),
    ('sagrada-familia',       NULL,  'cultural'),
    ('versailles',            NULL,  'cultural'),
    ('neuschwanstein',        NULL,  NULL),
    ('acropolis',             NULL,  'cultural'),
    ('santorini',             NULL,  NULL),
    ('stonehenge',            NULL,  'cultural'),
    ('pompeii',               NULL,  'cultural'),
    ('louvre',                NULL,  'cultural'),
    ('jungfrau',              NULL,  'natural'),
    ('charles-bridge',        NULL,  'cultural'),
    ('pyramids-of-giza',      NULL,  'cultural'),
    ('victoria-falls',        NULL,  'natural'),
    ('serengeti',             NULL,  'natural'),
    ('marrakech-medina',      NULL,  'cultural'),
    ('table-mountain',        NULL,  'natural'),
    ('grand-canyon',          NULL,  'natural'),
    ('statue-of-liberty',     NULL,  'cultural'),
    ('yellowstone',           NULL,  'natural'),
    ('chichen-itza',          NULL,  'cultural'),
    ('banff',                 NULL,  'natural'),
    ('niagara-falls',         NULL,  NULL),
    ('machu-picchu',          NULL,  'mixed'),
    ('christ-the-redeemer',   NULL,  'cultural'),
    ('iguazu-falls',          NULL,  'natural'),
    ('galapagos',             NULL,  'natural'),
    ('easter-island',         NULL,  'cultural'),
    ('sydney-opera-house',    NULL,  'cultural'),
    ('great-barrier-reef',    NULL,  'natural'),
    ('milford-sound',         NULL,  'natural'),
    ('guangzhou-chimelong',   '5A',  NULL),
    ('yellow-crane-tower',    '5A',  NULL),
    ('shenyang-imperial-palace',      '5A',  'cultural'),
    ('tengwang-pavilion',             '5A',  NULL),
    ('gulangyu-island',               '5A',  'cultural'),
    ('stone-forest',                  '5A',  'natural'),
    ('kumbum-monastery',              '5A',  NULL),
    ('yandang-mountain',              '5A',  NULL),
    ('yuantouzhu',                    '5A',  NULL),
    ('quanzhou-kaiyuan-temple',       NULL,  'cultural')
) AS m(slug, a_level, heritage)
WHERE a.slug = m.slug;

-- ---------------------------------------------------------------- 景点标签
--
-- 先清掉本文件认领的景点(source 是本文件的)的旧关联, 再按下面的清单重建。
-- 这样把某个标签从清单里删掉时数据库里也会跟着删, 不会留下悬空的旧关联。

DELETE FROM attraction_tag
WHERE attraction_id IN (SELECT id FROM attraction WHERE source = 'Have-A-Trip 自采（公开事实信息）');

INSERT INTO attraction_tag (attraction_id, tag_id)
SELECT a.id, t.id
FROM (VALUES
    ('west-lake',                'world-heritage'        ),
    ('west-lake',                'free'                  ),
    ('west-lake',                'photography'           ),
    ('west-lake',                'night-view'            ),
    ('huangshan',                'world-heritage'        ),
    ('huangshan',                'hiking'                ),
    ('huangshan',                'sunrise'               ),
    ('huangshan',                'photography'           ),
    ('jiuzhaigou',               'world-heritage'        ),
    ('jiuzhaigou',               'lake'                  ),
    ('jiuzhaigou',               'photography'           ),
    ('jiuzhaigou',               'hiking'                ),
    ('zhangjiajie',              'world-heritage'        ),
    ('zhangjiajie',              'hiking'                ),
    ('zhangjiajie',              'photography'           ),
    ('zhangjiajie',              'sunrise'               ),
    ('taishan',                  'world-heritage'        ),
    ('taishan',                  'hiking'                ),
    ('taishan',                  'sunrise'               ),
    ('taishan',                  'ancient-architecture'  ),
    ('huashan',                  'hiking'                ),
    ('huashan',                  'sunrise'               ),
    ('huashan',                  'photography'           ),
    ('lijiang-river',            'cruise'                ),
    ('lijiang-river',            'photography'           ),
    ('lijiang-river',            'must-see'              ),
    ('qinghai-lake',             'lake'                  ),
    ('qinghai-lake',             'photography'           ),
    ('qinghai-lake',             'grassland'             ),
    ('daocheng-yading',          'hiking'                ),
    ('daocheng-yading',          'photography'           ),
    ('daocheng-yading',          'lake'                  ),
    ('changbai-mountain',        'hiking'                ),
    ('changbai-mountain',        'lake'                  ),
    ('changbai-mountain',        'photography'           ),
    ('hulunbuir',                'grassland'             ),
    ('hulunbuir',                'photography'           ),
    ('hulunbuir',                'family'                ),
    ('kanas',                    'lake'                  ),
    ('kanas',                    'photography'           ),
    ('kanas',                    'hiking'                ),
    ('terracotta-army',          'world-heritage'        ),
    ('terracotta-army',          'family'                ),
    ('terracotta-army',          'indoor'                ),
    ('badaling-great-wall',      'world-heritage'        ),
    ('badaling-great-wall',      'hiking'                ),
    ('badaling-great-wall',      'must-see'              ),
    ('badaling-great-wall',      'ancient-architecture'  ),
    ('mogao-caves',              'world-heritage'        ),
    ('mogao-caves',              'grottoes'              ),
    ('mogao-caves',              'indoor'                ),
    ('mogao-caves',              'must-see'              ),
    ('yungang-grottoes',         'world-heritage'        ),
    ('yungang-grottoes',         'grottoes'              ),
    ('yungang-grottoes',         'indoor'                ),
    ('longmen-grottoes',         'world-heritage'        ),
    ('longmen-grottoes',         'grottoes'              ),
    ('longmen-grottoes',         'night-view'            ),
    ('pingyao',                  'world-heritage'        ),
    ('pingyao',                  'ancient-architecture'  ),
    ('pingyao',                  'night-view'            ),
    ('pingyao',                  'photography'           ),
    ('ming-xiaoling',            'world-heritage'        ),
    ('ming-xiaoling',            'ancient-architecture'  ),
    ('ming-xiaoling',            'photography'           ),
    ('huaqing-palace',           'ancient-architecture'  ),
    ('huaqing-palace',           'family'                ),
    ('huaqing-palace',           'night-view'            ),
    ('yinxu',                    'world-heritage'        ),
    ('yinxu',                    'indoor'                ),
    ('yinxu',                    'family'                ),
    ('liangzhu',                 'world-heritage'        ),
    ('liangzhu',                 'indoor'                ),
    ('liangzhu',                 'family'                ),
    ('liangzhu',                 'park'                  ),
    ('palace-museum',            'world-heritage'        ),
    ('palace-museum',            'family'                ),
    ('palace-museum',            'indoor'                ),
    ('palace-museum',            'ancient-architecture'  ),
    ('palace-museum',            'must-see'              ),
    ('national-museum',          'free'                  ),
    ('national-museum',          'family'                ),
    ('national-museum',          'indoor'                ),
    ('shanghai-museum',          'indoor'                ),
    ('shanghai-museum',          'family'                ),
    ('shanghai-museum',          'must-see'              ),
    ('shaanxi-history-museum',   'indoor'                ),
    ('shaanxi-history-museum',   'family'                ),
    ('shaanxi-history-museum',   'must-see'              ),
    ('sanxingdui-museum',        'indoor'                ),
    ('sanxingdui-museum',        'family'                ),
    ('sanxingdui-museum',        'must-see'              ),
    ('suzhou-museum',            'free'                  ),
    ('suzhou-museum',            'indoor'                ),
    ('suzhou-museum',            'family'                ),
    ('suzhou-museum',            'photography'           ),
    ('the-bund',                 'free'                  ),
    ('the-bund',                 'night-view'            ),
    ('the-bund',                 'photography'           ),
    ('the-bund',                 'ancient-architecture'  ),
    ('oriental-pearl-tower',     'city-view'             ),
    ('oriental-pearl-tower',     'night-view'            ),
    ('oriental-pearl-tower',     'family'                ),
    ('canton-tower',             'city-view'             ),
    ('canton-tower',             'night-view'            ),
    ('canton-tower',             'family'                ),
    ('temple-of-heaven',         'world-heritage'        ),
    ('temple-of-heaven',         'ancient-architecture'  ),
    ('temple-of-heaven',         'family'                ),
    ('temple-of-heaven',         'photography'           ),
    ('summer-palace',            'world-heritage'        ),
    ('summer-palace',            'garden'                ),
    ('summer-palace',            'family'                ),
    ('summer-palace',            'lake'                  ),
    ('orange-isle',              'free'                  ),
    ('orange-isle',              'night-view'            ),
    ('orange-isle',              'family'                ),
    ('orange-isle',              'city-view'             ),
    ('lingyin-temple',           'ancient-architecture'  ),
    ('lingyin-temple',           'photography'           ),
    ('potala-palace',            'world-heritage'        ),
    ('potala-palace',            'ancient-architecture'  ),
    ('potala-palace',            'must-see'              ),
    ('potala-palace',            'indoor'                ),
    ('mount-emei',               'world-heritage'        ),
    ('mount-emei',               'hiking'                ),
    ('mount-emei',               'sunrise'               ),
    ('mount-emei',               'ancient-architecture'  ),
    ('leshan-buddha',            'world-heritage'        ),
    ('leshan-buddha',            'ancient-architecture'  ),
    ('leshan-buddha',            'cruise'                ),
    ('wudang-mountain',          'world-heritage'        ),
    ('wudang-mountain',          'hiking'                ),
    ('wudang-mountain',          'ancient-architecture'  ),
    ('wudang-mountain',          'sunrise'               ),
    ('wuzhen',                   'water-town'            ),
    ('wuzhen',                   'night-view'            ),
    ('wuzhen',                   'photography'           ),
    ('zhouzhuang',               'water-town'            ),
    ('zhouzhuang',               'photography'           ),
    ('zhouzhuang',               'ancient-architecture'  ),
    ('zhouzhuang',               'cruise'                ),
    ('xitang',                   'water-town'            ),
    ('xitang',                   'night-view'            ),
    ('xitang',                   'photography'           ),
    ('hongcun',                  'world-heritage'        ),
    ('hongcun',                  'photography'           ),
    ('hongcun',                  'ancient-architecture'  ),
    ('hongcun',                  'water-town'            ),
    ('lijiang-old-town',         'world-heritage'        ),
    ('lijiang-old-town',         'ancient-architecture'  ),
    ('lijiang-old-town',         'night-view'            ),
    ('lijiang-old-town',         'photography'           ),
    ('fenghuang',                'water-town'            ),
    ('fenghuang',                'night-view'            ),
    ('fenghuang',                'photography'           ),
    ('fenghuang',                'ancient-architecture'  ),
    ('shanghai-disney',          'family'                ),
    ('shanghai-disney',          'amusement'             ),
    ('shanghai-disney',          'night-view'            ),
    ('chimelong-ocean-kingdom',  'family'                ),
    ('chimelong-ocean-kingdom',  'amusement'             ),
    ('chimelong-ocean-kingdom',  'indoor'                ),
    ('chimelong-ocean-kingdom',  'night-view'            ),
    ('universal-beijing',        'family'                ),
    ('universal-beijing',        'amusement'             ),
    ('universal-beijing',        'night-view'            ),
    ('universal-beijing',        'indoor'                ),
    ('window-of-the-world',      'family'                ),
    ('window-of-the-world',      'amusement'             ),
    ('window-of-the-world',      'night-view'            ),
    ('hangzhou-songcheng',       'family'                ),
    ('hangzhou-songcheng',       'amusement'             ),
    ('hangzhou-songcheng',       'night-view'            ),
    ('hangzhou-songcheng',       'indoor'                ),
    ('angkor-wat',               'world-heritage'),
    ('angkor-wat',               'ruins'),
    ('angkor-wat',               'ancient-civilization'),
    ('angkor-wat',               'sunrise'),
    ('angkor-wat',               'photography'),
    ('taj-mahal',                'world-heritage'),
    ('taj-mahal',                'ancient-architecture'),
    ('taj-mahal',                'must-see'),
    ('taj-mahal',                'photography'),
    ('mount-fuji',               'world-heritage'),
    ('mount-fuji',               'hiking'),
    ('mount-fuji',               'photography'),
    ('mount-fuji',               'sunrise'),
    ('petra',                    'world-heritage'),
    ('petra',                    'ruins'),
    ('petra',                    'ancient-civilization'),
    ('petra',                    'hiking'),
    ('petra',                    'must-see'),
    ('borobudur',                'world-heritage'),
    ('borobudur',                'ancient-architecture'),
    ('borobudur',                'sunrise'),
    ('borobudur',                'must-see'),
    ('hagia-sophia',             'world-heritage'),
    ('hagia-sophia',             'ancient-architecture'),
    ('hagia-sophia',             'indoor'),
    ('hagia-sophia',             'must-see'),
    ('ha-long-bay',              'world-heritage'),
    ('ha-long-bay',              'island'),
    ('ha-long-bay',              'cruise'),
    ('ha-long-bay',              'photography'),
    ('kinkakuji',                'world-heritage'),
    ('kinkakuji',                'ancient-architecture'),
    ('kinkakuji',                'garden'),
    ('kinkakuji',                'photography'),
    ('gyeongbokgung',            'ancient-architecture'),
    ('gyeongbokgung',            'indoor'),
    ('gyeongbokgung',            'family'),
    ('gyeongbokgung',            'photography'),
    ('eiffel-tower',             'world-heritage'),
    ('eiffel-tower',             'city-view'),
    ('eiffel-tower',             'night-view'),
    ('eiffel-tower',             'must-see'),
    ('eiffel-tower',             'architecture'),
    ('colosseum',                'world-heritage'),
    ('colosseum',                'ruins'),
    ('colosseum',                'ancient-architecture'),
    ('colosseum',                'indoor'),
    ('colosseum',                'must-see'),
    ('sagrada-familia',          'world-heritage'),
    ('sagrada-familia',          'architecture'),
    ('sagrada-familia',          'art'),
    ('sagrada-familia',          'indoor'),
    ('sagrada-familia',          'must-see'),
    ('versailles',               'world-heritage'),
    ('versailles',               'ancient-architecture'),
    ('versailles',               'garden'),
    ('versailles',               'must-see'),
    ('neuschwanstein',           'ancient-architecture'),
    ('neuschwanstein',           'must-see'),
    ('neuschwanstein',           'photography'),
    ('neuschwanstein',           'hiking'),
    ('acropolis',                'world-heritage'),
    ('acropolis',                'ruins'),
    ('acropolis',                'ancient-architecture'),
    ('acropolis',                'city-view'),
    ('acropolis',                'must-see'),
    ('santorini',                'island'),
    ('santorini',                'sunset'),
    ('santorini',                'photography'),
    ('santorini',                'cruise'),
    ('santorini',                'night-view'),
    ('stonehenge',               'world-heritage'),
    ('stonehenge',               'ruins'),
    ('stonehenge',               'ancient-civilization'),
    ('stonehenge',               'photography'),
    ('pompeii',                  'world-heritage'),
    ('pompeii',                  'ruins'),
    ('pompeii',                  'ancient-civilization'),
    ('pompeii',                  'hiking'),
    ('pompeii',                  'indoor'),
    ('louvre',                   'world-heritage'),
    ('louvre',                   'art'),
    ('louvre',                   'indoor'),
    ('louvre',                   'must-see'),
    ('louvre',                   'architecture'),
    ('jungfrau',                 'world-heritage'),
    ('jungfrau',                 'glacier'),
    ('jungfrau',                 'hiking'),
    ('jungfrau',                 'photography'),
    ('jungfrau',                 'family'),
    ('charles-bridge',           'world-heritage'),
    ('charles-bridge',           'free'),
    ('charles-bridge',           'night-view'),
    ('charles-bridge',           'photography'),
    ('charles-bridge',           'ancient-architecture'),
    ('pyramids-of-giza',         'world-heritage'),
    ('pyramids-of-giza',         'ruins'),
    ('pyramids-of-giza',         'ancient-civilization'),
    ('pyramids-of-giza',         'desert'),
    ('pyramids-of-giza',         'must-see'),
    ('victoria-falls',           'world-heritage'),
    ('victoria-falls',           'waterfall'),
    ('victoria-falls',           'photography'),
    ('victoria-falls',           'wildlife'),
    ('serengeti',                'world-heritage'),
    ('serengeti',                'wildlife'),
    ('serengeti',                'photography'),
    ('serengeti',                'sunrise'),
    ('marrakech-medina',         'world-heritage'),
    ('marrakech-medina',         'ancient-architecture'),
    ('marrakech-medina',         'night-view'),
    ('marrakech-medina',         'desert'),
    ('marrakech-medina',         'photography'),
    ('table-mountain',           'world-heritage'),
    ('table-mountain',           'hiking'),
    ('table-mountain',           'city-view'),
    ('table-mountain',           'photography'),
    ('table-mountain',           'sunset'),
    ('grand-canyon',             'world-heritage'),
    ('grand-canyon',             'canyon'),
    ('grand-canyon',             'hiking'),
    ('grand-canyon',             'sunrise'),
    ('grand-canyon',             'photography'),
    ('statue-of-liberty',        'world-heritage'),
    ('statue-of-liberty',        'city-view'),
    ('statue-of-liberty',        'cruise'),
    ('statue-of-liberty',        'must-see'),
    ('statue-of-liberty',        'family'),
    ('yellowstone',              'world-heritage'),
    ('yellowstone',              'wildlife'),
    ('yellowstone',              'hiking'),
    ('yellowstone',              'photography'),
    ('yellowstone',              'family'),
    ('chichen-itza',             'world-heritage'),
    ('chichen-itza',             'ruins'),
    ('chichen-itza',             'ancient-civilization'),
    ('chichen-itza',             'must-see'),
    ('chichen-itza',             'photography'),
    ('banff',                    'world-heritage'),
    ('banff',                    'glacier'),
    ('banff',                    'hiking'),
    ('banff',                    'photography'),
    ('banff',                    'family'),
    ('niagara-falls',            'waterfall'),
    ('niagara-falls',            'cruise'),
    ('niagara-falls',            'family'),
    ('niagara-falls',            'night-view'),
    ('niagara-falls',            'photography'),
    ('machu-picchu',             'world-heritage'),
    ('machu-picchu',             'ruins'),
    ('machu-picchu',             'ancient-civilization'),
    ('machu-picchu',             'hiking'),
    ('machu-picchu',             'sunrise'),
    ('machu-picchu',             'must-see'),
    ('christ-the-redeemer',      'world-heritage'),
    ('christ-the-redeemer',      'city-view'),
    ('christ-the-redeemer',      'must-see'),
    ('christ-the-redeemer',      'photography'),
    ('iguazu-falls',             'world-heritage'),
    ('iguazu-falls',             'waterfall'),
    ('iguazu-falls',             'wildlife'),
    ('iguazu-falls',             'photography'),
    ('galapagos',                'world-heritage'),
    ('galapagos',                'island'),
    ('galapagos',                'wildlife'),
    ('galapagos',                'cruise'),
    ('galapagos',                'photography'),
    ('easter-island',            'world-heritage'),
    ('easter-island',            'ruins'),
    ('easter-island',            'island'),
    ('easter-island',            'ancient-civilization'),
    ('easter-island',            'sunset'),
    ('sydney-opera-house',       'world-heritage'),
    ('sydney-opera-house',       'architecture'),
    ('sydney-opera-house',       'city-view'),
    ('sydney-opera-house',       'night-view'),
    ('sydney-opera-house',       'photography'),
    ('great-barrier-reef',       'world-heritage'),
    ('great-barrier-reef',       'reef'),
    ('great-barrier-reef',       'island'),
    ('great-barrier-reef',       'wildlife'),
    ('great-barrier-reef',       'cruise'),
    ('milford-sound',            'world-heritage'),
    ('milford-sound',            'glacier'),
    ('milford-sound',            'cruise'),
    ('milford-sound',            'waterfall'),
    ('milford-sound',            'sunset'),
    ('shanghai-natural-history-museum', 'family'                ),
    ('shanghai-natural-history-museum', 'indoor'                ),
    ('shanghai-natural-history-museum', 'must-see'              ),
    ('nanjing-museum',              'art'                   ),
    ('nanjing-museum',              'indoor'                ),
    ('nanjing-museum',              'must-see'              ),
    ('hubei-museum',                'art'                   ),
    ('hubei-museum',                'indoor'                ),
    ('hubei-museum',                'must-see'              ),
    ('henan-museum',                'art'                   ),
    ('henan-museum',                'indoor'                ),
    ('hunan-museum',                'art'                   ),
    ('hunan-museum',                'indoor'                ),
    ('jinsha-site-museum',          'art'                   ),
    ('jinsha-site-museum',          'indoor'                ),
    ('jinsha-site-museum',          'ancient-civilization'  ),
    ('guangdong-museum',            'art'                   ),
    ('guangdong-museum',            'indoor'                ),
    ('guangdong-museum',            'city-view'             ),
    ('china-science-technology-museum', 'family'                ),
    ('china-science-technology-museum', 'indoor'                ),
    ('guangzhou-chimelong',         'amusement'             ),
    ('guangzhou-chimelong',         'family'                ),
    ('guangzhou-chimelong',         'must-see'              ),
    ('guangzhou-chimelong',         'wildlife'              ),
    ('happy-valley-beijing',        'amusement'             ),
    ('happy-valley-beijing',        'family'                ),
    ('happy-valley-beijing',        'night-view'            ),
    ('shanghai-haichang-park',      'amusement'             ),
    ('shanghai-haichang-park',      'family'                ),
    ('shanghai-haichang-park',      'wildlife'              ),
    ('happy-valley-shenzhen',       'amusement'             ),
    ('happy-valley-shenzhen',       'family'                ),
    ('happy-valley-shenzhen',       'night-view'            ),
    ('happy-valley-wuhan',          'amusement'             ),
    ('happy-valley-wuhan',          'family'                ),
    ('happy-valley-chengdu',        'amusement'             ),
    ('happy-valley-chengdu',        'family'                ),
    ('happy-valley-chongqing',      'amusement'             ),
    ('happy-valley-chongqing',      'family'                ),
    ('happy-valley-chongqing',      'indoor'                ),
    ('hongkong-disneyland',         'amusement'             ),
    ('hongkong-disneyland',         'family'                ),
    ('hongkong-disneyland',         'must-see'              ),
    ('hongkong-disneyland',         'night-view'            ),
    ('shanghai-tower',              'city-view'             ),
    ('shanghai-tower',              'architecture'          ),
    ('shanghai-tower',              'night-view'            ),
    ('shanghai-tower',              'must-see'              ),
    ('citic-tower',                 'city-view'             ),
    ('citic-tower',                 'architecture'          ),
    ('citic-tower',                 'night-view'            ),
    ('ping-an-finance-center',      'city-view'             ),
    ('ping-an-finance-center',      'architecture'          ),
    ('ping-an-finance-center',      'night-view'            ),
    ('hongya-cave',                 'night-view'            ),
    ('hongya-cave',                 'photography'           ),
    ('hongya-cave',                 'architecture'          ),
    ('yellow-crane-tower',          'ancient-architecture'  ),
    ('yellow-crane-tower',          'city-view'             ),
    ('yellow-crane-tower',          'must-see'              ),
    ('tianjin-eye',                 'night-view'            ),
    ('tianjin-eye',                 'city-view'             ),
    ('tianjin-eye',                 'photography'           ),
    ('xian-bell-tower',             'ancient-architecture'  ),
    ('xian-bell-tower',             'night-view'            ),
    ('xian-bell-tower',             'photography'           ),
    ('macau-tower',                 'city-view'             ),
    ('macau-tower',                 'photography'           ),
    ('macau-tower',                 'night-view'            ),
    ('shenyang-imperial-palace',        'world-heritage'        ),
    ('shenyang-imperial-palace',        'ancient-architecture'  ),
    ('shenyang-imperial-palace',        'must-see'              ),
    ('palace-museum-of-manchukuo',      'indoor'                ),
    ('palace-museum-of-manchukuo',      'architecture'          ),
    ('harbin-saint-sophia-cathedral',   'architecture'          ),
    ('harbin-saint-sophia-cathedral',   'night-view'            ),
    ('harbin-saint-sophia-cathedral',   'photography'           ),
    ('inner-mongolia-museum',           'indoor'                ),
    ('inner-mongolia-museum',           'family'                ),
    ('shanxi-museum',                   'art'                   ),
    ('shanxi-museum',                   'indoor'                ),
    ('shanxi-museum',                   'must-see'              ),
    ('hebei-museum',                    'art'                   ),
    ('hebei-museum',                    'indoor'                ),
    ('zhaozhou-bridge',                 'ancient-architecture'  ),
    ('zhaozhou-bridge',                 'architecture'          ),
    ('shandong-museum',                 'art'                   ),
    ('shandong-museum',                 'indoor'                ),
    ('baotu-spring',                    'park'                  ),
    ('baotu-spring',                    'family'                ),
    ('baotu-spring',                    'photography'           ),
    ('zhanqiao-pier',                   'city-view'             ),
    ('zhanqiao-pier',                   'photography'           ),
    ('zhanqiao-pier',                   'sunset'                ),
    ('anhui-museum',                    'art'                   ),
    ('anhui-museum',                    'indoor'                ),
    ('tengwang-pavilion',               'ancient-architecture'  ),
    ('tengwang-pavilion',               'city-view'             ),
    ('tengwang-pavilion',               'night-view'            ),
    ('tengwang-pavilion',               'must-see'              ),
    ('three-lanes-seven-alleys',        'ancient-architecture'  ),
    ('three-lanes-seven-alleys',        'photography'           ),
    ('three-lanes-seven-alleys',        'must-see'              ),
    ('gulangyu-island',                 'world-heritage'        ),
    ('gulangyu-island',                 'island'                ),
    ('gulangyu-island',                 'architecture'          ),
    ('gulangyu-island',                 'photography'           ),
    ('stone-forest',                    'world-heritage'        ),
    ('stone-forest',                    'photography'           ),
    ('stone-forest',                    'hiking'                ),
    ('jiaxiu-pavilion',                 'ancient-architecture'  ),
    ('jiaxiu-pavilion',                 'night-view'            ),
    ('jiaxiu-pavilion',                 'city-view'             ),
    ('guangxi-museum-of-nationalities', 'indoor'                ),
    ('guangxi-museum-of-nationalities', 'family'                ),
    ('guangxi-museum-of-nationalities', 'art'                   ),
    ('gansu-provincial-museum',         'art'                   ),
    ('gansu-provincial-museum',         'indoor'                ),
    ('gansu-provincial-museum',         'must-see'              ),
    ('western-xia-tombs',               'ruins'                 ),
    ('western-xia-tombs',               'ancient-civilization'  ),
    ('western-xia-tombs',               'desert'                ),
    ('western-xia-tombs',               'photography'           ),
    ('kumbum-monastery',                'ancient-architecture'  ),
    ('kumbum-monastery',                'art'                   ),
    ('kumbum-monastery',                'must-see'              ),
    ('xinjiang-regional-museum',        'indoor'                ),
    ('xinjiang-regional-museum',        'art'                   ),
    ('tianyi-pavilion',                 'garden'                ),
    ('tianyi-pavilion',                 'ancient-architecture'  ),
    ('tianyi-pavilion',                 'art'                   ),
    ('yandang-mountain',                'hiking'                ),
    ('yandang-mountain',                'sunrise'               ),
    ('yandang-mountain',                'photography'           ),
    ('yuantouzhu',                      'lake'                  ),
    ('yuantouzhu',                      'park'                  ),
    ('yuantouzhu',                      'family'                ),
    ('foshan-ancestral-temple',         'ancient-architecture'  ),
    ('foshan-ancestral-temple',         'art'                   ),
    ('foshan-ancestral-temple',         'family'                ),
    ('quanzhou-kaiyuan-temple',         'world-heritage'        ),
    ('quanzhou-kaiyuan-temple',         'ancient-architecture'  ),
    ('quanzhou-kaiyuan-temple',         'art'                   )
) AS m(attraction_slug, tag_slug)
JOIN attraction a ON a.slug = m.attraction_slug
JOIN tag t        ON t.slug = m.tag_slug
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------- 旅游方案
--
-- 「怎么玩」独立于「是什么」: 一个景点可以有多个方案, 方案由有序步骤组成,
-- 步骤按天分组(day_no)。当前 140 个景点各一个方案(中国境内 100 + 境外 40)。
-- 步骤先按 source 认领后删除再重建, 与景点标签同一套做法, 所以删步骤也能同步。
-- 内容是本仓库自写的行程建议, 不是官方或旅行社线路。

INSERT INTO attraction_plan (
    attraction_id, slug, title, days, budget_level, best_for, summary,
    source, license, source_url
) VALUES
(
    (SELECT id FROM attraction WHERE slug = 'angkor-wat'),
    'angkor-wat-plan',
    '吴哥三日：小圈 · 大圈 · 外圈',
    3, 'mid', '第一次到吴哥、想把主要寺庙看全的游客',
    '按通行的小圈、大圈、外圈三段安排，第一天看核心与日出，第二天补大圈与日落，第三天走较远的女王宫与崩密列。全程以包车为主，中午回城避热。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'taj-mahal'),
    'taj-mahal-plan',
    '泰姬陵半日：赶早避开人流',
    1, 'mid', '把阿格拉作为一日游一站、时间有限的游客',
    '泰姬陵日出开门，人最少、光线也最柔。半日足够看完主体与两座配楼，如果还有时间，下午可补阿格拉堡。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'mount-fuji'),
    'mount-fuji-plan',
    '富士山一日：不登山也能看全',
    1, 'mid', '不想登山、只想看山的游客',
    '以河口湖一带为据点，上午看湖面倒影，中午转到大石公园与忍野八海，傍晚回到湖畔看落日侧影。全程公交与周游巴士可以覆盖。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'petra'),
    'petra-plan',
    '佩特拉一日：从蛇道走到代尔修道院',
    1, 'mid', '体力尚可、想一天看完主要建筑的游客',
    '园区很大且几乎全在户外，按「蛇道—卡兹尼—岩墓群—代尔修道院」由近及远推进，把最耗体力的修道院放在午后，最后原路返回。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'borobudur'),
    'borobudur-plan',
    '婆罗浮屠半日：从日出到顶层',
    1, 'mid', '想看日出又不想太赶的游客',
    '日出票需提前订，天亮前登顶占位；日出后先顺时针绕回廊看浮雕，最后上圆形顶层。半日足够，下午可顺路去附近的普兰巴南。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hagia-sophia'),
    'hagia-sophia-plan',
    '圣索菲亚半日：与老城连成一线',
    1, 'mid', '在伊斯坦布尔停留两三天、走经典路线的游客',
    '上午先看圣索菲亚，再步行到地下水宫与赛马场广场，下午过桥看博斯普鲁斯，傍晚到加拉塔桥边看落日。各点之间步行可达。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'ha-long-bay'),
    'ha-long-bay-plan',
    '下龙湾两日：船上过夜',
    2, 'mid', '想看日出日落、不想当天往返的游客',
    '白天登岛与进洞，傍晚在锚地过夜，次日清晨看日出后返港。过夜船比一日游能看到早晚两个最好的时段。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'kinkakuji'),
    'kinkakuji-plan',
    '金阁寺半日：串起北山一线',
    1, 'low', '在京都停留两三天、按区域安排路线的游客',
    '金阁寺本身一小时上下就能走完，连同龙安寺、仁和寺合成北山一线，半天到一天刚好。坐市内巴士串联，不必自驾。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'gyeongbokgung'),
    'gyeongbokgung-plan',
    '景福宫半日：宫殿加国立古宫博物馆',
    1, 'low', '在首尔停留两三天、对宫殿建筑感兴趣的游客',
    '上午看换岗仪式再进宫，沿中轴与东路走到庆会楼，出宫后进国立古宫博物馆，下午转去北村或三清洞。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'eiffel-tower'),
    'eiffel-tower-plan',
    '铁塔半日：登塔加塞纳河沿线',
    1, 'mid', '第一次到巴黎、想在半天里看铁塔与塞纳河核心段',
    '傍晚前登塔看白天全景，下来后在战神广场或对岸夏乐宫看整点灯光，再沿塞纳河散步。登塔建议提前订时段票，现场排队往往很久。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'colosseum'),
    'colosseum-plan',
    '斗兽场半日：与古罗马广场连游',
    1, 'mid', '想一次看完古罗马核心遗迹的游客',
    '斗兽场的票通常与古罗马广场、帕拉蒂尼山同票，按「斗兽场—广场—帕拉蒂尼山」顺序走，半天刚好。三个点之间步行数分钟。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'sagrada-familia'),
    'sagrada-familia-plan',
    '圣家堂半日：教堂加高迪街区',
    1, 'mid', '对建筑与设计感兴趣的游客',
    '预约上午进场看彩窗光线，午后转到格拉西亚大道看巴特罗之家与米拉之家外立面，傍晚到桂尔公园看马赛克与城市远景。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'versailles'),
    'versailles-plan',
    '凡尔赛一日：宫殿加园林',
    1, 'mid', '愿意花一整天、把宫殿和园林都走一遍的游客',
    '上午跟着指定路线看完宫殿主体与镜厅，午后进园林，先坐小火车到远处再走回来，最后看喷泉表演（开放日）。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'neuschwanstein'),
    'neuschwanstein-plan',
    '新天鹅堡一日：城堡加玛丽安桥',
    1, 'mid', '自驾或从慕尼黑当日往返的游客',
    '先到售票处取预约时段的票，再上玛丽安桥看城堡全景，按票面时段入堡参观，之后下山到旧天鹅堡与湖边的霍恩施万高。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'acropolis'),
    'acropolis-plan',
    '卫城半日：从山门走到博物馆',
    1, 'mid', '在雅典停留一两天、想系统看古典建筑的游客',
    '尽早从主入口上山，先看山门与帕特农，再看伊瑞克提翁，下山后进卫城博物馆看原件，最后到普拉卡老区吃饭。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'santorini'),
    'santorini-plan',
    '圣托里尼两日：费拉走到伊亚',
    2, 'high', '想看悬崖村落与爱琴海日落的游客',
    '第一天走费拉到伊亚的悬崖步道，傍晚在伊亚看日落；第二天出海看破火山口与温泉，下午回费拉看另一侧的落日。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'stonehenge'),
    'stonehenge-plan',
    '巨石阵半日：连看埃夫伯里',
    1, 'mid', '自驾、对史前遗址感兴趣的游客',
    '巨石阵一两小时就能看完，周边的埃夫伯里石圈与西肯尼特长冢同属一处世界遗产，串成半日到一天更值得。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'pompeii'),
    'pompeii-plan',
    '庞贝一日：按区域走完主要街区',
    1, 'mid', '体力尚可、想认真看遗址而不是走马观花的游客',
    '从海洋门或广场门进入，先看广场与神庙一带，再依次走剧场区、浴场与民居区，最后到悲剧诗人之家与遇难者石膏像展区。全程日晒严重。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'louvre'),
    'louvre-plan',
    '卢浮宫一日：先重点后补遗',
    1, 'mid', '第一次到访、想看完重点又不想走散的游客',
    '上午按德农馆的意大利绘画与古典雕塑走一轮，午后转叙利馆看古埃及与近东，最后按体力决定是否补黎塞留馆。三个馆在地下相通。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'jungfrau'),
    'jungfrau-plan',
    '少女峰一日：从格林德瓦上、劳特布龙嫩下',
    1, 'high', '想看冰川雪峰、愿意为此花一天和较高交通费的游客',
    '上山走格林德瓦一侧，途中在换乘站停留看冰川；山顶看完平台与冰宫后，从劳特布龙嫩一侧下山，两侧风景不重复。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'charles-bridge'),
    'charles-bridge-plan',
    '查理大桥半日：两侧桥塔加老城',
    1, 'low', '在布拉格停留两三天、想按老城步行范围游玩的游客',
    '清早过桥避开人流，上午登老城桥塔俯瞰，午后在老城广场一带看天文钟与泰恩教堂，傍晚回桥上等灯光。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'pyramids-of-giza'),
    'pyramids-of-giza-plan',
    '吉萨半日：三塔加狮身人面像',
    1, 'mid', '在开罗停留、想半天看完吉萨高原的游客',
    '从北侧的胡夫金字塔开始向南走，经哈夫拉与孟卡拉，再下到谷庙与狮身人面像，最后到高原西侧的全景机位。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'victoria-falls'),
    'victoria-falls-plan',
    '维多利亚瀑布一日：步道加河上游船',
    1, 'high', '想一次看完瀑布与赞比西河生态的游客',
    '上午走雨林步道逐段看瀑布，午后到河上游船，傍晚在河面看日落与河马、鳄鱼等活动。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'serengeti'),
    'serengeti-plan',
    '塞伦盖蒂两日：从中央草原到北部',
    2, 'high', '愿意为看野生动物安排至少两天园内行程的游客',
    '第一天从园区南门进，沿塞罗内拉河谷一带找兽群；第二天清晨做一次日出巡游后向北行驶，按季节追迁徙群体。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'marrakech-medina'),
    'marrakech-medina-plan',
    '马拉喀什老城一日：白天看建筑、入夜回广场',
    1, 'low', '喜欢在街巷里走路、不赶点的游客',
    '上午看库图比亚清真寺外观与萨阿德陵墓，午后进巴西亚宫与手工艺市集，傍晚回广场看演出与夜市。巷弄容易迷路，按主要地标定位。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'table-mountain'),
    'table-mountain-plan',
    '桌山半日：缆车上、步道下',
    1, 'mid', '想省力登顶又想走一段步道的游客',
    '上午乘缆车上顶，沿顶层环线走一圈；午后沿普拉特克利普峡谷步道下山，回市区正好赶傍晚。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'grand-canyon'),
    'grand-canyon-plan',
    '大峡谷一日：南缘看日出到日落',
    1, 'mid', '自驾、想在南缘看完主要观景点的游客',
    '清晨在东侧观景点看日出，沿南缘主路向西逐个停靠观景点，午后走一段光明天使步道下到第一个休息点后原路返回，傍晚在西侧看日落。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'statue-of-liberty'),
    'statue-of-liberty-plan',
    '自由女神半日：渡轮加埃利斯岛',
    1, 'mid', '第一次到纽约、想走完经典半日路线的游客',
    '从炮台公园乘渡轮先到自由岛，绕岛看基座与外观，再乘同一航线到埃利斯岛看移民博物馆，最后返回曼哈顿。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'yellowstone'),
    'yellowstone-plan',
    '黄石两日：先地热、后峡谷与湖区',
    2, 'mid', '自驾、想覆盖园区主要区域的游客',
    '第一天走南环，看间歇泉盆地与热泉；第二天走北环，看峡谷、瀑布与湖区，途中留意路边的野牛群。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'chichen-itza'),
    'chichen-itza-plan',
    '奇琴伊察半日：趁早走完核心建筑',
    1, 'mid', '从坎昆或梅里达当日往返的游客',
    '开门即入场，先看中央金字塔，再依次走大球场、武士神庙与天文台，两三个小时足够。午后可顺路去附近的天然井。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'banff'),
    'banff-plan',
    '班夫两日：路易斯湖与冰原大道',
    2, 'mid', '自驾、想看湖景与冰川的游客',
    '第一天在路易斯湖一带走湖岸步道并看梦莲湖；第二天沿冰原大道北上，看冰川与峡谷瀑布后返回。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'niagara-falls'),
    'niagara-falls-plan',
    '尼亚加拉半日：加拿大侧看正面',
    1, 'mid', '想半天看完瀑布正面与近距体验的游客',
    '沿加拿大侧河岸步道自上游走到马蹄瀑布正面，下午乘观光船靠近瀑布底部，入夜后看灯光与烟花（开放日）。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'machu-picchu'),
    'machu-picchu-plan',
    '马丘比丘一日：从库斯科乘火车往返',
    1, 'high', '按一日往返、不走印加古道的游客',
    '从库斯科或欧雁台乘火车到热水镇，转巴士上山；先到高处平台俯瞰全景，再按园区指定单向路线走完主要建筑，午后原路返回。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'christ-the-redeemer'),
    'christ-the-redeemer-plan',
    '基督像半日：小火车上山加城中天际线',
    1, 'mid', '想半天看完塑像并俯瞰里约的游客',
    '乘齿轨小火车上山看塑像与城市全景，下山后到面包山或科帕卡巴纳海滩，傍晚在海滩看落日。各点之间公交或打车都可。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'iguazu-falls'),
    'iguazu-falls-plan',
    '伊瓜苏一日：阿根廷侧步道为主',
    1, 'mid', '想走完整步道、近距离看瀑布的游客',
    '阿根廷侧步道层次更丰富，先走上层步道看各段瀑布的连续关系，再走下层步道接近水雾，最后乘园内列车到魔鬼咽喉栈道。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'galapagos'),
    'galapagos-plan',
    '加拉帕戈斯四日：跳岛加近岸浮潜',
    4, 'high', '愿意为野生动物安排多日行程的游客',
    '以阿约拉港为落脚点，按天安排跳岛一日游，覆盖圣克鲁斯高地、近岸小岛与浮潜点，最后一天留缓冲。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'easter-island'),
    'easter-island-plan',
    '复活节岛两日：遗址与海岸串成环线',
    2, 'high', '打算自驾或包车、把主要遗址走一遍的游客',
    '第一天走东海岸，看采石场与最大的石台群；第二天走西侧与北侧，看另一组祭台与火山口，傍晚在海岸看落日。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'sydney-opera-house'),
    'sydney-opera-house-plan',
    '歌剧院半日：导览加环形码头',
    1, 'mid', '在悉尼停留两三天、想看清建筑与港口的游客',
    '上午参加馆内导览看厅室结构，午后沿半岛步道走到植物园一侧回看壳体，傍晚在环形码头看夜景。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'great-barrier-reef'),
    'great-barrier-reef-plan',
    '大堡礁一日：外礁平台浮潜',
    1, 'high', '想一天内看到外礁珊瑚与鱼群的游客',
    '从凯恩斯码头出海，前往外礁的浮潜平台，上午先浮潜熟悉水况，午后可选择深潜或乘半潜艇看礁体，傍晚返航。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'milford-sound'),
    'milford-sound-plan',
    '米尔福德峡湾一日：从蒂阿瑙进峡湾',
    1, 'mid', '自驾或参加一日团、当天往返的游客',
    '清晨从蒂阿瑙出发，沿公路经镜湖与荷马隧道进峡湾，中午乘船游峡湾看崖壁与瀑布，午后原路返回。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'west-lake'),
    'west-lake-plan',
    '西湖一日：环湖主景串成一圈',
    1, 'free', '第一次到杭州、想一天看完湖区主景的人',
    '从断桥起步沿白堤进孤山，午后走苏堤，傍晚在雷峰塔一带收尾。湖区大部分区域全天开放且不收费，靠步行与骑行相接。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'huangshan'),
    'huangshan-plan',
    '黄山两日：前山上、后山下',
    2, 'mid', '想看日出、能接受山上住宿的游客',
    '第一天走前山到光明顶，在山上住一晚，第二天看日出后由后山下山。前山（慈光阁方向）与后山（云谷寺方向）各有一条主线路。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'jiuzhaigou'),
    'jiuzhaigou-plan',
    '九寨沟一日：三条沟按顺序走完',
    1, 'mid', '只想一天看水色、不打算在沟内住宿的人',
    '景区呈 Y 字形，靠观光车在沟内接驳。先上树正沟，再进日则沟看五花海与瀑布，最后到则查洼沟的长海与五彩池。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'zhangjiajie'),
    'zhangjiajie-plan',
    '张家界两日：金鞭溪、袁家界、天子山',
    2, 'mid', '想看峰林全貌、能走一段路的游客',
    '第一天从森林公园入口走金鞭溪，再上百龙天梯到袁家界看峰林；第二天走天子山与十里画廊。各片区之间靠缆车与环保车连接。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'lijiang-old-town'),
    'lijiang-old-town-plan',
    '丽江古城一日：四方街与木府',
    1, 'low', '到丽江第一天、想先熟悉古城的人',
    '以四方街为中心，顺水走街巷，上午看木府与万古楼，下午出城北到黑龙潭。古城内为石板路，行李多时用客栈接送。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'pingyao'),
    'pingyao-plan',
    '平遥一日：城墙、票号与县衙',
    1, 'low', '对晋商与明清县城格局感兴趣的人',
    '上午上城墙看清街巷走向，再看日昇昌票号与南大街，下午走县衙与文庙。进出古城不收费，参观各景点通常需要通票。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'yungang-grottoes'),
    'yungang-grottoes-plan',
    '云冈石窟半日：先看五窟六窟再到大佛',
    1, 'low', '对北魏造像与石窟艺术感兴趣的游客',
    '主要洞窟编号至 45 窟，按东向西的顺序看，重点是第 5、6 窟的整体雕刻与第 20 窟的露天大佛。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'longmen-grottoes'),
    'longmen-grottoes-plan',
    '龙门石窟半日：西山为主，傍晚看夜游',
    1, 'low', '想看唐代造像、时间只有半天的游客',
    '西山窟龛最集中，奉先寺是重点；过伊河到东山可回望西山全景，另可看香山寺与白园。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'mogao-caves'),
    'mogao-caves-plan',
    '莫高窟半日：先数字展示中心，再进窟',
    1, 'mid', '第一次到敦煌、想看懂壁画内容的人',
    '参观采用预约制，由讲解员带队分组进入，每个团队当天开放的洞窟不同。先看数字展示中心的影片，再进窟理解更完整。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'potala-palace'),
    'potala-palace-plan',
    '布达拉宫半日：按预约时段上红宫',
    1, 'mid', '初到拉萨、已适应海拔的游客',
    '参观按预约时段分批进入，先走白宫再看红宫，出宫后到山后的宗角禄康一带收尾。宫内步行距离长、台阶多。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'mount-emei'),
    'mount-emei-plan',
    '峨眉山两日：观光车加索道上金顶',
    2, 'mid', '想看金顶日出、不想全程徒步的人',
    '山脚报国寺一带海拔约 500 米，与金顶高差悬殊，通常以观光车、索道与短程徒步组合上山，在山上住一晚等日出。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'leshan-buddha'),
    'leshan-buddha-plan',
    '乐山大佛半日：栈道或乘船二选一',
    1, 'low', '把乐山当作半日站、时间有限的游客',
    '大佛面向岷江、大渡河与青衣江的汇流处。陆路沿九曲栈道从佛头走到佛脚，看细节但排队久；乘船看整体比例，用时短。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'wudang-mountain'),
    'wudang-mountain-plan',
    '武当山一日：太子坡上到金顶',
    1, 'mid', '想看明代道教建筑群、体力中等的游客',
    '主要建筑沿中轴线由低到高：太子坡、紫霄宫、南岩宫一路向上，金顶为终点。山体高差大、景点分散，通常需要一整天。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'taishan'),
    'taishan-plan',
    '泰山一日：红门上山、索道或步行下山',
    1, 'mid', '想把登山主路走完、体力尚可的游客',
    '登山主路自红门经中天门、十八盘至南天门，全程石阶约七千级；也可由天外村乘中巴至中天门再步行或乘索道。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hongcun'),
    'hongcun-plan',
    '宏村半日：水圳、月沼与南湖',
    1, 'low', '想看徽派民居与水系格局的游客',
    '村落由人工水系贯穿，水从村北引入，经月沼、南湖流出。上午看月沼与宅院，午后沿南湖走回村口。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'ming-xiaoling'),
    'ming-xiaoling-plan',
    '明孝陵半日：石象路进、方城明楼出',
    1, 'low', '秋冬季到南京、想顺走钟山一线的人',
    '神道自下马坊起，经石象路、翁仲路折向陵宫。石象路两侧的石兽与秋色是常见取景处，可与中山陵、灵谷寺一并安排。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'temple-of-heaven'),
    'temple-of-heaven-plan',
    '天坛半日：圜丘到祈年殿',
    1, 'low', '想看清祭天礼制布局的游客',
    '主要建筑沿南北轴线分布，圜丘坛在南用于祭天，祈年殿在北用于祈谷，两者之间由丹陛桥相连。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'summer-palace'),
    'summer-palace-plan',
    '颐和园一日：长廊、佛香阁、西堤',
    1, 'low', '想完整走一圈昆明湖的游客',
    '全园面积约 290 公顷，水面约占四分之三。由东宫门入最方便，上午走长廊与万寿山中轴，下午绕到十七孔桥与西堤。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'palace-museum'),
    'palace-museum-plan',
    '故宫半日：中轴线加一个专题馆',
    1, 'low', '第一次到故宫、时间只有半天的游客',
    '由午门入、神武门出，单向通行。先走中轴线三大殿与后三宫，剩下的时间只挑一个专题馆细看。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'terracotta-army'),
    'terracotta-army-plan',
    '兵马俑半日：一号坑到三号坑',
    1, 'low', '把兵马俑与华清宫放在同一天的游客',
    '已发掘三个俑坑，按一号、三号、二号坑的顺序看，最后看文物陈列。位于临潼一线，建议上午先看兵马俑。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'huaqing-palace'),
    'huaqing-palace-plan',
    '华清宫半日：汤池遗址加骊山',
    1, 'low', '与兵马俑同日安排、想加一处人文点的游客',
    '园内保留唐代汤池遗址与部分建筑基址，另有西安事变发生地五间厅；骊山可乘索道上山。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'huashan'),
    'huashan-plan',
    '华山一日：西峰上、北峰下',
    1, 'mid', '想走完主要峰头、不想通宵爬山的游客',
    '由东、西、南、北、中五峰组成，常见走法是西峰上、北峰下，或反之。险要路段需单独的安全装备与排队。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'badaling-great-wall'),
    'badaling-great-wall-plan',
    '八达岭半日：北段到北八楼',
    1, 'low', '第一次到长城、想走经典段落的游客',
    '关城与南北两侧城墙沿山脊延伸。北段坡度较陡，八达岭至北八楼是多数人走的路线；南段人流相对少。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'wuzhen'),
    'wuzhen-plan',
    '乌镇两日：白天东栅、入夜西栅',
    2, 'mid', '想住一晚看水乡夜景的游客',
    '东栅保留较多原住民生活场景，白天热闹；西栅由统一运营，入夜后河道、石桥与灯影连成一片。东西栅之间有免费班车。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'zhouzhuang'),
    'zhouzhuang-plan',
    '周庄一日：双桥与沈厅张厅',
    1, 'low', '从苏州或上海出发的一日水乡行程',
    '镇内河道呈井字形，居民依水而居。上午看双桥与沿河民居，再看沈厅、张厅两处明清宅院，午后坐一趟摇橹船。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'xitang'),
    'xitang-plan',
    '西塘一日：廊棚与石桥',
    1, 'low', '想找一处可以慢慢走的水乡的游客',
    '河边多建有带顶棚的廊棚，总长近千米，雨天也方便步行。石桥密度较高，入夜后沿河灯笼亮起。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'changbai-mountain'),
    'changbai-mountain-plan',
    '长白山两日：北坡上天池，再看瀑布与森林',
    2, 'mid', '想看天池、能接受天气不确定性的游客',
    '北坡设施最完备，西坡台阶最多。第一天走北坡上山看天池，顺路看长白瀑布与聚龙温泉，第二天走地下森林或换坡。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'kanas'),
    'kanas-plan',
    '喀纳斯三日：湖区加禾木村',
    3, 'high', '秋季到北疆、想看湖与村落的人',
    '湖区由喀纳斯湖与卧龙湾、月亮湾、神仙湾串联，靠区间车接驳；周边图瓦人村落常与湖区一并安排。往返通常需要三到四天。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'yinxu'),
    'yinxu-plan',
    '殷墟半日：宫殿宗庙区加王陵区',
    1, 'low', '对甲骨文与商代历史感兴趣的游客',
    '遗址位于安阳市西北的洹河两岸，包括宫殿宗庙区、王陵区与作坊遗址。先看宫殿区与妇好墓，再乘车到洹河北岸的王陵区。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'orange-isle'),
    'orange-isle-plan',
    '橘子洲半日：洲头到洲尾',
    1, 'low', '在长沙停留一两天、想走江心洲的游客',
    '洲长约五公里，地铁可直达洲上。从洲头看江面与雕像，再乘观光小火车或步行到洲尾，可顺路连岳麓山一线。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hangzhou-songcheng'),
    'hangzhou-songcheng-plan',
    '宋城半日：市井街区加主演出',
    1, 'mid', '带家人同行、想看一场大型演出的游客',
    '园区按宋代街市复建，街上有定时演出与手作店铺，核心是室内大型歌舞演出，需按场次入场。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'daocheng-yading'),
    'daocheng-yading-plan',
    '稻城亚丁两日：短线看仙乃日，长线走牛奶海',
    2, 'high', '海拔适应良好、能走长距离徒步的人',
    '景区入口在香格里拉镇，需换乘观光车再步行或骑马。第一天走短线看仙乃日，第二天走长线到牛奶海与五色海。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'oriental-pearl-tower'),
    'oriental-pearl-tower-plan',
    '东方明珠半日：登塔加陆家嘴天桥',
    1, 'mid', '想同时看外滩与陆家嘴的游客',
    '观光层分布在下球体、上球体与太空舱等位置，夜景比白天更值得上。塔下即为陆家嘴环形天桥，可与周边高楼串联。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'liangzhu'),
    'liangzhu-plan',
    '良渚一日：博物院加遗址公园',
    1, 'low', '对史前文明与考古感兴趣的游客',
    '先看良渚博物院，再进遗址公园看古城与水利系统。博物院在瓶窑镇另址，与遗址公园之间需要路程。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'fenghuang'),
    'fenghuang-plan',
    '凤凰古城一日：沱江两岸',
    1, 'low', '想在湘西停留一天、看江边吊脚楼的游客',
    '沱江穿城而过，虹桥、跳岩、万名塔沿江一线分布。白天走石板街，入夜后看江边灯影与吊脚楼倒影。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'sanxingdui-museum'),
    'sanxingdui-museum-plan',
    '三星堆半日：博物馆加遗址区',
    1, 'low', '对古蜀文明与青铜器感兴趣的游客',
    '新馆开放后展陈面积大幅增加，青铜大立人、青铜神树、金杖等依次陈列；遗址区与博物馆相邻，可一并参观。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shaanxi-history-museum'),
    'shaanxi-history-museum-plan',
    '陕历博半日：按年代走主线',
    1, 'low', '想一次看清周秦汉唐脉络的游客',
    '基本陈列按史前、周、秦、汉、魏晋南北朝、隋唐、宋元明清铺开，唐代部分器物最集中。另有专题馆需单独购票。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'national-museum'),
    'national-museum-plan',
    '国博半日：古代中国基本陈列',
    1, 'free', '在北京停留、想半天看完通史的游客',
    '「古代中国」基本陈列按年代铺开，从旧石器时代一直到清末，看完约需三小时；剩余时间挑一个当期专题展。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shanghai-museum'),
    'shanghai-museum-plan',
    '上博半日：青铜与陶瓷为主线',
    1, 'low', '对青铜器与陶瓷感兴趣的游客',
    '人民广场馆外形取「天圆地方」之意，青铜、陶瓷、书法、绘画四个门类都有分量。半天按青铜、陶瓷两馆为主线。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'suzhou-museum'),
    'suzhou-museum-plan',
    '苏博半日：新馆建筑加忠王府',
    1, 'free', '想看建筑与吴地文物、顺便连拙政园的人',
    '新馆以几何体量、白墙灰瓦与水院表达江南意趣，建筑本身即看点；忠王府部分与新馆相连，保留原有格局。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'canton-tower'),
    'canton-tower-plan',
    '广州塔半日：登塔加珠江夜游',
    1, 'mid', '想看广州夜景、把登塔与夜游并在一起的人',
    '塔身中部收细，得名「小蛮腰」。傍晚登塔看日落与亮灯，入夜后在塔下码头坐珠江夜游。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'lingyin-temple'),
    'lingyin-temple-plan',
    '灵隐半日：先飞来峰，再进寺',
    1, 'low', '在西湖附近、想加一处古寺与石刻的人',
    '寺院位于飞来峰与北高峰之间，中轴线上有天王殿、大雄宝殿、药师殿、藏经楼；对面飞来峰崖壁上有五代至宋元的石刻造像。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'the-bund'),
    'the-bund-plan',
    '外滩半日：从外白渡桥向南',
    1, 'free', '到上海当天晚上想先看城市天际线的人',
    '沿江步道全长约 1.5 公里，一侧是二十世纪初的各国风格建筑，另一侧隔江可见陆家嘴。日落后亮灯，从外白渡桥向南走视角较完整。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hulunbuir'),
    'hulunbuir-plan',
    '呼伦贝尔三日：海拉尔到额尔古纳一线',
    3, 'high', '夏季自驾或包车走草原环线的游客',
    '草原面积辽阔，公共交通不便，通常以自驾或包车方式游览。海拉尔、额尔古纳、恩和、室韦一线是常见线路。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shanghai-disney'),
    'shanghai-disney-plan',
    '迪士尼一日：开园前排队，闭园前看烟花',
    1, 'high', '带小孩同行、想一天玩完主要园区的家庭',
    '开园前排队入园可省不少时间，先冲热门项目，午后按当日时间表看演出与巡游，闭园前看烟花。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'chimelong-ocean-kingdom'),
    'chimelong-ocean-kingdom-plan',
    '珠海长隆一日：鲸鲨馆加剧场',
    1, 'high', '带小孩同行、以海洋动物展示为主的行程',
    '园区分为海洋大街、海豚湾、雨林飞翔、海洋奇观、极地探险等区域，鲸鲨馆的巨型展缸是主要看点，傍晚有花车巡游与焰火。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'universal-beijing'),
    'universal-beijing-plan',
    '环球影城一日：先热门，后巡游',
    1, 'high', '想把哈利·波特区与几个大项目都玩到的游客',
    '园区由主题公园、城市大道与度假酒店组成。热门项目排队时间长，开园后先去哈利·波特与变形金刚片区，夜间到城市大道收尾。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'window-of-the-world'),
    'window-of-the-world-plan',
    '世界之窗一日：按洲分区走',
    1, 'mid', '带小孩同行、想一天看各地地标的游客',
    '园内按亚洲、欧洲、美洲、非洲、大洋洲等区域布置微缩景观，靠步行与园内交通结合游览，晚间有灯光秀与巡游。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'qinghai-lake'),
    'qinghai-lake-plan',
    '青海湖两日：环湖自驾或骑行',
    2, 'mid', '夏季到青海、想走环湖公路的游客',
    '环湖公路全长约 360 公里，常见走法为自驾或骑行环湖，两天左右。夏季湖畔油菜花与湖水相接是主要拍摄场景。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'lijiang-river'),
    'lijiang-river-plan',
    '漓江一日：桂林到阳朔的水路',
    1, 'mid', '想在一天里走完桂林到阳朔水路的游客',
    '游览方式以竹筏与游船为主，全程水路通常四到五小时。兴坪一带是二十元人民币背面图案的取景处，也是常见的下船点。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shanghai-natural-history-museum'),
    'shanghai-natural-history-museum-plan',
    '上海自然博物馆半日：从生命长河走到底',
    1, 'low', '带孩子看展、只有半天的游客',
    '馆内展线是单向的，从上层逐层往下走最顺。重点放在生命长河与演化之道两段，其余展区按体力取舍。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'nanjing-museum'),
    'nanjing-museum-plan',
    '南京博物院半日：历史馆为主线',
    1, 'low', '想把江苏一带的文物脉络看一遍的游客',
    '六馆分散在同一片院落里，先走历史馆理清年代，再看民国馆与艺术馆。特展馆的当期展览按兴趣取舍。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hubei-museum'),
    'hubei-museum-plan',
    '湖北省博物馆半日：先看曾侯乙，再看编钟演奏',
    1, 'low', '对青铜器与先秦文物感兴趣的游客',
    '编钟、尊盘与越王勾践剑是必看的几件，按演奏场次把时间排开，剩下的展厅按体力走。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'henan-museum'),
    'henan-museum-plan',
    '河南博物院半日：按朝代往下走',
    1, 'low', '想在半天里看清中原文物脉络的游客',
    '主展馆按年代分层布置，自上而下走一遍就是一串中原通史。贾湖骨笛、莲鹤方壶、妇好鸮尊是几处常停留的展位。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hunan-museum'),
    'hunan-museum-plan',
    '湖南博物院半日：马王堆是重点',
    1, 'low', '专程来看马王堆文物的游客',
    '马王堆的陈列占据主要篇幅，帛画、素纱襌衣与漆器逐件看下来需要两小时以上，其余展厅按时间取舍。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'jinsha-site-museum'),
    'jinsha-site-museum-plan',
    '金沙遗址半日：先看现场，再看文物',
    1, 'low', '对古蜀文明与考古现场感兴趣的游客',
    '先到遗迹馆看祭祀区的原状现场，再进陈列馆看太阳神鸟金饰与金面具。两馆之间有绿地相连，全程步行。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'guangdong-museum'),
    'guangdong-museum-plan',
    '广东省博物馆半日：历史与工艺两条线',
    1, 'low', '在珠江新城一带安排半天的游客',
    '常设展以广东历史文化陈列为主，潮州木雕、端砚与历代陶瓷各有专厅。出馆后可以与周边的图书馆、大剧院连成一片。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'china-science-technology-museum'),
    'china-science-technology-museum-plan',
    '中国科技馆半日：主展厅挑重点',
    1, 'low', '带孩子体验互动展项的游客',
    '主展厅按主题分布，展项以动手操作为主，半天只能走完其中两三个主题。影院另需按场次安排时间。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'guangzhou-chimelong'),
    'guangzhou-chimelong-plan',
    '长隆两日：野生动物世界 + 欢乐世界',
    2, 'high', '带孩子、想在两天里玩两个园的游客',
    '单园面积都大，两天分别给野生动物世界与欢乐世界比较从容。两园之间有穿梭巴士，中午回酒店避热是常见的做法。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'happy-valley-beijing'),
    'happy-valley-beijing-plan',
    '北京欢乐谷一日：先热门后演艺',
    1, 'mid', '想玩大型项目的游客',
    '开园先排最热门的几项，午后转向演艺与室内项目，傍晚按体力决定是否留到夜场。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shanghai-haichang-park'),
    'shanghai-haichang-park-plan',
    '海昌海洋公园一日：按演艺场次排顺序',
    1, 'mid', '带孩子看海洋动物的游客',
    '园内演艺按场次开演，入园先看当日时间表，把几场演出定下来，剩下的时间按区域走展馆与游乐设施。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'happy-valley-shenzhen'),
    'happy-valley-shenzhen-plan',
    '深圳欢乐谷一日：华侨城同日两园取舍',
    1, 'mid', '在南山一带安排一天的游客',
    '欢乐谷与世界之窗相邻，一天通常只够一个园。园区按主题分区，上午玩大型项目，午后转向亲子区与演艺。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'happy-valley-wuhan'),
    'happy-valley-wuhan-plan',
    '武汉欢乐谷一日：主园与水公园',
    1, 'mid', '夏季到东湖一带的游客',
    '主园区与玛雅海滩水公园相邻但分别运营，一天通常选一个。夏季下午最晒，把大型项目排在上午。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'happy-valley-chengdu'),
    'happy-valley-chengdu-plan',
    '成都欢乐谷一日：上午玩项目，下午看演出',
    1, 'mid', '在成都安排一天游乐的游客',
    '园区在城西三环附近，上午人相对少，适合先玩大型项目；午后安排演艺与亲子区，晚上若有夜场可以留一会儿。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'happy-valley-chongqing'),
    'happy-valley-chongqing-plan',
    '重庆欢乐谷一日：室内外搭配',
    1, 'mid', '雨天也想安排游乐的游客',
    '礼嘉一带的主园区以大型机械项目为主，室内项目与演艺可以在雨天顶上，一天的节奏按天气调整。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hongkong-disneyland'),
    'hongkong-disneyland-plan',
    '香港迪士尼一日：全日票走完主要区域',
    1, 'high', '第一次到香港迪士尼的游客',
    '园区规模不大，一天可以把主要区域走完。上午玩项目，下午看巡游与剧场，闭园前的夜间演出是收尾。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shanghai-tower'),
    'shanghai-tower-plan',
    '上海中心大厦半日：观光层与陆家嘴',
    1, 'mid', '想看陆家嘴全景的游客',
    '观光层在高区，电梯直达，晴天时视野最好。下来后可以在陆家嘴一带把三座塔楼与滨江串起来走。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'citic-tower'),
    'citic-tower-plan',
    '国贸半日：看北京最高的一栋楼',
    1, 'low', '对城市建筑与天际线感兴趣的游客',
    '建筑以办公为主，看重的是外观与周边天际线。下午到国贸一带，走一圈看它与其他几座塔楼的关系。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'ping-an-finance-center'),
    'ping-an-finance-center-plan',
    '福田半日：从塔顶看深圳',
    1, 'mid', '想看深圳城市格局的游客',
    '观光层在高区，可以俯瞰福田中心区与香港方向。下来后到市民中心一带，把中轴线上的几处建筑连着看。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hongya-cave'),
    'hongya-cave-plan',
    '洪崖洞半日：从白天等到亮灯',
    1, 'low', '想看夜景与吊脚楼街区的游客',
    '白天先走一遍各层，弄清上下的出入口；傍晚亮灯后回到江边看整体轮廓，人流也在这时最密。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'yellow-crane-tower'),
    'yellow-crane-tower-plan',
    '黄鹤楼半日：登楼与蛇山',
    1, 'mid', '想在武汉安排半天的游客',
    '从山门进园，先到楼前看碑刻，再登楼看长江与大桥，最后沿蛇山走到另一侧的出口。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'tianjin-eye'),
    'tianjin-eye-plan',
    '天津之眼半日：傍晚到夜间',
    1, 'mid', '想看海河夜景的游客',
    '摩天轮转一圈约半小时，最佳时段是亮灯后。可以把它安排在傍晚，之前沿河岸走一段，之后从三岔河口一带收尾。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'xian-bell-tower'),
    'xian-bell-tower-plan',
    '西安钟楼半日：四条大街的中心',
    1, 'mid', '在城墙内安排半天的游客',
    '钟楼位于四条大街的交汇点，登楼看中轴最直观。与鼓楼相距不远，两处可以连着走，晚上回来看亮灯。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'macau-tower'),
    'macau-tower-plan',
    '澳门旅游塔半日：观景与半岛南部',
    1, 'mid', '在澳门半岛安排半天的游客',
    '先登观景层看澳门全景，再看是否要参加塔上的户外项目。下来后沿南湖一带走到半岛南部，行程紧凑。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shenyang-imperial-palace'),
    'shenyang-imperial-palace-plan',
    '沈阳故宫半日：中东西三路',
    1, 'low', '在沈阳老城安排半天的游客',
    '宫殿分中、东、西三路，先走中路的大政殿与十王亭，再看凤凰楼与文溯阁。整体规模不大，半天足够。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'palace-museum-of-manchukuo'),
    'palace-museum-of-manchukuo-plan',
    '伪满皇宫半日：按原状陈列走',
    1, 'low', '对近代史感兴趣的游客',
    '建筑按办公与居住两处原状布置，参观以室内为主。史料部分内容较重，慢慢看需要半天。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'harbin-saint-sophia-cathedral'),
    'harbin-saint-sophia-cathedral-plan',
    '圣索菲亚教堂半日：广场与老城',
    1, 'low', '在道里区安排半天的游客',
    '教堂本体不大，重点是外观与广场。看过内部展览之后，可以步行到中央大街与松花江边。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'inner-mongolia-museum'),
    'inner-mongolia-museum-plan',
    '内蒙古博物院半日：自然与草原两条线',
    1, 'low', '在呼和浩特安排半天的游客',
    '前半段看古生物化石，后半段看草原民族文物。展厅按楼层分布，跟着主题走一趟需要半天。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shanxi-museum'),
    'shanxi-museum-plan',
    '山西博物院半日：从晋侯鸟尊看起',
    1, 'low', '对青铜器与北朝文物感兴趣的游客',
    '「晋魂」主线按时间铺开，青铜器与北朝壁画是重点。展厅集中在主馆内，半天可以走完。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'hebei-museum'),
    'hebei-museum-plan',
    '河北博物院半日：满城汉墓为主',
    1, 'low', '专程来看满城汉墓文物的游客',
    '满城汉墓展区是重点，金缕玉衣与长信宫灯都在其中。其余展厅按时间安排。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'zhaozhou-bridge'),
    'zhaozhou-bridge-plan',
    '赵州桥半日：看桥也看陈列馆',
    1, 'low', '自驾或包车经过赵县的游客',
    '桥本体不大，重点是敞肩拱的构造。旁边的陈列馆有桥梁史料与更换下来的构件，两处加起来半天足够。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'shandong-museum'),
    'shandong-museum-plan',
    '山东博物馆半日：黑陶与画像石',
    1, 'low', '在济南安排半天的游客',
    '按时间顺序走一遍山东的考古发现，龙山黑陶与汉画像石是两处重点。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'baotu-spring'),
    'baotu-spring-plan',
    '趵突泉到护城河：泉水半日',
    1, 'low', '想按泉水一条线走的游客',
    '从趵突泉进园，看泉池与园林，再沿护城河走到另一处泉群，一条线把几处泉串起来。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'zhanqiao-pier'),
    'zhanqiao-pier-plan',
    '栈桥与老城半日：从桥上到中山路',
    1, 'low', '在青岛老城安排半天的游客',
    '先走栈桥到回澜阁，再沿中山路往北看老建筑，傍晚回到海边。冬季海鸥聚集时桥上人最多。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'anhui-museum'),
    'anhui-museum-plan',
    '安徽博物院半日：青铜与徽州',
    1, 'low', '在合肥安排半天的游客',
    '先看青铜部分的楚大鼎与蔡侯墓器物，再看徽州建筑与文房四宝。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'tengwang-pavilion'),
    'tengwang-pavilion-plan',
    '滕王阁半日：登阁与赣江',
    1, 'mid', '想在南昌安排半天的游客',
    '主阁明三层暗七层，逐层上行看陈列，高层可以望赣江。之后在园区与江边走一段。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'three-lanes-seven-alleys'),
    'three-lanes-seven-alleys-plan',
    '三坊七巷半日：主街与几条巷',
    1, 'low', '在福州老城安排半天的游客',
    '以主街南后街为轴，横向走进几条坊巷看民居与故居。院落多且结构相似，挑重点看即可。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'gulangyu-island'),
    'gulangyu-island-plan',
    '鼓浪屿一日：日光岩与老别墅',
    1, 'mid', '第一次上岛的游客',
    '岛上没有机动车，全程步行。上午登日光岩看全岛，下午按街巷看老建筑，傍晚回到菽庄花园一带。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'stone-forest'),
    'stone-forest-plan',
    '石林一日：大石林到小石林',
    1, 'mid', '想看喀斯特地貌的游客',
    '园区分若干片区，靠步道与摆渡车连接。先走大石林最密的石峰群，再去小石林一带的草地。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'jiaxiu-pavilion'),
    'jiaxiu-pavilion-plan',
    '甲秀楼半日：南明河两岸',
    1, 'low', '在贵阳老城安排半天的游客',
    '楼体不大，重点是临水的这一组建筑。白天看结构与浮玉桥，傍晚亮灯后再回来一次。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'guangxi-museum-of-nationalities'),
    'guangxi-museum-of-nationalities-plan',
    '广西民族博物馆半天：铜鼓与村寨',
    1, 'low', '带孩子或对民族文物感兴趣的游客',
    '馆内按民族分列，铜鼓单独成一部分。馆外的村寨式建筑与原状民居可以一并走，室内外各占一半时间。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'gansu-provincial-museum'),
    'gansu-provincial-museum-plan',
    '甘肃省博物馆半日：看铜奔马',
    1, 'low', '在兰州安排半天的游客',
    '铜奔马所在的展厅是重点，彩陶与丝路文物各占一条线。展厅集中在同一馆内。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'western-xia-tombs'),
    'western-xia-tombs-plan',
    '西夏陵半日：陵塔与博物馆',
    1, 'mid', '对西夏历史或戈壁景观感兴趣的游客',
    '陵区范围大，各陵之间距离远，通常乘车在主要几处停留。先看博物馆理清背景，再到现场看夯土陵塔。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'kumbum-monastery'),
    'kumbum-monastery-plan',
    '塔尔寺半日：按殿堂顺序走',
    1, 'mid', '在西宁安排半天的游客',
    '寺院依山而建，殿堂分散，按指示单向参观。大金瓦殿与酥油花馆是两处重点。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'xinjiang-regional-museum'),
    'xinjiang-regional-museum-plan',
    '新疆博物馆半日：丝路与干尸陈列',
    1, 'low', '在乌鲁木齐安排半天的游客',
    '常设陈列以丝路文物与古代干尸两部分最能代表这里，展品说明较细，按顺序看一遍需要半天。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'tianyi-pavilion'),
    'tianyi-pavilion-plan',
    '天一阁半日：藏书楼与园林',
    1, 'low', '在宁波老城安排半天的游客',
    '藏书楼本体是重点，院落里的水池、假山与碑廊可以一并走，之后到月湖一带收尾。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'yandang-mountain'),
    'yandang-mountain-plan',
    '雁荡山两日：灵峰 · 灵岩 · 大龙湫',
    2, 'mid', '想看流纹岩峰群的游客',
    '三个主要片区之间需要乘车，两天比较从容。白天看岩峰与瀑布，晚上再看一次灵峰夜景。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'yuantouzhu'),
    'yuantouzhu-plan',
    '鼋头渚半日：樱花与太湖',
    1, 'low', '春季到无锡的游客',
    '园区以半岛与湖面为主，春季看樱花，平时看湖景。可以乘船到湖中的岛上，整体步行量中等。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'foshan-ancestral-temple'),
    'foshan-ancestral-temple-plan',
    '佛山祖庙半日：三雕两塑与醒狮',
    1, 'low', '想一次看建筑装饰与民俗的游客',
    '沿中轴看牌坊与正殿，重点是建筑上的砖木石雕与屋脊陶塑，之后到旁边的纪念馆看醒狮与武术陈列。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
),
(
    (SELECT id FROM attraction WHERE slug = 'quanzhou-kaiyuan-temple'),
    'quanzhou-kaiyuan-temple-plan',
    '开元寺半日：东西塔与西街',
    1, 'low', '在泉州老城安排半天的游客',
    '先看大殿与月台的石刻构件，再走到寺外看东西两座石塔，最后沿西街逛一段。',
    'Have-A-Trip 自采（公开事实信息）', 'MIT', NULL
)
ON CONFLICT (slug) DO UPDATE SET
    attraction_id = EXCLUDED.attraction_id,
    title         = EXCLUDED.title,
    days          = EXCLUDED.days,
    budget_level  = EXCLUDED.budget_level,
    best_for      = EXCLUDED.best_for,
    summary       = EXCLUDED.summary,
    source        = EXCLUDED.source,
    license       = EXCLUDED.license,
    source_url    = EXCLUDED.source_url;

DELETE FROM attraction_plan_step
WHERE plan_id IN (SELECT id FROM attraction_plan WHERE source = 'Have-A-Trip 自采（公开事实信息）');

INSERT INTO attraction_plan_step (plan_id, day_no, sort, title, detail, duration_hours, tip)
SELECT p.id, m.day_no, m.sort, m.title, m.detail, m.duration_hours, m.tip
FROM (VALUES
    ('angkor-wat-plan',         1, 0, '清晨 · 吴哥寺日出与主体', '天亮前到西侧水池边占位，日出后直接进寺，从第一层回廊浮雕看起，再上第二、三层。登顶层有服装与人数限制，排队通常在上午。', 4.0, '第三层有每日限流，早去比晚去省时间。'),
    ('angkor-wat-plan',         1, 1, '上午后半 · 巴戎寺与巴方寺', '从吴哥寺南门出，经通王城胜利门进巴戎寺看四面佛塔，再步行到巴方寺。两处相距不远，可连着走。', 3.0, NULL),
    ('angkor-wat-plan',         1, 2, '下午 · 塔布茏寺与茶胶寺', '塔布茏寺以树根缠绕石构闻名，通行路线为单向；茶胶寺是未完成的大型国寺，台阶陡，量力而行。', 2.5, NULL),
    ('angkor-wat-plan',         2, 0, '上午 · 大圈东段', '圣剑寺、涅槃宫、塔逊寺依次向北，各点之间车程十来分钟。', 4.0, NULL),
    ('angkor-wat-plan',         2, 1, '下午 · 东梅奔与比粒寺日落', '比粒寺是高台建筑，登顶后往西看日落视野开阔，傍晚人比巴肯山少。', 3.0, '比粒寺台阶陡且窄，上下都要侧身。'),
    ('angkor-wat-plan',         3, 0, '全天 · 外圈', '女王宫以红色砂岩与细密浮雕著称，上午顺光更清楚；崩密列是未修复的废墟，需另购票且要按木栈道通行。', 7.0, '外圈路程远，包车一天比逐段打车便宜。'),
    ('taj-mahal-plan',          1, 0, '开门前抵达东门', '排队安检后第一批进园。正门到主体之间是长水池，趁人少先拍这个经典框景。', 1.0, '大理石在强光下反光刺眼，戴墨镜更舒服。'),
    ('taj-mahal-plan',          1, 1, '主体陵墓与台基', '沿中轴走到台基下，绕到两侧看清四座宣礼塔的对称关系。进入陵墓内部需另加购票，内部只有复制棺椁。', 1.0, NULL),
    ('taj-mahal-plan',          1, 2, '两侧清真寺与迎宾楼', '两座红砂岩建筑与水景构成完整构图，从西侧回望主体的角度通常少人。', 0.5, NULL),
    ('taj-mahal-plan',          1, 3, '河畔远望', '从亚穆纳河北岸一侧可以望见陵墓的河景轮廓，需另行前往，适合时间宽裕时补看。', 0.5, NULL),
    ('mount-fuji-plan',         1, 0, '上午 · 河口湖北岸', '湖水倒影对风很敏感，越早风越小。北岸一带机位集中，长焦与广角各有用处。', 2.0, '阴天或云层低时看不到山体，出发前先查实时能见度。'),
    ('mount-fuji-plan',         1, 1, '中午 · 大石公园与花田', '季节花卉与山体同框，夏季薰衣草、秋季扫帚草。', 1.5, NULL),
    ('mount-fuji-plan',         1, 2, '下午 · 忍野八海', '富士山融雪渗流形成的八个涌泉池，水清见底，村内步道平缓。', 2.0, NULL),
    ('mount-fuji-plan',         1, 3, '傍晚 · 湖畔落日', '回到湖边看山体侧影由白转粉，晴天时最明显。', 1.0, NULL),
    ('petra-plan',              1, 0, '清晨 · 穿蛇道进古城', '从游客中心出发，沿土路走到蛇道口，穿谷约二十分钟，尽头正对卡兹尼神殿。', 2.0, '开门即入园能比旅行团早一步到神殿前。'),
    ('petra-plan',              1, 1, '上午 · 岩墓群与剧场', '经过外立面街与罗马剧场，往北上山到王家墓群，居高看整片岩壁。', 2.5, NULL),
    ('petra-plan',              1, 2, '午后 · 代尔修道院', '从盆地后方上山，约 800 级石阶，终点是体量更大的修道院立面。', 3.0, '山路无遮阴且陡，带足水，正午前后最晒。'),
    ('petra-plan',              1, 3, '傍晚 · 原路返回', '下山按原路走回蛇道，日落前出园。', 1.0, NULL),
    ('borobudur-plan',          1, 0, '04:30 入园登顶等日出', '由指定入口进场，登到圆形层。日出方向在建筑东侧，云层低时看不到山影。', 2.0, '顶层夜间风大，带件外套。'),
    ('borobudur-plan',          1, 1, '回廊浮雕', '从底部逐层顺时针走，按叙事顺序看浮雕，走完一圈需要一个多小时。', 1.5, NULL),
    ('borobudur-plan',          1, 2, '顶层舍利塔', '数十座钟形塔环绕中央主塔，按顺时针依次看过，注意塔内佛像的朝向差异。', 0.5, NULL),
    ('hagia-sophia-plan',       1, 0, '09:00 圣索菲亚', '先到二层回廊看马赛克与穹顶结构，再下到底层看米哈拉布与苏丹包厢。', 1.5, '参观与礼拜时段可能分开安排，入口需现场确认。'),
    ('hagia-sophia-plan',       1, 1, '地下水宫', '斜对面的地下水宫由数百根石柱撑起穹顶，美杜莎头像基座在深处。', 1.0, NULL),
    ('hagia-sophia-plan',       1, 2, '赛马场广场与蓝色清真寺', '步行数分钟到广场，方尖碑与蛇柱在同一片区域。', 1.5, NULL),
    ('hagia-sophia-plan',       1, 3, '傍晚 · 加拉塔桥', '过桥后回望老城天际线，宣礼塔与穹顶叠在一起。', 1.5, '桥上人多，注意随身物品。'),
    ('ha-long-bay-plan',        1, 0, '中午 · 登船出发', '从巡洲码头出发，午餐在船上。沿途开始出现成片岩柱。', 2.0, NULL),
    ('ha-long-bay-plan',        1, 1, '下午 · 登岛观景与溶洞', '多为登高看全景加一处溶洞，台阶湿滑要慢走。', 3.0, '溶洞内灯光暗，穿防滑鞋。'),
    ('ha-long-bay-plan',        1, 2, '傍晚 · 锚地日落', '船在岛群间下锚，日落时分甲板视角最好。', 2.0, NULL),
    ('ha-long-bay-plan',        2, 0, '清晨 · 日出与皮划艇', '天亮前后在平静海面划艇穿行礁柱之间，之后返航。', 3.0, NULL),
    ('kinkakuji-plan',          1, 0, '上午 · 金阁寺', '进园后沿单向路线环池走，镜湖池南侧看楼阁与倒影。', 1.5, '开门时段人相对少，逆光也弱一些。'),
    ('kinkakuji-plan',          1, 1, '中午 · 龙安寺石庭', '枯山水石庭，白砂上耙出纹路，坐在方丈廊下静看。', 1.5, NULL),
    ('kinkakuji-plan',          1, 2, '下午 · 仁和寺', '以御殿庭园与五重塔为主，园内比前两处宽敞，节奏可以放慢。', 1.5, NULL),
    ('gyeongbokgung-plan',      1, 0, '10:00 光化门看换岗', '仪式在正门外广场进行，结束后正好随人流进宫。', 1.0, '着装租借的韩服可免门票，但要按现场规定。'),
    ('gyeongbokgung-plan',      1, 1, '勤政殿与庆会楼', '先走中轴到勤政殿，再往西路到建在池上的庆会楼。', 1.5, NULL),
    ('gyeongbokgung-plan',      1, 2, '国立古宫博物馆', '在宫门内侧，按朝代陈列宫廷遗物，适合雨天。', 1.5, NULL),
    ('gyeongbokgung-plan',      1, 3, '北村韩屋村', '步行十几分钟，坡道两侧为传统民居，仍有人居住，注意安静。', 1.5, NULL),
    ('eiffel-tower-plan',       1, 0, '下午 · 登二层与顶层', '二层视野最均衡，能看清街道格局；顶层更高但玻璃与栏杆会挡住部分视线。', 1.5, '顶层季节与天气不佳时可能关闭，出发前查运营公告。'),
    ('eiffel-tower-plan',       1, 1, '黄昏 · 夏乐宫平台', '过桥到对岸的夏乐宫平台，是拍整座铁塔最完整的机位。', 1.0, NULL),
    ('eiffel-tower-plan',       1, 2, '夜间 · 整点灯光', '天黑后每逢整点闪烁数分钟，在战神广场或河岸看都合适。', 1.0, NULL),
    ('eiffel-tower-plan',       1, 3, '沿塞纳河散步', '从耶拿桥往东走，沿岸可见到荣军院与奥赛一带的建筑。', 1.0, NULL),
    ('colosseum-plan',          1, 0, '上午 · 斗兽场', '先进场内看竞技场地下结构与看台分区，再上二层沿外圈走一圈。', 1.5, '安检队伍长，按预约时段提前到。'),
    ('colosseum-plan',          1, 1, '古罗马广场', '沿圣道走到元老院、神庙与凯旋门，遗址范围大，按主干道走不易乱。', 2.0, NULL),
    ('colosseum-plan',          1, 2, '帕拉蒂尼山', '从广场一侧上山，俯瞰广场与斗兽场，山上树荫多，适合午后。', 1.5, NULL),
    ('sagrada-familia-plan',    1, 0, '上午 · 圣家堂内部', '从诞生立面一侧进入，先看中殿立柱与穹顶，再沿受难立面一侧看侧窗颜色变化。', 2.0, '彩窗在晴天的上午最透，阴天效果差很多。'),
    ('sagrada-familia-plan',    1, 1, '塔楼登顶', '电梯上行后经由螺旋楼梯下行，途中可从小窗俯瞰城市。', 0.5, '恐高或不便走窄楼梯的可跳过。'),
    ('sagrada-familia-plan',    1, 2, '格拉西亚大道', '巴特罗之家与米拉之家外立面相邻数个街区，可只在外看，也可择一入内。', 2.0, NULL),
    ('sagrada-familia-plan',    1, 3, '傍晚 · 桂尔公园', '马赛克长椅与柱厅，登高可看城市与海。', 1.5, NULL),
    ('versailles-plan',         1, 0, '上午 · 宫殿主体', '按单向路线经国王套房、镜厅到王后套房，人流集中在前半段。', 2.5, '周一闭馆，出发前先查当日开放情况。'),
    ('versailles-plan',         1, 1, '午后 · 园林东段', '拉托娜池、阿波罗池沿中轴依次排开，这一段步行即可。', 1.5, NULL),
    ('versailles-plan',         1, 2, '园林西段与大小特里亚农', '坐园内小火车到运河一端，再往回走到特里亚农宫区域。', 2.0, '园林面积很大，全靠步行会超出体力预算。'),
    ('versailles-plan',         1, 3, '喷泉表演', '开放日按固定时段运行，主要水池沿线是最佳观看位置。', 1.0, NULL),
    ('neuschwanstein-plan',     1, 0, '上午 · 玛丽安桥', '步行或坐车上山，桥横跨峡谷，正对新天鹅堡侧面，是标准机位。', 1.5, '桥上人多且木板湿滑，停留时间有限。'),
    ('neuschwanstein-plan',     1, 1, '入堡参观', '按票面时段入内，全程为导览路线，经王座厅、歌唱厅到国王起居室。', 1.5, '内部禁止拍照，且必须按叫号顺序进场。'),
    ('neuschwanstein-plan',     1, 2, '旧天鹅堡与阿尔卑湖', '下山后可看黄色的旧天鹅堡外观，再走到湖边。', 2.0, NULL),
    ('acropolis-plan',          1, 0, '08:00 上山', '从西侧主入口进入，经山门登顶，趁人少绕帕特农一周。', 2.0, '台面为大理石，磨得很滑，穿防滑鞋。'),
    ('acropolis-plan',          1, 1, '伊瑞克提翁与女像柱', '北侧的女像柱廊是原件的复制品，原件在博物馆内。', 0.5, NULL),
    ('acropolis-plan',          1, 2, '卫城博物馆', '山脚东南侧，顶层按帕特农实际方位陈列，可对照山上的位置看。', 2.0, NULL),
    ('acropolis-plan',          1, 3, '普拉卡老区', '博物馆步行可到，街区狭窄，适合傍晚散步与吃饭。', 1.5, NULL),
    ('santorini-plan',          1, 0, '上午 · 费拉镇', '镇内巷弄纵横，先适应方向，找好主步道入口。', 2.0, NULL),
    ('santorini-plan',          1, 1, '午后 · 悬崖步道', '费拉到伊亚约十公里，沿途经菲罗斯特法尼与伊莫洛维里，多为石阶上下。', 4.0, '全程少遮阴，带足水，正午不宜走。'),
    ('santorini-plan',          1, 2, '傍晚 · 伊亚日落', '日落前一到两小时占位，城堡遗址一带视野最开阔。', 2.0, '散场时道路极拥挤，可等半小时再走。'),
    ('santorini-plan',          2, 0, '上午 · 出海游', '绕破火山口航行，途中在有温泉的海湾停留。', 4.0, NULL),
    ('santorini-plan',          2, 1, '下午 · 东侧海滩', '黑沙与红沙海滩水况不同，红沙需从崖上步行下去。', 2.5, NULL),
    ('stonehenge-plan',         1, 0, '上午 · 巨石阵', '在游客中心看展陈后沿栈道绕石阵一周，按语音导览听各段来历。', 2.0, '石阵内部仅特定日期开放，常规参观只能在外围栈道。'),
    ('stonehenge-plan',         1, 1, '埃夫伯里石圈', '规模更大的环形石阵，其中一段与村内道路共用，可自由走近。', 2.0, NULL),
    ('stonehenge-plan',         1, 2, '西肯尼特长冢', '石室墓，可弯腰进入墓室，内部空间不高。', 1.0, NULL),
    ('pompeii-plan',            1, 0, '上午 · 广场与神庙', '从广场门进入，看朱庇特神庙、元老院与市场建筑群。', 1.5, '入口处有寄存与饮水点，先补水再进。'),
    ('pompeii-plan',            1, 1, '剧场区与大剧场', '东南侧的剧场区地势起伏，大剧场依坡而建。', 1.5, NULL),
    ('pompeii-plan',            1, 2, '浴场与街区', '斯塔比伊浴场有完整的供暖与更衣结构，沿街能看到商铺柜台。', 2.0, NULL),
    ('pompeii-plan',            1, 3, '民居壁画与石膏像', '悲剧诗人之家等民居保存了壁画，遇难者石膏像集中在特定展区。', 1.5, '遗址内餐饮选择少，带干粮更稳妥。'),
    ('louvre-plan',             1, 0, '早场 · 从金字塔入口进', '避开上午高峰，先直奔德农馆二层看意大利绘画，此时人流最少。', 2.0, '馆内很大且易迷路，先拿平面图并记住所在馆名。'),
    ('louvre-plan',             1, 1, '德农馆 · 古典雕塑', '一层沿廊道看希腊罗马雕塑，胜利女神像在楼梯平台处。', 1.5, NULL),
    ('louvre-plan',             1, 2, '午后 · 叙利馆古埃及', '木乃伊与人面狮身像等在这一区，空间比德农馆安静。', 1.5, NULL),
    ('louvre-plan',             1, 3, '黎塞留馆与庭院', '法国雕塑与装饰艺术，逛不动可只走中庭看建筑本身。', 1.5, NULL),
    ('jungfrau-plan',           1, 0, '清晨 · 从因特拉肯出发', '换乘至格林德瓦终点站，再转登山齿轨列车。', 2.0, '车票价格高，提前买通票或早鸟票能省不少。'),
    ('jungfrau-plan',           1, 1, '途中 · 岩壁窗口停留', '列车在隧道内两处短暂停车，可下车看冰川与山谷。', 1.0, '停留时间有限，注意开车时间。'),
    ('jungfrau-plan',           1, 2, '山顶 · 观景平台与冰宫', '平台分室内外，室外风大；冰宫在冰川内部开凿，地面湿滑。', 2.0, '海拔高，走快容易头晕，放慢节奏。'),
    ('jungfrau-plan',           1, 3, '下山 · 劳特布龙嫩一侧', '另一侧线路经温根或劳特布龙嫩，可见瀑布与峡谷。', 2.0, NULL),
    ('charles-bridge-plan',     1, 0, '清晨 · 步行过桥', '趁团队客未到，沿桥面看两侧雕像，中段可以看到城堡方向的河景。', 1.0, '桥面全天免费开放，但正午前后极拥挤。'),
    ('charles-bridge-plan',     1, 1, '老城桥塔登顶', '塔内为螺旋楼梯，顶部平台可俯看桥面与河湾。', 0.5, NULL),
    ('charles-bridge-plan',     1, 2, '老城广场一带', '天文钟整点有报时装置动作，广场周围为泰恩教堂等建筑。', 2.0, NULL),
    ('charles-bridge-plan',     1, 3, '夜间 · 回桥上', '灯光亮起后桥塔与雕像剪影清晰，河面有倒影。', 1.0, NULL),
    ('pyramids-of-giza-plan',   1, 0, '上午 · 胡夫金字塔', '绕行一周看砌石与原入口，若入内需从特定通道购票进入。', 1.5, '高原日晒强且少遮阴，帽子和水必备。'),
    ('pyramids-of-giza-plan',   1, 1, '哈夫拉与孟卡拉', '南行看哈夫拉顶部的原外包石，再往西南到体量最小的孟卡拉。', 1.5, NULL),
    ('pyramids-of-giza-plan',   1, 2, '狮身人面像与谷庙', '从哈夫拉金字塔经坡道下到谷庙，正面看狮身人面像。', 1.0, NULL),
    ('pyramids-of-giza-plan',   1, 3, '全景机位', '高原西南侧可一次拍到三座金字塔同框，傍晚光线更好。', 1.0, NULL),
    ('victoria-falls-plan',     1, 0, '上午 · 雨林步道', '沿步道从东往西逐段看各段瀑布，丰水季水雾很大。', 2.5, '水雾区如遇下雨，防水袋比雨伞实用。'),
    ('victoria-falls-plan',     1, 1, '午后 · 观景台与大桥', '桥上可看到瀑布与峡谷的纵深关系，适合补拍全景。', 1.0, NULL),
    ('victoria-falls-plan',     1, 2, '傍晚 · 赞比西河游船', '从上游码头出发，沿岸可见河马与鸟类，日落时返航。', 3.0, NULL),
    ('serengeti-plan',          1, 0, '上午 · 入园与中央草原', '从南门进入，沿主路向塞罗内拉方向行驶，途中留意兽群与猛禽。', 4.0, '园内土路颠簸，晕车者提前备药。'),
    ('serengeti-plan',          1, 1, '午后 · 河谷一带', '河谷有水源，旱季动物集中，是观察捕食行为的时段。', 3.0, NULL),
    ('serengeti-plan',          2, 0, '清晨 · 日出巡游', '天不亮出发，清晨是猫科动物活动最频繁的时段。', 3.0, '清晨气温低，越野车敞顶风大，需加外套。'),
    ('serengeti-plan',          2, 1, '向北追迁徙', '按当季草场情况向北行驶，渡河点附近通常人流与车流都集中。', 5.0, NULL),
    ('marrakech-medina-plan',   1, 0, '上午 · 库图比亚清真寺', '清真寺非穆斯林不能入内，可在外围看塔与庭园。', 1.0, NULL),
    ('marrakech-medina-plan',   1, 1, '萨阿德王朝陵墓', '三座陵室以大理石与马赛克装饰，空间不大但细节密集。', 1.5, NULL),
    ('marrakech-medina-plan',   1, 2, '巴西亚宫与市集', '宫殿以庭院与雕花天花为主，出来即接手工市集，价格需议。', 2.5, '市集内有人主动带路，跟走后通常要付小费。'),
    ('marrakech-medina-plan',   1, 3, '傍晚 · 老城广场', '日落后摊位与演出同时展开，环绕广场一圈即可找到各个方向的热闹点。', 2.0, NULL),
    ('table-mountain-plan',     1, 0, '上午 · 缆车上顶', '旋转缆车数分钟到顶，出站即是环线起点。', 0.5, '风大时缆车停运，出发前先看运营状态。'),
    ('table-mountain-plan',     1, 1, '顶层环线', '沿边缘环走可看到市区、海湾与狮头山多个方向，全程平缓。', 2.0, '崖边无护栏处不要靠近。'),
    ('table-mountain-plan',     1, 2, '午后 · 峡谷步道下山', '沿普拉特克利普峡谷下行，部分路段需手脚并用。', 2.5, '下山比上山更费膝盖，穿抓地好的鞋。'),
    ('grand-canyon-plan',       1, 0, '日出 · 东侧观景点', '天不亮到观景点，日出时谷壁由暗转红的过程最明显。', 1.0, '清晨气温低，即使夏季也要加衣。'),
    ('grand-canyon-plan',       1, 1, '上午 · 南缘主路观景点', '沿主路自东向西逐个停靠，各点视角互不相同。', 3.0, NULL),
    ('grand-canyon-plan',       1, 2, '午后 · 光明天使步道', '沿步道下行一段即有明显落差，到第一个休息点折返。', 3.0, '谷内比缘上闷热，务必按往返时间带够水。'),
    ('grand-canyon-plan',       1, 3, '日落 · 西侧观景点', '西侧视野开阔，落日时层理颜色变化最丰富。', 1.0, NULL),
    ('statue-of-liberty-plan',  1, 0, '清晨 · 炮台公园登船', '安检后乘渡轮，航行途中从水面看曼哈顿天际线。', 1.5, '登冠冕需提前很久预约，普通票只能到基座。'),
    ('statue-of-liberty-plan',  1, 1, '自由岛', '绕岛步道看铜像各面，背面可看裙摆与内部支撑的痕迹。', 1.5, NULL),
    ('statue-of-liberty-plan',  1, 2, '埃利斯岛移民博物馆', '陈列当年入境检查的大厅与登记档案，可查询家族入境记录。', 2.0, NULL),
    ('yellowstone-plan',        1, 0, '清晨 · 间歇泉盆地', '趁气温低看喷发时的水汽柱，环形栈道可绕行各泉眼。', 3.0, '栈道紧邻热泉，务必留在栈道上。'),
    ('yellowstone-plan',        1, 1, '午后 · 大棱镜热泉', '从高处步道俯瞰热泉的同心色带，水汽大时看不清全貌。', 2.0, NULL),
    ('yellowstone-plan',        1, 2, '傍晚 · 老忠实一带', '喷发间隔较稳定，可先查下一次喷发时间再安排等待。', 2.0, NULL),
    ('yellowstone-plan',        2, 0, '上午 · 黄石大峡谷', '沿南缘与北缘的观景点看上下瀑布，北缘取景角度更好。', 3.0, NULL),
    ('yellowstone-plan',        2, 1, '午后 · 黄石湖区', '湖面开阔，沿岸是观察野牛与水鸟的常见位置。', 2.5, '遇野牛过路须留在车内等待，不要靠近。'),
    ('chichen-itza-plan',       1, 0, '08:00 中央金字塔', '开门即进，趁人少围绕塔身一周，正对阶梯拍全景。', 1.0, '塔身已不允许攀登，只能在外围观看。'),
    ('chichen-itza-plan',       1, 1, '大球场与武士神庙', '球场两侧有回音效应，武士神庙前有列柱与祭坛。', 1.5, '场内小贩叫卖声很密集，可径直穿过。'),
    ('chichen-itza-plan',       1, 2, '天文台与天然井', '圆形天文台为观测建筑；附近的天然井可下水，需另购票并冲洗。', 2.0, NULL),
    ('banff-plan',              1, 0, '清晨 · 路易斯湖', '清晨湖面平静、倒影清楚，湖岸步道平缓。', 2.0, '停车场很早就满，建议乘园区接驳车。'),
    ('banff-plan',              1, 1, '梦莲湖', '湖水颜色更浓，湖畔有石堆观景点，需短暂上坡。', 2.0, '部分季节限制私家车进入，需乘接驳车。'),
    ('banff-plan',              2, 0, '上午 · 冰原大道', '沿公路北上至冰川观景点，沿途可停靠多个湖与峡谷。', 4.0, NULL),
    ('banff-plan',              2, 1, '午后 · 冰川与瀑布', '看冰川舌部与融水瀑布，气温比谷地低很多。', 3.0, '冰川边缘有落石与裂缝，不要越过警戒线。'),
    ('niagara-falls-plan',      1, 0, '上午 · 河岸步道', '沿步道依次经过美国瀑布与新娘面纱，最后到马蹄瀑布正面。', 2.0, '靠近瀑布处终年有水雾，防水外套比伞实用。'),
    ('niagara-falls-plan',      1, 1, '午后 · 观光船', '乘船靠近瀑布底部，船上发放雨衣，全程十余分钟。', 1.5, NULL),
    ('niagara-falls-plan',      1, 2, '傍晚 · 瀑布后方隧道', '乘电梯下到瀑布后方的观景口，从内部看水幕。', 1.0, NULL),
    ('niagara-falls-plan',      1, 3, '夜间 · 灯光', '入夜后有彩色照明，瀑布前的步道是主要观赏位置。', 1.0, NULL),
    ('machu-picchu-plan',       1, 0, '清晨 · 库斯科出发', '乘火车到热水镇，再转乘上山巴士，车程约半小时。', 3.5, '票与入场时段需提前订，旺季常提前售完。'),
    ('machu-picchu-plan',       1, 1, '上午 · 卫城高处俯瞰', '进城后先上到高台，趁人少拍全景与背后的山峰。', 1.5, '海拔较高，走路放慢，避免快速登阶。'),
    ('machu-picchu-plan',       1, 2, '园区单向路线', '按指定路线经太阳神庙、拴日石与梯田区，路线方向现场有标识。', 3.0, NULL),
    ('machu-picchu-plan',       1, 3, '午后返程', '原路下山乘火车回库斯科，傍晚抵达。', 3.0, NULL),
    ('christ-the-redeemer-plan', 1, 0, '上午 · 齿轨小火车', '从山脚车站出发，穿过林区到山顶站，途中穿过林荫与隧道。', 1.5, '云雾天山顶会被云遮住，出发前先看实时画面。'),
    ('christ-the-redeemer-plan', 1, 1, '山顶塑像与观景', '绕到塑像正下方，再沿平台看瓜纳巴拉湾与城市。', 1.5, NULL),
    ('christ-the-redeemer-plan', 1, 2, '下午 · 面包山', '另一侧的山顶观景台，可看到科帕卡巴纳海滩的弧形。', 2.0, NULL),
    ('christ-the-redeemer-plan', 1, 3, '傍晚 · 科帕卡巴纳海滩', '海滩朝东，落日时人很多，沿岸步道适合散步。', 1.5, NULL),
    ('iguazu-falls-plan',       1, 0, '上午 · 上层步道', '沿步道依次经过各段瀑布，能看到整条断崖的走向。', 2.0, NULL),
    ('iguazu-falls-plan',       1, 1, '午后 · 下层步道', '下到河岸一带，部分路段会被水雾打湿。', 2.0, '下层步道有台阶且湿滑，穿防滑鞋。'),
    ('iguazu-falls-plan',       1, 2, '魔鬼咽喉栈道', '乘园内列车到栈道起点，沿栈道走到马蹄形瀑布正上方。', 2.0, '水雾极大，相机与手机需防水。'),
    ('galapagos-plan',          1, 0, '第一天 · 圣克鲁斯高地', '看象龟在放牧区的状态与火山口地貌，气温比海边低。', 5.0, '登岛与机场手续需预留时间，别把第一天排满。'),
    ('galapagos-plan',          2, 0, '第二天 · 近岸小岛', '乘船到附近的无人小岛，步行路线由向导指定。', 6.0, '不要触碰或投喂任何动物，也不要把生物带走。'),
    ('galapagos-plan',          3, 0, '第三天 · 浮潜', '在近岸水域与海龟、海鬣蜥共游，水温受季节影响。', 5.0, NULL),
    ('galapagos-plan',          4, 0, '第四天 · 缓冲与返程', '留出机动时间应对船期变化，返程前可再看一次海狮聚集的海滩。', 4.0, NULL),
    ('easter-island-plan',      1, 0, '上午 · 采石场', '人像多在山体岩壁上就地雕凿，半成品与成品在同一山坡。', 2.0, NULL),
    ('easter-island-plan',      1, 1, '午后 · 东海岸石台群', '规模最大的一组石台，人像林立，是岛上最常被拍摄的位置。', 2.5, '遗址不可踩踏石台，按木栈道通行。'),
    ('easter-island-plan',      2, 0, '上午 · 西侧祭台', '另一组立像与祭台，朝向与布局和东侧不同。', 2.0, NULL),
    ('easter-island-plan',      2, 1, '火山口与北侧海岸', '火山口湖与北侧沙滩颜色对比明显，可结合浮潜。', 3.0, NULL),
    ('easter-island-plan',      2, 2, '傍晚 · 海岸落日', '海岸线无遮挡，落日时人像剪影清楚。', 1.0, NULL),
    ('sydney-opera-house-plan', 1, 0, '上午 · 馆内导览', '由讲解带领进入音乐厅与歌剧院，能看到壳体在室内的交接方式。', 1.5, '有演出时部分厅室不开放，导览线路会调整。'),
    ('sydney-opera-house-plan', 1, 1, '午后 · 半岛步道', '沿海湾绕到西侧，从远处看整组壳体与海港大桥的关系。', 1.5, NULL),
    ('sydney-opera-house-plan', 1, 2, '植物园一侧', '从高处回望歌剧院与大桥同框，是常见的取景位置。', 1.0, NULL),
    ('sydney-opera-house-plan', 1, 3, '傍晚 · 环形码头', '码头与歌剧院的灯光在水面形成倒影。', 1.0, NULL),
    ('great-barrier-reef-plan', 1, 0, '清晨 · 出海', '船行约两小时到外礁平台，途中有浮潜教学与安全说明。', 2.5, '晕船者提前服药，外海涌浪比近岸明显。'),
    ('great-barrier-reef-plan', 1, 1, '上午 · 浮潜', '平台附近有浮标圈定的区域，沿绳圈移动即可看到珊瑚与鱼群。', 2.0, '不要触碰珊瑚，防晒建议用对珊瑚无害的产品。'),
    ('great-barrier-reef-plan', 1, 2, '午后 · 半潜艇或深潜', '半潜艇可不出水看礁体，深潜需持证或由教练带潜。', 2.0, NULL),
    ('great-barrier-reef-plan', 1, 3, '傍晚 · 返航', '回程多在日落前后抵达码头。', 2.5, NULL),
    ('milford-sound-plan',      1, 0, '清晨 · 沿途公路', '途中在镜湖等点短暂停留，靠近隧道一段山路坡陡弯多。', 2.0, '隧道高峰时段限流，出发时间要留余量。'),
    ('milford-sound-plan',      1, 1, '峡湾游船', '船沿峡湾驶向出海口，途中靠近瀑布与崖壁下的海豹聚集处。', 2.5, '瀑布水雾会打湿甲板，带防水外套。'),
    ('milford-sound-plan',      1, 2, '午后 · 原路返回', '返程可顺路走一小段步道，傍晚回到蒂阿瑙。', 3.5, NULL),
    ('west-lake-plan',          1, 0, '清晨 · 断桥与白堤', '从断桥起步沿白堤向东，平湖秋月一线视野开阔，清晨人少，湖面常有薄雾。', 1.0, NULL),
    ('west-lake-plan',          1, 1, '上午 · 孤山与西泠印社', '孤山不高，西泠印社一带可顺路看，适合放慢节奏。', 1.5, NULL),
    ('west-lake-plan',          1, 2, '午后 · 苏堤南北穿越', '沿苏堤步行或骑行，六桥串联，两侧湖面与山影是经典构图。', 1.5, '堤上遮阴少，夏天备水与防晒。'),
    ('west-lake-plan',          1, 3, '傍晚 · 雷峰塔与净慈寺', '塔上可俯瞰湖面，傍晚亮灯后观感最好；塔与个别园中园单独售票。', 1.5, '看雷峰夕照要在日落前半小时到位。'),
    ('huangshan-plan',          1, 0, '上午 · 慈光阁到玉屏楼', '前山登山道经半山寺、立马桥，迎客松在玉屏楼一带。', 3.0, '上山也可乘索道，省下的一段体力留给后面。'),
    ('huangshan-plan',          1, 1, '下午 · 光明顶等日落', '从玉屏楼经鳌鱼峰方向上山，傍晚在光明顶一带等日落，光明顶、丹霞峰是常见观景位置。', 2.5, '山上住宿需提前订，房间有限。'),
    ('huangshan-plan',          2, 0, '清晨 · 光明顶看日出', '日出时间随季节变化，提前问清当天时刻表。', 1.0, '山上比山下低约 8 至 10 摄氏度，外套必带。'),
    ('huangshan-plan',          2, 1, '上午 · 始信峰到云谷寺下山', '后山路线经北海、始信峰看奇松，再由云谷寺方向下山或乘索道。', 3.0, '下山石阶多，护膝比登山杖更好用。'),
    ('jiuzhaigou-plan',         1, 0, '上午 · 树正沟上行', '从沟口乘观光车到镜海一带，树正群海、火花海沿途湖群密集，可在树正寨附近步行一段。', 2.0, NULL),
    ('jiuzhaigou-plan',         1, 1, '午后 · 日则沟五花海与珍珠滩', '日则沟景观最集中，五花海、珍珠滩瀑布、诺日朗瀑布是主要停留点。', 3.0, '午后光线更适合看水色。'),
    ('jiuzhaigou-plan',         1, 2, '傍晚 · 则查洼沟长海与五彩池', '则查洼沟景点较少，长海与五彩池可一并看完，随后乘车出沟。', 2.0, '海拔在 2000 至 3100 米之间，节奏宜慢。'),
    ('zhangjiajie-plan',        1, 0, '上午 · 金鞭溪徒步', '从森林公园入口沿金鞭溪步行，溪谷两侧峰林夹道，全程平缓。', 3.0, NULL),
    ('zhangjiajie-plan',        1, 1, '下午 · 袁家界与天下第一桥', '乘百龙天梯或缆车上袁家界，后花园、迷魂台一线看峰林最集中。', 2.5, '梯与缆车排队时间长，尽量避开正午高峰。'),
    ('zhangjiajie-plan',        2, 0, '上午 · 天子山与贺龙公园', '天子山视野开阔，雨后云雾中的峰林是常见拍摄场景。', 3.0, NULL),
    ('zhangjiajie-plan',        2, 1, '下午 · 十里画廊', '出景区前走十里画廊，也可乘观光小火车节省体力。', 2.0, NULL),
    ('lijiang-old-town-plan',   1, 0, '上午 · 四方街与沿水巷子', '从大水车进入古城，玉泉水自北引入后分三股穿街过巷，顺水走不易迷路。', 2.0, NULL),
    ('lijiang-old-town-plan',   1, 1, '午后 · 木府与万古楼', '木府可看纳西族土司的院落格局，万古楼登高能俯瞰全城屋脊。', 2.0, NULL),
    ('lijiang-old-town-plan',   1, 2, '傍晚 · 黑龙潭与象山', '出城北到黑龙潭，天气好时潭面可映出玉龙雪山。', 1.5, '古城海拔约 2400 米，第一天不要走太急。'),
    ('pingyao-plan',            1, 0, '上午 · 城墙环走一段', '城墙周长约 6 公里，走南门上城墙的一段即可看清城内街巷走向。', 1.0, NULL),
    ('pingyao-plan',            1, 1, '上午后半 · 日昇昌票号与南大街', '晋商票号的发源地，柜台、账房与地下金库的格局保留完整。', 2.0, NULL),
    ('pingyao-plan',            1, 2, '下午 · 县衙与文庙', '县衙有升堂表演时段，文庙的大成殿是城内年代较早的建筑。', 2.0, '南大街早晚客流少，拍照更从容。'),
    ('yungang-grottoes-plan',   1, 0, '上午 · 第 5、6 窟', '两窟以整体雕刻与彩色装饰见长，是云冈保存较完整的一组。', 1.0, NULL),
    ('yungang-grottoes-plan',   1, 1, '中午 · 第 20 窟露天大佛', '标志性的造像，正面与侧面观感不同，露天的原因与崖壁坍塌有关。', 1.0, '洞窟内光线暗，拍照不要用闪光灯。'),
    ('yungang-grottoes-plan',   1, 2, '下午 · 其余洞窟与博物馆', '由东向西按编号看完主要洞窟，园区博物馆适合补背景。', 1.5, NULL),
    ('longmen-grottoes-plan',   1, 0, '上午 · 西山奉先寺', '卢舍那大佛是唐代造像的代表，西山窟龛最集中，先看这里最省时间。', 2.0, NULL),
    ('longmen-grottoes-plan',   1, 1, '下午 · 东山与香山寺', '过桥到东岸回望西山全景，香山寺、白园可一并走完。', 1.5, NULL),
    ('longmen-grottoes-plan',   1, 2, '傍晚 · 夜游时段', '有夜游时灯光下的造像与白天观感不同。', 1.0, '夜游是否开放以当日公告为准。'),
    ('mogao-caves-plan',        1, 0, '上午 · 数字展示中心', '先看球幕影片，了解洞窟的年代与题材，再进窟理解更完整。', 1.0, NULL),
    ('mogao-caves-plan',        1, 1, '上午后半 · 洞窟分组参观', '由讲解员带队分组进入，为控制洞窟内温湿度，洞内禁止拍照。', 2.5, '名额按场次放，旺季需提前安排。'),
    ('potala-palace-plan',      1, 0, '上午 · 白宫与壁画', '入口台阶多，慢走上行；白宫部分可看起居与办公的格局。', 1.5, NULL),
    ('potala-palace-plan',      1, 1, '上午后半 · 红宫灵塔与佛殿', '殿内壁画与灵塔是重点，宫内多数区域禁止拍照。', 1.5, NULL),
    ('potala-palace-plan',      1, 2, '下午 · 山下宗角禄康', '出宫后到山后龙王潭一带，可拍到宫殿背后的倒影。', 1.0, '海拔约 3700 米，当天不要排太满。'),
    ('mount-emei-plan',         1, 0, '上午 · 报国寺到清音阁', '山脚一带寺庙密集，伏虎寺、报国寺、清音阁可顺路看。', 3.0, NULL),
    ('mount-emei-plan',         1, 1, '下午 · 万年寺与洗象池方向', '沿中山区上行，这段是徒步与观光车结合的路段。', 3.0, '山上住宿需提前订。'),
    ('mount-emei-plan',         2, 0, '清晨 · 金顶看日出', '早班索道上金顶，十方普贤像、日出与云海能否看到取决于天气。', 2.0, '山顶气温远低于山脚，按冬季标准带衣服。'),
    ('mount-emei-plan',         2, 1, '上午 · 下山与猴区', '下山途中猴群活动频繁，食物与塑料袋要收好。', 2.0, '不要投喂，也不要手提敞口食品袋。'),
    ('leshan-buddha-plan',      1, 0, '上午 · 凌云山与佛头', '从景区入口上到佛头平台，可平视大佛头部，头部与山齐平。', 1.0, NULL),
    ('leshan-buddha-plan',      1, 1, '上午后半 · 九曲栈道下到佛脚', '沿崖壁栈道下行到脚背，脚背可容多人并立。', 1.5, '栈道排队时间长，节假日更明显。'),
    ('leshan-buddha-plan',      1, 2, '备选 · 江上观全景', '若栈道排队太久，可改乘船在汇流处远观大佛全貌。', 1.0, '两种方式视角不同，可只选其一。'),
    ('wudang-mountain-plan',    1, 0, '上午 · 太子坡与紫霄宫', '沿中轴线由低到高，太子坡的九曲黄河墙与紫霄宫的院落是重点。', 2.5, NULL),
    ('wudang-mountain-plan',    1, 1, '中午 · 南岩宫', '建在崖壁上的一处宫观，龙头香是常见取景点。', 1.5, NULL),
    ('wudang-mountain-plan',    1, 2, '下午 · 金顶太和宫', '可步行或乘索道上金顶，铜铸鎏金的宫殿是终点。', 2.0, '也可在山上住一晚，第二天看日出再下山。'),
    ('taishan-plan',            1, 0, '上午 · 红门到中天门', '登山主路的起始段，沿途碑刻、庙宇密集。', 2.5, '节奏放慢些，后面还有最陡的一段。'),
    ('taishan-plan',            1, 1, '中午 · 十八盘到南天门', '十八盘是最陡的一段，也是最费体力的一段。', 2.0, NULL),
    ('taishan-plan',            1, 2, '下午 · 玉皇顶与日观峰', '顶上视野开阔，天气好时可看到云海；主峰玉皇顶海拔 1545 米。', 1.5, '看日出需在山顶过夜或深夜上山。'),
    ('hongcun-plan',            1, 0, '清晨 · 月沼与民居', '半月形水塘四周是白墙黛瓦，清晨水面平静时倒影最完整。', 1.5, NULL),
    ('hongcun-plan',            1, 1, '上午 · 承志堂与南湖书院', '宅院的木雕与砖雕值得细看，南湖书院临南湖而建。', 1.5, NULL),
    ('hongcun-plan',            1, 2, '午后 · 南湖一线', '从南湖沿水系走回村口，可看清人工水系的分流走向。', 1.0, '水圳兼作生活用水，拍民居时不要打扰居民。'),
    ('ming-xiaoling-plan',      1, 0, '上午 · 下马坊到石象路', '神道自下马坊起，石象路两侧的石兽与秋色是南京常见的取景处。', 1.5, NULL),
    ('ming-xiaoling-plan',      1, 1, '中午 · 翁仲路与陵宫', '神道折向陵宫，主体建筑保留基址与部分复原。', 1.5, NULL),
    ('ming-xiaoling-plan',      1, 2, '下午 · 方城明楼', '可登方城明楼；与中山陵、灵谷寺同在钟山风景区内。', 1.0, NULL),
    ('temple-of-heaven-plan',   1, 0, '上午 · 圜丘坛与皇穹宇', '圜丘在南用于祭天，回音壁与三音石在皇穹宇一带。', 1.5, NULL),
    ('temple-of-heaven-plan',   1, 1, '上午后半 · 丹陛桥到祈年殿', '两坛之间由丹陛桥相连，祈年殿三重檐圆形殿身是北京的名片。', 1.5, NULL),
    ('temple-of-heaven-plan',   1, 2, '午后 · 园内古柏林', '古柏成片，清晨有大量市民在园中活动，氛围与其他景区不同。', 1.0, NULL),
    ('summer-palace-plan',      1, 0, '上午 · 东宫门进、长廊', '旺季从东宫门入最方便，长廊两侧梁枋彩画数量众多。', 2.0, NULL),
    ('summer-palace-plan',      1, 1, '中午 · 佛香阁与排云殿', '沿万寿山中轴上行，是俯瞰昆明湖的位置。', 1.5, NULL),
    ('summer-palace-plan',      1, 2, '下午 · 十七孔桥与南湖岛', '由东堤走到十七孔桥，也可乘园内游船换岸。', 1.5, NULL),
    ('summer-palace-plan',      1, 3, '傍晚 · 西堤看借景', '沿西堤往西可看到西山与玉泉山的借景。', 1.5, '环湖步行一圈约三小时，体力不足可只走东堤与西堤的一段。'),
    ('palace-museum-plan',      1, 0, '上午 · 午门到太和殿', '由午门入，中轴线依次是太和殿、中和殿、保和殿。', 1.5, NULL),
    ('palace-museum-plan',      1, 1, '中午 · 乾清宫与御花园', '后三宫与御花园的格局与前三殿不同，可对比着看。', 1.5, NULL),
    ('palace-museum-plan',      1, 2, '下午 · 专题馆择一', '书画、陶瓷、钟表等门类分馆陈列，半天时间建议只挑一个专题细看。', 2.0, '出口不可逆行，旺季务必提前预约。'),
    ('terracotta-army-plan',    1, 0, '上午 · 一号坑', '规模最大，以步兵与战车方阵为主，可沿参观廊道观看。', 1.5, NULL),
    ('terracotta-army-plan',    1, 1, '上午后半 · 三号坑与二号坑', '三号坑被认为是统帅机构，二号坑为多兵种混编。', 1.5, NULL),
    ('terracotta-army-plan',    1, 2, '中午 · 铜车马与文物陈列', '陶俑出土时原有彩绘，因接触空气而脱落，陈列里有相关说明。', 1.0, NULL),
    ('huaqing-palace-plan',     1, 0, '下午 · 唐代汤池遗址', '园内保留唐代汤池与建筑基址，是这处离宫的核心。', 1.5, NULL),
    ('huaqing-palace-plan',     1, 1, '下午 · 五间厅', '西安事变发生地，弹痕与办公陈设保留在原址。', 1.0, NULL),
    ('huaqing-palace-plan',     1, 2, '傍晚 · 骊山索道与兵谏亭', '索道上山后可到兵谏亭、老母殿一带，俯瞰临潼。', 2.0, '晚间有园林实景演出，需另行购票。'),
    ('huashan-plan',            1, 0, '上午 · 西峰索道上山', '西峰索道通向西峰下，上站海拔高，省去最长的一段爬升。', 1.0, NULL),
    ('huashan-plan',            1, 1, '中午 · 南峰与东峰', '南峰落雁峰海拔 2154 米为最高峰，东峰一线有下棋亭等看点。', 4.0, '长空栈道、鹞子翻身需单独的安全装备与排队，恐高者慎行。'),
    ('huashan-plan',            1, 2, '下午 · 北峰索道下山', '由北峰索道下山，比原路返回省时间。', 2.0, '索道末班时间随季节调整，上山前先确认。'),
    ('badaling-great-wall-plan', 1, 0, '上午 · 关城与北段城墙', '北段坡度较陡，八达岭到北八楼是多数人走的路线。', 2.0, NULL),
    ('badaling-great-wall-plan', 1, 1, '中午 · 南段漫步', '南段人流相对少，适合想避开人群时走。', 1.5, '可乘市郊铁路或缆车、滑车上下；节假日建议早到。'),
    ('wuzhen-plan',             1, 0, '下午 · 东栅街巷', '东栅保留较多原住民生活场景，街巷较窄、白天热闹。', 3.0, NULL),
    ('wuzhen-plan',             1, 1, '傍晚 · 西栅夜景', '西栅入夜后河道、石桥与灯影连成一片，是主要看点。', 3.0, NULL),
    ('wuzhen-plan',             2, 0, '清晨 · 西栅晨间与展馆', '住一晚后清晨人少，可看草木本色染坊、昭明书院等展馆。', 3.0, NULL),
    ('zhouzhuang-plan',         1, 0, '上午 · 双桥与沿河民居', '双桥由一座石拱桥与一座石梁桥相连，是镇内最典型的取景处。', 1.5, NULL),
    ('zhouzhuang-plan',         1, 1, '上午后半 · 沈厅与张厅', '明清宅院的砖雕门楼与厅堂格局保存较好。', 2.0, NULL),
    ('zhouzhuang-plan',         1, 2, '午后 · 摇橹船', '从水面看沿河民居，角度与街上不同。', 1.0, '早晚游客较少，中午前后最挤。'),
    ('xitang-plan',             1, 0, '上午 · 沿河廊棚', '河边廊棚总长近千米，是西塘与别处水乡最大的不同。', 2.0, NULL),
    ('xitang-plan',             1, 1, '午后 · 石桥连线', '石桥密度较高，送子来凤桥、五福桥是常见取景点。', 1.5, NULL),
    ('xitang-plan',             1, 2, '傍晚 · 入夜灯笼', '入夜后沿河灯笼亮起，氛围更贴近居民生活。', 1.5, NULL),
    ('changbai-mountain-plan',  1, 0, '上午 · 北坡上山看天池', '北坡换乘越野车上山，天池能否看到取决于天气，云雾常年较重。', 4.0, '山上风大，加一件防风外套。'),
    ('changbai-mountain-plan',  1, 1, '下午 · 长白瀑布与聚龙温泉', '瀑布与温泉在同一片区，可顺路走完。', 2.0, '泡温泉需另行安排时间。'),
    ('changbai-mountain-plan',  2, 0, '上午 · 地下森林与西坡台阶', '地下森林是谷底林区，西坡台阶最多。', 4.0, '换坡需要额外路程，也可只走一处。'),
    ('kanas-plan',              1, 0, '上午 · 湖区三湾', '卧龙湾、月亮湾、神仙湾由区间车串联，湖水会随季节与光线呈现不同颜色。', 3.0, NULL),
    ('kanas-plan',              1, 1, '下午 · 观鱼台与湖岸', '登观鱼台俯瞰湖区全貌，午后光线更适合看水色。', 3.0, NULL),
    ('kanas-plan',              2, 0, '全天 · 禾木村', '图瓦人村落，清晨与傍晚的炊烟与木屋是常见画面。', 6.0, '村内住宿需提前订。'),
    ('kanas-plan',              3, 0, '上午 · 白哈巴与返程', '距离主要城市较远，最后一天留给返程。', 4.0, '9 月下旬秋色最好，也最冷。'),
    ('yinxu-plan',              1, 0, '上午 · 宫殿宗庙区', '商代晚期都城遗址的核心，甲骨刻辞是汉字的早期形态。', 1.5, NULL),
    ('yinxu-plan',              1, 1, '上午后半 · 妇好墓与车马坑', '墓葬与车马坑在原址展示，配合博物馆一起看理解更完整。', 1.5, NULL),
    ('yinxu-plan',              1, 2, '下午 · 王陵区', '位于洹河北岸，与宫殿区隔河相望。', 1.0, '两区之间需要乘车。'),
    ('orange-isle-plan',        1, 0, '上午 · 洲头与雕像', '洲头的青年毛泽东雕像与江面是主要看点，隔江与岳麓山相对。', 1.5, NULL),
    ('orange-isle-plan',        1, 1, '中午 · 观光小火车与洲尾', '园内有观光小火车串联洲头与洲尾，步行也可。', 1.5, NULL),
    ('orange-isle-plan',        1, 2, '下午 · 岳麓山一线', '与岳麓山、岳麓书院同一片区，可通过橘子洲大桥步行往返。', 2.0, '周六晚间常有焰火表演，以当年公告为准。'),
    ('hangzhou-songcheng-plan', 1, 0, '下午 · 宋代街市', '街上有杂技、木偶、皮影等定时演出与手作店铺。', 2.0, NULL),
    ('hangzhou-songcheng-plan', 1, 1, '傍晚 · 室内大型演出', '时长约一小时，是园区的核心内容。', 1.5, '演出票与园区门票的搭配方式按季节调整，购票时看清包含内容。'),
    ('daocheng-yading-plan',    1, 0, '上午 · 冲古寺与珍珠海', '短线从冲古寺上到珍珠海，是看仙乃日的常见位置，强度较小。', 3.0, NULL),
    ('daocheng-yading-plan',    1, 1, '下午 · 镇上休整', '海拔普遍在 4000 米以上，第一天下午留在镇上适应，备好第二天的热量与饮水。', 2.0, '不要在第一天就加排别的目的地。'),
    ('daocheng-yading-plan',    2, 0, '全天 · 洛绒牛场到牛奶海', '长线需先乘观光车到洛绒牛场，再步行或骑马，途中经牛奶海、五色海。', 7.0, '高海拔徒步强度大，需按自身状况安排并预留适应时间。'),
    ('oriental-pearl-tower-plan', 1, 0, '傍晚 · 下球体与玻璃廊道', '其中有一段玻璃观景廊道可俯瞰地面。', 1.5, NULL),
    ('oriental-pearl-tower-plan', 1, 1, '入夜 · 上球体看外滩', '可看到外滩与黄浦江转弯处，夜景比白天更值得上。', 1.0, NULL),
    ('oriental-pearl-tower-plan', 1, 2, '夜间 · 陆家嘴环形天桥', '塔下即天桥，可与上海中心、金茂大厦串联游览。', 1.0, NULL),
    ('liangzhu-plan',           1, 0, '上午 · 良渚博物院', '馆藏玉琮、玉璧等器物，先看这里再看遗址更容易理解。', 2.0, NULL),
    ('liangzhu-plan',           1, 1, '下午 · 古城遗址公园', '由古城、水利系统与外围聚落组成，园内以展示性与复原性场景为主。', 2.5, NULL),
    ('liangzhu-plan',           1, 2, '傍晚 · 水坝与湿地一线', '可乘观光车在城址与湿地之间移动，看水利系统的位置关系。', 1.0, '按博物院在前、公园在后的顺序安排更顺。'),
    ('fenghuang-plan',          1, 0, '白天 · 虹桥与石板街', '虹桥、跳岩、万名塔沿沱江一线分布，石板街两侧店铺集中。', 2.0, NULL),
    ('fenghuang-plan',          1, 1, '傍晚 · 沿江吊脚楼', '临江吊脚楼保存较好，入夜后江边灯影与倒影是常见拍摄画面。', 1.5, NULL),
    ('fenghuang-plan',          1, 2, '择时 · 名人故居', '沈从文故居等具体景点通常需要另行购票。', 1.5, '进入古城本身不收费。'),
    ('sanxingdui-museum-plan',  1, 0, '上午 · 青铜大立人与神树', '新馆展陈面积大，青铜大立人、青铜神树、金杖依次陈列。', 2.0, NULL),
    ('sanxingdui-museum-plan',  1, 1, '上午后半 · 纵目面具与金器', '造型与中原风格差异明显，是古蜀国祭祀坑的代表器物。', 1.0, NULL),
    ('sanxingdui-museum-plan',  1, 2, '下午 · 遗址区', '遗址年代大致相当于中原的商代，与博物馆相邻。', 1.0, NULL),
    ('shaanxi-history-museum-plan', 1, 0, '上午 · 史前到秦汉', '基本陈列按年代铺开，前半段看周秦的青铜与礼制。', 1.5, NULL),
    ('shaanxi-history-museum-plan', 1, 1, '中午 · 隋唐部分', '唐代器物最集中，金银器是重点。', 1.5, NULL),
    ('shaanxi-history-museum-plan', 1, 2, '下午 · 专题馆择一', '唐代壁画珍品馆等专题馆需单独购票。', 1.0, '馆内人流较大，建议预约并尽量在开馆时段入馆。'),
    ('national-museum-plan',    1, 0, '上午 · 古代中国（前半）', '从旧石器时代到秦汉，按年代铺开。', 1.5, NULL),
    ('national-museum-plan',    1, 1, '中午 · 古代中国（后半）', '隋唐到清末部分，全程看完约需三小时。', 1.5, NULL),
    ('national-museum-plan',    1, 2, '下午 · 专题展', '可挑一个当期专题展补充。', 1.0, '免费参观但需提前实名预约；一层有多处寄存与休息区域。'),
    ('shanghai-museum-plan',    1, 0, '上午 · 青铜馆', '青铜收藏是分量最重的一门，先看这里。', 1.5, NULL),
    ('shanghai-museum-plan',    1, 1, '中午 · 陶瓷与书画', '陶瓷、书法、绘画三门可连着看，按兴趣决定停留时间。', 1.5, '人民广场馆与浦东东馆需分别预约，一天内不建议赶两馆。'),
    ('suzhou-museum-plan',      1, 0, '上午 · 新馆建筑与主庭院', '片石假山与主庭院的取景角度常被拍照。', 1.5, NULL),
    ('suzhou-museum-plan',      1, 1, '中午 · 吴地文物展厅', '馆藏以吴地文物、书画与工艺品为主。', 1.5, NULL),
    ('suzhou-museum-plan',      1, 2, '下午 · 忠王府', '太平天国忠王府部分保留原有格局。', 1.0, '免费参观需预约；紧邻拙政园与狮子林，可顺路安排。'),
    ('canton-tower-plan',       1, 0, '傍晚 · 高层观光层', '观光层在 400 米以上，可看珠江与城市天际线。', 1.5, NULL),
    ('canton-tower-plan',       1, 1, '入夜 · 高空项目', '摩天轮与极速云霄等高空项目需另外安排时间与排队。', 1.0, NULL),
    ('canton-tower-plan',       1, 2, '夜间 · 珠江夜游', '塔下是夜游的主要码头之一，可把登塔与夜游安排在同一个晚上。', 1.5, '隔江北望是珠江新城的花城广场与广州大剧院。'),
    ('lingyin-temple-plan',     1, 0, '上午 · 飞来峰造像', '崖壁上分布着五代至宋元的石刻造像三百余尊，进景区先看这里。', 1.5, NULL),
    ('lingyin-temple-plan',     1, 1, '上午后半 · 灵隐寺中轴线', '天王殿、大雄宝殿、药师殿、藏经楼依次排布。', 1.5, '进入景区与进入寺院需分别购票，飞来峰景区在前。'),
    ('the-bund-plan',           1, 0, '黄昏 · 外白渡桥到南京东路', '从外白渡桥向南走视角较完整，一侧是各国风格的历史建筑。', 1.5, NULL),
    ('the-bund-plan',           1, 1, '入夜 · 观景平台看陆家嘴', '观景平台分上下两层，上层视野更开阔且不收费。', 1.0, NULL),
    ('the-bund-plan',           1, 2, '夜间 · 亮灯后的江边', '日落后亮灯，对岸隔江可见东方明珠与上海中心。', 1.0, '节假日与晚间人流集中。'),
    ('hulunbuir-plan',          1, 0, '上午 · 海拉尔到莫日格勒河', '莫日格勒河曲流是草原上最常见的取景处。', 4.0, NULL),
    ('hulunbuir-plan',          1, 1, '下午 · 额尔古纳湿地', '夏季与初秋最为上镜，河曲与牧草是主要景致。', 3.0, NULL),
    ('hulunbuir-plan',          2, 0, '全天 · 恩和与室韦', '沿边境一线北行，途中以草原与林区过渡的景观为主。', 6.0, '昼夜温差大，需带外套。'),
    ('hulunbuir-plan',          3, 0, '上午 · 返程', '一线通常需要三到四天，最后一段留给返程。', 4.0, NULL),
    ('shanghai-disney-plan',    1, 0, '开园 · 热门项目', '开园前排队入园可省不少时间，创极速光轮与加勒比海盗是常被提到的项目。', 3.0, NULL),
    ('shanghai-disney-plan',    1, 1, '午后 · 演出与巡游', '七个主题园区之间的演出与巡游按当日时间表安排。', 3.0, NULL),
    ('shanghai-disney-plan',    1, 2, '闭园前 · 烟花表演', '烟花表演通常在闭园前举行，提前在城堡前占位。', 1.0, '门票按日期分档，需提前在官方渠道预约。'),
    ('chimelong-ocean-kingdom-plan', 1, 0, '开园 · 鲸鲨馆', '巨型展缸与前后的观赏廊道是主要看点，建议开园先去。', 2.0, NULL),
    ('chimelong-ocean-kingdom-plan', 1, 1, '午后 · 剧场表演', '海豚、白鲸等剧场按场次开演。', 2.0, '入园后先看时间表，按场次排顺序。'),
    ('chimelong-ocean-kingdom-plan', 1, 2, '傍晚 · 花车巡游与焰火', '傍晚有花车巡游与焰火表演。', 1.5, '邻接横琴口岸，可与澳门行程衔接。'),
    ('universal-beijing-plan',  1, 0, '开园 · 哈利·波特的魔法世界', '热门项目排队时间长，开园后先去这一片。', 3.0, NULL),
    ('universal-beijing-plan',  1, 1, '午后 · 变形金刚与侏罗纪', '园区提供付费的快速通行产品，按排队情况决定是否使用。', 3.0, NULL),
    ('universal-beijing-plan',  1, 2, '夜间 · 城市大道', '城市大道可单独进入，夜间餐饮与商店营业到较晚。', 1.5, NULL),
    ('window-of-the-world-plan', 1, 0, '上午 · 欧洲区与铁塔', '微缩景观按比例缩小后集中呈现，埃菲尔铁塔是园区地标。', 2.0, NULL),
    ('window-of-the-world-plan', 1, 1, '午后 · 亚洲与非洲区', '按区域布置，顺路走不易重复。', 2.0, NULL),
    ('window-of-the-world-plan', 1, 2, '傍晚 · 美洲与大洋洲区', '金字塔、悉尼歌剧院等集中在这些片区。', 1.5, NULL),
    ('window-of-the-world-plan', 1, 3, '入夜 · 灯光秀与巡游', '晚间有灯光秀与巡游，节假日另有专场演出。', 1.0, '园区面积较大，园内交通能省不少体力。'),
    ('qinghai-lake-plan',       1, 0, '上午 · 湖东到湖西', '沿环湖公路西行，湖面与远山一路相随。', 4.0, NULL),
    ('qinghai-lake-plan',       1, 1, '下午 · 油菜花与湖畔', '每年夏季湖畔油菜花与湖水相接是主要拍摄场景。', 2.0, '湖边风大，注意保暖。'),
    ('qinghai-lake-plan',       2, 0, '上午 · 湖西到湖东收尾', '鸟岛等区域在繁殖期会限流或关闭。', 4.0, '湖面海拔约 3200 米，初到者宜留出适应时间。'),
    ('lijiang-river-plan',      1, 0, '上午 · 竹筏或游船启程', '喀斯特峰丛夹岸，桂林至阳朔一段约 83 公里，是最典型的山水景致。', 3.0, NULL),
    ('lijiang-river-plan',      1, 1, '中午 · 兴坪一带', '兴坪是二十元人民币背面图案的取景处，也是常见的下船点。', 1.0, NULL),
    ('lijiang-river-plan',      1, 2, '下午 · 阳朔收尾', '也可在杨堤、兴坪分段乘竹筏。', 2.0, '枯水期水位偏低，部分航段会调整或改用其他码头。'),
    ('shanghai-natural-history-museum-plan', 1, 0, '上午 · 起源之谜与生命长河', '从顶层的宇宙与地球起源看起，往下进入生命长河展区，大型恐龙骨架与古生物复原集中在这一段。', 2.0, '展线单向，中途折返要走回头路，先把这段看完。'),
    ('shanghai-natural-history-museum-plan', 1, 1, '中午 · 馆内休息', '展馆与静安雕塑公园相连，天气好可以到园内坐一会儿再回馆。', 1.0, NULL),
    ('shanghai-natural-history-museum-plan', 1, 2, '下午 · 演化之道与大地探珍', '这一段以生物演化与矿物标本为主，互动展项集中，孩子停留时间通常最长。', 2.0, NULL),
    ('shanghai-natural-history-museum-plan', 1, 3, '收尾 · 临展与商店', '临时展按当期主题更换，出馆前看一眼当天还有哪些场次。', 0.5, NULL),
    ('nanjing-museum-plan',       1, 0, '上午 · 历史馆', '按年代自史前走到明清，江苏一带的出土文物是主线。', 2.0, NULL),
    ('nanjing-museum-plan',       1, 1, '中午 · 院内休息', '院落里有可以坐下的地方，午间人流比开馆时少。', 0.5, NULL),
    ('nanjing-museum-plan',       1, 2, '下午 · 民国馆与艺术馆', '民国馆做成街景式展陈，艺术馆以书画与工艺为主。', 2.0, NULL),
    ('nanjing-museum-plan',       1, 3, '收尾 · 特展馆', '当期特展的主题与档期会变，按现场海报决定是否再看一处。', 1.0, '各馆之间步行有距离，穿舒服的鞋。'),
    ('hubei-museum-plan',         1, 0, '上午 · 曾侯乙墓展厅', '编钟、尊盘与九鼎八簋集中在这里，是全院的核心。', 2.0, '人多时先从侧面的柜位看起，回头再补正面的展品。'),
    ('hubei-museum-plan',         1, 1, '中午 · 编钟演奏', '演奏按场次进行，进馆先记下当天的场次时间，按点回到演奏厅。', 0.5, '场次与票价以馆内公告为准。'),
    ('hubei-museum-plan',         1, 2, '下午 · 楚文化与专题馆', '越王勾践剑、元青花四爱图梅瓶等分散在不同展厅，按导览图顺路走。', 2.0, NULL),
    ('henan-museum-plan',         1, 0, '上午 · 史前与夏商周', '贾湖骨笛、杜岭方鼎与妇好鸮尊在这一段，青铜器是主体。', 2.0, NULL),
    ('henan-museum-plan',         1, 1, '中午 · 馆内休息', '馆内有休息区，餐饮集中在农业路一带。', 1.0, NULL),
    ('henan-museum-plan',         1, 2, '下午 · 汉唐与宋元', '陶瓷、玉器与画像石集中在这一段，与上一段接得上。', 2.0, NULL),
    ('henan-museum-plan',         1, 3, '收尾 · 临时展', '当期展览的主题会更换，出馆前按海报看一眼。', 0.5, NULL),
    ('hunan-museum-plan',         1, 0, '上午 · 马王堆汉墓陈列', 'T 形帛画、素纱襌衣与成套漆器集中在这里，墓葬结构在同一区内做了复原。', 2.5, '展厅光线偏暗，看清细节要靠近展柜。'),
    ('hunan-museum-plan',         1, 1, '中午 · 馆内休息', '馆内有休息区，周边东风路一带餐饮较多。', 1.0, NULL),
    ('hunan-museum-plan',         1, 2, '下午 · 青铜与长沙窑', '商周青铜器与长沙窑瓷器是另外两条线，可以按兴趣二选一。', 1.5, NULL),
    ('jinsha-site-museum-plan',   1, 0, '上午 · 遗迹馆', '保留的祭祀区考古现场按原状展示，成堆象牙与祭祀坑的位置都在这里。', 1.5, NULL),
    ('jinsha-site-museum-plan',   1, 1, '中午 · 园区休息', '两馆之间的绿地可以坐下，天气好时适合放慢节奏。', 0.5, NULL),
    ('jinsha-site-museum-plan',   1, 2, '下午 · 陈列馆', '太阳神鸟金饰、金面具与玉器是核心展品，太阳神鸟图案后来成为中国文化遗产标志。', 2.0, '展柜反光明显，看金饰的细节要换个角度。'),
    ('guangdong-museum-plan',     1, 0, '上午 · 广东历史文化陈列', '按时间顺序梳理广东的历史脉络，海上贸易与侨乡是其中的两条线。', 2.0, NULL),
    ('guangdong-museum-plan',     1, 1, '中午 · 花城广场', '出馆即是花城广场，餐饮与休息都在附近。', 1.0, NULL),
    ('guangdong-museum-plan',     1, 2, '下午 · 潮州木雕与端砚', '木雕与端砚各占一个展厅，陶瓷陈列在同一层附近，可以连着看。', 1.5, NULL),
    ('guangdong-museum-plan',     1, 3, '收尾 · 外墙与广场', '各展厅分布在不同楼层，按导览图走可以少走回头路；出馆后可以顺路看建筑外墙。', 0.5, NULL),
    ('china-science-technology-museum-plan', 1, 0, '上午 · 华夏之光与探索发现', '从古代技术与基础物理看起，机械与光学类的展项集中在这一段。', 2.0, NULL),
    ('china-science-technology-museum-plan', 1, 1, '中午 · 馆内休息', '馆内有休息区，奥林匹克公园一带餐饮集中在南侧。', 1.0, NULL),
    ('china-science-technology-museum-plan', 1, 2, '下午 · 科技与生活 · 挑战与未来', '这一段以能源、信息与航天为主，动手展项多，排队时间也更长。', 2.0, '孩子年龄偏小时可以先到儿童科学乐园，那里单独分场。'),
    ('guangzhou-chimelong-plan',  1, 0, '第一天上午 · 野生动物世界乘车区', '乘园区车辆穿过放养区，之后再换步行路线看展区。', 3.0, '放养区不能下车，拍摄隔着玻璃或栏杆。'),
    ('guangzhou-chimelong-plan',  1, 1, '第一天下午 · 步行展区与缆车', '步行区按区域分布，缆车可以居高看整片园区。', 3.0, NULL),
    ('guangzhou-chimelong-plan',  2, 0, '第二天 · 欢乐世界', '大型游乐设施集中在几处片区，热门项目排队时间最长。', 5.0, '节假日排队时间长，开园即入园。'),
    ('guangzhou-chimelong-plan',  2, 1, '第二天傍晚 · 水乐园或返程', '天气热时可以加玩水乐园，或者提前返程避开散场高峰。', 2.0, NULL),
    ('happy-valley-beijing-plan', 1, 0, '开园 · 热门项目', '开园后先排排队最长的几项，上午的等待时间明显短于午后。', 3.0, '身高与健康限制按各项目公告执行。'),
    ('happy-valley-beijing-plan', 1, 1, '午后 · 演艺与室内项目', '剧场与巡游按当日时间表演出，室内项目适合避开最晒的时段。', 2.5, NULL),
    ('happy-valley-beijing-plan', 1, 2, '傍晚 · 夜场与返程', '部分时段开放夜场，灯光与演出跟白天不同，也可以此时离园避开高峰。', 2.0, NULL),
    ('shanghai-haichang-park-plan', 1, 0, '开园 · 大型展缸', '开园先看人少的展缸，鲸鲨与企鹅展区通常上午更从容。', 2.0, NULL),
    ('shanghai-haichang-park-plan', 1, 1, '中午 · 演艺场次', '虎鲸与海豚等演出按场次进行，提前到场才有好位置。', 2.0, '场次与座位以园内公告为准。'),
    ('shanghai-haichang-park-plan', 1, 2, '下午 · 游乐设施与巡游', '过山车一类的设施集中在部分区域，午后可以按排队情况挑着玩。', 2.5, NULL),
    ('happy-valley-shenzhen-plan', 1, 0, '上午 · 大型项目', '过山车一类的项目集中在几处片区，上午排队相对短。', 3.0, NULL),
    ('happy-valley-shenzhen-plan', 1, 1, '午后 · 亲子区与演艺', '面向低龄观众的区域与剧场演出多安排在午后。', 2.5, NULL),
    ('happy-valley-shenzhen-plan', 1, 2, '傍晚 · 夜场或转场世界之窗', '部分时段有夜场；若不留夜场，可以步行到相邻的世界之窗看夜间灯光。', 1.5, NULL),
    ('happy-valley-wuhan-plan',   1, 0, '上午 · 主园区大型项目', '开园后先玩排队最长的几项。', 3.0, NULL),
    ('happy-valley-wuhan-plan',   1, 1, '午后 · 演艺与室内项目', '剧场与室内项目适合避开中午的高温。', 2.0, NULL),
    ('happy-valley-wuhan-plan',   1, 2, '下午 · 水公园或返程', '想玩水公园需另购票，两园之间的衔接以步行和园内交通为主。', 3.0, '夏季防晒与补水要提前准备。'),
    ('happy-valley-chengdu-plan', 1, 0, '上午 · 大型项目', '先排最热门的几项，之后按片区顺路走。', 3.0, NULL),
    ('happy-valley-chengdu-plan', 1, 1, '午后 · 亲子区与剧场', '面向儿童的区域与剧场演出多集中在午后。', 2.5, NULL),
    ('happy-valley-chengdu-plan', 1, 2, '傍晚 · 夜场或返程', '节假日前后可能安排夜场，按当日公告决定。', 1.5, NULL),
    ('happy-valley-chongqing-plan', 1, 0, '上午 · 户外大型项目', '天气好时先玩过山车一类的户外项目。', 3.0, NULL),
    ('happy-valley-chongqing-plan', 1, 1, '午后 · 室内项目与演艺', '雨天上半天可以反过来，先玩室内再看天气。', 2.5, '重庆夏季午后常有阵雨，随身带伞。'),
    ('happy-valley-chongqing-plan', 1, 2, '傍晚 · 返程', '园区离市区有距离，返程按轨道交通与自驾的末班时间安排。', 1.0, NULL),
    ('hongkong-disneyland-plan',  1, 0, '开园 · 热门项目', '开园后先进最里面的一片区域，由内往外玩可以少走回头路。', 3.0, '门票按日期分档，需提前在官方渠道购买。'),
    ('hongkong-disneyland-plan',  1, 1, '午后 · 巡游与剧场', '巡游与剧场演出按当日时间表进行，提前在路线旁占位。', 3.0, NULL),
    ('hongkong-disneyland-plan',  1, 2, '夜间 · 夜间演出与烟花', '闭园前的夜间演出是固定安排，城堡前的区域人流最密。', 1.5, '散场时地铁与专线都很拥挤，可以晚走一会儿。'),
    ('shanghai-tower-plan',       1, 0, '下午 · 登观光层', '选在傍晚前上楼，可以在同一场里看到白天与亮灯后的两种景。', 1.5, '能见度低时视野会打折，出发前先看天气。'),
    ('shanghai-tower-plan',       1, 1, '傍晚 · 滨江步道', '从陆家嘴走到江边，对岸是外滩的历史建筑群，亮灯后与白天差别很大。', 1.5, NULL),
    ('citic-tower-plan',          1, 0, '下午 · 国贸一带街面', '从光华路一带看楼体的收分轮廓，附近几座塔楼可以一并比较。', 1.0, NULL),
    ('citic-tower-plan',          1, 1, '傍晚 · 亮灯后的天际线', '入夜后楼体灯光与周边建筑形成一组轮廓，适合拍照。', 1.0, NULL),
    ('ping-an-finance-center-plan', 1, 0, '下午 · 登观光层', '晴天时能见度高，靠窗一侧可以看清福田的中轴与街道格局。', 1.5, NULL),
    ('ping-an-finance-center-plan', 1, 1, '傍晚 · 市民中心与中轴', '从塔下步行到市民中心一带，两侧是图书馆与音乐厅等公共建筑。', 1.5, NULL),
    ('hongya-cave-plan',          1, 0, '下午 · 分层走一遍', '上层临沧白路、下层临江，各层由街道与步道连通，先弄清出入口。', 1.5, NULL),
    ('hongya-cave-plan',          1, 1, '傍晚 · 江边看亮灯', '灯光亮起后从江边看整片楼体与倒影，是最常被拍的视角。', 1.0, '晚间人流集中，节假日常有限流。'),
    ('hongya-cave-plan',          1, 2, '晚上 · 周边收尾', '沿滨江路一带可以继续走，附近就是解放碑方向。', 1.0, NULL),
    ('yellow-crane-tower-plan',   1, 0, '上午 · 登楼', '五层逐层上行，各层陈列碑刻与楹联，向东可以望见长江与武汉长江大桥。', 1.5, NULL),
    ('yellow-crane-tower-plan',   1, 1, '中午 · 园区其他建筑', '白云阁等建筑在同一片园区内，可以顺路走。', 1.0, NULL),
    ('yellow-crane-tower-plan',   1, 2, '下午 · 长江大桥步行', '出园后可以上桥步行一段，从桥上回望蛇山与楼体。', 1.5, '桥上风大，注意保暖与安全。'),
    ('tianjin-eye-plan',          1, 0, '傍晚 · 河岸散步', '沿三岔河口一带的河岸走，两岸是天津的老城方向。', 1.0, NULL),
    ('tianjin-eye-plan',          1, 1, '入夜 · 乘摩天轮', '封闭座舱转一圈约半小时，最高处可以俯瞰海河两岸。', 0.5, '热门时段需要排队，提前到场取号或购票。'),
    ('tianjin-eye-plan',          1, 2, '夜 · 沿河收尾', '下轮后沿岸边继续走一段，灯光下的河面是常见的拍摄对象。', 1.0, NULL),
    ('xian-bell-tower-plan',      1, 0, '下午 · 登钟楼', '楼内陈列钟与鼓，四面看出去是四条大街延伸的方向。', 1.0, NULL),
    ('xian-bell-tower-plan',      1, 1, '傍晚 · 鼓楼与周边街区', '步行到鼓楼，周边是餐饮集中的街区。', 2.0, NULL),
    ('xian-bell-tower-plan',      1, 2, '入夜 · 回看亮灯', '夜间亮灯后从街面看楼体，是城墙内常见的拍摄对象。', 0.5, NULL),
    ('macau-tower-plan',          1, 0, '下午 · 观景层', '高区观景层可以俯瞰澳门半岛、氹仔与珠海方向。', 1.0, NULL),
    ('macau-tower-plan',          1, 1, '接着 · 户外项目', '高飞跳与空中漫步需另行预约，参加前先确认当日的开放与天气条件。', 1.5, '项目有健康与年龄限制，按现场规定执行。'),
    ('macau-tower-plan',          1, 2, '傍晚 · 南湾湖一带', '从塔下步行到南湾湖畔，傍晚的湖面与对岸建筑是常见的拍摄场景。', 1.5, NULL),
    ('shenyang-imperial-palace-plan',   1, 0, '上午 · 中路', '从大清门进，过大政殿与十王亭，向北到崇政殿与凤凰楼一带。', 1.5, '八旗与左右翼王亭的排列是这里最特别的地方。'),
    ('shenyang-imperial-palace-plan',   1, 1, '下午 · 东路与西路', '东路是大政殿周边的院落，西路有文溯阁等建筑。', 1.0, NULL),
    ('shenyang-imperial-palace-plan',   1, 2, '收尾 · 老城街巷', '出宫后是中街一带的老城街巷，可以顺路走一段。', 0.5, NULL),
    ('palace-museum-of-manchukuo-plan', 1, 0, '上午 · 勤民楼与缉熙楼', '办公楼与起居楼按原状布置，室内陈设不能触碰。', 1.5, NULL),
    ('palace-museum-of-manchukuo-plan', 1, 1, '中午 · 同德殿与庭院', '同德殿体量最大，内部陈列与庭院可以一并看。', 1.0, NULL),
    ('palace-museum-of-manchukuo-plan', 1, 2, '下午 · 专题陈列', '专题陈列说明那段历史的来龙去脉，内容偏文字，按体力取舍。', 1.5, NULL),
    ('harbin-saint-sophia-cathedral-plan', 1, 0, '傍晚 · 外观与广场', '红砖墙体与绿色穹顶在傍晚侧光下最清楚，广场一带可以绕行一圈。', 0.5, NULL),
    ('harbin-saint-sophia-cathedral-plan', 1, 1, '入内 · 展览', '内部现用作展览空间，展品以城市历史的图片为主。', 0.5, NULL),
    ('harbin-saint-sophia-cathedral-plan', 1, 2, '夜间 · 亮灯与中央大街', '亮灯后回广场再看一次，之后步行到中央大街一带收尾。', 1.5, '冬季路面结冰, 走慢一些。'),
    ('inner-mongolia-museum-plan',      1, 0, '上午 · 远古世界', '恐龙与哺乳动物化石集中在自然部分，标本体量都不小。', 1.5, NULL),
    ('inner-mongolia-museum-plan',      1, 1, '中午 · 馆内休息', '馆内有休息区，周边新华东街一带有餐饮。', 1.0, NULL),
    ('inner-mongolia-museum-plan',      1, 2, '下午 · 草原雄风与草原天骄', '民族部分按时期陈列，游牧器具、服饰与宗教用品是主要内容。', 2.0, NULL),
    ('shanxi-museum-plan',              1, 0, '上午 · 晋国霸业', '晋侯墓地出土器物成组陈列，鸟尊一类的青铜器集中在这一段。', 2.0, NULL),
    ('shanxi-museum-plan',              1, 1, '中午 · 馆内休息', '主馆一层有休息区与文创店，午间人流少一些。', 1.0, NULL),
    ('shanxi-museum-plan',              1, 2, '下午 · 北朝与晋商', '北朝壁画、佛教造像与晋商文物分列不同展厅，按兴趣取舍。', 2.0, NULL),
    ('hebei-museum-plan',               1, 0, '上午 · 满城汉墓', '刘胜与窦绾墓的随葬品集中展出，玉衣与宫灯是核心展品。', 2.0, '展厅光线偏暗, 看细节要靠近展柜。'),
    ('hebei-museum-plan',               1, 1, '中午 · 馆内休息', '馆内一层有休息区，周边东大街一带有餐饮。', 1.0, NULL),
    ('hebei-museum-plan',               1, 2, '下午 · 战国中山与燕赵故事', '中山国与燕赵两条线各占展厅，可以按兴趣挑一段。', 1.5, NULL),
    ('zhaozhou-bridge-plan',            1, 0, '上午 · 桥面与拱券', '沿桥面走一趟，再到桥侧看主拱与两端小拱的关系。', 1.0, '看桥侧会走到水边, 注意湿滑。'),
    ('zhaozhou-bridge-plan',            1, 1, '接着 · 陈列馆', '陈列馆展出桥梁史料与历次修缮替换下来的构件。', 1.0, NULL),
    ('zhaozhou-bridge-plan',            1, 2, '收尾 · 县城方向', '赵县县城内还有其他古迹，时间宽裕时可以顺路安排。', 0.5, NULL),
    ('shandong-museum-plan',            1, 0, '上午 · 史前与龙山文化', '蛋壳黑陶的器壁极薄，是这一段最常被提到的器物。', 2.0, NULL),
    ('shandong-museum-plan',            1, 1, '中午 · 馆内休息', '馆内有休息区，周边经十路一带有餐饮。', 1.0, NULL),
    ('shandong-museum-plan',            1, 2, '下午 · 汉画像石与佛教造像', '画像石与造像分列展厅，可以连着看。', 1.5, NULL),
    ('baotu-spring-plan',               1, 0, '上午 · 趵突泉园区', '泉池中的三股水是主要看点，园内其他泉池与建筑顺路走。', 1.5, '雨季与秋季水位较高, 涌势更明显。'),
    ('baotu-spring-plan',               1, 1, '中午 · 周边街巷', '园外是济南老城一带，餐饮集中。', 1.0, NULL),
    ('baotu-spring-plan',               1, 2, '下午 · 护城河一带', '沿护城河步道向东，一路可以看到取水的市民与另一处泉群。', 1.5, NULL),
    ('zhanqiao-pier-plan',              1, 0, '上午 · 栈桥与回澜阁', '沿栈桥走到尽头的八角亭，两侧是青岛湾。', 1.0, '冬季桥上风大, 注意保暖。'),
    ('zhanqiao-pier-plan',              1, 1, '中午 · 中山路一带', '从桥北端步行到中山路，周边是老城的商业街与旧建筑。', 1.5, NULL),
    ('zhanqiao-pier-plan',              1, 2, '傍晚 · 回到海边', '傍晚再回到栈桥一带，退潮时桥旁会有礁石与沙滩露出。', 1.0, NULL),
    ('anhui-museum-plan',               1, 0, '上午 · 安徽文明史', '青铜器集中在这一段，楚大鼎体量最大。', 2.0, NULL),
    ('anhui-museum-plan',               1, 1, '中午 · 馆内休息', '馆内有休息区，周边怀宁路一带有餐饮。', 1.0, NULL),
    ('anhui-museum-plan',               1, 2, '下午 · 徽州古建筑与文房四宝', '砖木雕件与原状构件是徽州部分的主要内容，文房部分另有专厅。', 1.5, NULL),
    ('tengwang-pavilion-plan',          1, 0, '下午 · 登阁', '各层陈列诗文与图画，登到高层看赣江与南昌城的轮廓。', 1.5, NULL),
    ('tengwang-pavilion-plan',          1, 1, '傍晚 · 园区与江边', '园区内另有附属建筑与庭院，出园后可以沿江边走一段。', 1.5, '夜间亮灯后楼体轮廓更清楚。'),
    ('three-lanes-seven-alleys-plan',   1, 0, '下午 · 主街南后街', '沿主街走一遍，两侧是商铺与各条巷子的入口。', 1.0, NULL),
    ('three-lanes-seven-alleys-plan',   1, 1, '接着 · 坊巷与故居', '挑两三处开放的宅院进去，看天井、厅堂与马鞍墙。', 2.0, '部分院落仍有人居住, 参观时保持安静。'),
    ('three-lanes-seven-alleys-plan',   1, 2, '傍晚 · 街区收尾', '傍晚亮灯后街巷氛围不同，可以再走一小段。', 1.0, NULL),
    ('gulangyu-island-plan',            1, 0, '上午 · 日光岩', '登高看全岛与厦门岛方向，台阶较陡，量力而行。', 2.0, '旺季登顶需要排队。'),
    ('gulangyu-island-plan',            1, 1, '中午 · 岛上街巷', '沿龙头路一带解决午饭，这一片是岛上最热闹的一段。', 1.5, NULL),
    ('gulangyu-island-plan',            1, 2, '下午 · 老别墅与菽庄花园', '按街巷走看各国风格的老建筑，菽庄花园临海而建。', 3.0, '渡轮班次需提前安排, 晚班船较挤。'),
    ('stone-forest-plan',               1, 0, '上午 · 大石林', '石峰最高最密，主步道穿行其间，部分路段要上下石阶。', 3.0, '石间小路易走岔, 跟着指示走。'),
    ('stone-forest-plan',               1, 1, '中午 · 园区休息', '园区内有休息与餐饮点，正午日照强。', 1.0, NULL),
    ('stone-forest-plan',               1, 2, '下午 · 小石林', '草地与石峰相间，那座形似人物的石峰在这一片。', 2.0, NULL),
    ('jiaxiu-pavilion-plan',            1, 0, '下午 · 楼体与浮玉桥', '从桥上走到楼前，看三层三重檐的结构与它在河中的位置。', 1.0, NULL),
    ('jiaxiu-pavilion-plan',            1, 1, '傍晚 · 河岸步道', '沿南明河两岸的步道走一段，周边是市区街巷。', 1.0, NULL),
    ('jiaxiu-pavilion-plan',            1, 2, '入夜 · 回看亮灯', '亮灯后河面有倒影，是常见的拍摄视角。', 0.5, NULL),
    ('guangxi-museum-of-nationalities-plan', 1, 0, '上午 · 民族陈列', '服饰、织锦与建筑构件按民族分列。', 2.0, NULL),
    ('guangxi-museum-of-nationalities-plan', 1, 1, '接着 · 铜鼓', '铜鼓集中陈列，数量较多，可以看到不同形制的差别。', 1.0, NULL),
    ('guangxi-museum-of-nationalities-plan', 1, 2, '下午 · 馆外村寨', '馆外的民族村寨式建筑与原状民居适合慢慢走。', 1.5, NULL),
    ('gansu-provincial-museum-plan',    1, 0, '上午 · 丝绸之路文明', '铜奔马与同出的铜车马仪仗队集中在这一段，另有简牍与织物。', 2.0, NULL),
    ('gansu-provincial-museum-plan',    1, 1, '中午 · 馆内休息', '馆内有休息区，周边西津西路一带有餐饮。', 1.0, NULL),
    ('gansu-provincial-museum-plan',    1, 2, '下午 · 彩陶与古生物', '彩陶按年代排列，从大地湾到马家窑连成一条线。', 1.5, NULL),
    ('western-xia-tombs-plan',          1, 0, '上午 · 博物馆与陈列馆', '先看展陈了解西夏与陵区布局，后面的现场会好懂很多。', 1.5, NULL),
    ('western-xia-tombs-plan',          1, 1, '中午 · 陵区主要点位', '在三号陵等主要点位下车看陵塔与陵城遗迹。', 2.0, '戈壁上没有遮阴, 带水与防晒。'),
    ('western-xia-tombs-plan',          1, 2, '返程 · 贺兰山下', '返程时可以从远处看整片陵区与贺兰山的轮廓。', 1.0, NULL),
    ('kumbum-monastery-plan',           1, 0, '上午 · 大金瓦殿一带', '核心殿堂与叩拜区都在这一片，人流集中。', 1.5, '宗教场所内按指示着装与拍摄。'),
    ('kumbum-monastery-plan',           1, 1, '中午 · 酥油花馆', '用彩色酥油塑成的造像与故事场景陈列在馆内。', 1.0, NULL),
    ('kumbum-monastery-plan',           1, 2, '下午 · 其他殿堂与塔', '沿山势向上分布的其他殿堂与如意宝塔顺序走过。', 1.5, NULL),
    ('xinjiang-regional-museum-plan',   1, 0, '上午 · 西域历史', '按时间顺序梳理，织锦、文书与钱币是主要内容。', 2.0, NULL),
    ('xinjiang-regional-museum-plan',   1, 1, '接着 · 古代干尸陈列', '出土于吐鲁番、罗布泊一带的古代遗体与随葬品在这一部分。', 1.0, '展厅内请保持安静。'),
    ('xinjiang-regional-museum-plan',   1, 2, '下午 · 民族风情', '服饰与生活器具按民族分列，可以按体力取舍。', 1.5, NULL),
    ('tianyi-pavilion-plan',            1, 0, '上午 · 藏书楼与院落', '两层硬山顶的藏书楼与院中的水池假山是这处园林的核心。', 1.5, NULL),
    ('tianyi-pavilion-plan',            1, 1, '接着 · 碑廊与专题陈列', '园内移入的碑刻与专题陈列分布在多个院落。', 1.0, NULL),
    ('tianyi-pavilion-plan',            1, 2, '下午 · 月湖一带', '出馆后可以步行到月湖周边，老城街巷与小桥连成一片。', 1.0, NULL),
    ('yandang-mountain-plan',           1, 0, '第一天 · 灵峰', '白天看岩峰与洞壑，同一处岩峰换个角度形态差别很大。', 3.0, NULL),
    ('yandang-mountain-plan',           1, 1, '第一天夜间 · 灵峰夜景', '夜景是当地常见的安排，跟着指示走。', 1.5, '夜间路暗, 台阶要看清。'),
    ('yandang-mountain-plan',           2, 0, '第二天上午 · 灵岩', '灵岩一带以峰与寺为主，另有高空表演按场次进行。', 2.5, NULL),
    ('yandang-mountain-plan',           2, 1, '第二天下午 · 大龙湫', '瀑布落差较大，水量随季节变化明显。', 2.5, '枯水期水量小, 观感差别较大。'),
    ('yuantouzhu-plan',                 1, 0, '上午 · 樱花区', '樱花集中的片区在春季人流最密，早进园更从容。', 2.0, '花期短, 出发前先看当年花讯。'),
    ('yuantouzhu-plan',                 1, 1, '中午 · 湖边休息', '环湖一带路况平缓，餐饮集中在主要入口附近。', 1.0, NULL),
    ('yuantouzhu-plan',                 1, 2, '下午 · 乘船与鹿顶山', '可乘船到湖中岛屿，也可以上鹿顶山俯瞰太湖。', 2.0, NULL),
    ('foshan-ancestral-temple-plan',    1, 0, '上午 · 中轴建筑', '从万福台进，经灵应牌坊到正殿，逐处看装饰构件。', 1.5, NULL),
    ('foshan-ancestral-temple-plan',    1, 1, '接着 · 屋脊与陶塑', '正殿屋顶的瓦脊上有成排陶塑人物，需要抬头细看。', 0.5, NULL),
    ('foshan-ancestral-temple-plan',    1, 2, '下午 · 黄飞鸿纪念馆与叶问堂', '同一片区域内有武术与醒狮相关的陈列，醒狮表演按场次进行。', 1.5, NULL),
    ('quanzhou-kaiyuan-temple-plan',    1, 0, '上午 · 大殿与月台', '殿前月台的须弥座上有狮身人面浮雕，廊柱中混有印度教石刻构件。', 1.5, NULL),
    ('quanzhou-kaiyuan-temple-plan',    1, 1, '接着 · 东西塔', '两座宋代石塔在寺外两侧，塔身浮雕保存较好。', 1.0, NULL),
    ('quanzhou-kaiyuan-temple-plan',    1, 2, '下午 · 西街', '出寺即是西街，老城街巷与小吃集中在这一带。', 1.5, NULL)
) AS m(plan_slug, day_no, sort, title, detail, duration_hours, tip)
JOIN attraction_plan p ON p.slug = m.plan_slug;

COMMIT;
