# 🛒 StreamShop: Complete Step-by-Step Azure Deployment Guide

Bhai! Welcome to the master deployment guide for **StreamShop**. 

This guide is written in very simple, easy-to-understand language. If you follow these steps one by one, you will deploy the entire microservices system on **Microsoft Azure** from scratch—without needing any other help.

---

## 🏗️ What are we building? (Simple Architecture)

Before we start, let's understand how our app works in the cloud:
1.  **Frontend (React UI)**: The Netflix-style web store that users open in their browser.
2.  **Azure API Management (APIM)**: Our main security guard (Darban). Every request from the frontend first hits APIM. It checks the user's security token (JWT), adds user details, and decides which backend service should handle the request.
3.  **AKS (Azure Kubernetes Service)**: A cluster of servers running our 9 backend microservices in separate boxes (called Pods).
4.  **Azure SQL Database**: The central database where all our tables (users, orders, products, audit logs) are saved.
5.  **Azure Storage File Share**: A shared hard disk where user files (uploaded in the Personal Vault) are saved safely.

---

## 📋 Prerequisites: What do you need on your laptop?
Before starting, make sure you have these tools installed on your local computer:
1.  **Azure CLI**: To run `az` commands. [Download here](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli).
2.  **Docker Desktop**: To build and push container images. [Download here](https://www.docker.com/products/docker-desktop/).
3.  **Kubectl**: To control your Kubernetes cluster. [Download here](https://kubernetes.io/docs/tasks/tools/).
4.  **Python 3**: To run database seeding scripts. [Download here](https://www.python.org/downloads/).

Open your terminal and log into your Azure Account:
```bash
az login
```
*(This will open a browser window. Log in with your Azure credentials, then close the browser).*

---

## 🛠️ PHASE 1: Create Azure Cloud Resources (Infrastructure)

We will build our cloud servers step-by-step. Run these commands in your terminal:

### Step 1.1: Create a Resource Group (Ghar)
A Resource Group is like a folder in Azure where all our services will live together.
*   **Command:**
    ```bash
    az group create --name StreamShopRG --location centralindia
    ```
    *   `--name StreamShopRG`: The name of our folder.
    *   `--location centralindia`: The physical data center location (India).

### Step 1.2: Create Azure Container Registry (ACR)
ACR is like Google Drive for our code containers. When we build our microservices into Docker images, we will upload them here.
*   **Command:**
    ```bash
    az acr create --resource-group StreamShopRG --name streamshopacr --sku Basic
    ```
    *   `--name streamshopacr`: The name of your registry (Must be unique, use lowercase only, no spaces).
    *   `--sku Basic`: The cheapest pricing plan for testing.

### Step 1.3: Create AKS Cluster (Kubernetes)
AKS is our group of virtual servers that will run our app containers.
*   **Command:**
    ```bash
    az aks create \
      --resource-group StreamShopRG \
      --name streamshop-aks \
      --node-count 2 \
      --generate-ssh-keys \
      --attach-acr streamshopacr
    ```
    *   `--node-count 2`: We are starting 2 virtual machines to run our apps.
    *   `--attach-acr streamshopacr`: This grants our AKS cluster permission to pull images from our ACR registry automatically.
    *(This command can take 5 to 10 minutes. Grab a cup of water!)*

### Step 1.4: Create Azure SQL Database (Data Store)
1.  Go to the [Azure Portal](https://portal.azure.com/).
2.  Search for **SQL servers** and click **Create**.
3.  Set:
    *   **Resource Group:** `StreamShopRG`
    *   **Server Name:** `streamshop-sqlserver` (Must be unique).
    *   **Location:** `Central India`.
    *   **Authentication Method:** Use **SQL authentication** (Set admin username to `dbadmin` and password to a strong password like `StrongPass123!`).
4.  Click **Review + Create** and then **Create**.
5.  Once the server is created, go to the SQL Server page, click **SQL databases** on the left menu, and click **Create database**.
    *   **Database Name:** `TestCase` (Must be exactly this).
    *   **Compute + storage:** Click *Configure database* and select **Serverless / Basic** (choose the lowest cost option).
    *   Click **Review + Create** > **Create**.
6.  **FIREWALL SETTING (Crucial!):** 
    *   Go to your SQL Server overview page.
    *   Click on **Security** > **Networking** in the left sidebar.
    *   Select **Selected networks**.
    *   Check the box: **"Allow Azure services and resources to access this server"**. *(If you miss this, Kubernetes and APIM won't be able to connect to the database!)*
    *   Click **Save**.

### Step 1.5: Create Storage Account (File Share for Vault)
We need a cloud disk so users can upload files into their personal vault.
1.  Go to the Azure Portal, search for **Storage accounts**, and click **Create**.
    *   **Resource Group:** `StreamShopRG`
    *   **Storage account name:** `streamshopstorage` (lowercase only).
    *   **Performance:** `Standard` (Locally redundant storage LRS).
    *   Click **Create**.
2.  Once created, click on **File shares** in the left sidebar of the storage account page.
3.  Click **+ File Share**, name it **`vault-share`**, and click **Create**.

### Step 1.6: Create Application Insights (Monitor)
To trace logs and errors across all microservices:
1.  Search for **Application Insights** in the Azure Portal and click **Create**.
    *   **Resource Group:** `StreamShopRG`
    *   **Name:** `streamshop-insights`
2.  Click **Create**.
3.  Once created, copy the **Connection String** from the Overview tab. It looks like:
    `InstrumentationKey=xxxx-xxxx-xxxx-xxxx;IngestionEndpoint=https://...`

---

## 📦 PHASE 2: Build & Push Docker Container Images

We need to bundle each microservice into a container image and upload it to Azure Container Registry (ACR).

1.  **Log in to your ACR Registry**:
    ```bash
    az acr login --name streamshopacr
    ```
2.  **Build and Push Backend Services**:
    Run these commands in the terminal from the root folder of the `Ecomm` project:
    ```bash
    SERVICES=(
      "auth-service"
      "user-service"
      "product-service"
      "cart-service"
      "order-service"
      "payment-service"
      "review-service"
      "wishlist-service"
      "vault-service"
    )

    for service in "${SERVICES[@]}"; do
      echo "🔨 Building $service..."
      docker build -t streamshopacr.azurecr.io/$service:latest ./services/$service
      echo "🚀 Pushing $service to Azure..."
      docker push streamshopacr.azurecr.io/$service:latest
    done
    ```
3.  **Build and Push the React Frontend**:
    ```bash
    echo "🔨 Building frontend..."
    docker build -t streamshopacr.azurecr.io/frontend:latest ./frontend
    echo "🚀 Pushing frontend to Azure..."
    docker push streamshopacr.azurecr.io/frontend:latest
    ```

---

## ☸️ PHASE 3: Deploy Microservices to AKS (Kubernetes)

We will now launch our backend services in Kubernetes.

### Step 3.1: Connect kubectl to your AKS Cluster
Tell your terminal to link up with your newly created AKS cluster:
```bash
az aks get-credentials --resource-group StreamShopRG --name streamshop-aks
```

### Step 3.2: Configure ConfigMaps and Secrets
Open the [k8s-deployments.yaml](file:///Users/puneetkumar/Desktop/Projects/Streamshop/Ecomm/k8s-deployments.yaml) file on your laptop. At the very top, you will see a ConfigMap and a Secret:

1.  **ConfigMap Configuration:**
    Replace the placeholders with your actual values:
    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: stream-config
    data:
      # Put your Azure SQL server domain here:
      DB_SERVER: "streamshop-sqlserver.database.windows.net"
      DB_NAME: "TestCase"
      DB_PORT: "1433"
      JWT_ALGORITHM: "HS256"
      # Paste your copied Application Insights Connection String here:
      APPLICATIONINSIGHTS_CONNECTION_STRING: "InstrumentationKey=xxxx-xxxx-xxxx-xxxx;..."
    ```

2.  **Secret Configuration:**
    Kubernetes secrets must be encoded in **Base64** format.
    *   Choose a strong JWT password (e.g. `my-streamshop-secret-key-12345`).
    *   To convert it to Base64, run this command in your terminal:
        ```bash
        echo -n "my-streamshop-secret-key-12345" | base64
        ```
        *Output will look like:* `bXktc3RyZWFtc2hvcC1zZWNyZXQta2V5LTEyMzQ1`
    *   Paste that output into `JWT_SECRET_KEY` under the Secret section in your YAML:
        ```yaml
        apiVersion: v1
        kind: Secret
        metadata:
          name: stream-secret
        type: Opaque
        data:
          JWT_SECRET_KEY: bXktc3RyZWFtc2hvcC1zZWNyZXQta2V5LTEyMzQ1
        ```

3.  **Update Image Registry Names:**
    Scroll down in `k8s-deployments.yaml` and make sure the `image` path for all services points to your registry.
    *   If your registry name is `streamshopacr`, the image tags should be `streamshopacr.azurecr.io/auth-service:latest`, `streamshopacr.azurecr.io/user-service:latest`, etc.

### Step 3.3: Launch everything on AKS
Run this command to send the manifest to AKS:
```bash
kubectl apply -f k8s-deployments.yaml
```

Check the status to ensure all services are starting up properly:
```bash
kubectl get pods
```
*(Wait until all pods show `STATUS: Running` and `READY: 1/1`).*

---

## 🚪 PHASE 4: Setup Azure API Management (APIM)

Azure APIM will replace our old Python API-gateway. It acts as our public gateway.

### Step 4.1: Provision the APIM Instance
Run this command in the terminal to create the APIM instance:
```bash
az apim create \
  --name streamshop-apim \
  --resource-group StreamShopRG \
  --location centralindia \
  --publisher-name StreamShop \
  --publisher-email admin@puneetdevops.online \
  --sku-name Developer
```
*(This is a cloud-provisioning step and will take some time. Let it finish!)*

### Step 4.2: Enable VNet Peering (Connect APIM to AKS)
APIM sits outside the AKS private network, but needs to reach K8s services (like `http://user-service:8002`).
1.  Go to the Azure Portal.
2.  Navigate to your **Virtual networks** page.
3.  Click on the APIM VNet, go to **Peerings** on the left menu, and click **+ Add**.
4.  Peer it with your AKS Virtual Network (choose the AKS VNet from the dropdown list).
5.  This allows APIM to route private network packets directly to AKS.

### Step 4.3: Configure the APIM Gateway Policy
1.  In the Azure Portal, open **API Management services** and select `streamshop-apim`.
2.  On the left menu, click **APIs** > **+ Add API** > select **HTTP (Create from scratch)**.
    *   **Display name:** `StreamShop API`
    *   **Name:** `streamshop-api`
    *   **Web service URL:** `http://user-service:8002` (This is a default placeholder backend).
    *   **API URL suffix:** Leave empty.
3.  Click **Create**.
4.  Click **+ Add operation** inside the API you just created.
    *   **Display name:** `Wildcard Route`
    *   **Method:** `*` (Any HTTP Method).
    *   **URL:** `/*` (Matches any sub-path).
    *   Click **Save**.
5.  Now we need to apply our custom gateway policy. Click **All operations** > click the **`</>` (Code editor)** button under **Inbound processing**:
    *   Select and delete the default XML code, paste the APIM policy XML code block below, and click **Save**.

#### APIM Policy XML Configuration:
```xml
<policies>
    <inbound>
        <base />
        <!-- 1. Enable CORS for frontend clients -->
        <cors allow-credentials="true">
            <allowed-origins>
                <origin>*</origin> <!-- Allow frontend requests -->
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

        <!-- 2. Parse Bearer JWT token & Inject context into X-User-Email header -->
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

        <!-- 3. Dynamic Path-Based Internal Routing -->
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
                <!-- Default backend fallback -->
            </otherwise>
        </choose>
    </inbound>
    <backend>
        <forward-request />
    </backend>
    <outbound>
        <base />
        
        <!-- 4. Asynchronous Audit Logging to user-service -->
        <choose>
            <when condition="@(context.Request.Method != "OPTIONS" && !context.Request.Url.Path.Contains("/internal/audit-logs"))">
                <send-one-way-request mode="new">
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
</policies>
```

---

## 🌐 PHASE 5: Point the Frontend to Azure APIM & Run

1.  **Retrieve your APIM Gateway URL**:
    Go to the APIM overview page in the Azure portal. The URL looks like:
    `https://streamshop-apim.azure-api.net`
2.  **Point the React Frontend to APIM**:
    Set the environment variable of the frontend container to target this URL. Run this terminal command:
    ```bash
    kubectl set env deployment/stream-ui-deploy VITE_API_HOST="https://streamshop-apim.azure-api.net"
    ```
3.  **Seed the Database with Products**:
    We need to add products to the catalog database. Run the seeding script locally:
    *   Make sure you have python packages installed (`pip install sqlalchemy pyodbc requests`).
    *   Execute the script:
        ```bash
        python3 seed_products.py
        ```
4.  **Open the Web Store**:
    Get the external IP of the frontend service:
    ```bash
    kubectl get service stream-ui-svc
    ```
    Copy the **`EXTERNAL-IP`** and open it in your browser (e.g. `http://52.140.x.x`).

🎉 **Congratulations!** Your entire microservices app is now live on Microsoft Azure! You can log in, add products to your cart, place orders, upload vault files, and view audit logs in the admin panel.

---

## 💻 Local Development (Offline Mode)

If you want to run the app offline on your laptop for code changes:
1.  Copy the environment settings:
    ```bash
    cp .env.example .env
    ```
2.  Run Docker Compose:
    ```bash
    docker-compose up --build
    ```
3.  Open `http://localhost:5173` in your browser. (The local `api-gateway` container handles request forwarding offline).

---

## 🤝 Developed by
**[Puneet Kumar](https://github.com/Puneet-K-Sharma)**