
# -*- coding: utf-8 -*-
"""
Created on Sat Feb 13 16:16:30 2016

@author: richard
"""
__version__ = '0.1.0'

import argparse
import datetime
import os
from fritzconnection import fritzstatus
from fritzconnection import fritztools
from emailAlert import EmailNotify
import cPickle as pickle

FRITZ_IP_ADDRESS = '192.168.1.1'
FRITZ_TCP_PORT = 49000

class FritzMonitorInternet(object):

    def __init__(self, master=None,
                       address=FRITZ_IP_ADDRESS,
                       port=FRITZ_TCP_PORT,
                       tx_alert_threshold_bytes=10000,
                       rx_alert_threshold_bytes=10000,
                       alert_interval=14400):
        
        self.status = fritzstatus.FritzStatus(address=address, port=port)
        self.max_upstream, self.max_downstream = self.status.max_byte_rate
        self.emailAlert = EmailNotify()
        self.emailAlert.set_smtp_password("XXXXXXXXX")
        self.emailAlert.set_from_address("reynolds.avenue@clarke.biz")
        self.emailAlert.set_to_address("richard@clarke.biz")
        self.emailAlert.set_subject("FritzBox: Internet Alert!")
       
        self.last_date_and_time = None
        self.last_bytes_received = None
        self.last_bytes_sent = None
        self.current_bytes_received = self.status.bytes_received
        self.current_bytes_sent = self.status.bytes_sent
        self.date_and_time = datetime.datetime.now()
        
        self.delta_tx = 0
        self.delta_rx = 0
        self.cummulative_rx = 0 #Actually need to read this from an external persistent file
        self.cummulative_tx = 0 #Actually need to read this from an external persistent file
        self.timer_count = 0
        self.alert_interval_seconds = alert_interval
        self.tx_alert_threshold = float(tx_alert_threshold_bytes)
        self.rx_alert_threshold = float(rx_alert_threshold_bytes)
        self.read_last_traffic_count_from_file()
        
    def set_alert_parameters(self, tx_alert_threshold_bytes = 2e9, rx_alert_threshold_bytes = 4e9):
        #self.alert_window_length_seconds = window_length
        self.tx_alert_threshold = tx_alert_threshold_bytes
        self.rx_alert_threshold = rx_alert_threshold_bytes
        
    def print_parameters(self):
        delta_received = fritztools.format_num(self.delta_rx)
        delta_sent = fritztools.format_num(self.delta_tx)
        total_sent = fritztools.format_num(self.cummulative_tx)
        total_received = fritztools.format_num(self.cummulative_rx)
        tx_thresh = fritztools.format_num(self.tx_alert_threshold)
        rx_thresh = fritztools.format_num(self.rx_alert_threshold)
        alertText = 'Time since last check: {}\n\n'.format(self.delta_time.seconds)
        alertText += 'Alert Interval = {}\n\n'.format(self.alert_interval_seconds)
        alertText += 'Alert Threshold TX/RX = %s/%s\n\n' % (tx_thresh,rx_thresh)
        alertText += 'Timer Count = {}\n\n'.format(self.timer_count)
        alertText += 'During the last monitor interval %s have been received and %s has been transmitted\n\n' % (delta_received,delta_sent)
        alertText += 'Total data sent: %s bytes\t Total data received = %s bytes\n\n' % (self.cummulative_tx,self.cummulative_rx)
        alertText += 'Total data sent: %s\t Total data received = %s\n\n' % (total_sent,total_received)
        print alertText
  
    def set_tx_threshold(self,threshold_bytes):
        self.tx_alert_threshold = threshold_bytes
        
    def set_rx_threshold(self,threshold_bytes):
        self.rx_alert_threshold = threshold_bytes
             
    def calculate_traffic_delta(self):
        self.read_last_traffic_count_from_file()
        self.current_bytes_received = self.status.bytes_received
        self.current_bytes_sent = self.status.bytes_sent
        self.date_and_time = datetime.datetime.now()
        
        self.delta_rx = self.current_bytes_received - self.last_bytes_received
        self.delta_tx = self.current_bytes_sent - self.last_bytes_sent
        self.delta_time = self.date_and_time - self.last_date_and_time
        
        self.timer_count += self.delta_time.seconds
        
        self.cummulative_rx += self.delta_rx 
        self.cummulative_tx += self.delta_tx
        
        #Internet plan data rollover date/time
        if self.date_and_time.day == 17:
            if ( (self.date_and_time.hour > 18) and (self.date_and_time.hour < 19) ):
                self.cummulative_rx = 0
                self.cummulative_tx = 0
        
        
        
        #text = "elapsed time: %d seconds, delta received: %d, delta sent: %s\n" % (self.delta_time.seconds,self.delta_rx, self.delta_tx)
        #print text
        #print "timer_count = %d\n" % self.timer_count
        #print "alert_interval_seconds = %d\n" % self.alert_interval_seconds
	
        
        if self.timer_count >= self.alert_interval_seconds:
            self.timer_count = 0
            text = "total sent = %d, total received = %d" % (self.cummulative_tx,self.cummulative_rx)
            print text
        
            if ( (self.delta_rx > self.rx_alert_threshold) or (self.delta_tx > self.tx_alert_threshold) ):
                print 'Alert triggered'
                received = fritztools.format_num(self.delta_rx)
                sent = fritztools.format_num(self.delta_tx)
                total_sent = fritztools.format_num(self.cummulative_tx)
                total_received = fritztools.format_num(self.cummulative_rx)
                alertText = 'Time since last check: {}\n\n'.format(self.delta_time)
                alertText += 'During the last monitor interval %s have been received and %s has been transmitted\n\n' % (received,sent)
                alertText += 'Total data sent: %s\t Total data received = %s' % (total_sent,total_received)
                
                self.emailAlert.set_text_body(alertText)
                self.emailAlert.send_email()
            
        self.write_current_traffic_count_to_file()
        self.print_parameters()
            
    def write_current_traffic_count_to_file(self):        
        f = open("internet_traffic.pickle","w") #opens file with name of "test.txt"
        pickle.dump([self.date_and_time, self.timer_count, self.current_bytes_received, self.current_bytes_sent, self.cummulative_rx, self.cummulative_tx], f)
        f.close()
        
    def read_last_traffic_count_from_file(self):
        if os.path.isfile("./internet_traffic.pickle"):
            with open("internet_traffic.pickle","r") as f:
                data = pickle.load(f)
                self.last_date_and_time = data[0]
                self.timer_count = data[1]
                self.last_bytes_received = data[2]
                self.last_bytes_sent = data[3]
                self.cummulative_rx = data[4]
                self.cummulative_tx = data[5]
                f.close()
                #print 'last_date_and_time = {}'.format(self.last_date_and_time)
                #print 'last_bytes_received = {}'.format(self.last_bytes_received)
                #print 'last_bytes_sent = {}'.format(self.last_bytes_sent)
        else:
            #May be first time the script has run so no previous record
            print 'internet_traffic.pickle file did not exist'
            self.last_date_and_time = self.date_and_time
            self.timer_count = 0
            self.last_bytes_received = self.status.bytes_received
            self.last_bytes_sent = self.status.bytes_sent
            
# ---------------------------------------------------------
# cli-section:
# ---------------------------------------------------------

def _get_cli_arguments():
    parser = argparse.ArgumentParser(description='FritzBox Monitor')
    parser.add_argument('-i', '--ip-address',
                        nargs='?', default=FRITZ_IP_ADDRESS,
                        dest='address',
                        help='ip-address of the FritzBox to connect to. '
                             'Default: %s' % FRITZ_IP_ADDRESS)
    parser.add_argument('-p', '--port',
                        nargs='?', default=FRITZ_TCP_PORT,
                        dest='port',
                        help='port of the FritzBox to connect to. '
                             'Default: %s' % FRITZ_TCP_PORT)
                             
    parser.add_argument('-s', '--send-thresh',
                        nargs='?', default=50000,
                        dest='tx_threshold',
                        help='Send traffic alert threshold '
                             'Default: %d' % 2e9)  
                             
    parser.add_argument('-r', '--receive-thresh',
                        nargs='?', default=50000,
                        dest='rx_threshold',
                        help='Receive traffic alert threshold '
                             'Default: %d' % 4e9)                          
     
    parser.add_argument('-t', '--alert-interval',
                            nargs='?', default=14400,
                            dest='alert_interval',
                            help='Traffic alerts window measurement interval '
                                 'Default: %d' % 14400)                                  
    args = parser.parse_args()
    return args
    
if __name__ == '__main__':
    root_dir = '/media/files/files/Seafile/Development/ShellScripts/checkFritzBox'
    arguments = _get_cli_arguments()
    print os.getcwd()
    os.chdir(root_dir)
    print os.getcwd()
    app = FritzMonitorInternet(address=arguments.address, port=arguments.port, tx_alert_threshold_bytes=arguments.tx_threshold, rx_alert_threshold_bytes=arguments.rx_threshold, alert_interval=int(arguments.alert_interval))
    
    #app.set_alert_parameters(tx_alert_threshold_bytes = 50000, rx_alert_threshold_bytes = 100000)
    app.calculate_traffic_delta()
    
