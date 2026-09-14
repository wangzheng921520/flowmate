import os
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


load_dotenv()


app = FastAPI(
    title="FlowMate Tool API",
    version="0.1.0",
)


# =========================
# 环境变量
# =========================

LARK_APP_ID = os.environ["LARK_APP_ID"]

LARK_APP_SECRET = os.environ["LARK_APP_SECRET"]


BITABLE_APP_TOKEN = os.environ["BITABLE_APP_TOKEN"]

BITABLE_TABLE_ID = os.environ["BITABLE_TABLE_ID"]


FLOWMATE_TOOL_KEY = os.environ["FLOWMATE_TOOL_KEY"]


FEISHU_CALENDAR_ID = os.environ.get(
    "FEISHU_CALENDAR_ID",
    "primary"
)


FEISHU_API = "https://open.feishu.cn/open-apis"



_token_cache = {
    "token": "",
    "expires_at": 0.0,
}



# =========================
# 数据模型
# =========================


class TaskSearchRequest(BaseModel):

    project: str = ""

    status: str = ""

    owner: str = ""




class CalendarCreateRequest(BaseModel):

    title: str

    start_time: str

    duration_minutes: int = 60

    project: str = ""

    # 正在与机器人对话的用户 open_id
    user_open_id: str




# =========================
# 获取飞书token
# =========================


async def get_tenant_access_token() -> str:


    now = time.time()



    if (

        _token_cache["token"]

        and _token_cache["expires_at"] > now + 60

    ):

        return str(
            _token_cache["token"]
        )



    async with httpx.AsyncClient(timeout=30) as client:


        response = await client.post(

            f"{FEISHU_API}/auth/v3/tenant_access_token/internal",

            json={

                "app_id": LARK_APP_ID,

                "app_secret": LARK_APP_SECRET,

            },

        )


        response.raise_for_status()


        data = response.json()



    if data.get("code") != 0:


        raise RuntimeError(

            f"获取飞书Token失败：{data}"

        )



    _token_cache["token"] = data["tenant_access_token"]


    _token_cache["expires_at"] = (

        now

        +

        int(data.get("expire", 7200))

    )



    return str(
        _token_cache["token"]
    )





# =========================
# 数据格式转换
# =========================



def convert_to_timestamp(
    time_str: str
) -> str:

    """
    将 ISO 时间转换成飞书需要的 Unix timestamp
    """

    dt = datetime.fromisoformat(
        time_str
    )


    timestamp = int(
        dt.timestamp()
    )


    return str(timestamp)





def normalize_value(
    value: Any
) -> str:


    if value is None:

        return ""



    if isinstance(value, str):

        return value



    if isinstance(value, bool):

        return "是" if value else "否"



    if isinstance(value, (int, float)):


        if value > 1_000_000_000_000:


            return datetime.fromtimestamp(

                value / 1000

            ).strftime(
                "%Y-%m-%d"
            )


        return str(value)



    if isinstance(value, list):

        return ", ".join(

            normalize_value(item)

            for item in value

        )



    if isinstance(value, dict):


        for key in (

            "text",

            "name",

            "value"

        ):


            if key in value:


                return normalize_value(

                    value[key]

                )



        return str(value)



    return str(value)





# =========================
# 查询多维表格
# =========================


async def fetch_records() -> list[dict]:


    token = await get_tenant_access_token()



    url = (

        f"{FEISHU_API}/bitable/v1/apps/"

        f"{BITABLE_APP_TOKEN}/tables/"

        f"{BITABLE_TABLE_ID}/records/search"

    )



    headers = {


        "Authorization":

        f"Bearer {token}",


        "Content-Type":

        "application/json",

    }



    async with httpx.AsyncClient(timeout=30) as client:


        response = await client.post(

            url,

            headers=headers,

            params={

                "page_size": 500

            },

            json={},

        )



        response.raise_for_status()


        data = response.json()



    if data.get("code") != 0:


        raise RuntimeError(

            f"读取多维表格失败:{data}"

        )



    return data.get(

        "data",

        {}

    ).get(

        "items",

        []

    )
# =========================
# 工具KEY验证
# =========================


def verify_key(
    x_tool_key: str
):

    if x_tool_key != FLOWMATE_TOOL_KEY:

        raise HTTPException(

            status_code=401,

            detail="Invalid tool key",

        )





# =========================
# 健康检查
# =========================


@app.get("/health")
async def health() -> dict:

    return {

        "status": "ok",

        "service": "flowmate",

    }


# =========================
# 测试获取飞书用户 open_id
# =========================

@app.get("/test/user")
async def test_user():

    token = await get_tenant_access_token()

    url = f"{FEISHU_API}/contact/v3/users/find_by_department"

    print("请求URL:", url)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    params = {
        "department_id": "0",
        "page_size": 10
    }

    print("请求参数:", params)

    async with httpx.AsyncClient(timeout=30) as client:

        response = await client.get(
            url,
            headers=headers,
            params=params
        )

    print("飞书返回:", response.text)

    return response.json()



# =========================
# 查询任务接口
# =========================


@app.post("/tools/tasks/search")
async def search_tasks(

    request: TaskSearchRequest,

    x_tool_key: str = Header(default=""),

) -> dict:


    verify_key(x_tool_key)



    records = await fetch_records()



    results = []



    for record in records:


        fields = record.get(
            "fields",
            {}
        )


        project = normalize_value(
            fields.get("项目")
        )


        status = normalize_value(
            fields.get("状态")
        )


        owner = normalize_value(
            fields.get("负责人")
        )



        if (
            request.project
            and request.project.lower()
            not in project.lower()
        ):

            continue



        if (
            request.status
            and request.status.lower()
            not in status.lower()
        ):

            continue



        if (
            request.owner
            and request.owner.lower()
            not in owner.lower()
        ):

            continue



        results.append({

            "record_id":
            record.get("record_id"),


            "project":
            project,


            "task":
            normalize_value(
                fields.get("任务")
            ),


            "owner":
            owner,


            "status":
            status,


            "priority":
            normalize_value(
                fields.get("优先级")
            ),


            "due_date":
            normalize_value(
                fields.get("截止日期")
            ),


            "progress":
            normalize_value(
                fields.get("进度")
            ),


            "risk":
            normalize_value(
                fields.get("风险")
            ),


            "weekly_progress":
            normalize_value(
                fields.get("本周进展")
            ),

        })



    return {

        "count":
        len(results),


        "filters":
        request.model_dump(),


        "tasks":
        results,

    }







# =========================
# 创建飞书日历事件
# 创建后自动把用户加入参与人
# =========================

@app.post("/tools/calendar/create")
async def create_calendar_event(
    request: CalendarCreateRequest,
    x_tool_key: str = Header(default=""),
) -> dict:

    verify_key(x_tool_key)

    print("==============================")
    print("开始创建飞书日程")
    print("标题:", request.title)
    print("开始时间:", request.start_time)
    print("用户 open_id:", request.user_open_id)
    print(
        "用户 open_id repr:",
        repr(request.user_open_id)
    )
    print("日历 ID:", FEISHU_CALENDAR_ID)
    print("==============================")

    # --------------------------------
    # 1. 检查用户 open_id
    # --------------------------------

    if not request.user_open_id.startswith("ou_"):

        raise HTTPException(
            status_code=400,
            detail=(
                "user_open_id 错误，"
                "必须是 ou_ 开头的飞书用户 open_id"
            ),
        )

    # --------------------------------
    # 2. 获取飞书 tenant token
    # --------------------------------

    token = await get_tenant_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":
            "application/json; charset=utf-8",
    }

    # --------------------------------
    # 3. 时间转换
    # --------------------------------

    try:

        start_dt = datetime.fromisoformat(
            request.start_time.replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail=(
                "start_time格式错误。"
                "示例："
                "2026-08-15T15:00:00+08:00"
            ),
        )

    end_dt = (
        start_dt
        + timedelta(
            minutes=request.duration_minutes
        )
    )

    # --------------------------------
    # 4. 创建日程
    # --------------------------------

    create_url = (
        f"{FEISHU_API}/calendar/v4/"
        f"calendars/{FEISHU_CALENDAR_ID}/"
        f"events"
    )

    create_body = {

        "summary": request.title,

        "description": (
            f"FlowMate自动创建\n"
            f"项目：{request.project}"
        ),

        "need_notification": True,

        "start_time": {
            "timestamp": str(
                int(start_dt.timestamp())
            ),
            "timezone": "Asia/Shanghai",
        },

        "end_time": {
            "timestamp": str(
                int(end_dt.timestamp())
            ),
            "timezone": "Asia/Shanghai",
        },

        "visibility": "default",

        "attendee_ability":
            "can_see_others",
    }

    print("创建日程请求:")
    print(create_body)

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        create_response = await client.post(

            create_url,

            headers=headers,

            params={
                "user_id_type":
                    "open_id"
            },

            json=create_body,
        )

    print(
        "创建日程 HTTP 状态:",
        create_response.status_code
    )

    print(
        "创建日程完整返回:",
        create_response.text
    )

    create_response.raise_for_status()

    create_data = (
        create_response.json()
    )

    if create_data.get("code") != 0:

        raise HTTPException(
            status_code=400,
            detail={
                "step":
                    "create_event",
                "feishu":
                    create_data,
            },
        )

    event = (
        create_data
        .get("data", {})
        .get("event", {})
    )

    event_id = event.get(
        "event_id"
    )

    if not event_id:

        raise HTTPException(
            status_code=500,
            detail=(
                "飞书返回创建成功，"
                "但没有event_id"
            ),
        )

    print("创建成功 event_id:")
    print(event_id)

    # --------------------------------
    # 5. 添加真人用户为参与人
    # --------------------------------

    attendee_url = (
        f"{FEISHU_API}/calendar/v4/"
        f"calendars/{FEISHU_CALENDAR_ID}/"
        f"events/{event_id}/attendees"
    )

    attendee_body = {

        "attendees": [
            {
                "type": "user",
                "user_id":
                    request.user_open_id,
            }
        ],

        "need_notification": True,
    }

    print("添加参与人请求:")
    print(attendee_body)

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        attendee_response = (
            await client.post(
                attendee_url,

                headers=headers,

                params={
                    "user_id_type":
                        "open_id"
                },

                json=attendee_body,
            )
        )

    print(
        "添加参与人 HTTP 状态:",
        attendee_response.status_code
    )

    print(
        "添加参与人完整返回:",
        attendee_response.text
    )

    attendee_response.raise_for_status()

    attendee_data = (
        attendee_response.json()
    )

    if attendee_data.get("code") != 0:

        raise HTTPException(
            status_code=400,
            detail={
                "step":
                    "add_attendee",
                "feishu":
                    attendee_data,
                "event_id":
                    event_id,
            },
        )

    # --------------------------------
    # 6. 再查询参与人进行验证
    # --------------------------------

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        check_response = await client.get(

            attendee_url,

            headers=headers,

            params={
                "user_id_type":
                    "open_id",

                "page_size": 100,
            },
        )

    print(
        "查询参与人 HTTP 状态:",
        check_response.status_code
    )

    print(
        "查询参与人完整返回:",
        check_response.text
    )

    check_data = {}

    try:
        check_data = (
            check_response.json()
        )
    except Exception:
        pass

    # --------------------------------
    # 7. 全部成功后才返回
    # --------------------------------

    return {

        "success": True,

        "message":
            "日程创建成功，并已添加用户为参与人",

        "calendar_id":
            FEISHU_CALENDAR_ID,

        "event":
            event,

        "added_user_open_id":
            request.user_open_id,

        "attendee_result":
            attendee_data,

        "attendee_check":
            check_data,
    }