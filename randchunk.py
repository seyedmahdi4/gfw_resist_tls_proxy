#!/usr/bin/env python3

import socket
import threading
import time
import random

listen_IP = "0.0.0.0"
listen_PORT = 2500
Cloudflare_IP = '162.159.137.232'
Cloudflare_port = 443

num_fragments = 150
fragment_sleep = 0.004

first_time_sleep = 0.05
# avoid server crash on flooding request -> max 100 sockets per second
accept_time_sleep = 0.01
worker_listen = 1024
my_socket_timeout = 21
# resource.setrlimit(resource.RLIMIT_NOFILE, (127000, 128000)) #TODO: test


def listen():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((listen_IP, listen_PORT))
    sock.listen(worker_listen)
    while True:
        client_sock = sock.accept()[0]
        client_sock.settimeout(5)
        thread_up = threading.Thread(
            target=my_upstream, args=(client_sock,))
        thread_up.daemon = True
        thread_up.start()


def my_upstream(client_sock):
    first_flag = True
    backend_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend_sock.settimeout(my_socket_timeout)
    backend_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    while True:
        try:
            if first_flag:
                first_flag = False
                time.sleep(first_time_sleep)
                data = client_sock.recv(16384)

                if data:
                    backend_sock.connect((Cloudflare_IP, Cloudflare_port))
                    thread_down = threading.Thread(
                        target=my_downstream, args=(backend_sock, client_sock))
                    thread_down.daemon = True
                    thread_down.start()
                    send_data_in_fragment(data, backend_sock)

            else:
                data = client_sock.recv(16384)

                if data:
                    backend_sock.sendall(data)

        except Exception as e:
            time.sleep(2)  # wait two second for another thread to flush
            client_sock.close()
            backend_sock.close()
            return False


def my_downstream(backend_sock, client_sock):
    while True:
        try:
            data = backend_sock.recv(16384)
            if data:
                client_sock.sendall(data)

        except Exception as e:
            time.sleep(2)  # wait two second for another thread to flush
            backend_sock.close()
            client_sock.close()
            return False


def send_data_in_fragment(data, sock):
    indices = random.sample(range(1, len(data)-1), num_fragments-1)
    indices.sort()

    i_pre = 0
    for i in indices:
        fragment_data = data[i_pre:i]
        i_pre = i
        sock.sendall(fragment_data)
        time.sleep(fragment_sleep)

    fragment_data = data[i_pre:len(data)]
    sock.sendall(fragment_data)
    print('finish fragment_data send')


print(f"Now listening at: {listen_IP}:{str(listen_PORT)}")
listen()