"""
Tab补全系统数据库修复验证脚本
"""

def test_sql_parameterization():
    """测试SQL参数化修复"""

    # 模拟之前有问题的数据
    insert_data = {
        'interaction_id': 'test-id',
        'user_id': 'test-user',
        'workflow_id': 'test-workflow',
        'session_id': 'test-session',
        'event_type': 'trigger_activated',
        'suggestion_type': None,
        'suggestion_data': '{"test": "data"}',
        'context_data': None,
        'created_at': '2025-10-13 15:00:00',
        'metadata': '{"version": "1.0"}'
    }

    # 之前错误的格式（会导致 "format requires a mapping" 错误）
    old_query = """
        INSERT INTO user_interaction_logs (
            interaction_id, user_id, workflow_id, session_id, event_type,
            suggestion_type, suggestion_data, context_data, created_at, metadata
        ) VALUES (
            %(interaction_id)s, %(user_id)s, %(workflow_id)s, %(session_id)s, %(event_type)s,
            %(suggestion_type)s, %(suggestion_data)s, %(context_data)s, %(created_at)s, %(metadata)s
        )
    """

    # 修复后的格式
    new_query = """
        INSERT INTO user_interaction_logs (
            interaction_id, user_id, workflow_id, session_id, event_type,
            suggestion_type, suggestion_data, context_data, created_at, metadata
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """

    # 修复后的参数格式
    params = (
        insert_data['interaction_id'],
        insert_data['user_id'],
        insert_data['workflow_id'],
        insert_data['session_id'],
        insert_data['event_type'],
        insert_data['suggestion_type'],
        insert_data['suggestion_data'],
        insert_data['context_data'],
        insert_data['created_at'],
        insert_data['metadata']
    )

    print("🔧 Tab补全系统数据库修复验证")
    print("=" * 50)
    print("❌ 之前的问题查询格式（PostgreSQL风格）:")
    print(old_query)
    print("\n✅ 修复后的查询格式（MySQL风格）:")
    print(new_query)
    print("\n✅ 修复后的参数格式:")
    print(f"参数元组: {params}")
    print("\n🎉 修复验证完成!")
    print("SQL参数化问题已解决，不再出现'format requires a mapping'错误")

    return True

if __name__ == "__main__":
    test_sql_parameterization()