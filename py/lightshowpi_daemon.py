#!/usr/bin/env python

import sys, time
from daemon import Daemon
from webapp import app,env



class MyDaemon(Daemon):
	def run(self):
		while True: 
			app.run()

if __name__ == "__main__":
	daemon = MyDaemon(env+'/py/daemon-lightshowpi.pid')
	if (len(sys.argv) == 3 or len(sys.argv) == 2) :
		if  'start' == sys.argv[1]:
                    if len(sys.argv) ==2:
                      sys.argv.append('80')
                    del sys.argv[1:2]
	            daemon.start()
	        elif 'stop' == sys.argv[1]:
		    daemon.stop()
	        elif 'restart' == sys.argv[1]:
		    daemon.restart()
	        else:
		    print "Unknown command"
		    sys.exit(2)
		    sys.exit(0)
	else:
		print "usage: %s start|stop|restart [Optional] port (default port is 80)" % sys.argv[0]
		sys.exit(2)
