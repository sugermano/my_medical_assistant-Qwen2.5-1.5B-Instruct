import uuid
import websocket
import json
import threading

# 引入信号灯，控制对话顺序
ai_ready_event = threading.Event()

def test_client():
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    ws_url = f"ws://127.0.0.1:8000/ws/medical/{session_id}"

    print("="*70)
    print("🤖 智医助手系统 (AI Pharmacist) - 已连接")
    print("="*70)

    def on_message(ws, message):
        """接收消息：打印回复并释放信号灯"""
        data = json.loads(message)
        # 打印 AI 回复
        print(f"\n🤖 智医助手: {data['content']}\n")
        # AI 说话完了，允许用户输入
        ai_ready_event.set()

    def on_error(ws, error):
        print(f"❌ 错误: {error}")
        ai_ready_event.set() # 出错时也释放，防止死锁

    def on_close(ws, close_status_code, close_msg):
        print("\n👋 连接已关闭")

    def on_open(ws):
        """连接打开：由服务器发送欢迎语触发第一次 ready"""
        def run():
            while True:
                # 等待 AI 回复完成的信号
                ai_ready_event.wait()
                
                user_input = input("👤 您: ")
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    ws.close()
                    break

                if user_input.strip():
                    # 发送前重置信号，阻塞下一次输入直到 AI 回复
                    ai_ready_event.clear()
                    ws.send(json.dumps({"message": user_input}))

        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()

    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )

    ws.run_forever()