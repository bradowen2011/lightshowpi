#!/usr/bin/env python

import web
import glob
import os
import hardware_controller as hc
import synchronized_lights as lights

template_dir = os.path.abspath(os.path.dirname(__file__)) + "/templates"

slc=lights.slc()
env=os.environ['SYNCHRONIZED_LIGHTS_HOME']

urls= (
    '/', 'index',
    '/ajax','ajax',
    '/getvars','getVars',
    '/upload','upload'
)
render = web.template.render(template_dir, globals={'glob':glob,'os':os,'slc':slc})

class index:
    def GET(self):        
        return render.index()

class ajax:
    #def GET(self):        
        #var = web.input()
        #return render.ajax(var)
    def POST(self):        
        vars = web.input()
        #print vars
        #return render.ajax(vars)
        if vars.option=='0':
            slc.playlist(vars.playlist)
        elif vars.option=='1':
            slc.playSingle(vars.song)
        elif vars.option=='3':
            slc.stop()
            hc.turn_on_lights()
        elif vars.option=='4':
            slc.stop()
            hc.turn_off_lights()
        elif vars.option=='5':
            return slc.getConfig()
        elif vars.option=='6':
            slc.setConfig(vars.object)
        elif vars.option=='7':
            slc.playAll()
        elif vars.option=='8':
            str1='{"songs":['
            for file in glob.glob(env+"/pi/lightshowpi/music/*.mp3"):
                str1=str1+'["'+os.path.basename(file)+'","'+file+'"],'
            str1=str1[:-1]
            str1=str1+']}'
            return str1
        elif vars.option=='9':
            #file = open("/home/pi/lightshowpi/music/playlists/"+vars.name+".playlist", "w")
            file = open(env+"/music/playlists/"+vars.name+".playlist", "w")
            file.write(vars.val)
            file.close()
            str1='{"playlists":['
            for file in glob.glob(env+"/music/playlists/*.playlist"):
                str1=str1+'["'+os.path.basename(file)+'","'+file+'"],'
            str1=str1[:-1]
            str1=str1+']}'
            return str1
        elif vars.option=='10':
            os.remove(vars.playlist)
            str1='{"playlists":['
            for file in glob.glob(env+"/music/playlists/*.playlist"):
                str1=str1+'["'+os.path.basename(file)+'","'+file+'"],'
            str1=str1[:-1]
            str1=str1+']}'
            return str1
        elif vars.option=='11':
            slc.applySettings()

class getVars:
    #def GET(self):        
        #return render.getvars()
    def POST(self):        
        #return render.getvars()
        str1=''
        for temp in slc.current_playlist:
            str1=str1+'"'+temp[0]+'",'
        str1=str1[:-1]
        return '{"currentsong":"'+slc.current_song_name+'","duration":"'+str(slc.duration)+'","currentpos":"'+str(slc.current_position)+'","playlist":['+str1+'],"playlistplaying":"'+slc.playlistplaying+'"}'

class upload:
    def POST(self):      
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
        
    #    x = web.input(myfile={})
    #    filedir = '/home/pi/lightshowpi/music/' # change this to the directory you want to store the file in.
    #    if 'myfile' in x: # to check if the file-object is created
    #        filepath=x.myfile.filename.replace('\\','/') # replaces the windows-style slashes with linux ones.
    #        filename=filepath.split('/')[-1] # splits the and chooses the last part (the filename with extension)
    #        fout = open(filedir +'/'+ filename,'w') # creates the file where the uploaded file should be stored
    #        fout.write(x.myfile.file.read()) # writes the uploaded file to the newly created file.
    #        fout.close() # closes the file, upload complete.
        #raise web.seeother('/upload')

if __name__ == "__main__": 
    #print web.__version__
    #print env
    app = web.application(urls, globals())
    app.run()
    