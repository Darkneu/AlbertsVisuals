# -*- coding: utf-8 -*-
"""
Created on Tue Dec 11 11:26:18 2018

@author: Dario


"""
import cv2
import time
import pickle

from Audio import AudioFile
from Video import Vid
from Control_Interface import fader_ux, trigger, osc
from Control_Visual import visualize

def main(video_filename = '/Users/Dario/Pictures/jumper.mp4', audio_filename = '/Users/Dario/Pictures/hero.wav', debug = 1, web_mode = False):
    """ 
    audio should be a wav file, video should be mp4 other video formats might work as well
    debug = 0 no fft, runs forever
    debug = 1 fft displayed, runs forever
    debug >1 fft displayed, run for debug seconds
    web_mode = True won't display video or any gui windows, the frames are returned
    web_mode = false, will display windows for gui and video
    """
    disp_fft = True if debug>0 and not(web_mode) else False  
    run_time = debug if debug>1 else False
    
    #create albert object that contains audio and video processing
    albi = Albert(v_filename=video_filename, a_filename=audio_filename, number_of_triggers = 2, number_of_oscillators = 3, resizefactor=0.75, disp_fft=disp_fft, web_mode=web_mode) 
    albi.video_object.resizefactor = 1
    albi.video_object.interpolationfactor = 1.2
    albi.video_object.framerate = 14
    albi.video_object.colmap = 0
    
    while albi.status:
        
        #compute next frame and display next frame and audio
        _ = albi.get_next_frame()
        
        #wait to reach desired framerate
        while time.time()-albi.update_start_time<(1.0/albi.video_object.framerate):
            pass
        print('frames per second: '+str(1.0/(time.time()-albi.update_start_time)))
        if debug>1 and run_time<time.time()-albi.start_time:
            albi.close()
            break



class Albert:
    """this class generates the video and audio objects and performs all the computations necessary to update a frame"""
    
    def __init__(self, v_filename, a_filename, number_of_triggers = 2, number_of_oscillators = 3, resizefactor=0.5, disp_fft=False, web_mode=True):
        print('----------------------------------------------------------')
        print('-----------------HELLOOOOOO ------------------------------')
        print('--------------- I am Albert ------------------------------')
        print('---------------now, watch this!---------------------------')
        print('----------------------------------------------------------')
        
        self.web_mode = web_mode
        self.disp_fft = disp_fft
        self.disp_stats = not(self.web_mode)
        self.disp_GUI = not(self.web_mode)
        self.v_filename = v_filename
        self.a_filename = a_filename
        self.status = True # turns false when user exits the program
        self.resizefactor = resizefactor
        self.en_audio_A_weighting = True # enable or disable A weighting of audio samples
        
        # generat audio and video objects
        self.audio_object = AudioFile(self.a_filename)
        self.audio_object.apply_A_weighting = self.en_audio_A_weighting 
    
        self.video_object = Vid(self.v_filename, resizefactor=self.resizefactor)
        self.video_object.interpolationfactor = 1.5
        self.video_object.audiorate = self.audio_object.rate
        self.video_object.framerate = 25 # desired framerate        
        
        # generate fader objects
        if self.disp_GUI:
            self.faders = []
            self.faders.append(fader_ux('color', ['hue1', 'hue2', 'sat1', 'sat2', 'val1', 'val2'], [0, 0, 0, 0, 0, 0]))
            self.faders.append(fader_ux('static', ['zoom', 'static_dilate', 'static_blur', 'static_blend', 'static_translation_x_img1', 'static_translation_y_img1'], [5, 0, 0, 50, 30, 20], maxvalue=100))
            self.faders.append(fader_ux('transmixer', ['M1_t_factor', 'M2_t_factor', 'M4_t_factor', 'M5_t_factor', 'M1_t_add', 'M4_t_add'], [50, 50, 50, 50, 50, 50], maxvalue=100))
    
    
        # generate trigger objects
        self.triggers = []
        for i in range(0, number_of_triggers):
            self.triggers.append(trigger('trigger '+str(i), self.audio_object.rate, frequency_r=(20,8000), f_width=(1,4000), max_attack_release=(10,30), displayGUI=self.disp_GUI))
    
        # generate oscillator objects
        self.oscillators = []
        for i in range(0,number_of_oscillators):
            self.oscillators.append(osc('OSC MODULE '+str(i), displayGUI=self.disp_GUI))
            
        # generate fft visualisation
        if disp_fft: self.vis = visualize(self.video_object)
        
        # for timekeeping
        self.nrframes=0
        self.start_time = time.time()
        
        
    def get_next_frame(self):
        """compute audio fft and next frame"""
        
        self.update_start_time = time.time()
        
        #perform fft of audio
        y_fft, amp, audio_status = self.audio_object.fft()
        if not(audio_status):
            self.restart_audio()
            y_fft, amp, audio_status = self.audio_object.fft()
        if self.disp_stats: print('time fft : '+str(time.time()-self.update_start_time))
        
        # get values from faders
        t_ui = time.time()
        for fad in self.faders: fad.set_values_video(self.video_object)
        if self.disp_stats: print('time fader update : '+str(time.time()-t_ui))
        
        # get values from triggers
        t_ui = time.time()
        for trig in self.triggers: trig.set_values_video(self.video_object, y_fft)
        if self.disp_stats: print('time trigger update : '+str(time.time()-t_ui))

        # get values from oscilators
        t_ui = time.time()
        for osci in self.oscillators: osci.set_values_video(self.video_object)
        if self.disp_stats: print('time oscillator update : '+str(time.time()-t_ui))
        
        # display equalizer
        if self.disp_fft: self.vis.plot_fast(y_fft, self.triggers)
                
        # read, process and display frame
        t_ui = time.time()
        frame = self.video_object.compute_and_disp_frame(return_frame = self.web_mode)
        if self.disp_stats: print('time video update : '+str(time.time()-t_ui))
        
        #update frame count and call key control
        if self.disp_stats: self.nrframes += 1
        if not(self.web_mode): self.status = self.key_control()
        
        return frame #cv2.cvtColor(frame,cv2.COLOR_BGR2RGB) #return RGB


        
    def key_control(self):
        """the user can press keys to trigger acctions"""
        
        k = cv2.waitKey(5) & 0xFF

        if k == ord('m'):
            #flips image
            self.video_object.flipimage = not(self.video_object.flipimage)
        elif k == ord('r'):
            self.video_object.parameter_dict['static_recursion_depth'] +=  1
        elif k == ord('d'):
            self.video_object.parameter_dict['static_recursion_depth'] -=  1
        elif k== ord('w'):
            #enable / disable audio sample A weighting
            self.audio_object.apply_A_weighting=not(self.audio_object.apply_A_weighting)
        elif k==ord('s'): 
            #save settings
            save_name = input('saving settings, enter filename: ')
            if save_name == 'd': save_name = 'Albert_settings_default'
            self.save_settings(filename=save_name)
        elif k==ord('S'): 
            #save default settings
            self.save_settings(filename='Albert_settings_default')
        elif k==ord('l'): 
            # recall settings
            load_name = input('loading settings, enter filename: ')
            self.recal_settings(filename=load_name)
        elif k==ord('L'):
            # recall default settings
            self.recal_settings(filename='Albert_settings_default')
        elif k==ord('+'):
            self.video_object.interpolationfactor+=0.1 #makes video larger
        elif k==ord('-'):
            self.videRo_object.interpolationfactor-=0.1
        if k == 27:
            #stop video and audio
            frame_rate = self.nrframes / (time.time() - self.start_time)
            print('average frame rate : '+str(frame_rate))
            
            self.close()
            
            return False
        
        return True
    
    
    def close(self):
        self.audio_object.close()
        self.video_object.video.release()
        cv2.destroyAllWindows()
        
    def restart_audio(self):
        self.audio_object.close()
        self.audio_object = AudioFile(self.a_filename)
        self.audio_object.apply_A_weighting = self.en_audio_A_weighting # enable or disable A weighting of audio samples


    def save_settings(self, filename):
        """save settings of ui (triggers, faders, oscillators)"""
        
        #make settings dict
        settings = {'faders': self.faders,
                   'triggers': self.triggers,
                   'oscillators': self.oscillators
                   }
        with open(str(filename)+'.pickle', 'wb') as handle:
            pickle.dump(settings, handle, protocol=pickle.HIGHEST_PROTOCOL)


    def recal_settings(self, filename):
        """load settings of ui (triggers, faders, oscillators)"""
        
        #open settings dict
        with open(str(filename)+'.pickle', 'rb') as handle:
            settings = pickle.load(handle)
        
        self.faders = settings['faders']
        self.triggers = settings['triggers']
        self.oscillators = settings['oscillators']
        
        #update settings
        for fad in self.faders:
                fad.set_all_values(fad.slidervalues, GUI=self.disp_GUI)
        for trig in self.triggers:
            trig.set_values(trig.gain, trig.frequency, trig.frequency_width, trig.routing, trig.attack, trig.release, GUI=self.disp_GUI)
        for osci in self.oscillators:
            osci.set_values(speed1=osci.speed1, amp1=osci.amp1, routing1=osci.routing1, speed2=osci.speed2, amp2=osci.amp2, routing2=osci.routing2, GUI=self.disp_GUI)



if __name__ == "__main__":
    main()
