from flask import request


def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)
