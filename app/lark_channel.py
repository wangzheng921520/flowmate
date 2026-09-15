import asyncio
import json
import lark_oapi as lark

from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)


class Message:

    def __init__(
        self,
        content_text,
        chat_id,
        sender_open_id,
    ):

        self.content_text = content_text
        self.chat_id = chat_id
        self.sender_open_id = sender_open_id



class FeishuChannel:


    def __init__(self, app_id: str, app_secret: str):

        self.app_id = app_id
        self.app_secret = app_secret

        self.callback = None

        # websocket客户端（接收消息）
        self.client = None

        # 普通API客户端（发送消息）
        self.api_client = None



    def on(self, event: str, callback):

        self.callback = callback



    async def send(self, chat_id: str, content: dict):

        print("发送消息:")
        print(content)


        try:

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(
                        json.dumps(
                            {
                                "text": content.get("text", "")
                            },
                            ensure_ascii=False
                        )
                    )
                    .build()
                )
                .build()
            )


            response = self.api_client.im.v1.message.create(
                request
            )


            print("飞书发送结果:")
            print(response)


        except Exception as e:

            print("发送失败:")
            print(e)



    def connect(self):

        print("飞书机器人连接成功")



        # 创建普通API客户端
        self.api_client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )



        # 创建事件监听
        event_handler = (
            lark.EventDispatcherHandler.builder(
                "",
                ""
            )
            .register_p2_im_message_receive_v1(
                self.handle_event
            )
            .build()
        )



        # 创建websocket连接
        self.client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
        )


        # 开始监听
        self.client.start()




    def handle_event(self, data):

        print("====================")
        print("收到飞书消息")
        print(data)
        print("====================")



        try:

            # 飞书消息内容
            body = data.event.message.content


            content_json = json.loads(body)


            text = content_json.get(
                "text",
                ""
            )



            # 会话ID
            chat_id = data.event.message.chat_id

            # 消息发送人的飞书 open_id
            sender_open_id = (
                data.event.sender.sender_id.open_id
            )

            print("chat_id =", chat_id)
            print("sender_open_id =", sender_open_id)



            msg = Message(
                content_text=text,
                chat_id=chat_id,
                sender_open_id=sender_open_id
            )



            print("转换后的消息:")
            print(msg.content_text)
            print(msg.chat_id)



            # 调用bot.py里面的on_message
            if self.callback:

                asyncio.create_task(
                    self.callback(msg)
                )



        except Exception as e:

            print("消息解析失败:")
            print(e)