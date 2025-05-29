import asyncio
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
import h11
import tlslite
from tlslite.api import TLSConnection, X509, X509CertChain, parsePEMKey, HandshakeSettings
from tlslite.constants import CertificateType, ExtensionType
from tlslite.extensions import SupportedGroupsExtension, AttestationTokenExtension, CustomExtensionType
from tlslite.messages import CertificateEntry
import pathlib
from settings import settings
from flare_ai_kit.tee.attestation import VtpmAttestation
    
attestation=VtpmAttestation(simulate=settings.simulate_attestation)
attestation_token = bytes(attestation.get_token([]), encoding='utf-8')
print(type(attestation_token))

BASE_DIR = pathlib.Path(__file__).parent
CERT_PATH = BASE_DIR / "serverCert.pem"
KEY_PATH = BASE_DIR / "serverKey.pem"
SIM_TOKEN_PATH = BASE_DIR / "sim_token.txt"

# Load certificate and private key
cert = X509()
with open(CERT_PATH, "rb") as f:
    decoded = f.read().decode()
    cert.parse(decoded)

cert_chain = X509CertChain([cert])
with open(KEY_PATH, "rb") as f:
    key_bytes = f.read()
    decoded = key_bytes.decode()
    private_key = parsePEMKey(decoded, private=True)


# Configure handshake settings for TLS 1.3
tls_settings = HandshakeSettings()
tls_settings.minVersion = (3, 4)  # TLS 1.3
tls_settings.maxVersion = (3, 4)  # TLS 1.3
supported_groups = SupportedGroupsExtension()
supported_groups.create([23, 24])  # secp256r1 (23), secp384r1 (24)
tls_settings.extensions = [supported_groups]

# Read attestation token as binary
#try:
#    with open(SIM_TOKEN_PATH, "rb") as f:
#        attestation_token = f.read()
#        print(f"Attestation token size: {len(attestation_token)} bytes")
#except FileNotFoundError:
#    print("Error: sim_token.txt not found")
#    exit(1)
#except Exception as e:
#    print(f"Error reading sim_token.txt: {e}")
#    exit(1)
print(f"Attestation token loaded: {len(attestation_token) == 2700}")
#

# Define handler functions
def handle_root(request):
    return {
        "status": 200,
        "headers": [(b"Content-Type", b"text/plain"), (b"Connection", b"close")],
        "body": b"Hello from root!"
    }

def handle_items(request):
    return {
        "status": 200,
        "headers": [(b"Content-Type", b"text/plain"), (b"Connection", b"close")],
        "body": b"List of items"
    }

def handle_data(request):
    return {
        "status": 201,
        "headers": [(b"Content-Type", b"text/plain"), (b"Connection", b"close")],
        "body": b"Data received: " + (request.get("body", b""))
    }

# Define routes
routes = {
    ("GET", "/"): handle_root,
    ("GET", "/items"): handle_items,
    ("POST", "/data"): handle_data
}

# Thread pool for synchronous TLS operations
executor = ThreadPoolExecutor(max_workers=10)

async def handle_connection(client_sock, addr):
    print(f"Accepted connection from {addr}")
    tls_conn = TLSConnection(client_sock)

    try:
        # Perform TLS handshake in a thread
        def do_handshake():
            tls_conn.handshakeServer(None, cert_chain, private_key, settings=tls_settings, attestation_token=attestation_token)
        await asyncio.get_event_loop().run_in_executor(executor, do_handshake)
        print("TLS handshake complete!")

        # HTTP/1.1 connection state
        h11_conn = h11.Connection(our_role=h11.SERVER)

        # Process one request per connection
        try:
            # Read request data
            data = await asyncio.get_event_loop().run_in_executor(executor, lambda: tls_conn.recv(4096))
            if not data:
                return  # Client closed connection

            h11_conn.receive_data(data)
            request_received = False
            method = None
            path = None
            headers = None
            body = b""

            # Parse request
            while True:
                event = h11_conn.next_event()
                if event is h11.NEED_DATA:
                    # Fetch more data if needed
                    more_data = await asyncio.get_event_loop().run_in_executor(executor, lambda: tls_conn.recv(4096))
                    if not more_data:
                        break
                    h11_conn.receive_data(more_data)
                    continue
                elif isinstance(event, h11.Request):
                    method = event.method.decode()
                    path = event.target.decode()
                    headers = dict(event.headers)
                    request_received = True
                elif isinstance(event, h11.Data):
                    body += event.data
                elif isinstance(event, h11.EndOfMessage):
                    break
                elif isinstance(event, h11.ConnectionClosed):
                    return

            if not request_received:
                return  # No valid request received

            # Route request
            handler = routes.get((method, path))
            if handler:
                request = {"method": method, "path": path, "headers": headers, "body": body}
                response = handler(request)
            else:
                response = {
                    "status": 404,
                    "headers": [(b"Content-Type", b"text/plain"), (b"Connection", b"close")],
                    "body": b"Not Found"
                }

            # Ensure Content-Length is set
            content_length = len(response["body"])
            response["headers"] = [
                h for h in response["headers"] if h[0].lower() != b"content-length"
            ] + [(b"Content-Length", str(content_length).encode())]

            # Debug response
            print(f"Sending response: status={response['status']}, headers={response['headers']}, body={response['body']}")

            # Send response
            resp_event = h11.Response(
                status_code=response["status"],
                headers=response["headers"]
            )
            await asyncio.get_event_loop().run_in_executor(executor, lambda: tls_conn.sendall(h11_conn.send(resp_event)))
            await asyncio.get_event_loop().run_in_executor(executor, lambda: tls_conn.sendall(h11_conn.send(h11.Data(data=response["body"]))))
            await asyncio.get_event_loop().run_in_executor(executor, lambda: tls_conn.sendall(h11_conn.send(h11.EndOfMessage())))

        except Exception as e:
            print(f"HTTP processing error: {e}")

    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        try:
            await asyncio.get_event_loop().run_in_executor(executor, tls_conn.close)
        except:
            pass
        client_sock.close()

async def main():
    # Set up TCP socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", 4433))
    server_sock.listen(5)
    server_sock.setblocking(False)

    loop = asyncio.get_event_loop()
    while True:
        client_sock, addr = await loop.sock_accept(server_sock)
        loop.create_task(handle_connection(client_sock, addr))

if __name__ == "__main__":
    asyncio.run(main())
    
def start():
    asyncio.run(main())
     