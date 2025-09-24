#!/usr/bin/env python3
"""Test script to check daemon events."""

import socket
import tempfile
import os
import json
import time

def find_daemon_socket():
    """Find the daemon socket file."""
    temp_dir = tempfile.gettempdir()
    socket_files = []
    
    for filename in os.listdir(temp_dir):
        if filename.startswith("walrio_player_") and filename.endswith(".sock"):
            socket_path = os.path.join(temp_dir, filename)
            if os.path.exists(socket_path):
                socket_files.append((socket_path, os.path.getmtime(socket_path)))
    
    if socket_files:
        return max(socket_files, key=lambda x: x[1])[0]
    return None

def test_events():
    """Test event subscription with daemon."""
    socket_path = find_daemon_socket()
    if not socket_path:
        print("No daemon socket found")
        return
    
    print(f"Connecting to daemon at: {socket_path}")
    
    try:
        # Connect to daemon
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(socket_path)
        client_socket.settimeout(1.0)
        
        # Subscribe to events
        print("Subscribing to events...")
        client_socket.send(b"subscribe")
        
        # Listen for events
        print("Listening for events (press Ctrl+C to stop)...")
        while True:
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if data:
                    print(f"Received: {data}")
                    for line in data.strip().split('\n'):
                        if line:
                            try:
                                event = json.loads(line)
                                print(f"Parsed event: {event}")
                            except json.JSONDecodeError:
                                print(f"Non-JSON message: {line}")
                else:
                    time.sleep(0.1)
            except socket.timeout:
                print(".", end="", flush=True)
                time.sleep(0.5)
                
    except KeyboardInterrupt:
        print("\nStopping event listener")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            client_socket.close()
        except:
            pass

if __name__ == "__main__":
    test_events()