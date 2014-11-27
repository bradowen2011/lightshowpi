#!/usr/bin/env python

import web
import glob
import os

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
            slc.stop()
            slc.play_playlist(vars.playlist)
        elif vars.option=='1':
            slc.stop()
            slc.play(vars.song)
        elif vars.option=='3':
            slc.stop()
            hc.turn_on_lights()
        elif vars.option=='4':
            slc.stop()
            hc.turn_off_lights()
#         elif vars.option=='5':
#             return slc.getConfig()
#         elif vars.option=='6':
#             slc.setConfig(vars.object)
#         elif vars.option=='7':
#             slc.playAll()
        elif vars.option=='8':
            str1='{"songs":['
            for filename in glob.glob(env+"/music/sample/*.mp3"):
                str1=str1+'["'+os.path.basename(filename)+'","'+filename+'"],'
            str1=str1[:-1]
            str1=str1+']}'
            print str1
            return str1
        elif vars.option=='9':
            f = open(env+"/music/sample/"+vars.name+".playlist", "w")
            f.write(vars.val)
            f.close()
            str1='{"playlists":['
            for filename in glob.glob(env+"/music/sample/*.playlist"):
                str1=str1+'["'+os.path.basename(filename)+'","'+filename+'"],'
            str1=str1[:-1]
            str1=str1+']}'
            print str1
            return str1
        elif vars.option=='10':
            os.remove(vars.playlist)
            str1='{"playlists":['
            for filename in glob.glob(env+"/music/sample/*.playlist"):
                str1=str1+'["'+os.path.basename(filename)+'","'+filename+'"],'
            str1=str1[:-1]
            str1=str1+']}'
            print str1
            return str1
#         elif vars.option=='11':
#             slc.applySettings()

class getVars:
    #def GET(self):        
        #return render.getvars()
    def POST(self):        
        #return render.getvars()
        str1=''
        for temp in slc.current_playlist['songs']:
            str1=str1+'"'+temp[0]+'",'
        str1=str1[:-1]
        response = '{"currentsong":"'+slc.current_song['name']+'","duration":"'+str(slc.current_song['duration'])+'","currentpos":"'+str(slc.current_song['position'])+'","playlist":['+str1+'],"playlistplaying":"'+slc.current_song['name']+'"}'
        print response
        return response

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
    hc.initialize()
    app = web.application(urls, globals())
    app.run()
    hc.clean_up()
    