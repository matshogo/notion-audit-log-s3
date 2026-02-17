-- ============================================
-- Athena クエリサンプル集
-- ============================================

-- 1. 基本的なイベント一覧
SELECT 
  event.id,
  event.timestamp,
  event.type,
  event.actor.person.email as user_email,
  event.ip_address,
  event.platform
FROM notion_audit_logs.events
ORDER BY event.timestamp DESC
LIMIT 100;

-- 2. イベントタイプ別の集計
SELECT 
  event.type,
  COUNT(*) as event_count
FROM notion_audit_logs.events
GROUP BY event.type
ORDER BY event_count DESC;

-- 3. ユーザー別のアクティビティ
SELECT 
  event.actor.person.email as user_email,
  COUNT(*) as action_count,
  COUNT(DISTINCT event.type) as unique_event_types
FROM notion_audit_logs.events
GROUP BY event.actor.person.email
ORDER BY action_count DESC;

-- 4. 日別のアクティビティ推移
SELECT 
  DATE(from_iso8601_timestamp(event.timestamp)) as date,
  COUNT(*) as event_count
FROM notion_audit_logs.events
GROUP BY DATE(from_iso8601_timestamp(event.timestamp))
ORDER BY date DESC;

-- 5. 時間帯別のアクティビティ
SELECT 
  HOUR(from_iso8601_timestamp(event.timestamp)) as hour,
  COUNT(*) as event_count
FROM notion_audit_logs.events
GROUP BY HOUR(from_iso8601_timestamp(event.timestamp))
ORDER BY hour;

-- 6. プラットフォーム別の利用状況
SELECT 
  event.platform,
  COUNT(*) as usage_count
FROM notion_audit_logs.events
GROUP BY event.platform
ORDER BY usage_count DESC;

-- 7. IPアドレス別のアクセス
SELECT 
  event.ip_address,
  event.actor.person.email as user_email,
  COUNT(*) as access_count
FROM notion_audit_logs.events
GROUP BY event.ip_address, event.actor.person.email
ORDER BY access_count DESC;

-- 8. 最近7日間のアクティビティ
SELECT 
  event.type,
  event.actor.person.email as user_email,
  event.timestamp
FROM notion_audit_logs.events
WHERE from_iso8601_timestamp(event.timestamp) >= current_timestamp - interval '7' day
ORDER BY event.timestamp DESC;

-- 9. ページ作成イベントの詳細
SELECT 
  event.timestamp,
  event.actor.person.email as user_email,
  event."page.created".page_name,
  event."page.created".page_audience
FROM notion_audit_logs.events
WHERE event.type = 'page.created'
ORDER BY event.timestamp DESC;

-- 10. ユーザー追加/削除イベント
SELECT 
  event.timestamp,
  event.type,
  event.actor.person.email as admin_email,
  CASE 
    WHEN event.type = 'user.added' THEN event."user.added".target.user_id
    WHEN event.type = 'user.removed' THEN event."user.removed".target.user_id
  END as target_user_id
FROM notion_audit_logs.events
WHERE event.type IN ('user.added', 'user.removed')
ORDER BY event.timestamp DESC;
