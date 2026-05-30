from __future__ import annotations

import re
from dataclasses import dataclass


PROXY_PATTERN = re.compile(
    r"^(?P<host>[^:]+):(?P<port>\d+):(?P<user>[^:]+):(?P<password>.+)$"
)


@dataclass(frozen=True)
class ProxyConfig:
    host: str
    port: int
    user: str
    password: str

    @classmethod
    def parse(cls, raw: str) -> ProxyConfig:
        raw = raw.strip()
        match = PROXY_PATTERN.match(raw)
        if not match:
            raise ValueError("Формат: IP:PORT:USER:PASS")
        return cls(
            host=match.group("host"),
            port=int(match.group("port")),
            user=match.group("user"),
            password=match.group("password"),
        )

    def upstream_url(self) -> str:
        return f"http://{self.user}:{self.password}@{self.host}:{self.port}"

    def masked(self) -> str:
        return f"{self.host}:{self.port}:{self.user}:{'*' * min(8, len(self.password))}"
