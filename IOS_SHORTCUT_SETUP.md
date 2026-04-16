# iPhone から X ハッシュタグ トレンド分析を実行する

iPhone のショートカット App から、ワンタップ（またはハッシュタグ入力）でトレンド分析を実行できます。

## 仕組み

```
iPhone ショートカット
  → GitHub Actions API (workflow_dispatch)
    → X API でツイート取得
    → トレンド分析
    → Notion DB に保存
  → Notion アプリで結果確認
```

---

## 事前準備

### 1. GitHub Personal Access Token の作成

1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. 「Generate new token」をクリック
3. 設定:
   - **Token name**: `hashtag-trend-iphone`
   - **Repository access**: `Only select repositories` → `matshogo/notion-audit-log-s3`
   - **Permissions**: Repository permissions → **Actions**: Read and write
4. 生成されたトークンをコピー（`github_pat_...` で始まる文字列）

### 2. GitHub リポジトリの Secrets 設定

リポジトリ → Settings → Secrets and variables → Actions で以下を登録:

| Secret 名 | 値 |
|---|---|
| `X_BEARER_TOKEN` | X API の Bearer Token |
| `NOTION_API_TOKEN` | Notion Integration のトークン |
| `NOTION_DATABASE_ID` | Notion データベースの ID |

---

## iOS ショートカットの作成

iPhone の **ショートカット** App を開き、以下の手順で作成します。

### 方法 A: ハッシュタグを毎回入力するバージョン

1. **「+」** で新規ショートカット作成
2. 名前を **「X トレンド分析」** に設定

#### アクション構成:

**① 入力を要求**
- プロンプト: `分析するハッシュタグを入力`
- 入力タイプ: テキスト

**② URL**
- `https://api.github.com/repos/matshogo/notion-audit-log-s3/actions/workflows/hashtag-trend.yml/dispatches`

**③ URLの内容を取得**
- 方法: `POST`
- ヘッダー:
  - `Authorization`: `Bearer <あなたのGitHub PAT>`
  - `Accept`: `application/vnd.github.v3+json`
- 本文: JSON
  ```json
  {
    "ref": "main",
    "inputs": {
      "hashtag": "(①の入力結果)",
      "max_tweets": "300"
    }
  }
  ```

**④ 通知を表示**
- `#(①の入力結果) のトレンド分析を開始しました。結果は Notion で確認できます。`

### 方法 B: 固定ハッシュタグをワンタップ実行

毎日同じタグを追いたい場合、入力を省略して直接実行:

1. 新規ショートカット作成、名前を **「#AI トレンド」** に設定
2. **URL** アクションで上記と同じ URL を設定
3. **URLの内容を取得** で:
   - 本文 JSON の `hashtag` を固定値（例: `AI`）に設定
4. **通知を表示**: `#AI のトレンド分析を開始しました`

→ ホーム画面にウィジェットとして追加すれば **ワンタップ** で実行

---

## 結果の確認方法

分析完了後（通常 1〜2 分）:

1. **Notion アプリ** → 該当データベースを開く → 最新のエントリを確認
2. **GitHub アプリ** → Actions タブ → 実行結果のサマリーを確認

---

## オートメーション（自動実行）

ショートカットの **オートメーション** で定期実行も可能:

1. ショートカット App → オートメーション → 「+」
2. **時刻** → 例: 毎日 9:00
3. アクション: 上で作った「X トレンド分析」ショートカットを実行
4. 「実行前に確認」をオフ

→ 毎朝自動でトレンド分析が走り、Notion に蓄積されます。

---

## トラブルシューティング

| 症状 | 原因・対処 |
|---|---|
| ショートカット実行時にエラー | GitHub PAT の有効期限切れ → 再生成 |
| Notion に結果が出ない | リポジトリの Secrets 設定を確認 |
| ツイートが 0 件 | ハッシュタグの綴り確認 / X API のレート制限（15分待つ） |
| Actions が起動しない | ワークフローファイルが main ブランチにマージされているか確認 |
