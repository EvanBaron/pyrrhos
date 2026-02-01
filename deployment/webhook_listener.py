import http.server
import socketserver
import hmac
import hashlib
import os
import subprocess

PORT = 5000
SECRET = os.environ.get("WEBHOOK_SECRET")
SCRIPT_PATH = "./update.sh"


class WebhookHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if not SECRET:
            print("Error: WEBHOOK_SECRET environment variable not set.")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Server misconfiguration: missing secret")
            return

        header_signature = self.headers.get("X-Hub-Signature-256")
        if not header_signature:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Missing signature")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        sha_name, signature = header_signature.split("=")
        if sha_name != "sha256":
            self.send_response(501)
            self.end_headers()
            self.wfile.write(b"Unsupported signature type")
            return

        mac = hmac.new(SECRET.encode(), msg=body, digestmod=hashlib.sha256)
        if not hmac.compare_digest(mac.hexdigest(), signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        try:
            print("Received valid webhook. Running update script...")
            subprocess.Popen([SCRIPT_PATH], shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Update triggered")
        except Exception as exception:
            print(f"Error running script: {exception}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exception).encode())


if __name__ == "__main__":
    if not os.access(SCRIPT_PATH, os.X_OK):
        print(f"Warning: {SCRIPT_PATH} is not executable. Attempting to fix...")
        os.chmod(SCRIPT_PATH, 0o755)

    print(f"Starting webhook listener on port {PORT}...")
    with socketserver.TCPServer(("", PORT), WebhookHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
