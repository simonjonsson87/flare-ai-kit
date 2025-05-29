import sys
import asyncio
import socket
import h11
import tlslite  # Your modified tlslite library
from tlslite.api import TLSConnection, HandshakeSettings
from tlslite.extensions import SupportedGroupsExtension

ip = sys.argv[1] if len(sys.argv) > 1 else None
 



async def send_request(host="127.0.0.1", port=4433, method="GET", path="/", body=None, attestation_token=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    try:
        loop = asyncio.get_event_loop()
        await loop.sock_connect(sock, (host, port))
        print(f"Connected to {host}:{port}")

        tls_conn = TLSConnection(sock)
        settings = HandshakeSettings()
        settings.minVersion = (3, 4)  # TLS 1.3
        settings.maxVersion = (3, 4)  # TLS 1.3
        supported_groups = SupportedGroupsExtension()
        supported_groups.create([23, 24])  # secp256r1 (23), secp384r1 (24)
        settings.extensions = [supported_groups]

        def do_handshake():
            tls_conn.handshakeClientCert(settings=settings)
        await loop.run_in_executor(None, do_handshake)
        print("TLS handshake complete!")

        h11_conn = h11.Connection(our_role=h11.CLIENT)
        headers = [
            (b"Host", f"{host}:{port}".encode()),
            (b"Accept", b"*/*"),
            (b"Connection", b"close")
        ]
        if body and isinstance(body, str):
            headers.append((b"Content-Length", str(len(body.encode())).encode()))
        elif body:
            headers.append((b"Content-Length", str(len(body)).encode()))

        request = h11.Request(method=method, target=path, headers=headers)
        await loop.run_in_executor(None, lambda: tls_conn.sendall(h11_conn.send(request)))
        if body:
            data = h11.Data(data=body.encode() if isinstance(body, str) else body)
            await loop.run_in_executor(None, lambda: tls_conn.sendall(h11_conn.send(data)))
            await loop.run_in_executor(None, lambda: tls_conn.sendall(h11_conn.send(h11.EndOfMessage())))

        response = None
        body = b""
        while True:
            try:
                data = await loop.run_in_executor(None, lambda: tls_conn.recv(4096))
                if not data:
                    break
            except Exception as e:
                print(f"Receive error: {e}")
                break

            h11_conn.receive_data(data)
            while True:
                event = h11_conn.next_event()
                if event is h11.NEED_DATA:
                    break
                elif isinstance(event, h11.Response):
                    response = event
                elif isinstance(event, h11.Data):
                    body += event.data
                elif isinstance(event, h11.EndOfMessage):
                    break
                elif isinstance(event, h11.ConnectionClosed):
                    break

            if response and h11_conn.our_state is h11.DONE:
                break

        if response:
            print(f"Received response: status={response.status_code}, headers={dict(response.headers)}, body={body}")
            return response, body
        else:
            print("No response received")
            return None, None

    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            await loop.run_in_executor(None, tls_conn.close)
        except:
            pass
        sock.close()

async def main():
    attestation_token = None
    try:
        with open("sim_token.txt", "rb") as f:
            attestation_token = f.read()
            print(f"Client attestation token size: {len(attestation_token)} bytes")
    except FileNotFoundError:
        print("No client attestation token provided")

    if ip:
        tasks = [
            send_request(host=ip, method="GET", path="/", attestation_token=attestation_token),
            send_request(host=ip, method="GET", path="/items", attestation_token=attestation_token),
            send_request(host=ip, method="POST", path="/data", body="Test data", attestation_token=attestation_token),
            send_request(host=ip, method="GET", path="/unknown", attestation_token=attestation_token)
        ]
    else:    
        tasks = [
            send_request(method="GET", path="/", attestation_token=attestation_token),
            send_request(method="GET", path="/items", attestation_token=attestation_token),
            send_request(method="POST", path="/data", body="Test data", attestation_token=attestation_token),
            send_request(method="GET", path="/unknown", attestation_token=attestation_token)
        ]
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        asyncio.run(main())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()