import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

class MedicalDatabase:
    """智医助手专用数据库管理"""

    def __init__(self, db_path: str = "medical_assistant.db"):
        self.db_path = db_path
        # 设置超时时间，避免数据库锁定
        self.timeout = 30.0
        self.init_db()
    
    def get_connection(self):
        """获取数据库连接，设置超时和其他参数"""
        conn = sqlite3.connect(
            self.db_path, 
            timeout=self.timeout,
            check_same_thread=False,  # 允许多线程访问
            isolation_level=None  # 自动提交模式
        )
        # 启用WAL模式以提高并发性能
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def init_db(self):
        """初始化医疗数据库结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. 用户基础表 (增加认证信息)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            name TEXT,
            gender TEXT CHECK(gender IN ('Male', 'Female', 'Other', 'Unknown')) DEFAULT 'Unknown',
            birth_year INTEGER,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. 健康档案表 (核心：存储过敏史、既往史、当前用药)
        # 使用 separate table 是一对一关系，便于隐私隔离和管理
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_profiles (
            user_id TEXT PRIMARY KEY,
            allergies TEXT DEFAULT '[]',         -- JSON List: ["青霉素", "磺胺"]
            chronic_diseases TEXT DEFAULT '[]',  -- JSON List: ["高血压", "糖尿病"]
            current_medications TEXT DEFAULT '[]', -- JSON List: 正在服用的药
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)

        # 3. 会话表 (增加会话标题)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT DEFAULT '新对话',
            status TEXT DEFAULT 'active', -- active, closed, archived
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)

        # 4. 消息记录表 (包含结构化消息标记)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,           -- user, assistant, system
            content TEXT NOT NULL,        -- 可能是纯文本，也可能是 JSON Report
            msg_type TEXT DEFAULT 'text', -- text, report_card, inquiry_question
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 5. 问诊记录表 (结构化存储：查过什么病，开过什么药)
        # 用于后续分析"用户最近查了什么"以及"推荐了哪些药"
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS consultation_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            symptom_summary TEXT,         -- 主诉症状摘要
            recommended_drugs TEXT,       -- JSON List: 推荐的药物名称
            risk_level TEXT,              -- otc_safe, pharmacist_consult, hospital_urgent
            full_report_json TEXT,        -- 完整报告的 JSON 备份
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 6. 反馈表 (增加专业性评价)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            rating INTEGER,               -- 1-5 星
            accuracy_score INTEGER,       -- 准确性打分 (可选)
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 7. 会话上下文表 (持久化关键信息：症状、禁忌等)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_context (
            session_id TEXT PRIMARY KEY,
            extracted_symptoms TEXT,          -- JSON: 症状列表
            extracted_contraindications TEXT, -- JSON: 禁忌列表
            extracted_feedback TEXT,          -- JSON: 用户反馈列表
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        );
        """)

        # 8. 药品信息缓存表 (减少API调用)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drug_info_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name TEXT UNIQUE NOT NULL,    -- 药名（索引）
            full_description TEXT,             -- API 返回的完整说明书
            contraindications TEXT,            -- 提取出的禁忌症字段（方便 LLM 直接读）
            dosage_info TEXT,                  -- 用法用量
            prescription_type TEXT,            -- OTC 或 处方药
            manufacturer TEXT,                 -- 生产厂家
            source TEXT,                       -- 标记来源（API 或 本地）
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 为药名创建索引以加速查询
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_drug_name ON drug_info_cache(drug_name);
        """)

        conn.commit()
        conn.close()

    # ================= 认证相关 =================
    
    def create_user_with_auth(self, user_id: str, username: str, password_hash: str, 
                             name: str, gender: str = "Unknown", birth_year: int = None):
        """创建带认证信息的用户"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username, password_hash, name, gender, birth_year) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, password_hash, name, gender, birth_year))
        
        # 初始化健康档案
        cursor.execute("INSERT INTO health_profiles (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """通过用户名获取用户信息"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, password_hash, name, gender, birth_year, phone, created_at
            FROM users WHERE username = ?
        """, (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_user_info(self, user_id: str) -> Dict:
        """获取用户基本信息"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, name, gender, birth_year, phone, created_at
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}
    
    def update_user_info(self, user_id: str, name: str = None, gender: str = None, 
                        birth_year: int = None, phone: str = None):
        """更新用户基本信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if gender is not None:
            updates.append("gender = ?")
            params.append(gender)
        if birth_year is not None:
            updates.append("birth_year = ?")
            params.append(birth_year)
        if phone is not None:
            updates.append("phone = ?")
            params.append(phone)
            
        if updates:
            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(sql, params)
            
        conn.commit()
        conn.close()

    # ================= 用户与档案管理 =================

    def upsert_user(self, user_id: str, name: str, gender: str = "Unknown", birth_year: int = None):
        """创建或更新用户基本信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, name, gender, birth_year) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                name=excluded.name, 
                gender=excluded.gender,
                birth_year=excluded.birth_year
        """, (user_id, name, gender, birth_year))
        
        # 同时也初始化一个空的健康档案
        cursor.execute("INSERT OR IGNORE INTO health_profiles (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

    def update_health_profile(self, user_id: str, allergies: list = None, chronic_diseases: list = None):
        """更新健康档案（过敏史、既往史）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if allergies is not None:
            updates.append("allergies = ?")
            params.append(json.dumps(allergies, ensure_ascii=False))
            
        if chronic_diseases is not None:
            updates.append("chronic_diseases = ?")
            params.append(json.dumps(chronic_diseases, ensure_ascii=False))
            
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            sql = f"UPDATE health_profiles SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(sql, params)
            
        conn.commit()
        conn.close()

    def get_user_profile(self, user_id: str) -> Dict:
        """获取用户画像（用于 Agent 上下文注入）"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.name, u.gender, u.birth_year, h.allergies, h.chronic_diseases
            FROM users u
            LEFT JOIN health_profiles h ON u.user_id = h.user_id
            WHERE u.user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "name": row["name"],
                "age": datetime.now().year - row["birth_year"] if row["birth_year"] else "未知",
                "gender": row["gender"],
                "allergies": json.loads(row["allergies"]) if row["allergies"] else [],
                "chronic_diseases": json.loads(row["chronic_diseases"]) if row["chronic_diseases"] else []
            }
        return {}

    # ================= 会话与消息管理 =================

    def create_session(self, session_id: str, user_id: str, title: str = "新对话"):
        """创建新会话"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_id, user_id, title) VALUES (?, ?, ?)", 
            (session_id, user_id, title)
        )
        conn.commit()
        conn.close()
    
    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """获取用户的所有会话"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, s.title, s.status, s.created_at, s.closed_at,
                   COUNT(m.message_id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.user_id = ?
            GROUP BY s.session_id
            ORDER BY s.created_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取单个会话信息"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, user_id, title, status, created_at, closed_at
            FROM sessions WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def delete_session(self, session_id: str):
        """删除会话及其相关消息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        # 删除消息
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        # 删除会话
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def save_message(self, session_id: str, role: str, content: str, msg_type: str = "text"):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, msg_type) VALUES (?, ?, ?, ?)",
            (session_id, role, content, msg_type)
        )
        conn.commit()
        conn.close()

    def get_session_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """获取最近的历史消息（用于 LangChain Memory）"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, msg_type FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?", 
            (session_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"], "msg_type": r["msg_type"]} for r in reversed(rows)]

    # ================= 问诊记录 (结构化) =================

    def save_consultation_result(self, session_id: str, user_id: str, report_data: Dict):
        """保存 Agent 生成的最终药单/报告"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 从 report 对象中提取关键字段
        symptom = report_data.get("summary_analysis", "")[:100] # 摘要
        drugs = [item["name"] for item in report_data.get("recommended_products", [])]
        risk = report_data.get("medical_warning", "otc_safe") # 需根据实际逻辑映射
        
        cursor.execute("""
            INSERT INTO consultation_records 
            (session_id, user_id, symptom_summary, recommended_drugs, risk_level, full_report_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id, 
            user_id, 
            symptom, 
            json.dumps(drugs, ensure_ascii=False), 
            risk, 
            json.dumps(report_data, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

    def get_past_consultations(self, user_id: str, limit: int = 5) -> List[Dict]:
        """查询用户过去查过什么病（用于'您上次问的头痛好点了吗'）"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT symptom_summary, recommended_drugs, created_at 
            FROM consultation_records 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def save_feedback(self, session_id: str, rating: int, comment: str):
        """
        将用户反馈存入 satisfaction 表
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            
            cursor = conn.cursor()
            query = "INSERT INTO feedback (session_id, rating, comment) VALUES (?, ?, ?)"
            cursor.execute(query, (session_id, rating, comment))
            conn.commit()
            print(f"✅ 反馈已存入数据库: Session {session_id}, Rating {rating}")
        except Exception as e:
            print(f"❌ 数据库存入失败: {e}")
            conn.rollback()
            raise e
        finally:
            conn.close()

    # ================= 药品信息缓存 =================
    
    def get_drug_from_cache(self, drug_name: str) -> Optional[Dict]:
        """
        从缓存表查询药品信息
        
        Args:
            drug_name: 药品通用名
            
        Returns:
            药品信息字典，未命中返回 None
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT drug_name, full_description, contraindications, dosage_info,
                   prescription_type, manufacturer, source, updated_at
            FROM drug_info_cache
            WHERE drug_name = ?
        """, (drug_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "drug_name": row["drug_name"],
                "full_description": row["full_description"],
                "contraindications": row["contraindications"],
                "dosage_info": row["dosage_info"],
                "prescription_type": row["prescription_type"],
                "manufacturer": row["manufacturer"],
                "source": row["source"],
                "updated_at": row["updated_at"]
            }
        return None
    
    def get_drugs_from_cache(self, drug_names: List[str]) -> Dict[str, Dict]:
        """
        批量从缓存表查询多个药品信息
        
        Args:
            drug_names: 药品名称列表
            
        Returns:
            {药品名: 药品信息字典} 的映射，未命中的药品不在结果中
        """
        if not drug_names:
            return {}
            
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 使用 IN 查询批量获取
        placeholders = ','.join(['?' for _ in drug_names])
        cursor.execute(f"""
            SELECT drug_name, full_description, contraindications, dosage_info,
                   prescription_type, manufacturer, source, updated_at
            FROM drug_info_cache
            WHERE drug_name IN ({placeholders})
        """, drug_names)
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {}
        for row in rows:
            result[row["drug_name"]] = {
                "drug_name": row["drug_name"],
                "full_description": row["full_description"],
                "contraindications": row["contraindications"],
                "dosage_info": row["dosage_info"],
                "prescription_type": row["prescription_type"],
                "manufacturer": row["manufacturer"],
                "source": row["source"],
                "updated_at": row["updated_at"]
            }
        return result
    
    def save_drug_to_cache(self, drug_info: Dict):
        """
        保存药品信息到缓存表
        
        Args:
            drug_info: 药品信息字典，包含以下字段：
                - drug_name: 药品通用名（必填）
                - full_description: 完整说明书
                - contraindications: 禁忌症
                - dosage_info: 用法用量
                - prescription_type: OTC 或 处方药
                - manufacturer: 生产厂家
                - source: 来源（API 或 本地）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO drug_info_cache 
            (drug_name, full_description, contraindications, dosage_info, 
             prescription_type, manufacturer, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(drug_name) DO UPDATE SET
                full_description = excluded.full_description,
                contraindications = excluded.contraindications,
                dosage_info = excluded.dosage_info,
                prescription_type = excluded.prescription_type,
                manufacturer = excluded.manufacturer,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
        """, (
            drug_info.get("drug_name"),
            drug_info.get("full_description", ""),
            drug_info.get("contraindications", ""),
            drug_info.get("dosage_info", ""),
            drug_info.get("prescription_type", ""),
            drug_info.get("manufacturer", ""),
            drug_info.get("source", "API")
        ))
        
        conn.commit()
        conn.close()
        print(f"💾 药品缓存已更新: {drug_info.get('drug_name')}")
    
    def save_drugs_to_cache(self, drug_infos: List[Dict]):
        """
        批量保存药品信息到缓存表
        
        Args:
            drug_infos: 药品信息字典列表
        """
        if not drug_infos:
            return
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for drug_info in drug_infos:
            cursor.execute("""
                INSERT INTO drug_info_cache 
                (drug_name, full_description, contraindications, dosage_info, 
                 prescription_type, manufacturer, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(drug_name) DO UPDATE SET
                    full_description = excluded.full_description,
                    contraindications = excluded.contraindications,
                    dosage_info = excluded.dosage_info,
                    prescription_type = excluded.prescription_type,
                    manufacturer = excluded.manufacturer,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                drug_info.get("drug_name"),
                drug_info.get("full_description", ""),
                drug_info.get("contraindications", ""),
                drug_info.get("dosage_info", ""),
                drug_info.get("prescription_type", ""),
                drug_info.get("manufacturer", ""),
                drug_info.get("source", "API")
            ))
        
        conn.commit()
        conn.close()
        print(f"💾 批量缓存已更新: {len(drug_infos)} 条药品信息")

    # ================= 会话上下文持久化 =================
    
    def update_session_context(self, session_id: str, extracted_data: Dict):
        """
        更新会话上下文（持久化关键信息：症状、禁忌、反馈）
        extracted_data 格式：
        {
            "symptoms": ["头痛", "发烧38度"],
            "contraindications": ["青霉素过敏", "孕期"],
            "feedback": ["上次推荐的药很有效"]
        }
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        symptoms_json = json.dumps(extracted_data.get('symptoms', []), ensure_ascii=False)
        contraindications_json = json.dumps(extracted_data.get('contraindications', []), ensure_ascii=False)
        feedback_json = json.dumps(extracted_data.get('feedback', []), ensure_ascii=False)
        
        cursor.execute("""
            INSERT INTO session_context 
            (session_id, extracted_symptoms, extracted_contraindications, extracted_feedback, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                extracted_symptoms = excluded.extracted_symptoms,
                extracted_contraindications = excluded.extracted_contraindications,
                extracted_feedback = excluded.extracted_feedback,
                last_updated = CURRENT_TIMESTAMP
        """, (session_id, symptoms_json, contraindications_json, feedback_json))
        
        conn.commit()
        conn.close()
        print(f"✅ 会话上下文已更新: {session_id}")
    
    def get_session_context(self, session_id: str) -> Dict:
        """
        获取会话的持久化上下文
        返回格式：
        {
            "symptoms": ["头痛", "发烧38度"],
            "contraindications": ["青霉素过敏"],
            "feedback": [],
            "last_updated": "2024-01-01 12:00:00"
        }
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT extracted_symptoms, extracted_contraindications, 
                   extracted_feedback, last_updated
            FROM session_context
            WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "symptoms": json.loads(row["extracted_symptoms"]) if row["extracted_symptoms"] else [],
                "contraindications": json.loads(row["extracted_contraindications"]) if row["extracted_contraindications"] else [],
                "feedback": json.loads(row["extracted_feedback"]) if row["extracted_feedback"] else [],
                "last_updated": row["last_updated"]
            }
        return {
            "symptoms": [],
            "contraindications": [],
            "feedback": [],
            "last_updated": None
        }

# ================= 使用示例 =================
if __name__ == "__main__":
    db = MedicalDatabase()
    
    # 1. 模拟用户注册
    user_id = "u123452"
    db.upsert_user(user_id, "张三", gender="Male", birth_year=1990)
    
    # 2. 更新过敏史（Agent 在对话中获知）
    db.update_health_profile(user_id, allergies=["青霉素", "芒果"])
    
    # 3. 创建会话
    session_id = "sess_004"
    db.create_session(session_id, user_id)
    
    # 4. 模拟 Agent 生成报告并保存
    mock_report = {
        "summary_analysis": "用户主诉偏头痛，无发热。",
        "medical_warning": "otc_safe",
        "recommended_products": [{"name": "布洛芬缓释胶囊"}, {"name": "天麻头痛片"}]
    }
    db.save_consultation_result(session_id, user_id, mock_report)
    
    # 5. 获取用户画像（用于下一轮对话）
    profile = db.get_user_profile(user_id)
    print("用户画像:", json.dumps(profile, ensure_ascii=False, indent=2))
    
    # 6. 获取历史问诊
    history = db.get_past_consultations(user_id)
    print("历史问诊:", history)
