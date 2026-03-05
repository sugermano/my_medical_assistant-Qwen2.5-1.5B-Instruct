"""
数据库迁移脚本
用于将旧数据库升级到新版本（添加认证功能）
"""
import sqlite3
import os

DB_PATH = "medical_assistant.db"

def migrate_database():
    """迁移数据库到新版本"""
    print("开始数据库迁移...")
    
    # 备份旧数据库
    if os.path.exists(DB_PATH):
        backup_path = DB_PATH + ".backup"
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ 已备份旧数据库到 {backup_path}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查是否需要添加 username 和 password_hash 列
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'username' not in columns:
            print("添加 username 列...")
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT UNIQUE")
            print("✅ username 列已添加")
        
        if 'password_hash' not in columns:
            print("添加 password_hash 列...")
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            print("✅ password_hash 列已添加")
        
        # 检查 sessions 表是否有 title 列
        cursor.execute("PRAGMA table_info(sessions)")
        session_columns = [col[1] for col in cursor.fetchall()]
        
        if 'title' not in session_columns:
            print("添加 title 列到 sessions 表...")
            cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT '新对话'")
            print("✅ title 列已添加")
        
        conn.commit()
        print("\n🎉 数据库迁移完成！")
        print("现在可以正常使用新版本的系统了。")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def reset_database():
    """完全重置数据库（删除并重新创建）"""
    print("⚠️  警告：此操作将删除所有现有数据！")
    response = input("确定要重置数据库吗？(yes/no): ")
    
    if response.lower() == 'yes':
        if os.path.exists(DB_PATH):
            backup_path = DB_PATH + ".old"
            import shutil
            shutil.move(DB_PATH, backup_path)
            print(f"✅ 旧数据库已移动到 {backup_path}")
        
        # 重新初始化数据库
        from database.medical_database import MedicalDatabase
        db = MedicalDatabase(DB_PATH)
        print("✅ 数据库已重新创建！")
    else:
        print("取消重置操作")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_database()
    else:
        migrate_database()
