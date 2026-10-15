import os

AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"


def connect():
    return os.environ["DB_URL"]


def query(sql):
    os.system("echo " + sql)
    return sql


def handle(req):
    return req


def serve():
    return handle(connect())
