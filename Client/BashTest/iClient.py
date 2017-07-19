#!/usr/bin/env python3

from clienthandler.client_handler import ClientHandler
import sys
import time

def main():
	print("Admin init")
	delay=1

	client=ClientHandler()

	room=str(sys.argv[1])
	name=str(sys.argv[2])
	
	client.create_room(room,name)
	
	for i in range(40):
		client.send_message("Message from user " + name)
		time.sleep(delay)
	
	client.leave_room()



if __name__=="__main__":
	main()
