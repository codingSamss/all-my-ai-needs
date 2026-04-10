# Xiaohongshu Extraction Checklist

## Goal

Use HTTP/API first to extract profile/note data, and use Playwright only as fallback when risk control blocks API.

## Quick Steps

1. Run HTTP-first reader:
   `python3 scripts/xhs_http_reader.py --url "<link>" --mode auto --pretty`
2. Check result:
   - `fallback.required=false`: use data directly.
   - `fallback.required=true`: run Playwright fallback for that step.
3. Normalize who-is-undercover lines with `scripts/undercover_parser.py`.

## HTTP Reader Behavior

- `profile` mode:
  - Resolves `xhslink` to final profile URL.
  - Extracts note cards from SSR HTML (title + note URL + note id).
- `note` mode:
  - Extracts title/desc/author from note SSR state.
  - Tries comment API and returns explicit status:
    - `ok`: comments available via HTTP
    - `blocked`: risk control; use Playwright for comments
    - `unavailable`: token missing; use Playwright

## Captcha/Login Gate Signals

- Page title is `Security Verification`.
- Only QR/login panel is visible.
- Redirect path includes `/website-login/captcha`.

When any signal appears:

1. Mark current step as HTTP blocked.
2. Switch to Playwright for this step.
3. If Playwright is also blocked, ask user to refresh local login session.

## Optional DOM Extraction Snippet

Use this in Playwright `browser_run_code` when snapshot text is insufficient:

```javascript
async (page) => {
  return await page.evaluate(() => {
    const seen = new Set();
    const out = [];
    const nodes = Array.from(document.querySelectorAll("section,article,div"));

    for (const el of nodes) {
      const txt = (el.innerText || "").replace(/\s+/g, " ").trim();
      if (!txt) continue;
      if (txt.length > 220) continue;
      if (!txt.includes("谁是卧底")) continue;
      if (seen.has(txt)) continue;
      seen.add(txt);
      out.push(txt);
    }
    return out.slice(0, 80);
  });
}
```

## Normalize and Detect Odd Word

```bash
python3 scripts/undercover_parser.py --file groups.txt --only-valid
```

Input line examples:

- `脑袋｜屁股｜屁股｜屁股`
- `暴富,暴富,暴富,搬砖`
- `1. 恋人 朋友 朋友 朋友`
