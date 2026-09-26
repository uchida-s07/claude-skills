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

## 仕様駆動ワークフロー

上の6文書のフローを軽くしたもの。要求（`docs/product/vision.md`）と要件（`docs/product/requirements/`）を**常設文書**として「今の姿」を積み上げ、変更ごとに **spec 1枚**（`docs/specs/NNN-<name>/`）を作る。DB・API はコードを正とし、受入基準は `[<要件ID>/AC-n]` のタグで自動テストと結ぶ。
要件と受入基準の書き方の正典は `product-requirements/rules.md`。

| 種類 | スキル | 役割 |
| --- | --- | --- |
| 作成 | `spec-setup` | プロジェクトに docs の構成と CLAUDE.md の「開発ワークフロー」節を用意する |
| 作成 | `product-vision` | 要求の常設文書 `vision.md` を作る・更新する（`update`） |
| 作成 | `product-requirements` | 常設要件を既存プロジェクトへ導入する（`init`）・spec を経ずに直す（`update`） |
| 作成 | `spec-new` | 変更ごとの spec を作る（ティア判定・常設 ID の予約・承認まで） |
| 作成 | `spec-plan` | approved の spec から実装計画 `tasks.md` を作る |
| 作成 | `spec-close` | 実装を検証し、要件を常設ドキュメントへ移して done にする |
| レビュー | `spec-review` | spec 承認の関門。vision・常設要件・他の spec・コードとの矛盾を見る |
| 実装検証 | `spec-verify` | 実装とテストが spec を満たすかを、実装と別のコンテキストで検証する |
| レビュー | `docs-review` | 範囲（`vision` / `requirements [領域]` / `all`）を指定して常設文書とコードを横断で点検する |
| 機械点検 | `spec-check` | 同梱スクリプトで ID・参照・未確定・AC とテストの対応を機械的に点検する |

作成用の6つは `/名前` で明示して呼ぶ（Claude が自動では起動しない）。レビュー用の3つは別コンテキスト（fork）で動き、文書を書き換えない。作成用のスキルが決まった位置で自動で呼ぶ。

```
【プロジェクト開始】 /spec-setup → /product-vision →（既存なら）/product-requirements init
【変更ごと（M/L）】  /spec-new → spec-review（関門）→ 承認 → /spec-plan → 実装（テストを先に）→ /spec-close → spec-verify（関門）→ 常設要件へ移す → spec-check
【変更ごと（S）】    修正 →（振る舞いが変わったら）/product-requirements update
【手動】             docs-review all（リリース前、久しぶりに戻ったとき）
```

関門は「未解決の矛盾・欠落が0件」。ユーザーが「誤検知」「承知で進める」と判断した指摘は、理由を各プロジェクトの `docs/review-notes.md` に書けば解消扱いになる。レビューのタイミングの一覧は、`/spec-setup` が各プロジェクトの CLAUDE.md に書く。

**旧フローとの使い分け**

| 場面 | 使うもの |
| --- | --- |
| 自分たちで開発を続けるプロダクト（新規・機能追加） | 仕様駆動ワークフロー |
| 顧客に6文書を納める案件など、連番の設計文書そのものが成果物のとき | 旧フロー（`request-doc` 〜 `scenario-test-doc-review`） |

**動作に必要なもの**

- Claude Code v2.1.218 以降（レビュー用スキルの `background: false` を使うため）
- Python 3（`spec-check` のスクリプト。標準ライブラリだけで動く）

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
