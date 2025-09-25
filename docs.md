Client ID: CKpPhu6aa6b24bw5tz2l0rdMrUwDXbL3i4OGvPlQ
Client Secret: TR3ZZcFdXgPIofUMVaCtVssPfb7lTcOW1oJRbBclLa4xOUCJp9uAqZiGA0ZDa9nadsM5DFrVAPZQhsYEdQGLrH8p5gmF9paAcKirzRo5dx7lWYxvNdE74bnrsaprkDds

# Get token
curl -X POST -d "grant_type=password&username=rb&password=rb" -u"eBG4y4dtR9p7lg4rAL072WR9PRJxlW5bsrGmKLJx:4dfcf547-3427-4f3a-a070-70570f616db1" http://localhost:8080/api/o/token/

```
{"access_token": "o8DvuJs2t9tvMvQGtMwjh0vTUpnGAA", "expires_in": 36000, "token_type": "Bearer", "scope": "read write groups", "refresh_token": "f5fUoCvelCIsTZWgcdy9tQBKyfNSWf"}
```

# Retrieve users
curl -H "Authorization: Bearer nPCl6kuk4CwS8mepxbIkSN4VT5QZWL" http://localhost:8080/api/users/
curl -H "Authorization: Token a2ba0feb95fca1d95c8bb0b597761a97e050a369" http://localhost:8080/api/users/

curl -H "Authorization: Bearer o8DvuJs2t9tvMvQGtMwjh0vTUpnGAA" http://localhost:8080/api/users/1/

# Retrieve groups
curl -H "Authorization: Bearer o8DvuJs2t9tvMvQGtMwjh0vTUpnGAA" http://localhost:8080/api/groups/

# Insert a new user
curl -H "Authorization: Bearer o8DvuJs2t9tvMvQGtMwjh0vTUpnGAA" -X POST -d"username=foo&password=bar" http://localhost:8080/api/users/

---


OAUTH_CLIENT_ID=CKpPhu6aa6b24bw5tz2l0rdMrUwDXbL3i4OGvPlQ
OAUTH_CLIENT_SECRET=TR3ZZcFdXgPIofUMVaCtVssPfb7lTcOW1oJRbBclLa4xOUCJp9uAqZiGA0ZDa9nadsM5DFrVAPZQhsYEdQGLrH8p5gmF9paAcKirzRo5dx7lWYxvNdE74bnrsaprkDds
OAUTH_CODE_VERIFIER=MZRX3EZ84JOBOMBPXZY1XVRH12BPZB5SWT4Y6IEOHJWY77XZYI8IRJR1P7K93U3HKX8KFHVI3M7AG9L56YG
OAUTH_CODE=jxJ6agEzdSMIYvAmhucF2m7NOvsHvG

http://localhost:8080/oauth/authorize/?response_type=code&code_challenge=PpTct8akOBdXfM0Wr1zKKwni-iaYpP2fT7z-m-Vnqf8&code_challenge_method=S256&client_id=CKpPhu6aa6b24bw5tz2l0rdMrUwDXbL3i4OGvPlQ&redirect_uri=http://localhost:8080/noexist/callback

```bash
echo "OAUTH_CLIENT_ID=${OAUTH_CLIENT_ID}"
echo "OAUTH_CLIENT_SECRET=${OAUTH_CLIENT_SECRET}"
echo "OAUTH_CODE=${OAUTH_CODE}"
echo "OAUTH_CODE_VERIFIER=${OAUTH_CODE_VERIFIER}"

curl -X POST \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  "http://localhost:8080/oauth/token/" \
  -d "client_id=${OAUTH_CLIENT_ID}" \
  -d "client_secret=${OAUTH_CLIENT_SECRET}" \
  -d "code=${OAUTH_CODE}" \
  -d "code_verifier=${OAUTH_CODE_VERIFIER}" \
  -d "redirect_uri=http://localhost:8080/noexist/callback" \
  -d "grant_type=authorization_code"
```

```
{"access_token": "nPCl6kuk4CwS8mepxbIkSN4VT5QZWL", "expires_in": 36000, "token_type": "Bearer", "scope": "read write groups", "refresh_token": "qPBT3EZGJSjehVfc6JgntTDjwI55sT"}
```

## DCR

curl -X POST http://localhost:8080/oauth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Amazing App",
    "redirect_uris": [
      "http://localhost:8080/noexist/callback"
    ],
    "grant_types": ["authorization_code"],
    "response_types": ["code"],
    "scope": "read write",
    "client_uri": "http://myapp.com",
    "contacts": ["admin@myapp.com"]
  }'

  {"client_id": "DGJC0iMFJE09z8mgrgUCCUk6TocvqFjDQI8RyC9D", "client_secret": "pbkdf2_sha256$1000000$I1T3gcFq1cq4TQJDyik70K$Ryem4+HhiBE3i0nTVT7JPOiEHuhDhGZiPCkKIWdGh2U=", "client_id_issued_at": 1758766310, "client_name": "My Amazing App", "redirect_uris": ["http://localhost:8080/noexist/callback"], "grant_types": ["authorization_code"], "response_types": ["code"], "token_endpoint_auth_method": "client_secret_basic"}

  ```bash
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=
OAUTH_CODE
OAUTH_CODE_VERIFIER

curl -X POST \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  "http://localhost:8080/oauth/token/" \
  -d "client_id=${OAUTH_CLIENT_ID}" \
  -d "client_secret=${OAUTH_CLIENT_SECRET}" \
  -d "code=${OAUTH_CODE}" \
  -d "code_verifier=${OAUTH_CODE_VERIFIER}" \
  -d "redirect_uri=http://localhost:8080/noexist/callback" \
  -d "grant_type=authorization_code"
```