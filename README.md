# Portfolio Acquisition Task Board

A shared task board for Adam and Catherine to track patent portfolio acquisition work.

## Local Setup

```bash
git clone <repo-url> && cd portfolio-taskboard
pip install flask
python app.py
```

Open http://localhost:5000 — default passphrase is `changeme`.

## Deploy to Render

1. Push this repo to GitHub
2. Connect the repo on [Render](https://render.com) (use the `render.yaml` blueprint)
3. Set the `PASSPHRASE` environment variable to something secure
4. Deploy
