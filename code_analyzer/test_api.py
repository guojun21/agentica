#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Poe API 调用和文档生成
"""
import os
import sys
import json
from datetime import datetime

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openai

# Poe API 配置
POE_API_KEY = "W4HQGO1TRCOcZzRv-8vB84REwnexAshVRVVhyZ9dpII"
POE_BASE_URL = "https://api.poe.com/v1"
POE_MODEL = "Claude-sonnet"  # Claude 4.5 Opus

# 测试代码
TEST_CODE = '''
// 手动触发数据拉取
func fetchPointsHistory(c *gin.Context) {
    var input struct {
        Cookie          string `json:"cookie" binding:"required"`
        FormKey         string `json:"form_key" binding:"required"`
        TChannel        string `json:"tchannel" binding:"required"`
        Revision        string `json:"revision"`
        TagID           string `json:"tag_id"`
        SubscriptionDay int    `json:"subscription_day"` // 每月订阅日（1-31）
        FullSync        bool   `json:"full_sync"`        // 是否全量拉取（覆盖已有数据）
    }

    if err := c.ShouldBindJSON(&input); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    // 设置默认值
    if input.Revision == "" {
        input.Revision = "59988163982a4ac4be7c7e7784f006dc48cafcf5"
    }
    if input.TagID == "" {
        input.TagID = "8a0df086c2034f5e97dcb01c426029ee"
    }
    if input.SubscriptionDay <= 0 || input.SubscriptionDay > 31 {
        input.SubscriptionDay = 1
    }

    // 计算当前订阅周期的开始时间
    now := time.Now()
    currentDay := now.Day()
    year := now.Year()
    month := int(now.Month())

    if currentDay < input.SubscriptionDay {
        month--
        if month < 1 {
            month = 12
            year--
        }
    }

    subscriptionStartTime := time.Date(year, time.Month(month), input.SubscriptionDay, 0, 0, 0, 0, time.Local)
    subscriptionStartMicros := subscriptionStartTime.UnixMicro()

    // 保存配置到数据库
    if err := upsertConfig(input.Cookie, input.FormKey, input.TChannel, input.Revision, input.TagID,
        input.SubscriptionDay, subscriptionAmount, subscriptionCurrency, autoFetchInterval, autoFetchEnabled); err != nil {
        log.Printf("Failed to save config during fetch: %v", err)
    }

    newRecords := 0
    updatedRecords := 0
    duplicateFound := false
    reachedSubscriptionStart := false
    cursor := ""

    for !duplicateFound && !reachedSubscriptionStart {
        // 构建请求体 - 调用 Poe API
        requestBody := map[string]interface{}{
            "queryName": "PointsHistoryPageColumnViewerPaginationQuery",
            "variables": map[string]interface{}{
                "limit": 20,
            },
            "extensions": map[string]string{
                "hash": "9b68fe8ea0017e5d7701c93a5db8323136f9cb023d514f8595ae0dde220be6d1",
            },
        }

        // 发送请求到 poe.com/api/gql_POST
        client := &http.Client{Timeout: 30 * time.Second}
        resp, err := client.Do(req)
        // ... 处理响应 ...

        // 处理每条记录
        for _, edge := range poeResp.Data.Viewer.PointsHistoryConnection.Edges {
            // 检查是否达到本订阅周期的开始时间
            if edge.Node.CreationTime <= subscriptionStartMicros {
                reachedSubscriptionStart = true
                break
            }

            // 检查是否已存在
            exists, err := recordExists(edge.Node.ID)
            if exists && !input.FullSync {
                duplicateFound = true
                break
            }

            // 插入或更新记录
            if exists {
                // 更新现有记录
                db.Exec("UPDATE points_history SET ... WHERE id = ?", node.ID)
                updatedRecords++
            } else {
                // 插入新记录
                insertRecord(node)
                newRecords++
            }
        }
    }

    c.JSON(http.StatusOK, gin.H{
        "new_records":     newRecords,
        "updated_records": updatedRecords,
        "message":         message,
    })
}

// 检查记录是否存在
func recordExists(id string) (bool, error) {
    var exists bool
    err := db.QueryRow("SELECT EXISTS(SELECT 1 FROM points_history WHERE id = ?)", id).Scan(&exists)
    return exists, err
}

// 插入记录
func insertRecord(node *PointsHistoryNode) error {
    _, err := db.Exec(`
        INSERT INTO points_history (id, point_cost, creation_time, bot_name, bot_id, cursor, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    `, node.ID, node.PointCost, node.CreationTime, node.BotName, node.BotID, node.Cursor, node.CreatedAt)
    return err
}
'''

ANALYSIS_PROMPT = """你是一个专业的代码分析师。请分析以下 Go 代码中的 HTTP 接口。

## 接口信息
- 接口名称: fetchPointsHistory
- 类型: HTTP POST
- 路径: /api/fetch
- 文件: main.go

## 代码
```go
{code}
```

## 分析要求

请按照以下结构生成详细的接口文档：

### 1. 接口概述
简要描述这个接口的功能

### 2. 请求参数
列出所有请求参数，包括类型、是否必填、说明

### 3. 处理流程
用树形结构描述从接口入口到数据库的完整调用链，包括：
- 每个步骤的函数名
- 条件分支
- 数据库操作

### 4. 数据库操作
列出涉及的表和 SQL 操作

### 5. 返回结果
描述响应数据结构

### 6. 业务目的
总结这个接口的业务价值

请用中文回答。
"""


def test_poe_api():
    """测试 Poe API"""
    print("=" * 60)
    print("测试 Poe API 调用")
    print("=" * 60)
    
    client = openai.OpenAI(
        api_key=POE_API_KEY,
        base_url=POE_BASE_URL,
    )
    
    prompt = ANALYSIS_PROMPT.format(code=TEST_CODE)
    
    print(f"\n使用模型: {POE_MODEL}")
    print(f"提示词长度: {len(prompt)} 字符")
    print("\n正在调用 API...")
    
    try:
        response = client.chat.completions.create(
            model=POE_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
        )
        
        content = response.choices[0].message.content
        
        print("\n" + "=" * 60)
        print("API 响应成功!")
        print("=" * 60)
        print(f"\n响应长度: {len(content)} 字符")
        print("\n--- 生成的文档 ---\n")
        print(content)
        
        # 保存到文件
        output_file = "/Users/oasmet/Documents/!002Projects/07-tools/agents/agentica/code_analyzer_output/test_api_result.md"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"""---
generated_at: {datetime.now().isoformat()}
model: {POE_MODEL}
---

{content}
""")
        
        print(f"\n✅ 文档已保存到: {output_file}")
        return True
        
    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")
        return False


if __name__ == "__main__":
    test_poe_api()

