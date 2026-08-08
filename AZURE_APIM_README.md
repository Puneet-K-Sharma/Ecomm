# 🚀 StreamShop: Azure API Management (APIM) Setup & Migration Guide

This document describes how to replace the custom python `api-gateway` service with **Azure API Management (APIM)**. By moving to APIM, you get enterprise-grade security, rate-limiting, custom caching, logging, and performance metrics, while maintaining the key features of the original gateway:
1. **Stateless JWT Validation & Context Injection (`X-User-Email` header)**.
2. **Asynchronous Audit Logging** into the Azure SQL database.
3. **CORS Management**.
4. **Dynamic routing** to the microservices.

---

## 🏗️ Architectural Topology

```
                   +-----------------------------+
                   |       React Frontend        |
                   +--------------+--------------+
                                  |
                                  | (HTTPS requests via APIM Gateway URL)
                                  v
                   +--------------+--------------+
                   |    Azure API Management     |
                   |                             |
                   |  - CORS Policy              |
                   |  - JWT claim extraction     |
                   |  - Path-based backend route |
                   |  - Async Audit Logging      |
                   +-------+--------------+------+
                           |              |
         (API Requests)    |              | (One-way Fire & Forget POST)
                           v              v
+--------------------------+--------------+--------------------------+
| AKS Cluster (Virtual Network)                                      |
|                                                                    |
|    +------------------+                   +--------------------+   |
|    |   auth-service   |                   |    user-service    |   |
|    |      :8001       |                   |       :8002        |   |
|    +------------------+                   +---------+----------+   |
|                                                     |              |
|    +------------------+                             |              |
|    |  product-service |                             |              |
|    |      :8003       |                             | (Saves log)  |
|    +------------------+                             v              |
|                                           +---------+----------+   |
|    +------------------+                   |     Azure SQL      |   |
|    |  wishlist/other  |                   |      Database      |   |
|    |  services...     |                   +--------------------+   |
|    +------------------+                                            |
+--------------------------------------------------------------------+
```

---

## 🛠️ Step 1: Provision the Azure APIM Instance

You can provision Azure APIM via the Azure Portal or using the Azure CLI.

### Option A: Via Azure Portal
1. Search for **API Management services** in the Azure Portal and click **Create**.
2. Set the following options:
   - **Subscription**: Your subscription.
   - **Resource group**: Select your AKS resource group.
   - **Region**: Central India (or the region where AKS is deployed).
   - **Resource name**: `streamshop-apim` (needs to be globally unique).
   - **Organization name**: `StreamShop`.
   - **Administrator email**: Your email.
   - **Pricing tier**: **Developer** (for testing/development) or **Basic/Standard/Premium** (for production).
3. Click **Review + Create**, then **Create**. *(APIM provisioning can take 30-40 minutes).*

### Option B: Via Azure CLI
Run the following command to create an APIM instance:
```bash
az apim create \
  --name streamshop-apim \
  --resource-group StreamShopRG \
  --location centralindia \
  --publisher-name StreamShop \
  --publisher-email admin@puneetdevops.online \
  --sku-name Developer
```

---

## 🔒 Step 2: Establish Secure Networking

Since APIM needs to route traffic to the AKS backend microservices, they must be reachable. Choose one of these networking patterns:

### Pattern A: Virtual Network Integration (Recommended for Enterprise)
Deploy APIM inside a Virtual Network that is peered with your AKS Virtual Network:
1. Go to your APIM instance in the Azure Portal.
2. Select **Network** > **Virtual network**.
3. Choose **Internal** or **External** integration. 
   - **External**: APIM gets a public IP address but is connected to the VNet to resolve internal AKS private endpoints.
4. Configure APIM to use AKS CoreDNS for name resolution, allowing APIM to directly resolve K8s internal endpoints like `http://auth-service.default.svc.cluster.local`.

### Pattern B: Ingress with Public IP Whitelisting (Easiest Setup)
Expose the backend microservices publicly using an Ingress Controller, but configure IP restrictions so only APIM can access them.
1. Get the **Public IP Address** of your APIM instance from the Azure Portal (under Overview).
2. Configure your Nginx Ingress or Application Gateway Ingress (AGIC) to only accept requests originating from APIM's public IP:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: stream-backends-ing
     annotations:
       kubernetes.io/ingress.class: azure/application-gateway
       # Whitelist APIM public IP only
       appgw.ingress.kubernetes.io/whitelist-source-ips: "52.172.x.x"
   ```
3. APIM will then route backend requests to the public Ingress endpoint (e.g. `https://api.puneetdevops.online`).

---

## 📜 Step 3: Configure APIM APIs & Global Policies

Rather than defining dozens of endpoints manually, you can create a single APIM API with wildcard operations that forwards all traffic dynamically to the correct backend, using the custom APIM policy below.

### 1. Create the API
1. In the APIM left menu, click **APIs** > **+ Add API** > **HTTP**.
2. Configure:
   - **Display name**: `StreamShop API`
   - **Name**: `streamshop-api`
   - **Web service URL**: `http://stream-api-svc.default.svc.cluster.local` (or your public backend Ingress endpoint if using Pattern B).
   - **API URL suffix**: `api` (or leave blank if you want APIM to listen directly on the root path).
3. Click **Create**.

### 2. Define Wildcard Operations
Add a wildcard operation to catch all HTTP methods and paths:
1. Click **+ Add operation**.
2. Configure:
   - **Display name**: `Wildcard Route`
   - **URL**: `/*`
   - **Method**: `*` (or create separate operations for GET, POST, PUT, DELETE, PATCH, OPTIONS).
3. Click **Save**.

### 3. Apply the Policy
Replace the API policy with the following XML. This policy does the following:
*   **CORS**: Configures cross-origin resource sharing.
*   **JWT Processing**: Decodes the incoming Bearer JWT token, extracts the subject (email), and injects it as `X-User-Email` header.
*   **Routing**: Decides the downstream destination service based on the URL path segment (e.g. `/auth/*` to `auth-service:8001`, `/user/*` to `user-service:8002`, `/admin/audit-logs` to `user-service:8002`).
*   **Asynchronous Audit Logging**: In the outbound section, uses `<send-one-way-request>` to fire a POST payload to `/internal/audit-logs` on the `user-service`. It runs asynchronously so it doesn't block the frontend response!

#### APIM Policy Code (`policy.xml`):
```xml
<policies>
    <inbound>
        <base />
        <!-- 1. CORS Preflight & Header setup -->
        <cors allow-credentials="true">
            <allowed-origins>
                <origin>https://jpshop.puneetdevops.online</origin>
                <origin>http://jpshop.puneetdevops.online</origin>
                <origin>http://localhost:5173</origin>
                <origin>http://localhost:3000</origin>
            </allowed-origins>
            <allowed-methods>
                <value>GET</value>
                <value>POST</value>
                <value>PUT</value>
                <value>DELETE</value>
                <value>OPTIONS</value>
                <value>PATCH</value>
            </allowed-methods>
            <allowed-headers>
                <value>*</value>
            </allowed-headers>
        </cors>

        <!-- 2. Parse Bearer JWT token and inject X-User-Email -->
        <set-header name="X-User-Email" exists-action="override">
            <value>@{
                string authHeader = context.Request.Headers.GetValueOrDefault("Authorization", "");
                if (!string.IsNullOrEmpty(authHeader) && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
                {
                    try
                    {
                        string token = authHeader.Substring(7);
                        var jwt = token.AsJwt();
                        if (jwt != null)
                        {
                            return jwt.Claims.GetValueOrDefault("sub", "Unknown");
                        }
                    }
                    catch { }
                }
                return "Anonymous";
            }</value>
        </set-header>

        <!-- 3. Dynamic Routing to Downstream Services -->
        <choose>
            <when condition="@(context.Request.Url.Path.StartsWith("/auth"))">
                <set-backend-service base-url="http://auth-service:8001" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/user"))">
                <set-backend-service base-url="http://user-service:8002" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/product"))">
                <set-backend-service base-url="http://product-service:8003" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/cart"))">
                <set-backend-service base-url="http://cart-service:8004" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/order"))">
                <set-backend-service base-url="http://order-service:8005" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/payment"))">
                <set-backend-service base-url="http://payment-service:8006" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/review"))">
                <set-backend-service base-url="http://review-service:8007" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/wishlist"))">
                <set-backend-service base-url="http://wishlist-service:8008" />
            </when>
            <when condition="@(context.Request.Url.Path.StartsWith("/vault"))">
                <set-backend-service base-url="http://vault-service:8009" />
            </when>
            <!-- Map admin/audit-logs request directly to user-service -->
            <when condition="@(context.Request.Url.Path.StartsWith("/admin/audit-logs"))">
                <set-backend-service base-url="http://user-service:8002" />
            </when>
            <otherwise>
                <!-- Default fallback or 404 -->
            </otherwise>
        </choose>
    </inbound>
    <backend>
        <forward-request />
    </backend>
    <outbound>
        <base />
        
        <!-- 4. Fire-and-forget Audit Log trigger -->
        <choose>
            <!-- Only log requests that are not CORS OPTIONS preflights or internal audit calls -->
            <when condition="@(context.Request.Method != "OPTIONS" && !context.Request.Url.Path.Contains("/internal/audit-logs"))">
                <send-one-way-request mode="new">
                    <!-- Target our updated user-service internal endpoint -->
                    <set-url>http://user-service:8002/internal/audit-logs</set-url>
                    <set-method>POST</set-method>
                    <set-header name="Content-Type" exists-action="override">
                        <value>application/json</value>
                    </set-header>
                    <set-body>@{
                        var clientIp = context.Request.IpAddress;
                        var method = context.Request.Method;
                        var path = context.Request.Url.Path;
                        var statusCode = context.Response.StatusCode;
                        var userEmail = context.Request.Headers.GetValueOrDefault("X-User-Email", "Anonymous");
                        
                        // Parse service name from path (e.g. /product/list -> product)
                        string serviceName = "unknown";
                        var pathParts = path.Split(new char[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
                        if (pathParts.Length > 0)
                        {
                            serviceName = pathParts[0];
                        }
                        
                        return new Newtonsoft.Json.Linq.JObject(
                            new Newtonsoft.Json.Linq.JProperty("ip_address", clientIp),
                            new Newtonsoft.Json.Linq.JProperty("method", method),
                            new Newtonsoft.Json.Linq.JProperty("service_name", serviceName),
                            new Newtonsoft.Json.Linq.JProperty("path", path),
                            new Newtonsoft.Json.Linq.JProperty("status_code", statusCode),
                            new Newtonsoft.Json.Linq.JProperty("user_email", userEmail)
                        ).ToString();
                    }</set-body>
                </send-one-way-request>
            </when>
        </choose>
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

---

## ⚡ Step 4: Rebuild and Deploy the Updated User Service

Since we added the audit log endpoints and SQL model to `user-service`, we must rebuild and deploy it.

1. **Rebuild the image**:
   ```bash
   # From the root of Ecomm directory
   docker build -t akscr123.azurecr.io/user-service:latest ./services/user-service
   ```
2. **Push the image**:
   ```bash
   docker push akscr123.azurecr.io/user-service:latest
   ```
3. **Restart the User Service Deployment**:
   ```bash
   kubectl rollout restart deployment/stream-user-deploy
   ```
   *(On start, SQLAlchemy will automatically run DB migrations to create the `audit_logs` table in your SQL Database).*

---

## 🧹 Step 5: Decommission the Old API Gateway

Now that Azure APIM handles incoming requests, we can clean up the AKS cluster resource:

1. **Delete the Gateway resources**:
   ```bash
   kubectl delete deployment stream-api-deploy
   kubectl delete service stream-api-service
   ```
2. **Remove from Ingress**:
   Modify your Kubernetes ingress configuration file (e.g., `ingress_fix.yaml`) to route public requests to the frontend only, removing the `/` route to `stream-api-svc` if they are now handled by APIM.
3. **Clean up Docker Compose (Optional)**:
   If you wish to do local testing without the old gateway, you can route frontend requests directly to downstream ports. However, **keeping the gateway in `docker-compose.yml` is recommended** so your developers can work completely offline without needing to connect to Azure APIM!

---

## 🌐 Step 6: Point the Frontend to Azure APIM

In your frontend environment injection (or CI/CD pipeline configuration):

1. Set the variable `VITE_API_HOST` to the public gateway URL of your Azure APIM instance:
   ```bash
   VITE_API_HOST="https://streamshop-apim.azure-api.net"
   ```
2. Apply this environment configuration to your frontend deployment:
   ```bash
   kubectl set env deployment/stream-ui-deploy VITE_API_HOST="https://streamshop-apim.azure-api.net"
   ```

Now, the React Frontend will call Azure APIM, which handles token validation, header injection, logging, and forwards traffic to the internal microservices in your Kubernetes cluster!
