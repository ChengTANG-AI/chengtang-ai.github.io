# 唐成 個人ウェブサイト

このリポジトリは，名古屋工業大学准教授 唐成の個人研究者ウェブサイトです．

Hugo により構築された三言語対応サイトであり，Research，Publications，Projects，News などの情報は YAML ファイルで管理しています．通常の更新ではテンプレートを編集せず，データファイルを修正するだけで内容を更新できます．

## 主な機能

- 英語，日本語，中国語の三言語対応．
- プロフィール，略歴，外部リンク，連絡先を含む個人ホームページ．
- Research，Publications，Projects，News，Access，Links のデータ管理．
- 論文情報は `data/publications/` に年度別で保存．
- 研究紹介は `data/research/` に研究方向ごとに保存．
- `scripts/update_citations.py` による Google Scholar 引用数更新．
- GitHub Actions による GitHub Pages 自動デプロイ．

## ローカル確認

```powershell
hugo server -D
```

本番用ビルド：

```powershell
hugo --minify
```

## データ管理

- `data/home/`: プロフィール，略歴，ホームページ内容．
- `data/access/`: 連絡先・アクセス情報．
- `data/links/`: Google Scholar，ORCID，GitHub，researchmap などの外部リンク．
- `data/research/`: 研究方向と代表論文．
- `data/publications/`: 年度別論文リスト．
- `data/projects/items.yaml`: 研究プロジェクト．
- `data/news/<year>/`: 年度別ニュース．
- `data/citations/meta.yaml`: 引用統計と最終更新時刻．

三言語データでは，共通項目を可能な限り `en.yaml` に置き，`ja.yaml` と `zh.yaml` には同じ ID に対応する翻訳・上書き情報のみを記述します．

## 引用数更新

手動更新：

```powershell
python scripts/update_citations.py
```

このスクリプトは Google Scholar プロフィールから論文情報を取得し，全ての論文 YAML に引用数を反映します．また `data/citations/meta.yaml` を更新し，新しい論文が検出された場合は対応する年度ファイルへ追加できます．

`.github/workflows/update-citations.yml` は，日本時間の深夜頃と中国時間の正午頃に毎日自動実行されます．

## デプロイ

`.github/workflows/hugo.yml` により GitHub Pages へ自動公開されます．GitHub に push すると，サイトが自動的にビルド・公開されます．
