#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库索引添加脚本

此脚本用于为fail2ban-sync项目的SQLite数据库添加额外的索引，以优化查询性能。
当前已添加的索引会被保留，脚本只添加新的索引。
"""

import sqlite3
import os
import time
from datetime import datetime

# 数据库文件路径
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Server', 'ip_management.db')

def log_message(message):
    """打印带时间戳的日志消息"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def get_existing_indexes(cursor):
    """获取表中已存在的索引列表"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='ip_addresses'
    """)
    return {row[0] for row in cursor.fetchall()}

def add_index(cursor, conn, index_name, table_name, columns):
    """添加索引到数据库"""
    try:
        # 构建索引创建语句
        columns_str = ', '.join(columns)
        create_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({columns_str})"
        
        # 执行索引创建
        start_time = time.time()
        cursor.execute(create_sql)
        conn.commit()
        duration = time.time() - start_time
        
        log_message(f"✓ 成功添加索引: {index_name} ({columns_str}) - 耗时: {duration:.4f}秒")
        return True
    except sqlite3.Error as e:
        log_message(f"✗ 添加索引失败 {index_name}: {str(e)}")
        return False

def main():
    """主函数"""
    log_message("开始添加数据库索引...")
    log_message(f"数据库路径: {DATABASE_PATH}")
    
    try:
        # 连接数据库
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # 获取当前索引
        existing_indexes = get_existing_indexes(cursor)
        log_message(f"当前已存在的索引数量: {len(existing_indexes)}")
        if existing_indexes:
            log_message(f"已存在的索引: {', '.join(sorted(existing_indexes))}")
        
        # 定义要添加的新索引
        # 格式: (索引名, 表名, [列1, 列2, ...])
        indexes_to_add = [
            # 基于时间的索引，用于查询即将过期的封禁
            ('idx_ip_addresses_blocked_until', 'ip_addresses', ['blocked_until']),
            
            # 基于报告源的索引，用于按来源统计
            ('idx_ip_addresses_reported_by', 'ip_addresses', ['reported_by']),
            
            # 基于允许时间的索引，用于查询最近允许的IP
            ('idx_ip_addresses_allowed_since', 'ip_addresses', ['allowed_since']),
            
            # 基于封禁次数的索引，用于查询被多次封禁的IP
            ('idx_ip_addresses_block_count', 'ip_addresses', ['block_count']),
            
            # 复合索引：状态和时间，用于查询特定状态且在特定时间范围内的IP
            ('idx_ip_addresses_status_time', 'ip_addresses', ['status', 'blocked_until']),
            
            # 复合索引：报告源和状态，用于按来源和状态筛选
            ('idx_ip_addresses_reported_status', 'ip_addresses', ['reported_by', 'status']),
            
            # 复合索引：状态和允许时间，用于查询特定状态且在特定时间被允许的IP
            ('idx_ip_addresses_status_allowed', 'ip_addresses', ['status', 'allowed_since'])
        ]
        
        # 添加索引
        success_count = 0
        skipped_count = 0
        
        for index_name, table_name, columns in indexes_to_add:
            if index_name in existing_indexes:
                log_message(f"ℹ 索引 {index_name} 已存在，跳过")
                skipped_count += 1
            else:
                if add_index(cursor, conn, index_name, table_name, columns):
                    success_count += 1
        
        # 统计信息
        log_message("\n索引添加完成！")
        log_message(f"总计: {len(indexes_to_add)} 个索引")
        log_message(f"成功添加: {success_count} 个索引")
        log_message(f"已存在跳过: {skipped_count} 个索引")
        
        # 显示最终索引列表
        final_indexes = get_existing_indexes(cursor)
        log_message(f"\n最终索引列表 ({len(final_indexes)} 个):")
        for idx in sorted(final_indexes):
            log_message(f"  - {idx}")
        
        # 分析表（优化数据库）
        log_message("\n执行数据库分析以优化索引使用...")
        cursor.execute("ANALYZE ip_addresses")
        conn.commit()
        log_message("数据库分析完成")
        
        # 显示表信息
        log_message("\n表结构信息:")
        cursor.execute("PRAGMA table_info(ip_addresses)")
        print("  列名               类型           非空   默认值")
        print("  " + "-" * 60)
        for row in cursor.fetchall():
            print(f"  {row[1]:<20} {row[2]:<15} {row[3]:<5} {row[4] or ''}")
        
    except sqlite3.Error as e:
        log_message(f"数据库操作失败: {str(e)}")
        return 1
    except Exception as e:
        log_message(f"发生未知错误: {str(e)}")
        return 1
    finally:
        if 'conn' in locals():
            conn.close()
            log_message("数据库连接已关闭")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        print("\n脚本执行" + ("成功" if exit_code == 0 else "失败"))
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n脚本被用户中断")
        exit(130)
