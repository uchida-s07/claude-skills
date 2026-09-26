---
name: spec-setup
description: 仕様駆動ワークフロー（docs/product・docs/specs）用。プロジェクトに docs の構成（vision・常設要件・用語集・architecture・ADR・specs・review-notes）の雛形と、CLAUDE.md の「開発ワークフロー」節を用意する。既存のファイルは上書きしない。新規プロジェクトの開始時や、既存プロジェクトにこのワークフローを入れるときに最初に使う。旧フロー（01〜06 の連番文書を作る request-doc など）とは別物。
disable-model-invocation: true
---

# spec-setup（ワークフローの導入）

プロジェクトに仕様駆動ワークフローの docs 構成を用意する。中身を書くのは後続のスキル（`/product-vision` など）で、ここでは器を置くだけ。
要件の書き方の正典は `${CLAUDE_SKILL_DIR}/../product-requirements/rules.md`。

## 作る構成

```
<project>/
├── CLAUDE.md                     # 「開発ワークフロー」節を追記する
└── docs/
    ├── README.md                 # template-docs-readme.md
    ├── product/
    │   ├── vision.md             # ここでは作らない（/product-vision が作る）
    │   ├── requirements/
    │   │   ├── README.md         # ../product-requirements/template-readme.md
    │   │   └── common.md         # ../product-requirements/template-common.md
    │   └── glossary.md           # template-glossary.md
    ├── architecture.md           # template-architecture.md
    ├── adr/
    │   └── 0000-template.md      # template-adr.md
    ├── review-notes.md           # template-review-notes.md
    └── specs/                    # 空のディレクトリ（.gitkeep を置く）
```

雛形はすべて `${CLAUDE_SKILL_DIR}/` と `${CLAUDE_SKILL_DIR}/../product-requirements/` にある。
`requirements/README.md` と `common.md` の中身を決めるのは `/product-requirements init`（既存プロジェクト）か `/spec-new`〜`/spec-close`（新規）なので、ここでは器だけ置く。
`spec-check` が例の行を本物の要件として読まないよう、次のように置く。
- `README.md`：領域一覧は `COMMON` の行だけ残し、`{CODE}` の行は消す。「旧 FUNC-xx との対応表」の節は消す。
- `common.md`：非機能要件の表は見出し行と区切り行だけ残し、`COMMON-N-00n` の例の行は消す。`updated:` は今日の日付にする。

## 手順

### 1. 現状を確認する

- プロジェクトのルートを確認する（git リポジトリならそのルート）。
- `CLAUDE.md` と `docs/` の中身を見る。上の構成のうち、**すでにあるもの**と**無いもの**を一覧にする。
- 旧フローの文書（`01-request.md`、`02-requirement.md`、`03-spec.md`、`04-db.md`、`05-api-ipo.md`、`06-scenario-test.md`）がどこかにあるか探す。

### 2. 無いファイルだけ作る

- **既存ファイルは上書きしない。** 同じ場所に別の中身のファイルがあるなど、ぶつかるものは一覧で見せ、扱い（そのまま使う / 別名で置く / 作らない）をユーザーに聞く。
- 作ったファイルを一覧で報告する。

### 3. CLAUDE.md に「開発ワークフロー」節を追記する

- 追記する内容は `${CLAUDE_SKILL_DIR}/claude-md-section.md`。**既存の内容は変えない。** CLAUDE.md が無ければ作る。
- すでに「開発ワークフロー」節があれば、差分を見せて、どう直すかをユーザーに聞く。
- 「設定」のうち次は、プロジェクトを見て案を書き、**ユーザーに確かめてから**埋める。分からなければ聞く（推測で書かない）。
  - テストの実行コマンド（`spec-verify` がここを読む）
  - lint の実行コマンド（無ければ「なし」）
  - テストの置き場所（任意。`spec-check` がここを読む）
- 件数の基準（done 3件・進行中 2件）と日数（30日）は既定値のまま置き、変えたいかだけ聞く。

### 4. 実行環境を確かめる

- `python3 --version`（無ければ `python --version`）で Python 3 が使えるか確かめる。使えなければ、`spec-check` が動かないことを伝える。
- プロジェクトが git 管理か確かめる。git でなければ、`/spec-plan` の「承認後の変更」の確認がファイルの更新日時で代わることを伝える。

### 5. 次の一手を案内する

| プロジェクトの状態 | 次の一手 |
|---|---|
| 新規 | `/product-vision` → 最初の機能は `/spec-new`（L ティア） |
| 旧文書のある既存プロジェクト | `/product-vision`（旧 01 を移行元に）→ `/product-requirements init`（旧 02 とコードから） |
| 旧文書の無い既存プロジェクト | `/product-vision` → `/product-requirements init`（コードから） |

## やらないこと

- vision.md・領域ファイルの中身を書く → `/product-vision`、`/product-requirements`
- 旧文書を消す・移す → 扱いは `/product-requirements init` の後の `docs-review all` で決める
- 既存ファイルの上書き
