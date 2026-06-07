"""
URL 内容抓取服务
功能：给定 URL，抓取网页正文，清洗 HTML 返回纯文本
"""

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 不需要抓取内容的标签（导航、脚本、广告等）
_SKIP_TAGS = {
    "script", "style", "nav", "footer", "header", "aside",
    "noscript", "iframe", "form", "button", "input",
}

_TIMEOUT = 15  # 秒


def _validate_url(url: str) -> None:
    """
    SSRF 防护：校验 URL 不指向内网地址。
    解析 hostname 并拒绝私有 IP、回环地址、链路本地等。
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("无法解析 URL 中的主机名")

    # 拒绝常见的内网主机名
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError(f"不允许访问内网地址: {hostname}")

    try:
        # 解析 DNS，获取实际 IP
        addr_infos = socket.getaddrinfo(hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError(f"无法解析主机名: {hostname}")

    for family, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"不允许访问内网地址: {hostname} -> {ip}")


def fetch_url_text(url: str) -> dict:
    """
    抓取 URL 并提取正文文本。

    返回：
    {
        "title": str,        # 网页标题
        "text": str,         # 提取的正文（换行分隔）
        "url": str,          # 最终 URL（可能经过重定向）
        "char_count": int,   # 字符数
    }

    异常：直接 raise，由调用方处理。
    """
    _validate_url(url)
    logger.info(f"抓取 URL: {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        final_url = str(response.url)
        html = response.text

    soup = BeautifulSoup(html, "html.parser")

    # 提取标题
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # 删除不需要的标签
    for tag in soup(list(_SKIP_TAGS)):
        tag.decompose()

    # 优先找 article / main / .content / .post 等语义标签
    body_el = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_=re.compile(r"\b(content|post|article|entry|body)\b", re.I))
        or soup.body
    )

    if not body_el:
        body_el = soup

    # 提取文字，按段落合并
    lines = []
    for el in body_el.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
        text = el.get_text(" ", strip=True)
        if text and len(text) > 20:  # 过滤太短的片段
            lines.append(text)

    text = "\n".join(lines)

    # 清洗：折叠连续空行
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    logger.info(f"抓取完成：标题='{title}'，正文 {len(text)} 字符")

    return {
        "title": title,
        "text": text,
        "url": final_url,
        "char_count": len(text),
    }
