-- Have-A-Trip · 种子数据
--
-- 一期 50 个景点, 全部为自采的公开事实信息, 不引入任何第三方数据集,
-- 以便「将来可闭源」。判断见 docs/LICENSE-AUDIT.md 第三节。
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
--   * attraction_image 一条都不插 —— 没有可靠出处的图不进仓库; 有出处时逐条带
--     credit 与 license(两列均为 NOT NULL)。
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
    ('theme-park',    '主题乐园',  70)
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
    ('amusement',             '游乐项目'  )
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
    ('hangzhou-songcheng',       'indoor'                )
) AS m(attraction_slug, tag_slug)
JOIN attraction a ON a.slug = m.attraction_slug
JOIN tag t        ON t.slug = m.tag_slug
ON CONFLICT DO NOTHING;

COMMIT;
