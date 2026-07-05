import os
import urllib.parse
import struct
import time
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


def get_db_url():
    url = os.getenv("DBURL")
    if not url and os.path.exists("/data/DBURL"):
        try:
            with open("/data/DBURL", "r") as f:
                url = f.read().strip().replace("\n", "").replace("\r", "")
        except Exception:
            pass
    if not url:
        kv_url = os.getenv("KEYVAULT_URL")
        if kv_url:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient
                client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
                url = client.get_secret("DBURL").value
            except Exception:
                pass

    if url:
        if "Driver=" in url or ";" in url:
            if "database.windows.net" in url:
                if "TrustServerCertificate=yes" in url:
                    url = url.replace("TrustServerCertificate=yes", "TrustServerCertificate=no")
                elif "TrustServerCertificate=" not in url:
                    url += ";TrustServerCertificate=no"
            params = urllib.parse.quote_plus(url)
            return f"mssql+pyodbc:///?odbc_connect={params}"
        return url

    user = os.getenv("DB_USER", "SA")
    password = os.getenv("DB_PASSWORD", "")
    server = os.getenv("DB_SERVER", "localhost")
    port = os.getenv("DB_PORT", "1433")
    db_name = os.getenv("DB_NAME", "master")
    driver = "ODBC Driver 18 for SQL Server"
    params = f"Driver={{{driver}}};Server=tcp:{server},{port};Database={db_name};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    if password:
        params += f"Uid={user};Pwd={password};"
    quoted_params = urllib.parse.quote_plus(params)
    return f"mssql+pyodbc:///?odbc_connect={quoted_params}"


SQLALCHEMY_DATABASE_URL = get_db_url()
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_recycle=300, connect_args={"timeout": 30})


@event.listens_for(engine, "do_connect")
def provide_token(dialect, conn_rec, cargs, cparams):
    conn_str = cargs[0] if cargs else ""
    if "database.windows.net" in conn_str and ("ODBC Driver 18" in conn_str or "msodbcsql18" in conn_str.lower()):
        if "Pwd=" not in conn_str and "password=" not in conn_str.lower():
            try:
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()
                token = credential.get_token("https://database.windows.net/.default").token
                token_bytes = token.encode("utf-16-le")
                token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
                cparams["attrs_before"] = {1256: token_struct}
            except Exception:
                time.sleep(1)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
