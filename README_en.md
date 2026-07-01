# Cheng Tang Academic Website

This repository contains the personal academic website of Cheng Tang, Associate Professor at Nagoya Institute of Technology.

The site is built with Hugo and organized as a data-driven multilingual website. Research, publications, projects, and news are managed through YAML files so that routine updates can be made without editing templates.

## Main Features

- Multilingual pages in English, Japanese, and Chinese.
- Personal home page with profile, biography, links, and contact information.
- Reusable data structure for Research, Publications, Projects, News, Access, and Links.
- Publication records grouped by year under `data/publications/`.
- Research topics grouped by folder under `data/research/`.
- Google Scholar citation updates through `scripts/update_citations.py`.
- Automatic GitHub Pages deployment with GitHub Actions.

## Local Preview

```powershell
hugo server -D
```

Build the production site:

```powershell
hugo --minify
```

## Data Management

- `data/home/`: profile, biography, and home-page content.
- `data/access/`: contact and access information.
- `data/links/`: profile links such as Google Scholar, ORCID, GitHub, and researchmap.
- `data/research/`: research directions and featured papers.
- `data/publications/`: yearly publication files.
- `data/projects/items.yaml`: research projects.
- `data/news/<year>/`: yearly news entries.
- `data/citations/meta.yaml`: citation metrics and latest update time.

When a multilingual folder contains `en.yaml`, `ja.yaml`, and `zh.yaml`, shared fields are stored in `en.yaml` whenever possible. The Japanese and Chinese files provide translations or language-specific overrides by matching IDs.

## Citation Updates

Run manually:

```powershell
python scripts/update_citations.py
```

The script reads Cheng Tang's Google Scholar profile, updates citation counts across all publication YAML files, updates `data/citations/meta.yaml`, and can insert newly detected publications into the corresponding yearly file.

The scheduled workflow `.github/workflows/update-citations.yml` runs twice per day, around midnight in Japan and noon in China time.

## Deployment

The site is deployed to GitHub Pages by `.github/workflows/hugo.yml`. Push changes to GitHub, and the site will be built and published automatically.
