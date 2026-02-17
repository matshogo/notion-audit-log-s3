# GitHubリポジトリのセットアップ手順

このプロジェクトをGitHubで管理するための手順です。

## 1. GitHubでリポジトリを作成

### 方法A: GitHub Web UIを使用

1. https://github.com/new にアクセス
2. 以下を入力：
   - **Repository name**: `notion-audit-log-s3`
   - **Description**: `Notion Audit Log to S3 with Athena and QuickSight visualization`
   - **Public** または **Private** を選択
   - **Initialize this repository with:** は全てチェックを外す（既にローカルにファイルがあるため）
3. **Create repository** をクリック

### 方法B: GitHub CLIを使用

```bash
# GitHub CLIがインストールされている場合
gh repo create notion-audit-log-s3 --public --source=. --remote=origin --push
```

## 2. リモートリポジトリを追加

GitHub Web UIで作成した場合、以下のコマンドを実行：

```bash
# GitHubのユーザー名を設定
GITHUB_USERNAME="your-github-username"

# リモートリポジトリを追加
git remote add origin https://github.com/${GITHUB_USERNAME}/notion-audit-log-s3.git

# または SSH を使用する場合
git remote add origin git@github.com:${GITHUB_USERNAME}/notion-audit-log-s3.git
```

## 3. プッシュ

```bash
# メインブランチにプッシュ
git push -u origin main
```

## 4. リポジトリの確認

ブラウザで以下のURLにアクセス：
```
https://github.com/${GITHUB_USERNAME}/notion-audit-log-s3
```

README.mdが表示されていれば成功です。

## 5. 今後の更新方法

ファイルを変更した後：

```bash
# 変更をステージング
git add .

# コミット
git commit -m "Update: 変更内容の説明"

# プッシュ
git push
```

## 6. リポジトリの設定（オプション）

### トピックの追加

GitHubリポジトリページで：
1. **About** の歯車アイコンをクリック
2. **Topics** に以下を追加：
   - `notion`
   - `aws`
   - `lambda`
   - `s3`
   - `athena`
   - `quicksight`
   - `audit-log`
   - `serverless`
   - `sam`

### GitHub Actionsの設定（オプション）

自動テストやデプロイを設定する場合、`.github/workflows/` ディレクトリにワークフローファイルを追加できます。

## 7. セキュリティ設定

### Secretsの管理

GitHub Actionsで自動デプロイする場合：

1. リポジトリの **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** をクリック
3. 以下のSecretsを追加：
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `WEBHOOK_SECRET`

**重要**: これらの値は絶対にコードにコミットしないでください。

## 8. ライセンスの確認

このプロジェクトはMITライセンスで公開されています。
必要に応じて `LICENSE` ファイルを編集してください。

## トラブルシューティング

### エラー: remote origin already exists

```bash
# 既存のリモートを削除
git remote remove origin

# 再度追加
git remote add origin https://github.com/${GITHUB_USERNAME}/notion-audit-log-s3.git
```

### エラー: Permission denied (publickey)

SSH接続の場合、SSH鍵が設定されていない可能性があります。
HTTPSを使用するか、SSH鍵を設定してください：

```bash
# HTTPSに変更
git remote set-url origin https://github.com/${GITHUB_USERNAME}/notion-audit-log-s3.git
```

### ブランチ名がmasterの場合

```bash
# ブランチ名をmainに変更
git branch -M main
```
