"""用户动态区: 发一条、按景点或作者看一列、删自己的。

为什么没有账号体系也能有「作者」
--------------------------------
本项目唯一的匿名身份来源是前端 localStorage 里的 device_id, 服务端把它映射成
app_user 一行(与 app/api/events.py 同一套写法)。动态挂在这行上, 于是「同一个人」
= 同一个 device_id。这不是认证: 谁拿到别人的 device_id 就能冒名。但动态是公开内容,
冒名发帖最坏的后果是一条可以被下架的帖子; 为了它上手机号+密码+找回那一整套,
与「景点大全」的定位不成比例。将来真要接账号, 把 user_id 接上即可, 表结构不用改。

为什么这里可以直出自增 id, 行程却必须用 token
---------------------------------------------
行程那条路用 token, 是因为 id 递增能遍历**所有人的需求原文** —— 那是私密内容。
动态是公开内容, 本来就写给所有人看, 藏 id 换不来任何安全, 只挡住正经用法。

删除是硬删, 下架是软删
----------------------
作者删自己的动态 = DELETE, 一行不留, 顺手把当天名额还给他(删了就不该继续占着位置)。
运营下架 = update post set status = 'hidden'(见 db/README.md), 内容留着, 列表不再返回。
两者不能合成一个开关: 前者是用户撤回自己的话, 后者是平台收走别人的话, 留痕要求不同。

翻页
----
列表按 **id 倒序**(也就是插入顺序)取, 游标是"你已经看到的那条的 id" —— 再要下一页就带
`before=<id>`。界面上的「加载更多」一律走它: 这个列表的头部一直在长, 偏移分页的第二页
会整体下移一格, 已经看过的那条被再摆一遍; 删一条则相反, 会有一条被跳过。

为什么不用 (created_at, id) 这种更像时间线的游标 —— 实测踩过: 时间戳在测试库的 SQLite
上只存到秒, 而绑进去的参数带微秒, 两边做行值比较时第一段永远"小于", id 那一半的平局
规则根本轮不上, 同一秒里的行会被重复吐出来。本仓库的用例跑 SQLite、生产跑 PostgreSQL,
不能只在一边对。id 是整数, 两种库比出来一样, 发新帖删旧帖都不影响已经翻过的位置。

偏移那一支(page/size)留着给"跳到第 N 页"用, 两种给法只能挑一个。

限流
----
按东八区自然日计数。计数器与行程共用 trip_quota 表, 但 owner_key 带 post: 前缀 ——
发动态吃不掉生成行程的名额, 反过来也一样。见 app/quota.py。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import quota
from ..config import Settings, get_settings
from ..db import get_db
from ..models import AppUser, Attraction, Post
from ..schemas import PostAttractionOut, PostAuthorOut, PostIn, PostOut, PostPage

router = APIRouter(prefix="/posts", tags=["posts"])

DISCLAIMER = "动态由用户发布, 只代表发布者本人, 不代表本站观点。"

# 没给 device_id 时的兜底标识。与 quota.owner_key_for 落下的 d:anonymous 是同一个身份,
# 「匿名发的动态」与「匿名占的名额」始终指向同一行
ANONYMOUS_DEVICE = "anonymous"
DEFAULT_AUTHOR = "游客"
# 限额作用域与删除权限共用这一个前缀: 只加命名空间, 不改 quota 里的口径。
# 动态一律按 app_user.id 计(即 post:u:<id>): 作者行本身就是身份, 按 device_id 计
# 会与删除路径对不上。
OWNER_PREFIX = "post:"

REASON_DAILY_LIMIT = "daily_limit_exceeded"


def _owner_key(user_id: int | None, device_id: str | None) -> str:
    return OWNER_PREFIX + quota.owner_key_for(user_id, device_id)


def _rejected(limit: int) -> HTTPException:
    """429 的 detail 与行程那条路同形, 前端可以复用同一段提示逻辑。"""
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "status": "rejected",
            "reason": REASON_DAILY_LIMIT,
            "retry_after": quota.retry_after(),
            "limit": limit,
        },
    )


def _resolve_user(db: Session, *, user_id: int | None, device_id: str | None) -> AppUser:
    """按 user_id 或 device_id 找作者行, 没有就建一个。

    user_id 给了就必须真实存在 —— 与行程接口同口径, 404 而不是悄悄新建一个。
    """
    if user_id is not None:
        user = db.get(AppUser, user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
        return user
    device = device_id or ANONYMOUS_DEVICE
    user = db.scalar(select(AppUser).where(AppUser.device_id == device))
    if user is None:
        user = AppUser(device_id=device)
        db.add(user)
        db.flush()
    return user


def _is_author(db: Session, row: Post, *, user_id: int | None, device_id: str | None) -> bool:
    """请求者是不是这条动态的作者。一个身份都给不出来就直接否掉。

    两个都给了就都得对上: 宁可错拒, 不可错放。
    """
    if user_id is None and not device_id:
        return False
    if user_id is not None and user_id != row.user_id:
        return False
    if device_id:
        owner_id = db.scalar(select(AppUser.id).where(AppUser.device_id == device_id))
        if owner_id != row.user_id:
            return False
    return True


def _to_out(row: Post, *, viewer_user_id: int | None) -> PostOut:
    attraction = None
    live = row.attraction
    if live is not None:
        # 景点下架或归档就不给链接(点了会 404), 但名字照显 —— 那是发布时的快照
        slug = live.slug if live.status == "published" else None
        attraction = PostAttractionOut(
            slug=slug,
            name=row.attraction_name or live.name,
            name_en=live.name_en if slug else None,
        )
    elif row.attraction_name:
        # 景点被硬删了(外键 SET NULL), 快照名字还在
        attraction = PostAttractionOut(slug=None, name=row.attraction_name)
    return PostOut(
        id=row.id,
        author=PostAuthorOut(name=row.author_name or DEFAULT_AUTHOR),
        body=row.body,
        attraction=attraction,
        created_at=row.created_at,
        mine=viewer_user_id is not None and row.user_id == viewer_user_id,
    )


def _page_out(
    items: list[PostOut],
    *,
    page: int,
    size: int,
    total: int,
    settings: Settings,
    used: int | None,
    next_cursor: int | None = None,
) -> PostPage:
    return PostPage(
        items=items,
        page=page,
        size=size,
        total=total,
        daily_limit=settings.post_daily_limit,
        used_today=used,
        disclaimer=DISCLAIMER,
        next_cursor=next_cursor,
    )


@router.get("", response_model=PostPage, summary="动态列表")
def list_posts(
    page: int = Query(1, ge=1),
    size: int | None = Query(None, ge=1, description="默认取配置值, 上限 max_page_size"),
    before: int | None = Query(
        None,
        ge=1,
        description="只取 id 比它小的, 「加载更多」用: 把上一页的 next_cursor 原样带回来",
    ),
    attraction: str | None = Query(None, description="只看挂在这个景点(slug)下的动态"),
    device_id: str | None = Query(None, description="只看这个设备发的: 精确匹配, 用于「我的」"),
    viewer: str | None = Query(None, description="谁在看, 只用来算 mine"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PostPage:
    """只出 status = 'visible' 的动态, 按时间倒序。

    两个筛选都是**精确匹配**, 不做自由文本搜索: 库里的动态量级用不上全文索引,
    而模糊匹配只会把「找这个景点的动态」变成「找含这两个字的动态」。

    翻页: `page`/`size` 是偏移, `before` 是游标(id), 两种给法**只能挑一个** —— 一起给
    说不清从哪儿开始, 与其猜不如报错。响应里的 next_cursor 就是给 `before` 用的。
    """
    size_limit = min(size or settings.default_page_size, settings.max_page_size)

    if before is not None and page != 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="page 与 before 只能给一个"
        )

    # 没给 viewer 就拿 device_id 顶: 按设备筛选这件事本来就只发生在"我自己的动态"这一处。
    # 判断错了也没有安全后果 —— mine 只是前端要不要显示删除按钮, 真删的时候服务端再查一次。
    me = viewer or device_id
    viewer_user_id = db.scalar(select(AppUser.id).where(AppUser.device_id == me)) if me else None
    # 当天已用几个名额(给前端算"今天还能发几条")。键与发帖、删除两处一致, 都按作者行 id;
    # 没有作者行 = 一条都没发过 = 0。没给身份就不查, 也就不报。
    used = None
    if me:
        used = (
            quota.used(db, owner_key=_owner_key(viewer_user_id, None), day=quota.today())
            if viewer_user_id
            else 0
        )

    # 过滤条件复用给 count 与取数两条语句, 免得"数出来"和"列出来"不是同一批
    filters: list = [Post.status == "visible"]

    if attraction:
        attr_id = db.scalar(select(Attraction.id).where(Attraction.slug == attraction))
        if attr_id is None:
            # 没这个 slug: 空列表比"返回全站动态"更接近用户的意思
            return _page_out([], page=page, size=size_limit, total=0, settings=settings, used=used)
        filters.append(Post.attraction_id == attr_id)

    if device_id:
        owner_id = db.scalar(select(AppUser.id).where(AppUser.device_id == device_id))
        if owner_id is None:
            return _page_out([], page=page, size=size_limit, total=0, settings=settings, used=used)
        filters.append(Post.user_id == owner_id)

    if before is not None:
        # 与下面的 order_by 同序(都是 id), 所以不会重复也不会跳
        filters.append(Post.id < before)

    total = db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
    # 多取一条来判断"还有没有更旧的"。用 total 也能算, 但那样偏移与游标两支要各写一套
    # 判断(游标那支还能不能用 total 得想一下) —— 统一成"多取一条"更不容易写歪。
    rows = db.scalars(
        select(Post)
        .where(*filters)
        .options(selectinload(Post.attraction))
        # 按 id 倒序 = 插入顺序。列表与游标必须同序, 否则游标指哪儿都是错的
        .order_by(Post.id.desc())
        # 游标已经指明了从哪儿开始, 再叠一个偏移就成了"游标之后再跳 N 条", 不是本意
        .offset(0 if before is not None else (page - 1) * size_limit)
        .limit(size_limit + 1)
    ).all()

    has_more = len(rows) > size_limit
    rows = rows[:size_limit]

    return _page_out(
        [_to_out(row, viewer_user_id=viewer_user_id) for row in rows],
        page=page,
        size=size_limit,
        total=int(total),
        settings=settings,
        used=used,
        next_cursor=rows[-1].id if has_more and rows else None,
    )


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED, summary="发一条动态")
def create_post(
    payload: PostIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PostOut:
    """发一条动态。可以挂一个**已发布**景点, 不存任何定位。"""
    attraction = None
    if payload.attraction_slug:
        attraction = db.scalar(select(Attraction).where(Attraction.slug == payload.attraction_slug))
        # 未发布/草稿的景点不给挂: 挂了等于把它提前公开给所有人
        if attraction is None or attraction.status != "published":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="景点不存在或未发布")

    # 作者先解析: 这一步会 404(给了一个不存在的 user_id), 不该让这种请求占掉当天名额
    user = _resolve_user(db, user_id=payload.user_id, device_id=payload.device_id)

    # 计数器键统一取作者行 id, 不按"这次请求给的是谁"算: 删除那条路只有 user_id,
    # 两边必须落在同一个桶上, 否则删完名额还不回去(这个 bug 真出现过)。
    owner_key = _owner_key(user.id, None)
    # 扣名额在落库之前。反过来就是"先发出去再判断超没超", 超了还得把已经公开的内容回滚掉
    if not quota.consume_slot(
        db, owner_key=owner_key, day=quota.today(), limit=settings.post_daily_limit
    ):
        raise _rejected(settings.post_daily_limit)

    user.last_seen_at = datetime.now(timezone.utc)
    if payload.nickname:
        # 记下来, 下次发不用重填; 但每条动态的署名仍是各自的快照
        user.nickname = payload.nickname

    row = Post(
        user_id=user.id,
        author_name=payload.nickname or user.nickname or DEFAULT_AUTHOR,
        body=payload.body.strip(),
        attraction_id=attraction.id if attraction is not None else None,
        attraction_name=attraction.name if attraction is not None else None,
    )
    db.add(row)
    db.flush()
    db.commit()
    db.refresh(row)
    return _to_out(row, viewer_user_id=user.id)


@router.delete(
    "/{post_id}", status_code=status.HTTP_204_NO_CONTENT, summary="作者删除自己的动态"
)
def delete_post(
    post_id: int,
    device_id: str | None = Query(None, max_length=200),
    user_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """只有作者能删, 而且是硬删(见文件头)。

    不是作者一律 404, 不区分"不存在"与"不是你的" —— 后者能让人拿 id 试出谁发过什么。
    删掉就把当天名额还回去: 那一格不该继续占着。
    """
    row = db.get(Post, post_id)
    if row is None or not _is_author(db, row, user_id=user_id, device_id=device_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="动态不存在")

    db.delete(row)
    db.commit()
    # user_id 非空, owner_key_for 会走 u: 那一支, 不需要再查作者的 device_id
    quota.release_slot(db, owner_key=_owner_key(row.user_id, None), day=quota.today())
    return Response(status_code=status.HTTP_204_NO_CONTENT)
