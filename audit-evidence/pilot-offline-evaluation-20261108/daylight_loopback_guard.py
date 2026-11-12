import sys

LOOPBACK = {"localhost", "127.0.0.1", "::1"}

def local_only(event, args):
    if event in {"socket.connect", "socket.bind", "socket.sendto", "socket.getnameinfo"}:
        address = args[0] if event == "socket.getnameinfo" else args[1]
        allowed = isinstance(address, tuple) and address[0] in LOOPBACK
    elif event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        allowed = args[0] in LOOPBACK or args[0] is None
    else:
        return
    if not allowed:
        raise PermissionError(1, "DAYLIGHT_OFFLINE_EXTERNAL_SOCKET_DENIED")

sys.addaudithook(local_only)
