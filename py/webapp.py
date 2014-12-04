#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Stephen Burning
# Author: Todd Giles (todd@lightshowpi.com)
"""Web interface for Lightshow Pi

Start the webserver on port 80:
  sudo webapp.py 80

Then visit it on your local network (replace with your RPi's IP address):
  http://192.168.X.Y/

glob2: for easier listing of music files / playlists
web: web.py for basic web server - http://webpy.org
"""

import web
import glob2 as glob
import os

import configuration_manager as cm
import hardware_controller as hc
import synchronized_lights as lightshow

template_dir = os.path.abspath(os.path.dirname(__file__)) + "/templates"

slc=lightshow.slc()
env=os.environ['SYNCHRONIZED_LIGHTS_HOME']

urls= (
    '/', 'index',
    '/ajax','ajax',
    '/getvars','getVars',
    '/upload','upload'
)
render = web.template.render(template_dir, globals={'glob':glob,'os':os,'slc':slc})

class index:
    '''Renders the main index template - i.e. the main entry point'''
    def GET(self):        
        return render.index()

class ajax:
    '''Handles ajax requests from the webapp'''
    def POST(self):        
        vars = web.input()
        # TODO(toddgiles): Make options a bit more readable (rather than #s)
        if vars.option=='0':
            # play playlist
            slc.stop()
            slc.play_playlist(vars.playlist)
        elif vars.option=='1':
            # play playlist w/SMS
            slc.stop()
	    slc.start_sms(vars.playlist)
            slc.play_playlist(vars.playlist)
        elif vars.option=='2':
            # play single song
            slc.stop()
            slc.play(vars.song)
        elif vars.option=='3':
            # turn on all lights
            slc.stop()
            hc.turn_on_lights()
        elif vars.option=='4':
            # turn off all lights
            slc.stop()
            hc.turn_off_lights()
        elif vars.option=='5':
            # get configuration options
            return cm.get_config_json()
#         elif vars.option=='6':
#             cm.set_config_json(vars.object)
#         elif vars.option=='7':
#             slc.play_all()
        elif vars.option=='8':
            response = '{"songs":['
            for filename in glob.glob(env+"/music/**/*.mp3"):
                response = response+'["'+os.path.basename(filename)+'","'+filename+'"],'
            response = response[:-1]
            response = response+']}'
            return response
        elif vars.option=='9':
            f = open(env + "/music/" + vars.name + ".playlist", "w")
            f.write(vars.val)
            f.close()
            response = '{"playlists":['
            for filename in glob.glob(env+"/music/**/*.playlist"):
                response=response+'["'+os.path.basename(filename)+'","'+filename+'"],'
            response = response[:-1]
            response = response+']}'
            return response
        elif vars.option=='10':
            os.remove(vars.playlist)
            response = '{"playlists":['
            for filename in glob.glob(env+"/music/**/*.playlist"):
                response = response+'["'+os.path.basename(filename)+'","'+filename+'"],'
            response = response[:-1]
            response = response+']}'
            return response

class getVars:
    '''Retrieves current state of the lightshow'''
    def POST(self):        
        playlist = ''
        for temp in slc.current_playlist['songs']:
            playlist = playlist + '"' + temp[0] + '",'
        playlist = playlist[:-1]
        response = '{"currentsong":"' + slc.current_song['name'] + '","duration":"' + str(slc.current_song['duration']) + '","currentpos":"' + str(slc.current_song['position']) + '","playlist":[' + playlist + '],"playlistplaying":"' + slc.current_song['name']+'"}'
        return response

class upload:
    '''Handles uploading photo(s) via the web interface'''
    def POST(self):      
        # TODO(todd): Make this location configurable via config file
        # TODO(todd): Allow adding to sub-directories
        filedir = env+"/music/" # change this to the directory you want to store the file in.
        i = web.webapi.rawinput()
        files = i.myfile
        if not isinstance(files, list):
            files = [files]
        for x in files:
            filepath=x.filename.replace('\\','/') # replaces the windows-style slashes with linux ones.
            filename=filepath.split('/')[-1] # splits the and chooses the last part (the filename with extension)
            fout = open(filedir +'/'+ filename,'w') # creates the file where the uploaded file should be stored
            fout.write(x.file.read()) # writes the uploaded file to the newly created file.
            fout.close() # closes the file, upload complete.
        
if __name__ == "__main__": 
    hc.initialize()
    app = web.application(urls, globals())
    app.run()
    hc.clean_up()
    
