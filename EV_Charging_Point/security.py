import base64
import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PBKDF2_ALG = "sha256"
_PBKDF2_ITER = 200_000
_SALT_LEN = 16


# -------- Password hashing (para EV_Registry) --------

def hash_password(plain: str) -> str:
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALG,
        plain.encode("utf-8"),
        salt,
        _PBKDF2_ITER,
    )
    return "pbkdf2${}${}${}".format(
        _PBKDF2_ITER,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _, iter_s, salt_b64, dk_b64 = hashed.split("$")
        iters = int(iter_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
    except Exception:
        return False

    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALG,
        plain.encode("utf-8"),
        salt,
        iters,
    )
    return hashlib.compare_digest(dk, expected)


# -------- Clave simétrica AES-GCM (para Central <-> CP) --------

def generate_sym_key() -> str:
    key = AESGCM.generate_key(bit_length=256)
    return base64.b64encode(key).decode("ascii")


def _decode_key(b64: str) -> bytes:
    return base64.b64decode(b64.encode("ascii"))


def encrypt_message(plaintext: str, base64_key: str) -> str:
    key = _decode_key(base64_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    data = nonce + ct
    return base64.b64encode(data).decode("ascii")


def decrypt_message(ciphertext: str, base64_key: str) -> str:
    key = _decode_key(base64_key)
    data = base64.b64decode(ciphertext.encode("ascii"))
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(nonce, ct, None)
    return pt.decode("utf-8")
