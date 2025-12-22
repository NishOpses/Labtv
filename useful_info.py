import datetime
import platform
import socket

def get_time_info():
    now = datetime.datetime.now()
    return {
        'time': now.strftime('%H:%M:%S'),
        'date': now.strftime('%A, %d %B %Y'),
        'day': now.strftime('%A'),
        'iso': now.isoformat(),
    }

def get_hostname():
    return socket.gethostname()

def get_os_info():
    return f"{platform.system()} {platform.release()} ({platform.version()})"

if __name__ == "__main__":
    print(get_time_info())
    print(get_hostname())
    print(get_os_info())
