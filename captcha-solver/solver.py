#!/usr/bin/env python3
"""Pure Python Friendly Captcha v1 puzzle solver."""
import hashlib
import struct
import base64
import json
import sys
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler


def encode_base64(data):
    return base64.b64encode(data).decode()


def decode_puzzle(puzzle_str):
    parts = puzzle_str.split('.')
    if len(parts) != 2:
        raise ValueError(f"Invalid puzzle format: expected 2 parts, got {len(parts)}")
    
    signature = parts[0]
    b64_data = parts[1]
    raw = base64.b64decode(b64_data)
    
    if len(raw) != 128:
        raise ValueError(f"Puzzle data should be 128 bytes, got {len(raw)}")
    
    n = raw[14]
    difficulty = raw[15]
    if difficulty > 255:
        difficulty = 255
    if difficulty < 0:
        difficulty = 0
    threshold = int(pow(2, (255.999 - difficulty) / 8))
    expiry = raw[13] * 300000
    start_nonce = struct.unpack_from('<I', raw, 124)[0]
    
    return {
        'signature': signature,
        'base64': b64_data,
        'buffer': raw,
        'n': n,
        'threshold': threshold,
        'expiry': expiry,
        'start_nonce': start_nonce,
    }


def solve_single(buffer_128, threshold, start_nonce=0, max_attempts=None):
    buff = bytearray(buffer_128)
    num_hashes = 0
    
    if max_attempts is None:
        max_attempts = 0xFFFFFFFF
    
    nonce = start_nonce
    end = start_nonce + max_attempts
    
    while nonce < end:
        struct.pack_into('<I', buff, 124, nonce)
        h = hashlib.blake2b(bytes(buff), digest_size=32).digest()
        first_u32 = struct.unpack_from('<I', h)[0]
        num_hashes += 1
        
        if first_u32 < threshold:
            return bytes(buff), num_hashes
        
        nonce += 1
        if nonce == 0:
            break
    
    return None, num_hashes


def solve_puzzle(puzzle_data, max_attempts_per_sub=50000, max_total_hashes=5000000):
    total_hashes = 0
    start_time = time.time()
    
    n = puzzle_data['n']
    threshold = puzzle_data['threshold']
    buffer_template = puzzle_data['buffer']
    signature = puzzle_data['signature']
    b64_data = puzzle_data['base64']
    
    solutions = bytearray()
    diagnostics = bytearray()
    
    for sub_idx in range(n):
        found = False
        for trial_byte in range(256):
            if total_hashes >= max_total_hashes:
                return None
            
            sub_buffer = bytearray(buffer_template)
            sub_buffer[120] = sub_idx
            sub_buffer[123] = trial_byte
            
            start_nonce = struct.unpack_from('<I', sub_buffer, 124)[0]
            solved_buffer, num_hashes = solve_single(
                sub_buffer, threshold,
                start_nonce=start_nonce,
                max_attempts=max_attempts_per_sub
            )
            total_hashes += num_hashes
            
            if solved_buffer is not None:
                sln = bytes(solved_buffer[-8:])
                solutions.extend(sln)
                found = True
                break
        
        if not found:
            return None
    
    elapsed = time.time() - start_time
    solver_type = 1
    ts_sec = int(elapsed * 10) & 0xFFFFFF
    diag = struct.pack('B', solver_type) + struct.pack('>I', ts_sec)[1:4]
    
    solution_b64 = encode_base64(bytes(solutions))
    diag_b64 = encode_base64(bytes(diagnostics) + diag)
    
    token = f"{signature}.{b64_data}.{solution_b64}.{diag_b64}"
    return token


def fetch_puzzle(sitekey, puzzle_endpoint):
    url = f"{puzzle_endpoint}?sitekey={sitekey}"
    req = urllib.request.Request(url, headers={
        'x-frc-client': 'js-0.9.20',
        'User-Agent': 'Mozilla/5.0',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    
    if data.get('success') and 'data' in data and 'puzzle' in data['data']:
        return data['data']['puzzle']
    raise ValueError(f"Failed to fetch puzzle: {data}")


class SolverHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        if self.path != '/solve':
            self.send_error(404)
            return
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        
        try:
            data = json.loads(body)
            sitekey = data.get('sitekey', 'FCMGDDIJTON17UAD')
            puzzle_endpoint = data.get('puzzleEndpoint', 'https://eu.frcapi.com/api/v1/puzzle')
            
            self.log_message(f"Solving captcha: sitekey={sitekey}")
            start = time.time()
            
            puzzle_str = fetch_puzzle(sitekey, puzzle_endpoint)
            puzzle = decode_puzzle(puzzle_str)
            token = solve_puzzle(puzzle)
            
            elapsed = int((time.time() - start) * 1000)
            
            if token:
                self.log_message(f"Solved in {elapsed}ms")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True, 'token': token, 'elapsed_ms': elapsed
                }).encode())
            else:
                raise RuntimeError("Failed to solve captcha")
                
        except Exception as e:
            self.log_message(f"Error: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False, 'error': str(e)
            }).encode())
    
    def log_message(self, format, *args):
        sys.stderr.write(f"[solver] {format % args}\n")


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3001
    
    if '--once' in sys.argv:
        sitekey = 'FCMGDDIJTON17UAD'
        endpoint = 'https://eu.frcapi.com/api/v1/puzzle'
        print("Fetching puzzle...", file=sys.stderr)
        puzzle_str = fetch_puzzle(sitekey, endpoint)
        puzzle = decode_puzzle(puzzle_str)
        print(f"Solving (threshold={puzzle['threshold']}, n={puzzle['n']})...", file=sys.stderr)
        start = time.time()
        token = solve_puzzle(puzzle)
        elapsed = int((time.time() - start) * 1000)
        if token:
            print(json.dumps({'success': True, 'token': token, 'elapsed_ms': elapsed}))
        else:
            print(json.dumps({'success': False, 'error': 'Failed to solve'}))
        sys.exit(0)
    
    server = HTTPServer(('127.0.0.1', port), SolverHandler)
    print(f"[solver] Listening on http://127.0.0.1:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
