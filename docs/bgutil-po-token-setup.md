# bgutil-ytdlp-pot-provider Setup (macOS, Node 22)

YouTube now requires **GVS PO Tokens** for almost all yt-dlp client paths. Without one, downloads fail with:

```
android client https formats require a GVS PO Token which was not provided.
... HTTP Error 403: Forbidden
```

The fix is to run a local **PO Token provider** (Node service) and a yt-dlp Python plugin that talks to it. The official project is [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider).

This doc captures the exact setup that worked on macOS with Node v22 and yt-dlp nightly. The upstream README assumes Docker; this doc walks the no-Docker path and the ESM/CJS quirk we hit along the way.

---

## What you end up with

- A long-running Node helper on `http://127.0.0.1:4416` that mints PO Tokens.
- A yt-dlp Python plugin that auto-discovers it.
- Two new env vars in this project's `.env` so the pipeline uses both correctly.

```
+----------------+       +-----------------------------+       +-----------+
| social_crew.py | --->  | yt-dlp + Python plugin      | --->  | YouTube   |
| (PipelineConfig|       | (uses PO Tokens)            |       |           |
|  YTDLP_*)      |       +--------------+--------------+       +-----------+
+----------------+                      |
                                        v
                       +----------------------------------+
                       | Node helper @ 127.0.0.1:4416     |
                       | (server/src/main.ts)             |
                       +----------------------------------+
```

---

## Prerequisites

- Node `>= 20` (we used 22.x). `node -v`
- Python venv from this repo. `./venv/bin/python --version`
- A `cookies.txt` (Netscape format) export of `youtube.com` while logged in.
  See README "YouTube downloads (403 / SABR)" section for export instructions.

---

## 1. Clone the helper repo

```bash
cd ~
git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider
cd bgutil-ytdlp-pot-provider/server
npm install
```

The repo has no `npm run build`. The TypeScript is run directly via a loader.

---

## 2. Patch `src/main.ts` for ESM/CJS interop

Out of the box `src/main.ts` starts with:

```ts
import { Command } from "commander";
```

When run under Node's ESM loader (Node 22 + the project's `"type": "module"`), this fails with:

```
SyntaxError: The requested module 'commander' does not provide an export named 'Command'
```

Variants we tried that ALSO fail:

- `import commander from "commander"; const { Command } = commander;`  
  -> `does not provide an export named 'default'`
- `import * as commanderPkg from "commander"; const { Command } = commanderPkg;`  
  -> `Command is not a constructor` (namespace shape mismatch under the loader)

The fix is to force CommonJS resolution via `createRequire`:

```bash
sed -i '' 's|import { Command } from "commander";|import { createRequire as __cr } from "module"; const { Command } = __cr(import.meta.url)("commander");|' src/main.ts
```

Verify:

```bash
sed -n '1,7p' src/main.ts
# expect line 3 to read:
# import { createRequire as __cr } from "module"; const { Command } = __cr(import.meta.url)("commander");
```

> If you ever `git pull` upstream and it breaks again, re-apply this patch.

---

## 3. Run the helper server

In its own terminal (leave it running):

```bash
cd ~/bgutil-ytdlp-pot-provider/server
node --import @swc-node/register/esm-register src/main.ts
```

Verify in another terminal:

```bash
curl http://127.0.0.1:4416/ping
# {"server_uptime":...,"version":"1.3.1"}
```

If you ever stop seeing 200 here, the rest of the pipeline will silently lose PO Token coverage and YouTube downloads will start 403'ing again.

---

## 4. Install the Python plugin into this repo's venv

```bash
cd /Users/alexglaze/revenue_crew
./venv/bin/python -m pip install -U bgutil-ytdlp-pot-provider
```

The plugin auto-detects the helper at `http://127.0.0.1:4416`.

---

## 5. Configure `.env`

Add (or confirm):

```
YTDLP_COOKIES_FILE=cookies.txt
YTDLP_PLAYER_CLIENT=web,tv,android
```

These two variables together tell yt-dlp:

1. Use the logged-in cookies for `youtube.com`.
2. Mint PO Tokens via the plugin for these clients.

---

## 6. Run the pipeline

Helper terminal still running. In project terminal:

```bash
python social_crew.py
```

Success markers:

- The `GVS PO Token which was not provided` warning is gone.
- Files appear under `outputs/` (e.g. `EvIBrUDnh8s.mp4`).
- Telegram run summary shows `> 0` approval candidates.
- DB row in `runs` shows `total_clips > 0`.

---

## Optional: smoke test yt-dlp directly

```bash
./venv/bin/yt-dlp --cookies cookies.txt \
  --extractor-args "youtube:player_client=web,tv,android" \
  -f 18 -o "outputs/%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

If this downloads a file, the full pipeline will too.

---

## Maintenance

YouTube changes the token format every few weeks. When downloads start failing again:

```bash
# Update plugin + yt-dlp
cd /Users/alexglaze/revenue_crew
./venv/bin/python -m pip install -U bgutil-ytdlp-pot-provider yt-dlp

# Update helper
cd ~/bgutil-ytdlp-pot-provider
git pull
cd server
npm install
# re-apply the createRequire patch from step 2 if upstream main.ts changed
```

Then restart the helper and rerun.

---

## If this stops working entirely

Fallback paths in priority order:

1. Drop a manually downloaded mp4 into a local source folder (planned `LOCAL_SOURCE_DIR` mode).
2. Move to a paid hosted downloader API or residential proxy (see chat history "option 3" details).
3. Switch primary source to platforms that don't require token games (Twitch VODs, podcast RSS, TikTok).

---

## Why we did this

For this project's goal (clip generation from long-form video), YouTube is by far the deepest catalog. Accepting periodic ~24-72h breakage is cheaper than maintaining alternative source pipelines for everyday use, but the local-source fallback (above) keeps the pipeline usable on bad days.
