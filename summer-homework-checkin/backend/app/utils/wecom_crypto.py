"""企业微信智能机器人回调加解密工具。

协议要点（官方文档 101033）：
- EncodingAESKey 为 43 字符，Base64Decode(EncodingAESKey + "=") 得 32 字节 AES key；
- AES-256-CBC，iv = key 前 16 字节，PKCS7 填充（块长 32）；
- 明文结构 = 16 字节随机串 + 4 字节网络序 msg 长度 + msg + receiveid（智能机器人场景 receiveid 为空串）；
- 签名 = SHA1(字典序排序(token, timestamp, nonce, encrypt) 后直接拼接)。
"""
import base64
import hashlib
import hmac
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _aes_key(encoding_aes_key: str) -> bytes:
    """EncodingAESKey → 32 字节 AES key，长度非法时抛 ValueError。"""
    try:
        key = base64.b64decode((encoding_aes_key or "").strip() + "=")
    except Exception:
        raise ValueError("EncodingAESKey 不是合法的 Base64 字符串")
    if len(key) != 32:
        raise ValueError("EncodingAESKey 长度非法（解码后必须为 32 字节，原文 43 字符）")
    return key


def compute_signature(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    """SHA1 字典序签名，用于验签与生成回复签名。"""
    raw = "".join(sorted([token, timestamp, nonce, encrypt]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def verify_signature(token: str, timestamp: str, nonce: str, encrypt: str, signature: str) -> bool:
    """恒定时间比对签名，防时序侧信道。"""
    expected = compute_signature(token, timestamp, nonce, encrypt)
    return hmac.compare_digest(expected, (signature or "").strip())


def decrypt(encoding_aes_key: str, encrypt_b64: str) -> str:
    """解密回调密文，返回明文 msg（忽略尾部 receiveid）。失败抛 ValueError。"""
    key = _aes_key(encoding_aes_key)
    try:
        cipher_bytes = base64.b64decode(encrypt_b64)
        decryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).decryptor()
        padded = decryptor.update(cipher_bytes) + decryptor.finalize()
        # 去 PKCS7 填充（块长 32，pad 值 1~32）
        pad = padded[-1]
        if pad < 1 or pad > 32:
            raise ValueError("PKCS7 填充非法")
        plain = padded[:-pad]
        # 掐头 16 字节随机串，读 4 字节网络序长度取 msg
        msg_len = struct.unpack(">I", plain[16:20])[0]
        return plain[20:20 + msg_len].decode("utf-8")
    except ValueError:
        raise
    except Exception:
        raise ValueError("密文解密失败（密钥不匹配或密文损坏）")


def encrypt(encoding_aes_key: str, plain: str) -> str:
    """加密回复明文：16 随机字节 + 长度 + msg + 空 receiveid → PKCS7 → AES → Base64。"""
    key = _aes_key(encoding_aes_key)
    msg = plain.encode("utf-8")
    raw = os.urandom(16) + struct.pack(">I", len(msg)) + msg  # receiveid 为空串
    pad = 32 - len(raw) % 32
    raw += bytes([pad]) * pad
    encryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).encryptor()
    return base64.b64encode(encryptor.update(raw) + encryptor.finalize()).decode("utf-8")
