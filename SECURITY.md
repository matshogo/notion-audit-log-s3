# Security Policy

## Supported Versions

現在サポートされているバージョン：

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

セキュリティ脆弱性を発見した場合は、以下の手順で報告してください：

### 報告方法

1. **GitHub Security Advisories** を使用（推奨）
   - リポジトリの **Security** タブ → **Report a vulnerability** をクリック
   - 脆弱性の詳細を記入して送信

2. **プライベートな報告**
   - リポジトリのIssuesは使用しないでください（公開されてしまうため）
   - GitHubのSecurity Advisoriesを使用してください

### 報告に含めるべき情報

- 脆弱性の種類（例: SQL Injection, XSS, 認証バイパスなど）
- 影響を受けるファイルやコンポーネント
- 再現手順
- 想定される影響
- 可能であれば、修正案

### 対応プロセス

1. **確認**: 報告を受け取ってから48時間以内に確認
2. **調査**: 脆弱性の検証と影響範囲の調査
3. **修正**: パッチの作成とテスト
4. **公開**: 修正版のリリースとセキュリティアドバイザリの公開

## セキュリティのベストプラクティス

### デプロイ時の注意事項

1. **Webhook Secretの管理**
   - 強力なランダム文字列を使用
   - 定期的にローテーション
   - 環境変数として管理（コードにハードコーディングしない）

2. **AWS認証情報**
   - IAMロールを使用（可能な限り）
   - 最小権限の原則に従う
   - アクセスキーは定期的にローテーション

3. **S3バケット**
   - パブリックアクセスをブロック
   - バージョニングを有効化
   - 暗号化を有効化（推奨）

4. **Lambda関数**
   - 環境変数で機密情報を管理
   - VPC内で実行（必要に応じて）
   - CloudWatch Logsで監視

### 既知の制限事項

- このプロジェクトはWebhook Secretによる基本的な認証のみを実装
- より高度なセキュリティが必要な場合は、追加の認証レイヤーを実装してください

## セキュリティスキャン

このリポジトリでは以下のセキュリティスキャンを実施しています：

- **TruffleHog**: シークレットスキャン
- **Trivy**: 依存関係の脆弱性スキャン
- **CodeQL**: コードセキュリティ分析
- **Bandit**: Python固有のセキュリティ問題検出
- **Dependabot**: 依存関係の自動更新

## 参考リンク

- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GitHub Security Features](https://docs.github.com/en/code-security)
