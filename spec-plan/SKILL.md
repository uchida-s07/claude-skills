---
name: spec-plan
description: 仕様駆動ワークフロー（docs/product・docs/specs）用。approved の spec から実装計画 tasks.md を作る。承認後に vision・常設要件・他の spec・architecture・ADR が git 上で変わっていたら spec-review をもう一度通す。タスクは「DB変更 → 受入基準のテスト（失敗する状態）→ 実装 → テストが通る」の順で、各タスクに対応する要件 ID / AC・対象ファイル・完了条件を書き、すべての AC がどれかのタスクで扱われているかを確かめる。コードは変更しない。引数に spec 番号を渡す。
disable-model-invocation: true
argument-hint: "<spec番号>"
---

# spec-plan（実装計画を作る）

approved の spec から `tasks.md` を作る。対象の spec：$ARGUMENTS
**コードは変更しない。**

- 共通ルール：`${CLAUDE_SKILL_DIR}/../product-requirements/rules.md`（ID・テスト名の規則、レビュー指摘の扱い）
- 雛形：`${CLAUDE_SKILL_DIR}/template-tasks.md`

## 手順

### 1. spec を確かめる

- `docs/specs/NNN-*/spec.md` を探す（番号は3桁ゼロ埋め）。見つからなければ止める。
- `status` が `approved` でなければ中止する。draft なら `/spec-new` で承認まで進めるよう案内する。
- すでに `tasks.md` があれば、作り直すか、差分を足すかをユーザーに聞く。

### 2. 承認後の変更を確かめる（タイミング⑤）

spec の `approved:` の日時より後に、周辺の文書が変わっていないかを確かめる。

```bash
git log --since="<approved: の日時>" --name-only --format="%h %ad %s" --date=short -- docs/product docs/architecture.md docs/adr docs/specs
```

- 自分の spec のディレクトリ（`docs/specs/NNN-*/`）の変更は除いて判断する。
- git 管理でなければ、同じ範囲のファイルの更新日時で代える。
- **変わっていなければ** 3 へ。
- **変わっていれば**、変わったファイルと内容の要点を見せ、`spec-review` を呼ぶ（Skill ツールで `spec-review`、引数 `NNN ⑤`）。
  - 未解決の矛盾・欠落が0件 → spec の `review:` 欄を更新して 3 へ。
  - 残った → spec を `status: draft` に戻し（`approved:` は空にする）、rules.md 第12章の「直し方」で直して、ユーザーの再承認を得てから計画に進む。誤検知・承知で進めるの判断は `docs/review-notes.md` に書く。

### 3. 読む

`CLAUDE.md`（テストの実行方法・規約）、`docs/architecture.md`、spec（と L なら design.md）、関連するコードとテストを読む。
「変更」「廃止」の要件については、今の常設要件の該当ブロックと、`[<要件ID>/AC-n]` のタグが付いた既存テストを探す（grep）。

### 4. tasks.md を作る

雛形から `docs/specs/NNN-*/tasks.md` を作る。

- 各タスクに、**対応する要件 ID / AC、対象ファイル、完了条件**を書く。
- 並びは次を基本にする：
  1. DB の変更（マイグレーションなど）
  2. 受入基準のテストを書く（**失敗する状態**で）。テスト名（または説明文）に `[<要件ID>/AC-n]` を含める
  3. 実装
  4. テストが通る（完了条件に「対象のテストとテスト全体が通る」を書く）
- 1タスクは1コミットで収まる粒度にする。
- 「変更」の要件で中身を書き換えた AC、「（廃止）」にした AC、「廃止」した要件について、**既存テストの修正・削除のタスク**を入れる。「影響を受ける既存テスト」の表にも書く。
- 画面・API の変更で、spec の「変更差分」に無いものが必要だと分かったら、タスクに入れずに止め、spec を直す必要があることをユーザーに伝える（spec に無い変更を計画に紛れ込ませない）。

### 5. AC の網羅を確かめる

- spec のすべての有効な AC（「（廃止）」を除く）が、どれかのタスクで扱われているか。「AC カバレッジ」の表を埋める。
- 影響を受ける既存テストがすべてタスクにあるか。
- 結果を**会話に表で出す**（AC ごとに対応タスク、漏れがあれば漏れ）。漏れがあればタスクを足す。

### 6. 見せて確かめる

tasks.md を見せ、並びと粒度をユーザーに確かめる。赤入れはその場でファイルに反映する。
最後に、実装の進め方（受入基準のテストを先に書くこと）と、全タスクが済んだら `/spec-close NNN` を使うことを案内する。

## やらないこと

- コード・テストを書く（計画だけ）
- spec の中身を変える（直す必要があれば spec を draft に戻して `/spec-new` の流れで直す）
