#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Chris Usey (chris.usey@gmail.com)
# Author: Ryan Jennings
# Author: Paul Dunn (dunnsept@gmail.com)
"""Play any audio file and synchronize lights to the music

When executed, this script will play an audio file, as well as turn on and off N channels
of lights to the music (by default the first 8 GPIO channels on the Rasberry Pi), based upon
music it is playing. Many types of audio files are supported (see decoder.py below), but
it has only been tested with wav and mp3 at the time of this writing.

The timing of the lights turning on and off is based upon the frequency response of the music
being played.  A short segment of the music is analyzed via FFT to get the frequency response
across each defined channel in the audio range.  Each light channel is then faded in and out based
upon the amplitude of the frequency response in the corresponding audio channel.  Fading is 
accomplished with a software PWM output.  Each channel can also be configured to simply turn on
and off as the frequency response in the corresponding channel crosses a threshold.

FFT calculation can be CPU intensive and in some cases can adversely affect playback of songs
(especially if attempting to decode the song as well, as is the case for an mp3).  For this reason,
the FFT calculations are cached after the first time a new song is played.  The values are cached
in a gzip'd text file in the same location as the song itself.  Subsequent requests to play the
same song will use the cached information and not recompute the FFT, thus reducing CPU utilization
dramatically and allowing for clear music playback of all audio file types.

Recent optimizations have improved this dramatically and most users are no longer reporting
adverse playback of songs even on the first playback.

Sample usage:
To play an entire list -
sudo python synchronized_lights.py --playlist=/home/pi/music/.playlist

To play a specific song -
sudo python synchronized_lights.py --file=/home/pi/music/jingle_bells.mp3

Third party dependencies:

alsaaudio: for audio input/output - http://pyalsaaudio.sourceforge.net/
decoder.py: decoding mp3, ogg, wma, ... - https://pypi.python.org/pypi/decoder.py/1.5XB
numpy: for FFT calculation - http://www.numpy.org/
"""

# Moved the logging basic configuration above all other imports to avoid logging being
# overrided by imports.
# TODO(todd): Look into using a separate logger for our app to clean this up.
import logging
import configuration_manager as cm
# Log everything to our log file
# TODO(todd): Add logging configuration options.
logging.basicConfig(filename=cm.LOG_DIR + '/music_and_lights.play.dbg',
                    format='[%(asctime)s] %(levelname)s {%(pathname)s:%(lineno)d}'
                    ' - %(message)s',
                    level=logging.DEBUG)

import argparse
import csv
import fcntl
import numpy as np
import os
import random
import subprocess
import sys
import time
import wave

import alsaaudio as aa
import fft
import decoder
import hardware_controller as hc

from preshow import Preshow


def calculate_channel_frequency(min_frequency, max_frequency, custom_channel_mapping,
                                custom_channel_frequencies):
    '''Calculate frequency values for each channel, taking into account custom settings.'''

    # How many channels do we need to calculate the frequency for
    if custom_channel_mapping != 0 and len(custom_channel_mapping) == hc.GPIOLEN:
        logging.debug("Custom Channel Mapping is being used: %s", str(custom_channel_mapping))
        channel_length = max(custom_channel_mapping)
    else:
        logging.debug("Normal Channel Mapping is being used.")
        channel_length = hc.GPIOLEN

    logging.debug("Calculating frequencies for %d channels.", channel_length)
    octaves = (np.log(max_frequency / min_frequency)) / np.log(2)
    logging.debug("octaves in selected frequency range ... %s", octaves)
    octaves_per_channel = octaves / channel_length
    frequency_limits = []
    frequency_store = []

    frequency_limits.append(min_frequency)
    if custom_channel_frequencies != 0 and (len(custom_channel_frequencies) >= channel_length + 1):
        logging.debug("Custom channel frequencies are being used")
        frequency_limits = custom_channel_frequencies
    else:
        logging.debug("Custom channel frequencies are not being used")
        for i in range(1, hc.GPIOLEN + 1):
            frequency_limits.append(frequency_limits[-1]
                                    * 10 ** (3 / (10 * (1 / octaves_per_channel))))
    for i in range(0, channel_length):
        frequency_store.append((frequency_limits[i], frequency_limits[i + 1]))
        logging.debug("channel %d is %6.2f to %6.2f ", i, frequency_limits[i],
                      frequency_limits[i + 1])

    # we have the frequencies now lets map them if custom mapping is defined
    if custom_channel_mapping != 0 and len(custom_channel_mapping) == hc.GPIOLEN:
        frequency_map = []
        for i in range(0, hc.GPIOLEN):
            mapped_channel = custom_channel_mapping[i] - 1
            mapped_frequency_set = frequency_store[mapped_channel]
            mapped_frequency_set_low = mapped_frequency_set[0]
            mapped_frequency_set_high = mapped_frequency_set[1]
            logging.debug("mapped channel: " + str(mapped_channel) + " will hold LOW: "
                          + str(mapped_frequency_set_low) + " HIGH: "
                          + str(mapped_frequency_set_high))
            frequency_map.append(mapped_frequency_set)
        return frequency_map
    else:
        return frequency_store

def load_playlist(playlist_filename):
    '''Loads a playlist from the given filename'''
    most_votes = [None, None, []]
    with open(playlist_filename, 'rb') as playlist_fp:
        fcntl.lockf(playlist_fp, fcntl.LOCK_SH)
        playlist = csv.reader(playlist_fp, delimiter='\t')
        songs = []
        for song in playlist:
            if len(song) < 2 or len(song) > 4:
                logging.error('Invalid playlist.  Each line should be in the form: '
                             '<song name><tab><path to song>')
                sys.exit()
            elif len(song) == 2:
                song.append(set())
            else:
                song[2] = set(song[2].split(','))
                if len(song) == 3 and len(song[2]) >= len(most_votes[2]):
                    most_votes = song
            songs.append(song)
        fcntl.lockf(playlist_fp, fcntl.LOCK_UN)

    return {'filename': playlist_filename, 
            'songs': songs,
            'most_votes': most_votes}

class slc:
    '''Synchronized lights controller class (slc)'''
    _no_song = {'name': "No song playing",
                'filename': "",
                'duration': -1,
                'position': -1}
    
    def __init__(self):
        '''Constructor, initialize state of the lightshow'''

        self.loadConfig()
        self.readcache = True # Move default into config
        self.arg_file = None
        self.arg_playlist = slc._PLAYLIST_PATH
        self.stop_now = False
        self.playing = False
        self.current_playlist = load_playlist(slc._PLAYLIST_PATH)
        self.current_song = slc._no_song.copy()

    def loadConfig(self):
        # Configurations - TODO(todd): Move more of this into configuration manager
        slc._CONFIG = cm.CONFIG
        slc._MODE = cm.lightshow()['mode']
        slc._MIN_FREQUENCY = slc._CONFIG.getfloat('audio_processing', 'min_frequency')
        slc._MAX_FREQUENCY = slc._CONFIG.getfloat('audio_processing', 'max_frequency')
        slc._RANDOMIZE_PLAYLIST = slc._CONFIG.getboolean('lightshow', 'randomize_playlist')
        try:
            slc._CUSTOM_CHANNEL_MAPPING = [int(channel) for channel in
                                       slc._CONFIG.get('audio_processing', 'custom_channel_mapping').split(',')]
        except:
            slc._CUSTOM_CHANNEL_MAPPING = 0
        try:
            slc._CUSTOM_CHANNEL_FREQUENCIES = [int(channel) for channel in
                                           slc._CONFIG.get('audio_processing',
                                                       'custom_channel_frequencies').split(',')]
        except:
            slc._CUSTOM_CHANNEL_FREQUENCIES = 0
        try:
            slc._PLAYLIST_PATH = cm.lightshow()['playlist_path'].replace('$SYNCHRONIZED_LIGHTS_HOME', cm.HOME_DIR)
        except: 
            slc._PLAYLIST_PATH = "/home/pi/music/.playlist"
        try:
            slc._usefm = slc._CONFIG.get('audio_processing','fm')
            slc._frequency = slc._CONFIG.get('audio_processing','frequency')
            slc._play_stereo = True
            slc._music_pipe_r,slc._music_pipe_w = os.pipe()
        except:
            slc._usefm='false'
        slc.CHUNK_SIZE = 2048  # Use a multiple of 8 (move this to config)

    def update_lights(self, matrix, mean, std):
        '''Update the state of all the lights based upon the current frequency response matrix'''
        for i in range(0, hc.GPIOLEN):
            # Calculate output pwm, where off is at some portion of the std below
            # the mean and full on is at some portion of the std above the mean.
            brightness = matrix[i] - mean[i] + 0.5 * std[i]
            brightness = brightness / (1.25 * std[i])
            if brightness > 1.0:
                brightness = 1.0
            if brightness < 0:
                brightness = 0
            if not hc.is_pin_pwm(i):
                # If pin is on / off mode we'll turn on at 1/2 brightness
                if (brightness > 0.5):
                    hc.turn_on_light(i, True)
                else:
                    hc.turn_off_light(i, True)
            else:
                hc.turn_on_light(i, True, brightness)
    
    def audio_in(self):
        '''Control the lightshow from audio coming in from a USB audio card'''
        sample_rate = cm.lightshow()['audio_in_sample_rate']
        input_channels = cm.lightshow()['audio_in_channels']
    
        # Open the input stream from default input device
        stream = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, cm.lightshow()['audio_in_card'])
        stream.setchannels(input_channels)
        stream.setformat(aa.PCM_FORMAT_S16_LE) # Expose in config if needed
        stream.setrate(sample_rate)
        stream.setperiodsize(slc.CHUNK_SIZE)
             
        logging.debug("Running in audio-in mode - will run until Ctrl+C is pressed")
        print "Running in audio-in mode, use Ctrl+C to stop"
        try:
            frequency_limits = calculate_channel_frequency(slc._MIN_FREQUENCY,
                                                           slc._MAX_FREQUENCY,
                                                           slc._CUSTOM_CHANNEL_MAPPING,
                                                           slc._CUSTOM_CHANNEL_FREQUENCIES)
    
            # Start with these as our initial guesses - will calculate a rolling mean / std 
            # as we get input data.
            mean = [12.0 for _ in range(hc.GPIOLEN)]
            std = [0.5 for _ in range(hc.GPIOLEN)]
            recent_samples = np.empty((250, hc.GPIOLEN))
            num_samples = 0
        
            # Listen on the audio input device until CTRL-C is pressed
            while True:            
                l, data = stream.read()
                
                if l:
                    try:
                        matrix = fft.calculate_levels(data, slc.CHUNK_SIZE, sample_rate, frequency_limits, input_channels)
                        if not np.isfinite(np.sum(matrix)):
                            # Bad data --- skip it
                            continue
                    except ValueError as e:
                        # TODO(todd): This is most likely occuring due to extra time in calculating
                        # mean/std every 250 samples which causes more to be read than expected the
                        # next time around.  Would be good to update mean/std in separate thread to
                        # avoid this --- but for now, skip it when we run into this error is good 
                        # enough ;)
                        logging.debug("skipping update: " + str(e))
                        continue
    
                    self.update_lights(matrix, mean, std)
    
                    # Keep track of the last N samples to compute a running std / mean
                    #
                    # TODO(todd): Look into using this algorithm to compute this on a per sample basis:
                    # http://www.johndcook.com/blog/standard_deviation/                
                    if num_samples >= 250:
                        no_connection_ct = 0
                        for i in range(0, hc.GPIOLEN):
                            mean[i] = np.mean([item for item in recent_samples[:, i] if item > 0])
                            std[i] = np.std([item for item in recent_samples[:, i] if item > 0])
                            
                            # Count how many channels are below 10, if more than 1/2, assume noise (no connection)
                            if mean[i] < 10.0:
                                no_connection_ct += 1
                                
                        # If more than 1/2 of the channels appear to be not connected, turn all off
                        if no_connection_ct > hc.GPIOLEN / 2:
                            logging.debug("no input detected, turning all lights off")
                            mean = [20 for _ in range(hc.GPIOLEN)]
                        else:
                            logging.debug("std: " + str(std) + ", mean: " + str(mean))
                        num_samples = 0
                    else:
                        for i in range(0, hc.GPIOLEN):
                            recent_samples[num_samples][i] = matrix[i]
                        num_samples += 1
     
        except KeyboardInterrupt:
            pass
        finally:
            print "\nStopping"
    
    def get_next_song(self, playlist_filename):
        '''Determine the next song to play from the given playlist'''
        current_song = None
            
        # Load the play list (which also counts current votes for each song)
        playlist = load_playlist(playlist_filename)
        most_votes = playlist['most_votes']
        songs = playlist['songs']
        
        if most_votes[0] != None:
            logging.info("Choosing next song based upon votes: " + str(most_votes))
            current_song = most_votes

            # Update play list with latest votes
            with open(playlist['filename'], 'wb') as playlist_fp:
                fcntl.lockf(playlist_fp, fcntl.LOCK_EX)
                writer = csv.writer(playlist_fp, delimiter='\t')
                for song in songs:
                    if current_song == song and len(song) == 3:
                        song.append("playing!")
                    if len(song[2]) > 0:
                        song[2] = ",".join(song[2])
                    else:
                        del song[2]
                writer.writerows(songs)
                fcntl.lockf(playlist_fp, fcntl.LOCK_UN)

        else:
            # Get a "play now" requested song
            play_now = int(cm.get_state('play_now', 0))
            if play_now > 0 and play_now <= len(songs):
                current_song = songs[play_now - 1]
            # Get random song
            elif slc._RANDOMIZE_PLAYLIST:
                current_song = songs[random.randint(0, len(songs) - 1)]
            # Play next song in the lineup
            else:
                song_to_play = int(cm.get_state('song_to_play', 0))
                song_to_play = song_to_play if (song_to_play <= len(songs) - 1) else 0
                current_song = songs[song_to_play]
                next_song = (song_to_play + 1) if ((song_to_play + 1) <= len(songs) - 1) else 0
                cm.update_state('song_to_play', next_song)

        # Store the current song and the current playlist
        cm.update_state('current_song', songs.index(current_song))
        self.current_playlist = playlist
        self.current_song = {'name': current_song[0],
                             'filename': current_song[1],
                             'votes': current_song[2],
                             'duration': -1,
                             'position': -1}
        return self.current_song

    def play_playlist(self, playlist_filename):
        '''Play songs from the given playlist until stop() is called'''
        while not self.stop_now:
            print "play playlist: " + playlist_filename
            self.play(self.get_next_song(playlist_filename)['filename'])
        
    def stop(self):
        '''Stop playing current song / playlist - does not return until song is stopped'''
        self.stop_now = True

        # Wait until the stop is successful before returning
        while self.playing:
            time.sleep(0.1)

        # Reset the current song to nothing
        self.current_song = slc._no_song.copy()
        self.stop_now = False
    
    # TODO(todd): Refactor more of this to make it more readable / modular.
    def play(self, song_filename):
        '''Play the specified song.'''
        song_filename = song_filename.replace("$SYNCHRONIZED_LIGHTS_HOME", cm.HOME_DIR)
        self.current_song['filename'] = song_filename
        if self.current_song['name'] == "No song playing":
            self.current_song['name'] = song_filename

        # Handle the pre-show
        play_now = int(cm.get_state('play_now', 0))
        if not play_now:
            result = Preshow().execute()
            if result == Preshow.PlayNowInterrupt:
                play_now = True
    
        # Ensure play_now is reset before beginning playback
        if play_now:
            cm.update_state('play_now', 0)
            play_now = 0
    
        # Set up audio playback
        if song_filename.endswith('.wav'):
            musicfile = wave.open(song_filename, 'r')
        else:
            musicfile = decoder.open(song_filename)
    
        sample_rate = musicfile.getframerate()
        num_channels = musicfile.getnchannels()
    
        if slc._usefm=='true':
            logging.info("sending output as fm transmission on pin 4 via pifm")
            with open(os.devnull, "w") as dev_null:
                fm_process = subprocess.Popen(["sudo",cm.HOME_DIR + "/bin/pifm","-",str(slc._frequency),"44100", "stereo" if slc._play_stereo else "mono"], stdin=slc._music_pipe_r, stdout=dev_null)
        else:
            output = aa.PCM(aa.PCM_PLAYBACK, aa.PCM_NORMAL)
            output.setchannels(num_channels)
            output.setrate(sample_rate)
            output.setformat(aa.PCM_FORMAT_S16_LE)
            output.setperiodsize(slc.CHUNK_SIZE)
        
        # Output a bit about what we're about to play to the logs
        self.current_song['duration'] = musicfile.getnframes() / sample_rate
        logging.info("Playing: " + song_filename + " (" + str(self.current_song['duration']) + " sec)")
        song_filename = os.path.abspath(song_filename)
        
        # Initialize FFT levels array
        fft_levels = [0 for _ in range(hc.GPIOLEN)]
    
        cache = []
        cache_found = False
        cache_filename = os.path.dirname(song_filename) + "/." + os.path.basename(song_filename) + ".sync"
        # The values 12 and 1.5 are good estimates for first time playing back (i.e. before we have
        # the actual mean and standard deviations calculated for each channel).
        mean = [12.0 for _ in range(hc.GPIOLEN)]
        std = [1.5 for _ in range(hc.GPIOLEN)]
        if self.readcache:
            # Read in cached fft
            try:
                with open(cache_filename, 'rb') as cache_fp:
                    cachefile = csv.reader(cache_fp, delimiter=',')
                    for row in cachefile:
                        cache.append([0.0 if np.isinf(float(item)) else float(item) for item in row])
                    # TODO(todd): Optimize this and / or cache it to avoid delay here
                    cache_matrix = np.array(cache)
                    # TODO(todd): Save configuration this cache is for so we can re-generate whenver config changes
                    if cache_matrix.shape[1] == hc.GPIOLEN:
                        logging.info("Found valid cached fft values, using values from cache")
                        for i in range(0, hc.GPIOLEN):
                            std[i] = np.std([item for item in cache_matrix[:, i] if item > 0])
                            mean[i] = np.mean([item for item in cache_matrix[:, i] if item > 0])
                        cache_found = True
                        logging.debug("std: " + str(std) + ", mean: " + str(mean))
                    else:
                        logging.warn("Cached sync data doesn't match current configuration, regenerating")
                        cache_found = False
            except IOError:
                logging.warn("Cached sync data song_filename not found: '" + cache_filename
                             + ".  One will be generated.")
    
        # Process audio song_filename
        row = 0
        data = musicfile.readframes(slc.CHUNK_SIZE)
        frequency_limits = calculate_channel_frequency(slc._MIN_FREQUENCY,
                                                       slc._MAX_FREQUENCY,
                                                       slc._CUSTOM_CHANNEL_MAPPING,
                                                       slc._CUSTOM_CHANNEL_FREQUENCIES)

        self.playing = True
        while data != '' and not play_now and not self.stop_now:
            self.current_song['position'] = musicfile.tell() / sample_rate
            
            if slc._usefm=='true':
                os.write(slc._music_pipe_w, data)
            else:
                output.write(data)
    
            # Control lights with cached timing values if they exist
            fft_levels = None
            if cache_found and self.readcache:
                if row < len(cache):
                    fft_levels = cache[row]
                else:
                    logging.warning("Ran out of cached FFT values, will update the cache.")
                    cache_found = False
    
            if fft_levels == None:
                # No cache - Compute FFT in this chunk, and cache results
                fft_levels = fft.calculate_levels(data, slc.CHUNK_SIZE, sample_rate, frequency_limits)
                cache.append(fft_levels)
                
            self.update_lights(fft_levels, mean, std)
    
            # Read next chunk of data from music song_filename
            data = musicfile.readframes(slc.CHUNK_SIZE)
            row = row + 1
    
            # Load new application state in case we've been interrupted
            cm.load_state()
            play_now = int(cm.get_state('play_now', 0))
    
        if not cache_found:
            with open(cache_filename, 'wb') as playlist_fp:
                writer = csv.writer(playlist_fp, delimiter=',')
                writer.writerows(cache)
                logging.info("Cached sync data written to '." + cache_filename
                             + "' [" + str(len(cache)) + " rows]")
    
        # Cleanup the pifm process
        if slc._usefm=='true':
            fm_process.kill()
    
        # Song is done playing
        self.playing = False

    def parse_args(self):
        '''Parse command line arguments used by the synchronized lightshow controller (slc)'''
        parser = argparse.ArgumentParser()
        filegroup = parser.add_mutually_exclusive_group()
        filegroup.add_argument('--playlist', default=slc._PLAYLIST_PATH,
                               help='Playlist to choose song from.')
        filegroup.add_argument('--file', help='path to the song to play (required if no'
                               'playlist is designated)')
        parser.add_argument('--readcache', type=int, default=1,
                            help='read light timing from cache if available. Default: true')
        args = parser.parse_args()
        self.readcache = args.readcache
        self.arg_playlist = args.playlist
        self.arg_file = args.file
        
if __name__ == "__main__":
    lightshow = slc()
    lightshow.parse_args()
    hc.initialize()
    if cm.lightshow()['mode'] == 'audio-in':
        # Turn on audio in mode
        lightshow.audio_in()
    else:
        # Make sure one of --playlist or --file was specified
        if lightshow.arg_file == None and lightshow.arg_playlist == None:
            print "One of --playlist or --file must be specified"
            hc.clean_up()
            sys.exit()

        # Play the chosen song
        if lightshow.arg_file != None:
            lightshow.play(lightshow.arg_file)
        else:
            next_song = lightshow.get_next_song(lightshow.arg_playlist)
            lightshow.play(next_song['filename'])
            
    # Clean-up on shutdown
    hc.clean_up()
