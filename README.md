# AIC Lab Multilingual Hugo Website

This starter is designed for the AIC Lab research website with English, Japanese, and Chinese pages. The layout reads structured YAML files from `data/`, so routine maintenance can be done by editing data instead of touching templates.

## Display Names

- Header brand: language-specific abbreviation plus full lab name
- Site title: AIC Lab
- Browser tab title: AIC Lab
- Footer: AIC Lab
- Main page title: AIC Lab

The browser tab title is fixed to `AIC Lab` for every page.

The lab logo is stored at:

```text
static/images/aiclab_logo.png
```

## Language URLs

- English: `/en/`
- Japanese: `/ja/`
- Chinese: `/zh/`

## Main Sections

- Home
- Members
- Publications
- Projects
- News
- Access
- Links

## What To Edit Later

Most updates should happen in these folders:

```text
data/
+-- en/
+-- ja/
+-- projects.yaml
+-- publications.yaml
`-- zh/
```

For example:

- Add a paper: edit the shared `data/publications.yaml`.
- Add a research project/grant: edit the shared `data/projects.yaml`.
- Add news: edit the shared `data/news.yaml`.
- Add or update members: edit the shared `data/members.yaml`.
- Update address or map link: edit `data/*/access.yaml`.
- Add external resources: edit `data/*/links.yaml`.

## Members

Members are shared across English, Japanese, and Chinese pages. Edit only:

```text
data/members.yaml
```

The file is organized as one top-level entry per member, similar to `data/projects.yaml` and `data/publications.yaml`:

```yaml
cheng_tang:
  group: "faculty"
  display: true
  sort_weight: 10
  name:
    en: "Cheng Tang"
    ja: "唐 成"
    zh: "唐 成"
  role:
    en: "Associate Professor"
    ja: "准教授"
    zh: "副教授"
  grade: ""
  email: "tangcheng.ac@outlook.com"
  url: ""
  origin:
    en: ""
    ja: ""
    zh: ""
  interests:
    en: "Artificial intelligence, communication systems"
    ja: "人工知能，通信システム"
    zh: "人工智能、通信系统"
  hobbies:
    en: ""
    ja: ""
    zh: ""
  message:
    en: ""
    ja: ""
    zh: ""
```

Use `display: true` to show a member and `display: false` to hide one without deleting the entry. If `display` is omitted, the site treats the member as visible by default.

Use `group: "faculty"`, `group: "collaborator"`, `group: "student"`, or `group: "alumni"`. For students, add `student_type: "doctoral"`, `student_type: "master"`, `student_type: "research"`, or `student_type: "undergraduate"`. The Students section is displayed as a collapsible section. Use `grade` values such as `D1`, `D2`, `D3`, `M1`, `M2`, or `B4`. Alumni and former faculty use `group: "alumni"` with a `year` field and are grouped by year on the website. Empty groups are hidden automatically. Optional profile fields include `origin`, `interests`, `hobbies`, `message`, `email`, and `url`. The `data/members.yaml` file includes visible `example_*` entries for faculty, collaborators, doctoral students, master's students, undergraduate students, and alumni; copy one of them when adding a new member.

## Publications

Publications are shared across English, Japanese, and Chinese pages. Edit only:

```text
data/publications.yaml
```

The list is organized as one top-level entry per paper, similar to BibTeX:

```yaml
journal_2026_01:
  type: "journal"
  title: "Paper title"
  authors: "Author A, Cheng Tang, Author B"
  journal: "Journal name"
  year: 2026
  month: "01"
  volume: "10"
  number: "2"
  pages: "100--110"
  doi: "https://doi.org/..."
  url: "https://..."
```

To add a paper, copy one of the hidden `example_*` entries at the top of `data/publications.yaml`, give it a unique entry ID, edit the fields, and change `display: false` to `display: true`. Use IDs such as `journal_2026_01`, `conference_2026_01`, or `preprint_01`. Use `type: "preprint"`, `type: "journal"`, or `type: "conference"`. For the publication source, use `journal:`, `conference:`, or `preprint:` according to the type. Add `month: "01"` to display dates as `2026.01`. Add `doi: "https://doi.org/..."` when available, or `url: "https://..."` when there is no DOI. The right-side `Link` button uses DOI first, then URL, and falls back to a Google Scholar title search. The site automatically displays preprints first, then groups journal and conference papers by Japanese academic/fiscal year in descending order. The Japanese academic year runs from April to March, so January-March papers are grouped into the previous fiscal year. Each fiscal year contains collapsible `Journal Papers` and `Conference Papers` sections. Publication numbers are generated automatically from the oldest to newest item within each type: `P001` for preprints, `J001` for journal papers, and `C001` for conference papers.

## Citation Updates

Citation display can be turned on or off in `hugo.toml`:

```toml
[params]
  showCitations = true
```

When `showCitations` is `true`, the Publications page displays the top citation metrics panel, citation totals beside publication groups, and citation counts beside individual papers. When it is `false`, all citation metrics are hidden from the site, while the updater can still keep citation fields in `data/publications.yaml` and `data/citation_meta.yaml`.

The workflow at `.github/workflows/update-citations.yml` updates citation counts once per day using Google Scholar through the Python `scholarly` package. The configured Google Scholar profile ID is:

```text
GvXOVv0AAAAJ
```

The script also updates `data/citation_meta.yaml`, which is displayed next to the citation source as the latest update date. After this workflow completes successfully, `.github/workflows/hugo.yml` is also triggered so the public GitHub Pages site can be rebuilt with the latest citation data.

The script is:

```text
scripts/update_citations.py
```

It reads publication field names case-insensitively, so `title`, `Title`, and `TITLE` are treated the same. Title matching is also case-insensitive. It updates existing entries in place by replacing or inserting only citation-related fields, instead of reformatting and reordering the whole file. If there are no citation changes and no new papers, the script leaves `data/publications.yaml` untouched.

With the default Google Scholar source, the script loads the publication list from the configured Scholar profile and matches existing entries by title. Publications from the Scholar profile that are not yet in `data/publications.yaml` are inserted near the top as review-required templates.

Some Google Scholar records can be intentionally ignored. The ignore list is maintained in `scripts/update_citations.py` as `IGNORED_PUBLICATION_TITLE_TEXTS`; ignored titles are neither updated nor inserted as new publication templates. If Google Scholar returns duplicate records with the same normalized title, their citation counts are merged before matching, so duplicate Scholar records contribute a combined citation count to the corresponding YAML entry.

The citation source can be changed with:

```text
CITATION_SOURCE=google_scholar
GOOGLE_SCHOLAR_ID=GvXOVv0AAAAJ
```

OpenAlex remains available as a fallback source:

```text
CITATION_SOURCE=openalex
OPENALEX_AUTHOR_ID=...
```

Optional OpenAlex repository secrets:

```text
OPENALEX_API_KEY
OPENALEX_EMAIL
```

If the selected source contains papers that are not yet in `data/publications.yaml`, the script inserts review-required templates near the top of the file:

```yaml
new_publication_2026_01:
  # TODO: Review this automatically added Google Scholar entry.
  type: ""
  title: "Paper title from Google Scholar"
  authors: ""
  journal: ""
  conference: ""
  preprint: ""
  year: 2026
  month: ""
  doi: ""
  link: ""
  citations: 0
```

Review these entries regularly, fill missing fields, and rename IDs to the normal format such as `journal_2026_01`, `conference_2026_01`, or `preprint_01`. The publication page displays citation counts on the right side of each paper title. The right-side paper button supports `doi`, `url`, and `link`; if none exists, it falls back to a Google Scholar title search.

## Projects

Research grants/projects are shared across English, Japanese, and Chinese pages. Edit only:

```text
data/projects.yaml
```

The list is organized as one top-level entry per project:

```yaml
rg_003:
  code: "RG003"
  title: "Project title"
  title_ja: "Japanese title, if available"
  funder: "Funding agency"
  funder_ja: "Japanese funding program name, if available"
  institution: "Institution name"
  program: "Program name"
  grant_number: "JP..."
  period: "2025-2026"
  start_year: 2025
  end_year: 2026
  role: "PI"
  role_type: "principal"
```

To add a project, copy one of the hidden `example_*` entries at the top of `data/projects.yaml`, give it a unique entry ID, edit the fields, and change `display: false` to `display: true`. Use `role_type: "principal"` for projects led by the lab member and `role_type: "collaborator"` for collaborative projects. The projects page groups entries into collapsible ongoing and completed sections, and each section is further grouped by role. The Japanese labels are `代表者` and `分担者`; the Chinese labels are `项目负责人` and `共同研究人员`. Empty role groups are hidden automatically. Projects are sorted by `start_year` in descending order; if two projects have the same `start_year`, the project with the later `end_year` appears first. A project is treated as completed when `end_year` is earlier than the current year.

## News

News items are shared across English, Japanese, and Chinese pages. Edit only:

```text
data/news.yaml
```

The file is organized as one top-level entry per news item, similar to `data/projects.yaml` and `data/publications.yaml`. Each language-specific text field uses `en`, `ja`, and `zh` subfields:

```yaml
news_2026_04_01_01:
  display: true
  date: "2026-04-01"
  student_year: ""
  title:
    en: "News title"
    ja: "ニュースタイトル"
    zh: "动态标题"
  person_name:
    en: "Cheng Tang"
    ja: "唐 成"
    zh: "唐 成"
  person_type:
    en: "Faculty"
    ja: "教員"
    zh: "教师"
  position:
    en: "Associate Professor"
    ja: "准教授"
    zh: "副教授"
  text:
    en: "News body with **Markdown** and [links](https://example.com/)."
    ja: "Markdown と [リンク](https://example.com/) を利用できます．"
    zh: "可以使用 **Markdown** 和 [链接](https://example.com/)。"
```

Use `display: true` to show a news item and `display: false` to hide it. The website renders the person fields as a prefix such as `(Faculty, Associate Professor) Cheng Tang`. For students, use fields such as `person_type.en: "Student"` and `position.en: "M1"`, `M2`, `D1`, or `B4`, with corresponding Japanese and Chinese values. Markdown links in `title` and `text` are rendered as clickable links on the website. News is sorted automatically by `date` and grouped by Japanese academic/fiscal year, where April to the following March forms one fiscal year.

## Theme Strategy

This starter includes local layouts in `layouts/` so it can work as a minimal Hugo site. If you later choose an existing Hugo theme, keep `data/` and `hugo.toml`, then either:

1. Move these layouts into the theme override layer, or
2. Adapt the selected theme templates to read from the same `data/` files.

The important boundary is:

- Design and HTML: `layouts/`, `assets/css/`
- Lab content and maintenance: `data/`
- Language and menus: `hugo.toml`

## Run Locally

Install Hugo Extended, then run:

```powershell
hugo server
```

Build the static site:

```powershell
hugo --minify
```

## GitHub Pages

The included workflow at `.github/workflows/hugo.yml` builds the site and deploys it to GitHub Pages.

In the GitHub repository, enable:

Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
