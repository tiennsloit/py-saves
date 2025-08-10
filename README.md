base64 -i credentials.json -o credentials.json.b64

az login

az keyvault secret set \
  --vault-name saves \
  --name "google-sheet--credential--file" \
  --value "$(cat credentials.json.b64)"

  pip install azure-identity azure-keyvault-secrets google-auth google-auth-oauthlib google-api-python-client

