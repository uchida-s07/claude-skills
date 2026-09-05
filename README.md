# claude-skills

Claude Code の個人用スキル集（private）。
`~/.claude/skills`（Windows: `C:\Users\<ユーザー名>\.claude\skills`）そのものをリポジトリにして、複数端末で同期する。

## 収録スキル

Vモデルに沿った設計ドキュメント作成・レビュー用スキル。

| ドキュメント | 作成 | 単体レビュー | 横断レビュー |
| --- | --- | --- | --- |
| ① 要求定義書 `01-request.md` | `request-doc` | `request-doc-review` | |
| ② 要件定義書 `02-requirement.md` | `requirement-doc` | `requirement-doc-review` | `requirement-spec-crossreview`（②×③） |
| ③ 仕様書 `03-spec.md` ＋ モック | `spec-doc` | `spec-doc-review` | |
| ④ データ構造設計書 `04-db.md` | `db-doc` | `db-doc-review` | `db-api-crossreview`（④×⑤） |
| ⑤ API・IPO一覧 `05-api-ipo.md` | `api-ipo-doc` | `api-ipo-doc-review` | |
| ⑥ シナリオテスト仕様書 `06-scenario-test.md` | `scenario-test-doc` | `scenario-test-doc-review` | |

## 新しい端末での導入

`~/.claude/skills` が **存在しない or 空** の場合:

```bash
git clone git@github.com:uchida-s07/claude-skills.git ~/.claude/skills
```

HTTPS を使う場合（GitHub CLI で認証済みなら簡単）:

```bash
gh repo clone uchida-s07/claude-skills ~/.claude/skills
```

Windows（PowerShell）:

```powershell
gh repo clone uchida-s07/claude-skills "$env:USERPROFILE\.claude\skills"
```

### すでに `~/.claude/skills` に中身がある場合

上書きされると困るので、いったん退避してから clone する。

```bash
mv ~/.claude/skills ~/.claude/skills.bak
gh repo clone uchida-s07/claude-skills ~/.claude/skills
# 必要なら skills.bak から個別スキルを戻す
```

導入後、Claude Code を再起動すれば `/` でスキルが選べる。

## 更新の流れ

**取り込む（各端末で作業開始前）**

```bash
cd ~/.claude/skills && git pull
```

**変更を上げる（スキルを直したら）**

```bash
cd ~/.claude/skills
git add -A
git commit -m "スキルの変更内容"
git push
```

## 注意

- private リポジトリなので、社外秘の手順やプロジェクト固有の情報を書いても外部には公開されない。ただし **API キー・トークン・パスワードは絶対に置かない**（private でも履歴に残り、共有時に漏れる）。
- `~/.claude` 直下の `settings.json` や `.credentials.json` はこのリポジトリに含めない（`skills` ディレクトリのみが対象）。
