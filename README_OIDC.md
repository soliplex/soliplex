1. Create workspace in ORY
2. Create a project inside that workspace
3. Go to Oauth2 tab in your project
4. Create a new Oauth2 Client of type "Server application"
5. Give it a name
6. For scope, specify "openid" "email" "profile" "offline_access"
7. For "Redirect URIs" it will depend on your case, but if running in localhost, specify http://localhost:8000/api/auth/{client_name}
8. For the rest of configurations, you can leave them as the default values.

When clicking "Save", you will get a Client Secret. Note it down as CLIENT_SECRET

Now, click the three dots for the client you just created, and click "Edit client". In the modal that pops up, you will find the "Client ID". Note it down as CLIENT_ID. You can click "Cancel" to close the modal

On the left side, click the "Endpoints" menu. Look for any of the provided endpoints and only copy the hostname, without the path, as the SERVER_URL


Now, when configuring the "oidc" for soliplex, in the config.yaml, you will have something like this:
```
oidc_client_pem_path: "./cacert.pem"
auth_systems:

  - id: "ory"
    title: "Authenticate with Ory"
    server_url: "{{ SERVER_URL }}"
    client_id: "{{ CLIENT_ID }}"
    client_secret: "{{ CLIENT_SECRET }}"
    scope: "openid email profile offline_access"
    include_return_to: false
```

After saving and restarting the server, you should be able to login by visiting http://localhost:8000/api/login/{client_name}

the `include_return_to` setting is included so you can avoid having the `return_to` added to the `redirect_url` as apparently ory doesn't support that.
