---
name: spec-check
description: 仕様駆動ワークフロー（docs/product・docs/specs）用の機械点検。同梱のスクリプトで、ID の重複・新規 ID の予約の重なり・vision や要件への参照の実在と廃止・受入基準の有無・AC とテスト（[<要件ID>/AC-n] のタグ）の対応・未定/TBD の残り・未決事項・領域の登録・done の spec の反映漏れ・雛形の節の揃いを判定し、矛盾/欠落/注意の一覧と合否を返す。ワークフローの決まった位置で作成用・レビュー用スキルから呼ぶもの、またはユーザーが明示して呼ぶもの。文書は書き換えない。旧フロー（01〜06 の連番文書）には使わない。
argument-hint: "[all | spec <番号> | area <領域コード>] [--with-tests]"
allowed-tools: Bash(python *) Bash(python3 *)
---

# spec-check（機械点検）

決まった規則で判定できる点検を、同梱のスクリプト `${CLAUDE_SKILL_DIR}/scripts/spec_check.py` で行う。
意味の判断（矛盾しているか、妥当か）はしない。それはレビュー用スキル（`spec-review` / `spec-verify` / `docs-review`）の仕事。
**文書もスクリプトも書き換えない。**

重大度・指摘の状態・除外の扱いは `${CLAUDE_SKILL_DIR}/../product-requirements/rules.md` 第12章に従う。

## 手順

### 1. 実行する

プロジェクトのルート（`docs/` のあるディレクトリ）で実行する。`python3` があれば `python3`、無ければ `python` を使う。

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/spec_check.py" $ARGUMENTS --root .
```

| 引数 | 範囲 |
|---|---|
| なし / `all` | 全体 |
| `spec <番号>` | その spec に関わる点検だけ。`--with-tests` を付けると、その spec の AC にテストがあるかも見る（`spec-verify` が使う。draft の段階では付けない） |
| `area <領域コード>` | その領域の常設要件に関わる点検だけ |

終了コード: 0 = 未解決の矛盾・欠落なし / 1 = あり / 2 = 実行できない（`docs/` が無い、spec が見つからないなど）。

### 2. 結果を示す

- スクリプトの出力をそのまま示す。
- 矛盾・欠落の各指摘に、**直し方の案を1行ずつ**添える（直すのは呼び出し元のスキルか、ユーザーとの会話）。
- 書式の読み違いなど、**スクリプトの誤りが疑われる指摘**はその旨を添える。スクリプトを勝手に直さない。
- 「情報」の行に「docs-review all を勧める」とあれば、それも伝える。

### 3. 呼び出し元へ返す

呼び出し元（作成用・レビュー用スキル）は、未解決の矛盾・欠落が0件になるまで先へ進まない。
ユーザーが「誤検知」「承知で進める」と判断した指摘は、呼び出し元が `docs/review-notes.md` の表に、キー（`SC:…`）をそのまま書いて除外する。`*` でまとめて除外できる（例 `SC:ac-no-test:NOTE-*`）。

## 点検項目

| キー | 重大度 | 内容 |
|---|---|---|
| `dup-id` | 矛盾 | 常設要件・vision・spec の中で ID や AC 番号が重複している。「廃止した要件」にある ID が有効な要件としても定義されている |
| `id-reserve-clash` | 矛盾 | 進行中の spec どうし、または spec と常設要件で、新規として予約した ID が重なっている |
| `ref-missing` | 欠落 | 存在しない vision 項目（G/P/J）や要件 ID を参照している。spec が「変更 / 廃止」する要件が常設要件に無い |
| `ref-retired` | 欠落 | 廃止済みの vision 項目・要件を参照している |
| `no-ac` | 欠落 | 有効な受入基準が無い機能要件 |
| `ac-no-test` | 欠落 | 受入基準に `[<要件ID>/AC-n]` のタグが付いたテストが無い（all / area、または spec と `--with-tests`） |
| `test-orphan` | 欠落 | テストのタグが、存在しない・廃止された AC を指している |
| `tbd` | 欠落 | vision.md・常設要件に「未定」「TBD」「要検討」が残っている |
| `open-question` | 欠落 | approved / done の spec に未決事項が残っている（draft なら注意） |
| `area-registry` | 欠落 | README の領域一覧と領域ファイルが一致しない。未登録の領域コードを使っている |
| `vision-unused` | 欠落 | どの要件にも「やらないこと」にも出てこない vision 項目（要件が1件も無いときは注意） |
| `done-not-merged` | 欠落 | done の spec の新規・変更の要件が常設要件に無い、出典に `specs/NNN` が無い、廃止が反映されていない |
| `index-mismatch` | 欠落 | 領域ファイルの「要件一覧」と本文の見出しが一致しない |
| `section-missing` | 欠落 | 雛形の節・項目（5項目、対応する要求、出典、status など）が無い。spec の「変更」で常設要件の AC が黙って消えている |
| `stale-approved` | 注意 | approved のまま一定日数（既定30日）経った spec |

「情報」には、進行中の spec の件数と、最後の全体レビュー以降に done になった spec の件数が出る（タイミング⑧⑨の判断に使う）。
件数の基準と日数は、プロジェクトの CLAUDE.md「開発ワークフロー」節の「設定」で変えられる。

## 注意

- スクリプトは雛形（`product-vision/template.md`、`product-requirements/template-*.md`、`spec-new/template-spec.md`、`spec-setup/template-review-notes.md`）の書式に依存して読む。**雛形の書式を変えたら、スクリプトも直す。**
- テストは、CLAUDE.md の「テストの置き場所」があればそこから、無ければリポジトリ全体（`docs/`・`.git`・`node_modules` などと `.md` ファイルを除く）から探す。
