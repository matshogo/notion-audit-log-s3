# Notion Audit Log to S3 完全セットアップガイド

NotionのWebhookを使ってAudit logをS3に保存し、Athena + QuickSightで可視化するシステムの構築手順です。

## 目次
1. [環境構築](#1-環境構築)
2. [Notionの設定](#2-notionの設定)
3. [Athenaのセットアップ](#3-athenaのセットアップ)
4. [QuickSightのセットアップ](#4-quicksightのセットアップ)
5. [トラブルシューティング](#5-トラブルシューティング)

---

## 1. 環境構築

### 1-1. Webhook Secretの生成

```bash
openssl rand -base64 32
```

出力例: `abc123xyz789...`（ランダムな文字列）

**重要**: この値を安全に保管してください（後で使用します）

### 1-2. SAMビルド

```bash
cd notion-audit-log-s3
sam build
```

### 1-3. デプロイ

```bash
sam deploy --guided --parameter-overrides WebhookSecret=<1-1で生成したSecret>
```

対話形式で以下を入力：
- Stack Name: `notion-audit-log-s3`
- AWS Region: `ap-northeast-1`（または任意のリージョン）
- Confirm changes before deploy: `Y`
- Allow SAM CLI IAM role creation: `Y`
- Disable rollback: `Y`
- NotionWebhookFunction has no authentication: `y`
- Save arguments to configuration file: `Y`

### 1-4. デプロイ結果の確認

デプロイ完了後、以下の情報が表示されます：

```
Outputs:
WebhookUrl: https://xxxxx.execute-api.{region}.amazonaws.com/prod/webhook
BucketName: notion-audit-logs-{AccountId}
FunctionName: notion-webhook-handler
```

**WebhookUrl** を控えてください（Notionの設定で使用します）

---

## 2. Notionの設定

### 2-1. Custom SIEM Integrationの設定

1. Notion Workspace Settings を開く
2. **Integrations** → **Custom SIEM Integration** を選択
3. 以下を設定：

**Webhook URL**
```
https://xxxxx.execute-api.{region}.amazonaws.com/prod/webhook
```
（1-4でコピーしたWebhookUrlを貼り付け）

**Webhook headers**
- Header name: `x-notion-webhook-secret`
- Header value: （1-1で生成したSecretを貼り付け）

4. **Save** をクリック

### 2-2. 動作確認

Notionで何かアクション（ページ作成、閲覧など）を実行後、S3にログが保存されているか確認：

```bash
aws s3 ls s3://notion-audit-logs-{YourAccountId}/audit-logs/flat/ --recursive
```

出力例：
```
2026-02-10 18:42:32  1038  audit-logs/flat/2026/02/10/20260210_094231_301028.json
```

ファイルが表示されれば成功です。

---

## 3. Athenaのセットアップ

### 3-1. クエリ結果保存用バケットの作成

```bash
# AccountIdとRegionを自分の環境に合わせて変更
aws s3 mb s3://aws-athena-query-results-{YourAccountId}-{YourRegion}
```

例: `aws s3 mb s3://aws-athena-query-results-123456789012-ap-northeast-1`

### 3-2. Athenaコンソールでの設定

1. AWSコンソールで **Athena** を開く
2. 初回の場合、**Settings** → **Manage** で以下を設定：
   - Query result location: `s3://aws-athena-query-results-{YourAccountId}-{YourRegion}/`
   - **Save** をクリック

### 3-3. データベースの作成

Athenaクエリエディタで以下を実行：

```sql
CREATE DATABASE IF NOT EXISTS notion_audit_logs;
```

### 3-4. テーブルの作成

**重要**: Athenaは一度に1つのSQL文しか実行できません。以下を順番に実行してください。

#### ステップ1: 既存テーブルを削除（既に作成済みの場合）

```sql
DROP TABLE IF EXISTS notion_audit_logs.events_flat;
```

#### ステップ2: 平坦化されたデータ用のテーブルを作成

```sql
CREATE EXTERNAL TABLE notion_audit_logs.events_flat (
  event_id string,
  event_timestamp string,
  workspace_id string,
  workspace_name string,
  ip_address string,
  platform string,
  event_type string,
  user_email string,
  actor_id string,
  actor_type string,
  raw_event string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://notion-audit-logs-{YourAccountId}/audit-logs/flat/';
```

**注意**: `{YourAccountId}` を実際のAWSアカウントIDに置き換えてください。

### 3-5. 動作確認

```sql
-- データ件数を確認
SELECT COUNT(*) FROM notion_audit_logs.events_flat;
```

データ件数が表示されればOK

```sql
-- データの内容を確認
SELECT * FROM notion_audit_logs.events_flat LIMIT 10;
```

全てのフィールドにデータが入っていればOK

---

## 4. QuickSightのセットアップ

### 4-1. QuickSightの有効化

1. AWSコンソールで **QuickSight** を開く
2. 初回の場合、Sign up for QuickSight
3. Edition: **Enterprise** 推奨（Standard Editionでも可）
4. アカウント名とメールアドレスを入力
5. Finish

### 4-2. S3アクセス権限の付与

1. QuickSight → 右上のアカウント名 → **Manage QuickSight**
2. **Security & permissions** → **QuickSight access to AWS services**
3. **Add or remove** をクリック
4. **Amazon S3** にチェック
5. **Select S3 buckets** をクリック
6. 以下のバケットにチェック：
   - `notion-audit-logs-{YourAccountId}`
   - `aws-athena-query-results-{YourAccountId}-{YourRegion}`
7. **Finish** → **Update**

### 4-3. データソースの作成

1. QuickSight ホーム → **Datasets** → **New dataset**
2. データソース: **Athena** を選択
3. データソース名: `notion-audit-logs`
4. Athena workgroup: `primary`
5. **Create data source**

### 4-4. データセットの作成

1. Database: `notion_audit_logs` を選択
2. Tables: **`events_flat`** を選択（重要: eventsではなくevents_flat）
3. **Select** をクリック
4. データ取り込み方法を選択：
   - **Import to SPICE**: 高速、推奨（データ更新が必要）
   - **Directly query your data**: リアルタイム（遅い）
5. **Visualize** をクリック

### 4-5. データの確認

分析画面が開いたら、左側のフィールドリストに以下が表示されます：
- event_id
- event_timestamp
- event_type
- user_email
- platform
- ip_address
- workspace_name
- actor_id
- actor_type
- raw_event

これらのフィールドを使ってビジュアルを作成できます。

### 4-6. ダッシュボードの作成

1. **Create analysis** をクリック
2. 以下のビジュアルを追加：

**推奨ビジュアル**:
- イベント数の推移（折れ線グラフ）
- イベントタイプ別分布（円グラフ）
- ユーザー別アクティビティ（横棒グラフ）
- プラットフォーム別利用状況（縦棒グラフ）

3. 完成したら **Share** → **Publish dashboard**
4. ダッシュボード名を入力（例: `Notion Audit Log Dashboard`）
5. **Publish dashboard** をクリック

### 4-7. 自動更新の設定（SPICEの場合）

1. **Datasets** → `notion-audit-logs` → **Refresh**
2. **Schedule refresh** をクリック
3. 頻度を設定（例: 毎日午前9時）
4. **Save**

---

## 5. Notionへの埋め込み

QuickSightのダッシュボードをNotionページに埋め込むことができます。

### 5-1. ダッシュボードの公開設定

1. QuickSight → **Dashboards** → 作成したダッシュボードを開く
2. 右上の **Share** → **Share dashboard** をクリック
3. **Manage dashboard access** セクションで：
   - **Public access** を有効化
   - または特定のユーザー/グループに共有

### 5-2. 埋め込みURLの取得

#### オプションA: 公開ダッシュボード（推奨）

1. ダッシュボード画面右上の **Share** をクリック
2. **Get embed code** を選択
3. 表示されたURLをコピー

#### オプションB: 埋め込みコンソールを使用

1. QuickSight → 左メニュー → **Manage QuickSight**
2. **Domains and embedding** を選択
3. 埋め込みを許可するドメインを追加（例: `notion.so`）
4. ダッシュボードの埋め込みURLを取得

### 5-3. Notionページへの埋め込み

1. Notionページを開く
2. `/embed` と入力してEmbedブロックを作成
3. 取得したQuickSightのURLを貼り付け
4. **Embed link** をクリック

**注意**: 
- QuickSightの公開設定によっては、Notionで表示できない場合があります
- Enterprise Editionの場合、埋め込み機能がより柔軟に使えます

### 5-4. 代替案: スクリーンショットの自動更新

QuickSightの埋め込みが難しい場合、以下の方法も検討できます：

1. QuickSightでダッシュボードのスクリーンショットを定期的に取得
2. S3に保存
3. NotionのImage URLとして参照

または

1. QuickSightのダッシュボードへのリンクをNotionに貼り付け
2. Notionのリンクプレビュー機能で表示

---

## 6. トラブルシューティング

### 問題1: Notionからログが送信されない

**症状**: S3にファイルが作成されない

**確認事項**:
1. Webhook URLが正しいか確認
2. Webhook headerの名前が `x-notion-webhook-secret` か確認
3. Webhook headerの値がデプロイ時のSecretと一致するか確認

**確認方法**:
```bash
# Lambda関数のログを確認
aws logs tail /aws/lambda/notion-webhook-handler --follow
```

**対処法**:
- Notionの設定を再確認
- Lambda関数の環境変数 `WEBHOOK_SECRET` を確認

---

### 問題2: QuickSightでデータが全てnull

**症状**: データは取り込めているが全てnull

**原因**: テーブル定義とJSONの構造が合っていない

**対処法**:
1. 3-4の手順で `events_flat` テーブルを使用していることを確認
2. QuickSightでデータセットを削除して再作成
3. テーブル選択時に `events_flat` を選択

---

### 問題3: QuickSightで「このテーブルを準備できません」エラー

**症状**: データセット作成時にエラー

**原因A**: QuickSightにS3アクセス権限がない

**対処法**:
1. QuickSight → Manage QuickSight → Security & permissions
2. QuickSight access to AWS services → Add or remove
3. Amazon S3 → Select S3 buckets
4. 必要なバケットにチェック
5. Update

**原因B**: Athenaでクエリが失敗している

**対処法**:
1. Athenaコンソールで直接クエリを実行
2. エラーメッセージを確認
3. テーブル定義を修正

**原因C**: Athenaのクエリ結果の場所が未設定

**対処法**:
1. Athena → Settings → Manage
2. Query result location: `s3://aws-athena-query-results-491767864459-ap-northeast-1/`
3. Save

---

### 問題4: Lambda関数が401エラーを返す

**症状**: Notionからのリクエストが拒否される

**原因**: Webhook Secretが一致していない

**確認方法**:
```bash
# Lambda関数の環境変数を確認
aws lambda get-function-configuration --function-name notion-webhook-handler --query 'Environment.Variables.WEBHOOK_SECRET'
```

**対処法**:
1. Notionの設定でヘッダー値を確認
2. Lambda関数の環境変数と一致させる
3. 必要に応じて再デプロイ

---



---

### 問題5: QuickSightダッシュボードがNotionに埋め込めない

**症状**: Notionの埋め込みブロックでQuickSightが表示されない

**原因**: QuickSightの埋め込み設定が不足している

**対処法**:

#### 方法1: 公開ダッシュボードを使用
1. QuickSight → Dashboards → Share → Publish to web
2. 公開URLを取得
3. NotionのEmbedブロックに貼り付け

#### 方法2: リンクとして共有
1. QuickSightダッシュボードのURLをコピー
2. Notionページに貼り付け
3. リンクプレビューで表示

#### 方法3: スクリーンショットを使用
1. QuickSightでダッシュボードのスクリーンショットを撮影
2. Notionページに画像として貼り付け
3. 定期的に更新

---

## 7. コスト見積もり

### Lambda
- 無料枠: 100万リクエスト/月
- 通常使用: ほぼ無料

### S3
- ストレージ: $0.025/GB/月
- 1日100イベント（各1KB）の場合: 月3MB = $0.0001/月

### Athena
- クエリ実行: $5/TB
- 通常使用: 月$1以下

### QuickSight
- Standard Edition: $9/月/ユーザー
- Enterprise Edition: $18/月/ユーザー
- SPICE: 10GB無料、追加$0.25/GB/月

**合計**: 月$10〜$20程度

---

## 8. 参考リンク

- [Notion API Documentation](https://developers.notion.com/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [Athena JSON SerDe](https://docs.aws.amazon.com/athena/latest/ug/json-serde.html)
- [QuickSight User Guide](https://docs.aws.amazon.com/quicksight/)
- [QuickSight Embedding](https://docs.aws.amazon.com/quicksight/latest/user/embedding-dashboards.html)

---

## 9. サポート

問題が解決しない場合:
1. CloudWatch Logsでエラー詳細を確認
2. Athenaのクエリ履歴を確認
3. S3バケットのアクセス権限を確認
