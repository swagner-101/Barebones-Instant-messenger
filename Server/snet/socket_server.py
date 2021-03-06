import threading
import queue
import socket
import time
import errno
import atexit
import logging
import json
import settings
from snet.snet_interface import Networking

class ServerNetwork(Networking):

    def __init__(self, address, port):
        logging.basicConfig(format=settings.ChatServer.get('flog'), level=settings.ChatServer.get('logging'))

        logging.info("Starting Server Networking")

        self._host = address
        self._port = port

        self._socket_dict = dict()
        self._accept_s = socket.socket()

        self._rmsgs_queue = queue.Queue()
        self._smsgs_queue = queue.Queue()

        self._thread_lock = threading.Lock()
        self._delete_thread_lock = threading.Lock()

        logging.info("Creating Accept Socket Thread")
        accept_args = (self._accept_s, self._socket_dict, self._delete_thread_lock, self._thread_lock)
        self._accept_thread = threading.Thread(target = self._accept_sockets, args = accept_args )
        self._accept_thread.setDaemon(True)
        self._accept_thread.start()

        logging.info("Creating Send Messages Thread")
        smsgs_args = (self._socket_dict, self._delete_thread_lock, self._smsgs_queue)
        self._smsgs_thread = threading.Thread(target=self._execute_send, args=smsgs_args)
        self._smsgs_thread.setDaemon(True)
        self._smsgs_thread.start()

        logging.info("Creating Receive Messages Thread")
        rmsgs_args = (self._socket_dict, self._thread_lock, self._delete_thread_lock, self._rmsgs_queue)
        self._rmsgs_thread = threading.Thread(target=self._exceute_receive, args=rmsgs_args)
        self._rmsgs_thread.setDaemon(True)
        self._rmsgs_thread.start()

        atexit.register(self.shutdown)

    def _accept_sockets(self,s, s_dict, d_lock, delete_lock):
        server_address = (self._host, self._port)
        logging.info("Binding To: " + str(server_address))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(server_address)

        s.listen(5)

        while True:
            try:
                client, addr = s.accept()
            except ConnectionAbortedError:
                logging.debug("Accept Socket: Connection Aborted")
                return
            except OSError as e:
                logging.debug("Accept Socket: OS Error")
            client.setblocking(0)
            str_addr = str(addr[0]) + ":" +  str(addr[1])
            logging.info("Adding Client: " + str_addr)

            d_lock.acquire()
            delete_lock.acquire()

            s_dict[str_addr] = client
            logging.info("Networking: " + str(len(s_dict)) + " Client(s) Connected")
            delete_lock.release()
            d_lock.release()

    def _execute_send(self, s_dict, d_lock, s_queue):
        def thread_send_message(s_dict, addr_list, msg_to_send):
            for addr in addr_list:
                try:
                    s_dict[addr].send(msg_to_send.encode("utf-8"))
                except KeyError:
                    # Socket Will Be Cleaned Up By Recieve Function, Just Log Error
                    logging.debug("Networking: Invalid Address (" + addr + ")")
                except BrokenPipeError:
                    logging.debug("Networking: Send Failure (" + addr + ") Broken Pipe Error")


        while True:
            addr_list, msg_to_send = s_queue.get()
            s_queue.task_done()

            #Append Appropriate Amount of Characters
            msg_length = len(msg_to_send)
            msg_to_send = msg_to_send + ' ' * (280 - msg_length)

            #Send Message
            d_lock.acquire()

            logging.info("Networking: Sending Messages: " + msg_to_send.rstrip(" "))

            #Create Sublists of Address List
            addr_chunks = list()
            addr_chunks.append(list())
            curr_chunk = 0

            i = 0
            max = 100;

            for addr in addr_list:
                if i > max:
                    i = 0
                    curr_chunk += 1
                    addr_chunks.append(list())

                addr_chunks[curr_chunk].append(addr)
                i += 1

            #Spawn new threads to handle each chunk of the list
            thread_list = []
            for chunk in addr_chunks:
                t_args = (s_dict, chunk, msg_to_send)
                t = threading.Thread(target=thread_send_message, args=t_args)
                t.start()
                thread_list.append(t)

            #Wait for the threads to finish
            for t in thread_list:
                t.join()

            logging.info("Networking: Messages Sent")
            d_lock.release()

    def _exceute_receive(self, s_dict, d_lock, delete_lock, r_queue):

        def shut_down_socket(conn, addr):
            logging.info("Networking: Closing Connection " + key)
            delete_lock.acquire()
            conn.close()
            del s_dict[addr]
            delete_lock.release()

        while True:
            d_lock.acquire()

            #Iterate Through All Sockets Checking if Data is Available
            for key in s_dict.keys():
                s = s_dict[key]
                try:
                    msg = s.recv(280)
                    if len(msg) != 0:
                        msg = msg.decode("utf-8")
                        msg = msg.rstrip(" ")
                        logging.info("Received(" + key + "): " + msg)

                        r_queue.put(msg)
                        if msg[13] == "Q":  #Client Shutdown
                            shut_down_socket(s, key)
                            break

                except socket.error as e:
                    err = e.args[0]
                    if err != errno.EAGAIN and err != errno.EWOULDBLOCK:
                        #Socket Error Close and Tell Client
                        leave_command = {
                            "command": "Q",
                            "alias": "",
                            "address": key,
                            "room": "",
                            "message": ""
                        }

                        shut_down_socket(s, key)
                        create_json = json.dumps(leave_command)
                        r_queue.put(create_json)
                        break

            d_lock.release()
            time.sleep(settings.ChatServer.get('updatetime'))

    def send_response(self, address, response):
        addr_list = list()
        addr_list.append(address)
        e = (addr_list, response)
        self._smsgs_queue.put(e)

    def send_message(self, addresses, msg):
        e = (addresses, msg)
        self._smsgs_queue.put(e)

    def retrieve_next_message(self):
        if not self._rmsgs_queue.empty():
            return self._rmsgs_queue.get()
        return None

    def _socket_cleanup(self):
        logging.info("Cleaning Up Sockets")
        self._thread_lock.acquire()
        for key, s in self._socket_dict.items():
            try:
                s.shutdown(socket.SHUT_RDWR)
            except:
                logging.info("Socket(" + key + "): Not Connected ")
        logging.info("Successful Socket Cleanup")
        self._accept_s.close()
        self._thread_lock.release()

    def shutdown(self):
        self._socket_cleanup()

    def __del__(self):
        self.shutdown()

def main():
    #Start Up Network Manually
    n = ServerNetwork("127.0.0.1", 8000)
    input("Press a key to exit\n")

if __name__ == "__main__":
    main()