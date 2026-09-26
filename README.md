# YouTube Downloader — FastAPI + GPT Action

A small FastAPI service designed to be connected to a GPT Action.

## Important use restriction

Use this project only for videos you own, videos whose creator/rightsholder has
given you permission to download, or content for which downloading is otherwise
authorized by the applicable service terms and law. YouTube's Terms restrict
downloading/reproducing content except where authorized by the service, with
permission, or as otherwise permitted by law.

## 1. Run locally with Docker

Install Docker, then:

```bash
docker compose up --build
```

Test:

```bash
curl http://localhost:8000/health
```

You should receive:

```json
{"status":"ok"}
```

## 2. Test the API

Set your API key:

```bash
export API_KEY="change-this-to-a-long-random-key"
```

Metadata:

```bash
curl -X POST http://localhost:8000/info \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}'
```

MP4:

```bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID","format":"mp4"}'
```

MP3:

```bash
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID","format":"mp3"}'
```

For MP3, FFmpeg is required. The Docker image includes it.

## 3. Deploy

Deploy the container to a server/container host that gives you HTTPS and a
public hostname.

Set:

- `DOWNLOADER_API_KEY` to a long random secret.
- `PUBLIC_BASE_URL` to your HTTPS public URL.
- `MAX_DURATION_SECONDS` to a sensible limit.

Example:

```text
DOWNLOADER_API_KEY=use-a-long-random-secret
PUBLIC_BASE_URL=https://downloader.example.com
MAX_DURATION_SECONDS=3600
```

Do not use `http://localhost:8000` as `PUBLIC_BASE_URL` after deployment.

## 4. Connect it to a GPT Action

In your GPT's Actions configuration:

1. Add an Action.
2. Import `openapi.yaml`.
3. Replace `https://YOUR_PUBLIC_DOMAIN.example` in the OpenAPI server URL
   with your real HTTPS URL.
4. Configure API-key authentication using the same value as
   `DOWNLOADER_API_KEY`.
5. The header name is `X-API-Key`.
6. Save/test the Action.

The GPT can then call:

- `getVideoInfo`
- `downloadVideo`

## 5. Suggested GPT instructions

Paste something like this into the GPT instructions:

```text
You are a YouTube download assistant for content the user is authorized to
download.

Before calling downloadVideo, ask for the YouTube URL and desired format if
they are not already supplied.

Only use the download action when the user confirms that they own the content,
have permission from the rights holder, or otherwise have the legal right to
download it.

For ordinary YouTube viewing, suggest using YouTube's official player instead.

When downloadVideo returns download_url, provide that link to the user.
If download_url is null, explain that the server needs a public HTTPS base URL.
```

## Production notes

- Add authentication/rate limiting at your reverse proxy.
- Consider automatic deletion of old files.
- Keep `downloads/` outside the public internet if you do not need public links.
- For a public service, add quotas and logging.
- Do not put the API key in the OpenAPI file.
- Do not commit `.env` or secrets to Git.
