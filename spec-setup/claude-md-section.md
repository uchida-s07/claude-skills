## 開発ワークフロー

このプロジェクトは仕様駆動ワークフローで開発する。常設の要求（`docs/product/vision.md`）と要件（`docs/product/requirements/`）を「今の姿」として積み上げ、変更ごとに spec（`docs/specs/NNN-<name>/`）を1枚作る。
要件と受入基準の書き方は `~/.claude/skills/product-requirements/rules.md` に従う。

### 設定

<!-- spec-check と spec-verify がこの節を読む。項目名を変えない。 -->

- テストの実行: `{テスト全体を実行するコマンド}`
- lint の実行: `{lint のコマンド。無ければ「なし」}`
- テストの置き場所: {任意。例 `tests/**`, `src/**/*.test.ts`。書かなければリポジトリ全体から探す}
- 全体レビューを勧める done の件数: 3
- 全体レビューを勧める進行中 spec の件数: 2
- approved のまま注意を出す日数: 30

### ティア

| ティア | 対象 | 用意するもの |
|---|---|---|
| S | バグ修正、文言変更、小さなUI調整 | spec ファイルは作らない。振る舞いが変わったら `/product-requirements update` で常設要件を直す |
| M | 通常の機能追加 | `spec.md`、`tasks.md` |
| L | 新規プロジェクト、アーキテクチャに影響する変更 | `spec.md`、`design.md`、`tasks.md`。必要なら ADR。`vision.md` が必須 |

### 流れ

```
/spec-new → （spec-review で未解決0件・未決事項ゼロ）→ ユーザーが承認 → /spec-plan → 実装（AC ごとのサイクル）→ /spec-close
```

### レビューと点検のタイミング

| # | タイミング | 呼ぶもの | 誰が呼ぶか | 未解決の矛盾・欠落が残ったとき |
|---|---|---|---|---|
| ① | vision.md を作った・更新した直後 | `spec-check` → `docs-review vision` | `/product-vision` が自動で | vision を完成にしない |
| ② | 常設要件を導入した・spec を経ずに直した直後 | `spec-check` → init は `docs-review all`、update は `docs-review requirements <領域>` | `/product-requirements` が自動で | 導入・更新を完了にしない |
| ③ | Lティアの spec を書き始める前 | `spec-check`（全体） | `/spec-new` が自動で | 先に直すか承知で進めるかをユーザーが決める |
| ④ | spec の draft を書き上げた直後 | `spec-check spec NNN` → `spec-review NNN` | `/spec-new` が自動で | approved にしない |
| ⑤ | tasks.md を作る前（承認後に周辺の文書が git 上で変わっていたときだけ） | `spec-review NNN` | `/spec-plan` が自動で | spec を draft に戻して直す |
| ⑥ | spec を閉じる前 | `spec-verify NNN` | `/spec-close` が自動で | 常設要件へ移さない |
| ⑦ | 常設要件へ移した直後 | `spec-check`（全体） | `/spec-close` が自動で | done にしない |
| ⑧ | done にしたとき、前回の全体レビューから done が上の件数以上たまっていたら | `docs-review all` | `/spec-close` が勧める | — |
| ⑨ | リリース前、久しぶりに戻ったとき、進行中の spec が上の件数以上になったとき | `docs-review all` | ユーザーが手動で（`/spec-new` も勧める） | — |

- 関門は「未解決の矛盾・欠落が0件」。ユーザーが「誤検知」「承知で進める」と判断した指摘は、理由を `docs/review-notes.md` に書けば解消扱いになる。
- 自動のレビュー・点検は省略しない。ユーザーが明示して飛ばしたときは `docs/review-notes.md` に「飛ばした」と書く。

### 規則

- ID は常設 ID を使う（spec の中でも）。機能要件 `<領域>-F-nnn`、非機能要件 `<領域>-N-nnn` / `COMMON-N-nnn`、受入基準 `<要件ID>/AC-n`。
- テスト名（または説明文）に `[<要件ID>/AC-n]` を含める。例：`[MEAL-F-004/AC-1] 前日21時に不要を登録すると一覧から除外される`
- DB・API の設計書は持たない。**コードが正。** spec には差分だけ書く。
- 実装は tasks.md のタスクを AC ごとのサイクルで進める：受入基準のテストを書く → 実行して**期待どおりの理由で失敗する**ことを確かめ、失敗の要点を tasks.md の「Red」欄に書く（コンパイルエラーや import の失敗は数えない）→ 実装する（込み入った部分は単体テストを先に書きながら）→ 対象のテストとテスト全体が通る → リファクタしてもう一度全体が通る → テストと実装を1コミットにする。Red の記録は `spec-verify` が確かめる。
