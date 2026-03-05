import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import hashlib
import secrets
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
from database.medical_database import MedicalDatabase
db = MedicalDatabase()

# 导入图谱和状态回调
from src.agents.graph import app as medical_graph, register_status_callback, unregister_status_callback

app = FastAPI(title="智医助手系统 (AI Pharmacist)")
security = HTTPBearer()

# Pydantic models for API
class UserRegister(BaseModel):
    username: str
    password: str
    name: str
    gender: Optional[str] = "Unknown"
    birth_year: Optional[int] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    phone: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_diseases: Optional[List[str]] = None

class SessionCreate(BaseModel):
    title: Optional[str] = "新对话"

# Token storage (in production, use Redis or database)
active_tokens = {}

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token and return user_id"""
    token = credentials.credentials
    user_id = active_tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

# 初始化一个用于总结的小模型
summary_llm = init_chat_model(
    model="Qwen/Qwen2.5-7B-Instruct",
    model_provider="openai",
    temperature=0.1,
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.cn/v1"
)

async def save_message_smart(session_id: str, role: str, content: str):
    """
    智能存储消息：如果太长，先总结再存储 TEXT 格式
    """
    final_content = content
    # 设定阈值，例如 500 字符
    if len(content) > 500:
        try:
            prompt = f"以下是一条对话消息，请将其总结为精简的文本（保留核心医学信息）：\n\n{content}"
            summary = await summary_llm.ainvoke(prompt)
            final_content = f"【系统总结】{summary.content}"
        except Exception as e:
            print(f"总结失败: {e}")
            final_content = content[:1000] + "..." # 降级截断

    # 根据内容判断 msg_type
    msg_type = "text"
    if role == "assistant":
        if "summary_analysis" in content and "recommended_products" in content:
            msg_type = "report_card"
    
    # 存入数据库
    db.save_message(session_id, role, final_content, msg_type)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_json(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

manager = ConnectionManager()

# ==================== REST API Endpoints ====================

@app.post("/api/auth/register")
async def register(user_data: UserRegister):
    """用户注册"""
    try:
        # Check if username exists
        existing_user = db.get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        # Create user with hashed password
        user_id = f"user_{secrets.token_hex(8)}"
        hashed_pw = hash_password(user_data.password)
        
        db.create_user_with_auth(
            user_id=user_id,
            username=user_data.username,
            password_hash=hashed_pw,
            name=user_data.name,
            gender=user_data.gender,
            birth_year=user_data.birth_year
        )
        
        # Generate token
        token = generate_token()
        active_tokens[token] = user_id
        
        return {
            "success": True,
            "message": "注册成功",
            "token": token,
            "user_id": user_id,
            "username": user_data.username,
            "name": user_data.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")

@app.post("/api/auth/login")
async def login(credentials: UserLogin):
    """用户登录"""
    try:
        user = db.get_user_by_username(credentials.username)
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # Verify password
        hashed_pw = hash_password(credentials.password)
        if user['password_hash'] != hashed_pw:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # Generate token
        token = generate_token()
        active_tokens[token] = user['user_id']
        
        return {
            "success": True,
            "message": "登录成功",
            "token": token,
            "user_id": user['user_id'],
            "username": user['username'],
            "name": user['name']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")

@app.post("/api/auth/logout")
async def logout(user_id: str = Depends(verify_token)):
    """用户登出"""
    # Remove token
    tokens_to_remove = [token for token, uid in active_tokens.items() if uid == user_id]
    for token in tokens_to_remove:
        del active_tokens[token]
    
    return {"success": True, "message": "登出成功"}

@app.get("/api/user/profile")
async def get_profile(user_id: str = Depends(verify_token)):
    """获取用户档案"""
    try:
        profile = db.get_user_profile(user_id)
        user_info = db.get_user_info(user_id)
        
        return {
            "success": True,
            "data": {
                **user_info,
                **profile
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取档案失败: {str(e)}")

@app.put("/api/user/profile")
async def update_profile(profile_data: UserProfile, user_id: str = Depends(verify_token)):
    """更新用户档案"""
    try:
        # Update basic info
        if profile_data.name or profile_data.gender or profile_data.birth_year or profile_data.phone:
            db.update_user_info(
                user_id=user_id,
                name=profile_data.name,
                gender=profile_data.gender,
                birth_year=profile_data.birth_year,
                phone=profile_data.phone
            )
        
        # Update health profile
        if profile_data.allergies is not None or profile_data.chronic_diseases is not None:
            db.update_health_profile(
                user_id=user_id,
                allergies=profile_data.allergies,
                chronic_diseases=profile_data.chronic_diseases
            )
        
        return {"success": True, "message": "档案更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新档案失败: {str(e)}")

@app.get("/api/sessions")
async def get_sessions(user_id: str = Depends(verify_token)):
    """获取用户的所有会话"""
    try:
        sessions = db.get_user_sessions(user_id)
        return {
            "success": True,
            "data": sessions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")

@app.post("/api/sessions")
async def create_session(session_data: SessionCreate, user_id: str = Depends(verify_token)):
    """创建新会话"""
    try:
        # 生成唯一session_id，添加时间戳确保唯一性
        import time
        session_id = f"sess_{int(time.time() * 1000)}_{secrets.token_hex(6)}"
        
        # 检查session_id是否已存在，如果存在则重新生成
        max_retries = 3
        for _ in range(max_retries):
            existing = db.get_session_info(session_id)
            if not existing:
                break
            session_id = f"sess_{int(time.time() * 1000)}_{secrets.token_hex(6)}"
        
        db.create_session(session_id, user_id, session_data.title)
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "title": session_data.title,
                "created_at": datetime.now().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")

@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, user_id: str = Depends(verify_token)):
    """获取会话的历史消息"""
    try:
        # Verify session belongs to user
        session = db.get_session_info(session_id)
        if not session or session['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        messages = db.get_session_history(session_id, limit=100)
        return {
            "success": True,
            "data": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = Depends(verify_token)):
    """删除会话"""
    try:
        # Verify session belongs to user
        session = db.get_session_info(session_id)
        if not session or session['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="无权删除此会话")
        
        db.delete_session(session_id)
        return {"success": True, "message": "会话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

class SessionTitleUpdate(BaseModel):
    title: str

@app.put("/api/sessions/{session_id}/title")
async def update_session_title(session_id: str, title_data: SessionTitleUpdate, user_id: str = Depends(verify_token)):
    """更新会话标题"""
    try:
        # Verify session belongs to user
        session = db.get_session_info(session_id)
        if not session or session['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="无权修改此会话")
        
        # 更新标题
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (title_data.title, session_id)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "标题更新成功", "title": title_data.title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新标题失败: {str(e)}")

@app.post("/api/sessions/{session_id}/generate-title")
async def generate_session_title(session_id: str, user_id: str = Depends(verify_token)):
    """根据对话内容自动生成标题"""
    try:
        # Verify session belongs to user
        session = db.get_session_info(session_id)
        if not session or session['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="无权访问此会话")
        
        # 获取会话的前几条消息
        messages = db.get_session_history(session_id, limit=3)
        if not messages:
            return {"success": True, "title": "新对话"}
        
        # 提取用户消息内容
        user_messages = [msg['content'] for msg in messages if msg['role'] == 'user']
        if not user_messages:
            return {"success": True, "title": "新对话"}
        
        # 使用LLM生成标题
        first_msg = user_messages[0][:200]  # 限制长度
        prompt = f"""请为以下医疗咨询生成一个简短的标题（不超过15个字）。
用户咨询内容：{first_msg}

只输出标题，不要有其他内容。例如：
- 头痛咨询
- 感冒用药建议
- 胃痛问诊
"""
        
        title_response = await summary_llm.ainvoke(prompt)
        generated_title = title_response.content.strip()[:20]  # 限制长度
        
        # 更新数据库
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (generated_title, session_id)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "title": generated_title}
    except HTTPException:
        raise
    except Exception as e:
        print(f"生成标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成标题失败: {str(e)}")

class FeedbackSubmit(BaseModel):
    session_id: str
    rating: int
    comment: Optional[str] = ""

@app.post("/api/feedback")
async def submit_feedback(feedback_data: FeedbackSubmit, user_id: str = Depends(verify_token)):
    """提交用户反馈"""
    try:
        # Verify session belongs to user
        session = db.get_session_info(feedback_data.session_id)
        if not session or session['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="无权对此会话进行评价")
        
        db.save_feedback(
            session_id=feedback_data.session_id,
            rating=feedback_data.rating,
            comment=feedback_data.comment
        )
        
        return {"success": True, "message": "感谢您的反馈"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {str(e)}")

@app.websocket("/ws/medical/{session_id}")
async def medical_websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    
    # 检查session是否存在，如果不存在才创建（用于兼容旧的WebSocket直连方式）
    session_info = db.get_session_info(session_id)
    if not session_info:
        # 这是直接WebSocket连接，创建临时用户和会话
        user_id = f"user_{session_id[:8]}"
        db.upsert_user(user_id, f"用户{session_id[:8]}")
        db.create_session(session_id, user_id, "临时会话")
    else:
        # Session已存在（通过REST API创建），使用现有user_id
        user_id = session_info['user_id']

    # 检查是否已有欢迎语（避免重复发送）
    history = db.get_session_history(session_id, limit=1)
    if not history:
        # 欢迎语
        welcome_text = "您好！我是小团医生。请告诉我您哪里不舒服？"
        await manager.send_json(session_id, {"role": "assistant", "type": "text", "content": welcome_text})
        
        # 🌟 存储欢迎语
        await save_message_smart(session_id, "assistant", welcome_text)

    config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}

    # 🔥 注册状态回调函数 - 用于接收处理进度
    async def status_callback(status: str):
        """将处理状态发送到前端"""
        await manager.send_json(session_id, {
            "type": "status",
            "content": status
        })
    
    register_status_callback(session_id, status_callback)

    try:
        while True:
            # 1. 接收前端消息
            data = await websocket.receive_json()
            user_input = data.get("message", "")
            
            # 存储用户消息
            await save_message_smart(session_id, "user", user_input)

            # 🔥 发送初始 thinking 状态
            await manager.send_json(session_id, {
                "type": "status",
                "content": "正在分析您的问题..."
            })

            # 2. 使用 astream（节点级别流式）+ 模拟逐字输出
            import asyncio
            accumulated_content = ""
            current_stage = None
            
            async for chunk in medical_graph.astream(
                {
                    "messages": [HumanMessage(content=user_input)],
                    "user_id": user_id,
                    "session_id": session_id
                },
                config=config
            ):
                # astream 的 chunk 格式: {node_name: {state_updates}}
                for node_name, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue
                    
                    print(f"📦 节点 [{node_name}] 输出: keys={list(node_output.keys())}")
                    
                    # 获取当前阶段
                    if "workflow_stage" in node_output:
                        current_stage = node_output["workflow_stage"]
                        print(f"📍 当前阶段: {current_stage}")
                    
                    # 处理消息
                    if "messages" in node_output:
                        node_messages = node_output["messages"]
                        if not isinstance(node_messages, list):
                            node_messages = [node_messages]
                        
                        for msg in node_messages:
                            if isinstance(msg, AIMessage) and msg.content:
                                new_content = msg.content
                                
                                # 🔥 判断是否是报告JSON（不要流式发送JSON）
                                is_report = False
                                if "summary_analysis" in new_content:
                                    try:
                                        json.loads(new_content)
                                        is_report = True
                                    except json.JSONDecodeError:
                                        pass
                                
                                if is_report:
                                    # 报告内容：不流式发送，直接累积
                                    accumulated_content += new_content
                                    print(f"📋 报告内容已累积 ({node_name})")
                                else:
                                    # 🔥 普通文本：模拟逐字流式输出
                                    print(f"📤 开始流式发送 ({node_name}): {new_content[:80]}...")
                                    # 按小块发送，模拟打字效果
                                    chunk_size = 4  # 每次发送4个字符
                                    for i in range(0, len(new_content), chunk_size):
                                        text_chunk = new_content[i:i+chunk_size]
                                        await manager.send_json(session_id, {
                                            "type": "stream",
                                            "content": text_chunk
                                        })
                                        await asyncio.sleep(0.03)  # 30ms延迟，模拟打字效果
                                    accumulated_content += new_content
            
            # 3. 流式传输完成，处理最终内容
            content = accumulated_content
            print(f"🏁 流式完成: 内容长度={len(content)}, 阶段={current_stage}")
            
            # 4. 判断并处理不同类型的响应
            # 如果是报告阶段产出的 JSON
            if current_stage == "awaiting_confirmation" or (content and "summary_analysis" in content):
                try:
                    parsed_json = json.loads(content)
                    
                    # 🔥 Bug1修复：发送丢弃信号（以防万一有流式文本残留）
                    await manager.send_json(session_id, {
                        "type": "stream_discard"
                    })
                    
                    # 发送报告卡片（唯一的报告展示方式）
                    await manager.send_json(session_id, {
                        "role": "assistant",
                        "type": "report_card",
                        "content": parsed_json
                    })
                    
                    # 发送流式结束信号
                    await manager.send_json(session_id, {
                        "type": "stream_end"
                    })
                    
                    # 存储 AI 报告
                    await save_message_smart(session_id, "assistant", content)
                    
                    continue 

                except json.JSONDecodeError:
                    # 如果解析失败，按普通文本处理
                    pass

            # 🔥 发送流式结束信号（普通文本消息）
            await manager.send_json(session_id, {
                "type": "stream_end",
                "final_content": content,
                "stage": current_stage
            })

            # 存储 AI 回复
            if content:
                await save_message_smart(session_id, "assistant", content)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        unregister_status_callback(session_id)  # 🔥 清理状态回调
        # 更新会话结束时间
        # db.close_session(session_id) 
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保清理
        unregister_status_callback(session_id)
