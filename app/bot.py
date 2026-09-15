import asyncio
import os
import re
from typing import Dict

import httpx
from dotenv import load_dotenv

from app.lark_channel import FeishuChannel


load_dotenv()

LARK_APP_ID = os.environ["LARK_APP_ID"]
LARK_APP_SECRET = os.environ["LARK_APP_SECRET"]

DIFY_API_KEY = os.environ["DIFY_API_KEY"]

DIFY_API_BASE = os.getenv(
    "DIFY_API_BASE",
    "https://api.dify.ai/v1",
)

print("DIFY_BASE:", DIFY_API_BASE)
print("KEY长度:", len(DIFY_API_KEY))

channel = FeishuChannel(
    app_id=LARK_APP_ID,
    app_secret=LARK_APP_SECRET,
)


# 保存飞书用户和Dify会话关系
conversation_map: Dict[str, str] = {}



def clean_think(text: str) -> str:
    """
    删除DeepSeek等模型输出的<think>内容
    """

    if not text:
        return ""

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.S
    )

    return text.strip()



async def call_dify(
    query: str,
    user_id: str,
) -> str:


    conversation_id = conversation_map.get(
        user_id,
        ""
    )


    payload = {

        "inputs": {
            "feishu_user_id": user_id
        },

        "query": query,

        "response_mode": "blocking",

        "user": user_id,

    }


    # 有历史会话才传
    if conversation_id:

        payload["conversation_id"] = conversation_id



    headers = {

        "Authorization":
            f"Bearer {DIFY_API_KEY}",

        "Content-Type":
            "application/json",

    }



    print("==========调用Dify==========")
    print(payload)



    try:

        async with httpx.AsyncClient(
            timeout=120
        ) as client:


            response = await client.post(

                f"{DIFY_API_BASE}/chat-messages",

                headers=headers,

                json=payload,

            )



            print(
                "Dify状态:",
                response.status_code
            )


            print(
                "Dify返回:",
                response.text
            )



            response.raise_for_status()


            data=response.json()



        new_id=data.get(
            "conversation_id"
        )


        if new_id:

            conversation_map[user_id]=new_id



        answer=data.get(
            "answer",
            ""
        )


        return clean_think(answer)



    except Exception as e:

        print("========== Dify调用异常 ==========")

        print("异常类型:", type(e))

        print("异常详情:", repr(e))

        import traceback
        traceback.print_exc()

        return "Dify调用失败，请检查配置。"





async def on_message(msg):


    print(
        "进入消息处理函数"
    )


    print(
        vars(msg)
    )



    text=msg.content_text



    print(
        "收到文本:"
    )

    print(text)



    print(
        "当前用户open_id:",
        msg.sender_open_id
    )

    answer = await call_dify(

        query=text,

        user_id=msg.sender_open_id,

    )



    print(
        "最终回复:"
    )

    print(answer)



    await channel.send(

        msg.chat_id,

        {
            "text": answer
        }

    )





def main():


    channel.on(

        "im.message.receive_v1",

        on_message

    )


    print(
        "FlowMate机器人已启动"
    )


    channel.connect()





if __name__=="__main__":

    main()
