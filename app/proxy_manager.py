# proxy_manager.py
import os
import sys
import time
import random
import socket
import threading
import requests
from urllib.parse import urlparse

# Ensure aiohttp_socks can be imported if needed
try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None

class Proxy:
    def __init__(self, url, source="Free List"):
        self.url = url  # e.g. "socks5://user:pass@ip:port" or "http://ip:port"
        self.source = source
        self.latency = 999.0  # in seconds
        self.success_count = 0
        self.fail_count = 0
        self.status = "Testing"  # Active, Failed, Testing
        
        # Parse connection details
        try:
            parsed = urlparse(self.url)
            self.protocol = parsed.scheme.lower()
            self.host = parsed.hostname
            self.port = parsed.port
            self.username = parsed.username
            self.password = parsed.password
        except Exception:
            self.protocol = "http"
            self.host = "127.0.0.1"
            self.port = 8080
            self.username = None
            self.password = None

    def to_dict(self):
        return {
            "url": self.url,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "latency": self.latency,
            "status": self.status,
            "success": self.success_count,
            "fail": self.fail_count,
            "source": self.source
        }

class ProxyManager:
    def __init__(self, change_callback=None):
        self.all_proxies = []  # List of Proxy objects
        self.live_proxies = []  # List of Proxy objects (Active only, sorted by latency)
        self.lock = threading.Lock()
        
        self.change_callback = change_callback  # Callback when proxy list updates
        self.is_replenishing = False
        self.replenish_enabled = False
        self.last_replenish_time = 0
        self.current_protocol = "HTTP"
        
        # Built-in free proxy sources
        self.free_sources = {
            "HTTP": [
                ("proxifly", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt", True),
                ("TheSpeedX", "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt", False),
                ("Thordata", "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt", False),
            ],
            "SOCKS5": [
                ("proxifly", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt", True),
                ("hookzof", "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt", False),
                ("TheSpeedX", "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt", False),
                ("Thordata", "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks5.txt", False),
            ],
            "SOCKS4": [
                ("proxifly", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt", True),
                ("TheSpeedX", "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt", False),
            ],
        }
        
        # Start daemon thread to check pool size and auto-replenish
        self.monitor_thread = threading.Thread(target=self._pool_monitor_loop, daemon=True)
        self.monitor_thread.start()

    def set_replenish(self, enabled, protocol="HTTP"):
        with self.lock:
            self.replenish_enabled = enabled
            self.current_protocol = protocol

    def clear(self):
        with self.lock:
            self.all_proxies = []
            self.live_proxies = []
        self._notify_change()

    def import_from_text(self, text, protocol="http", source="Custom Import"):
        parsed_count = 0
        imported_list = []
        
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Formats: 
            # 1. protocol://user:pass@ip:port
            # 2. user:pass@ip:port
            # 3. ip:port
            proxy_url = line
            if "://" not in proxy_url:
                proxy_url = f"{protocol.lower()}://{proxy_url}"
                
            try:
                # Basic validation
                parsed = urlparse(proxy_url)
                if parsed.hostname and parsed.port:
                    imported_list.append(Proxy(proxy_url, source=source))
                    parsed_count += 1
            except Exception:
                pass
                
        if imported_list:
            with self.lock:
                # Deduplicate based on URL
                existing_urls = {p.url for p in self.all_proxies}
                new_proxies = [p for p in imported_list if p.url not in existing_urls]
                self.all_proxies.extend(new_proxies)
            self._notify_change()
            
            # Trigger asynchronous validation for new proxies
            threading.Thread(target=self.validate_untested, daemon=True).start()
            
        return parsed_count

    def import_from_file(self, file_path, protocol="http"):
        if not os.path.exists(file_path):
            return 0
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return self.import_from_text(content, protocol=protocol, source=os.path.basename(file_path))
        except Exception as e:
            print(f"Error importing from file: {e}")
            return 0

    def export_live(self, file_path):
        try:
            with self.lock:
                urls = [p.url for p in self.live_proxies]
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(urls))
            return len(urls)
        except Exception as e:
            print(f"Error exporting live proxies: {e}")
            return 0

    def get_proxy(self, service_type=None):
        """
        Returns a random proxy from the top 15 fastest live proxies (latency-based routing).
        Prioritizes SOCKS proxies for Edge-TTS (WebSockets) and HTTP proxies for ElevenLabs (REST).
        """
        with self.lock:
            if not self.live_proxies:
                return None
            
            # Filter and prioritize based on service type
            if service_type == "Edge-TTS":
                # WebSockets work best over SOCKS
                preferred = [p for p in self.live_proxies if p.protocol.startswith("socks")]
                fallback = [p for p in self.live_proxies if not p.protocol.startswith("socks")]
                filtered = preferred + fallback
            elif service_type == "ElevenLabs":
                # REST API works best over HTTP/HTTPS
                preferred = [p for p in self.live_proxies if not p.protocol.startswith("socks")]
                fallback = [p for p in self.live_proxies if p.protocol.startswith("socks")]
                filtered = preferred + fallback
            else:
                filtered = list(self.live_proxies)
                
            if not filtered:
                return None
                
            # Pick from the top-N fastest proxies of the prioritized list
            top_n = filtered[:15]
            selected = random.choice(top_n)
            return selected.url

    def report_success(self, proxy_url, latency):
        with self.lock:
            for p in self.all_proxies:
                if p.url == proxy_url:
                    p.success_count += 1
                    # Smooth latency update
                    if p.latency == 999.0:
                        p.latency = latency
                    else:
                        p.latency = p.latency * 0.7 + latency * 0.3
                    p.status = "Active"
                    if p not in self.live_proxies:
                        self.live_proxies.append(p)
                    break
            # Sort live proxies by latency (fastest first)
            self.live_proxies.sort(key=lambda x: x.latency)
        self._notify_change()

    def report_failure(self, proxy_url):
        with self.lock:
            for p in self.all_proxies:
                if p.url == proxy_url:
                    p.fail_count += 1
                    # Remove from live pool if it fails too many times or consecutively
                    if p.fail_count >= 2:
                        p.status = "Failed"
                        p.latency = 999.0
                        if p in self.live_proxies:
                            self.live_proxies.remove(p)
                    break
        self._notify_change()

    def validate_untested(self):
        with self.lock:
            untested = [p for p in self.all_proxies if p.status == "Testing"]
        if not untested:
            return
        self._validate_batch(untested)

    def validate_all(self):
        with self.lock:
            for p in self.all_proxies:
                p.status = "Testing"
            all_list = list(self.all_proxies)
        self._validate_batch(all_list)

    def _validate_batch(self, proxies_list):
        from concurrent.futures import ThreadPoolExecutor
        
        # Split into batches and test in parallel
        max_workers = min(len(proxies_list), 60)
        max_workers = max(1, max_workers)
        
        def test_one(proxy_obj):
            url = proxy_obj.url
            host = proxy_obj.host
            port = proxy_obj.port
            
            # Step 1: TCP Socket check (fast check)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.2)
                result = sock.connect_ex((host, port))
                sock.close()
                if result != 0:
                    proxy_obj.status = "Failed"
                    proxy_obj.latency = 999.0
                    return
            except Exception:
                proxy_obj.status = "Failed"
                proxy_obj.latency = 999.0
                return
                
            # Step 2: HTTP check (verify actual routing & measure latency)
            test_url = "https://www.microsoft.com"
            proxies_dict = {
                "http": url,
                "https": url
            }
            
            start_time = time.time()
            try:
                resp = requests.head(test_url, proxies=proxies_dict, timeout=2.5)
                if resp.status_code >= 200 and resp.status_code < 400:
                    latency = time.time() - start_time
                    proxy_obj.status = "Active"
                    proxy_obj.latency = latency
                    with self.lock:
                        if proxy_obj not in self.live_proxies:
                            self.live_proxies.append(proxy_obj)
                            self.live_proxies.sort(key=lambda x: x.latency)
                else:
                    proxy_obj.status = "Failed"
                    proxy_obj.latency = 999.0
            except Exception:
                proxy_obj.status = "Failed"
                proxy_obj.latency = 999.0
                
            self._notify_change()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(test_one, proxies_list)

    def load_free_proxies(self, protocol_type):
        """Fetch free proxies in background."""
        with self.lock:
            if self.is_replenishing:
                return
            self.is_replenishing = True
            
        def run_fetch():
            try:
                sources = self.free_sources.get(protocol_type, [])
                protocol = protocol_type.lower()
                all_urls = set()
                
                for src_name, url, has_protocol_prefix in sources:
                    try:
                        resp = requests.get(url, timeout=8)
                        if resp.status_code == 200:
                            for line in resp.text.split("\n"):
                                line = line.strip()
                                if not line or line.startswith("#"):
                                    continue
                                if has_protocol_prefix:
                                    all_urls.add(line)
                                else:
                                    all_urls.add(f"{protocol}://{line}")
                    except Exception as e:
                        print(f"Error fetching free source {src_name}: {e}")
                
                if all_urls:
                    with self.lock:
                        existing_urls = {p.url for p in self.all_proxies}
                        new_urls = [url for url in all_urls if url not in existing_urls]
                        
                        # Limit new proxies from free sources to 200 per load to avoid overloading
                        sampled_new = random.sample(new_urls, min(len(new_urls), 200))
                        
                        for url in sampled_new:
                            self.all_proxies.append(Proxy(url, source=f"Free {protocol_type}"))
                            
                    # Start validation
                    self.validate_untested()
            finally:
                with self.lock:
                    self.is_replenishing = False
                self.last_replenish_time = time.time()
                self._notify_change()

        threading.Thread(target=run_fetch, daemon=True).start()

    def _pool_monitor_loop(self):
        """Background daemon monitoring pool size and auto-healing."""
        while True:
            time.sleep(10)
            
            with self.lock:
                should_replenish = (
                    self.replenish_enabled
                    and not self.is_replenishing
                    and len(self.live_proxies) < 15
                    and (time.time() - self.last_replenish_time > 60)
                )
                protocol = self.current_protocol
                
            if should_replenish:
                print(f"[Smart Proxy Manager] Live proxies count ({len(self.live_proxies)}) is low. Replenishing automatically...")
                self.load_free_proxies(protocol)

    def _notify_change(self):
        if self.change_callback:
            try:
                self.change_callback()
            except Exception:
                pass
