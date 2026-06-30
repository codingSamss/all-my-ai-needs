# Video Transcribe Troubleshooting

## yt-dlp

- `No video formats found`, `SABR`, or YouTube challenge errors: retry with `uvx --from yt-dlp yt-dlp` before changing the global install.
- Browser cookie errors: retry without `--cookies-from-browser chrome`.
- Private or age-gated sources: ask the user for an accessible URL or explicit login/cookie direction.

## Groq

- `401`: `GROQ_API_KEY` is missing, invalid, or expired.
- `403`: network path is blocked; retry with `HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897`.
- `413`: the audio chunk is too large; reduce `--segment-seconds`.
- `429`: rate limit; retry after a short wait.
- Bad terminology: rerun with a stronger `--prompt` containing product names and acronyms.

## ffmpeg

- Empty audio output usually means the source has no audio track or the downloaded file is incomplete.
- If copied audio segments remain too large, lower `--segment-seconds`; if copy segmentation fails, re-encode the source audio at lower bitrate first.
- For keyframes around exact chapter starts, prefer `--timestamps` over uniform extraction.

## Note Quality

- If the note feels like a wall of timestamps, add a phase guide table and collapse timestamp detail under callouts.
- If the user says they will not watch the video, include coverage evidence and accuracy notes, not only a polished summary.
- If a section is derived from synthesis rather than directly stated, label it as a derived playbook or interpretation.
