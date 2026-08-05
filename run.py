name: Build and deploy

on:
  push:
    branches: [main]
  workflow_dispatch:          # the "Run workflow" button in the Actions tab

  # Uncomment these once the scrapers in pipeline/run.py actually work.
  # schedule:
  #   - cron: "0 22 * * 5"    # Fri 5pm Chicago (UTC, drifts an hour in winter)
  #   - cron: "0 13 * * 6,0"  # Sat & Sun 8am Chicago

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # ---------------------------------------------------------------
      # LISTINGS — commented out on purpose. The site deploys with demo
      # data until you've written the scrapers. Uncomment this whole
      # block when pipeline/run.py works, and add AMC_KEY and TMDB_KEY
      # under Settings > Secrets and variables > Actions.
      # ---------------------------------------------------------------
      # - uses: actions/setup-python@v5
      #   with:
      #     python-version: "3.12"
      #     cache: pip
      # - run: pip install -r pipeline/requirements.txt
      # - run: python -m playwright install --with-deps chromium
      # - name: Fetch showtimes
      #   env:
      #     AMC_KEY: ${{ secrets.AMC_KEY }}
      #     TMDB_KEY: ${{ secrets.TMDB_KEY }}
      #   run: python pipeline/run.py --out src/slate.json
      # - name: Commit listings
      #   run: |
      #     git config user.name  "marquee-bot"
      #     git config user.email "marquee-bot@users.noreply.github.com"
      #     git add src/slate.json
      #     git diff --staged --quiet || git commit -m "listings $(date -u +%F)"
      #     git push

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
      - run: npm ci
      - run: npm run build

      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
