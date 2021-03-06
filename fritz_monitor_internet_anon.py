
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
    """
    The calculate_traffic_delta() method of this class will need to be executed
    frequently enough to be able to detect an overflow of the FritzBox 32 bit
    traffic registers so that the correct delta can be calculated. The maximum 
    duration between calls is determined by the maximum speed of the internet 
    connection and 2^32 bytes, i.e what is the minimum time 2^32 bytes could
    possibly be downloaded at the maximum line speed of the internet connection,
    assuming that the downstream speed is the higher than the upstream rate.
    e.g For a connection supporting 100Mbit/s downstream it will take
    (2^32 * 8)/100e6 = 343 seconds. Thus we should ensure that the shell script
    that we get cron to call to execute the traffic calc method is called at 
    least once per say 340 seconds.
    """

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
        self.last_fritzbox_traffic_counter_rx_32bit = 0
        self.last_fritzbox_traffic_counter_tx_32bit = 0
        #self.fritzbox_traffic_counter_rx_32bit = self.status.bytes_received
        #self.fritzbox_traffic_counter_tx_32bit = self.status.bytes_sent
        
        self.total_traffic_counter_at_last_alert_interval_tx = 0
        self.total_traffic_counter_at_last_alert_interval_rx = 0
        self.delta_traffic_counter_since_last_alert_interval_tx = 0
        self.delta_traffic_counter_since_last_alert_interval_rx = 0
        self.date_and_time = datetime.datetime.now()
        
        self.delta_tx = 0
        self.delta_rx = 0
       
        
        self.total_traffic_in_this_billing_interval_tx = 0
        self.total_traffic_in_this_billing_interval_rx = 0
        
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
        delta_rx_bytes = self.total_traffic_in_this_billing_interval_rx - self.total_traffic_counter_at_last_alert_interval_rx
        delta_tx_bytes = self.total_traffic_in_this_billing_interval_tx - self.total_traffic_counter_at_last_alert_interval_tx
        delta_received = fritztools.format_num(delta_rx_bytes)
        delta_sent = fritztools.format_num(delta_tx_bytes)
        
        tx_thresh = fritztools.format_num(self.tx_alert_threshold)
        rx_thresh = fritztools.format_num(self.rx_alert_threshold)
        rx_billing_delta = fritztools.format_num(self.total_traffic_in_this_billing_interval_rx)
        tx_billing_delta = fritztools.format_num(self.total_traffic_in_this_billing_interval_tx )
        alertText = 'Time since last check: {}\n\n'.format(self.delta_time.seconds)
        alertText += 'Alert Interval = {}\n\n'.format(self.alert_interval_seconds)
        alertText += 'Alert Threshold TX/RX = %s/%s\n\n' % (tx_thresh,rx_thresh)
        alertText += 'Timer Count = {}\n\n'.format(self.timer_count)
        alertText += 'FritzBox register bytes_received: {}\n\n'.format(self.status.bytes_received)
        alertText += 'FritzBox register bytes_sent: {}\n\n'.format(self.status.bytes_sent)
        alertText += 'During the last monitor interval %s have been received and %s has been transmitted\n\n' % (delta_received,delta_sent)
        alertText += 'Since start of billing interval : Data Sent = %s\t Data Received = %s' %(tx_billing_delta,rx_billing_delta)
        print alertText
  
    def set_tx_threshold(self,threshold_bytes):
        self.tx_alert_threshold = threshold_bytes
        
    def set_rx_threshold(self,threshold_bytes):
        self.rx_alert_threshold = threshold_bytes
             
    def calculate_traffic_delta(self):
        self.read_last_traffic_count_from_file()
        
        self.date_and_time = datetime.datetime.now()
        
        self.delta_rx = self.status.bytes_received - self.last_fritzbox_traffic_counter_rx_32bit
        #Check to see if the 32 bit traffic counter in Fritzbox has wrapped and compensate
        if self.delta_rx < 0:
            self.delta_rx = self.delta_rx + pow(2,32)
            
        self.delta_tx = self.status.bytes_sent - self.last_fritzbox_traffic_counter_tx_32bit
        #Check to see if the 32 bit traffic counter in Fritzbox has wrapped and compensate
        if self.delta_tx < 0:
            self.delta_tx = self.delta_tx + pow(2,32)
            
        self.delta_time = self.date_and_time - self.last_date_and_time
        
        self.timer_count += self.delta_time.seconds
        
        self.total_traffic_in_this_billing_interval_tx = self.total_traffic_in_this_billing_interval_tx + self.delta_tx
        self.total_traffic_in_this_billing_interval_rx = self.total_traffic_in_this_billing_interval_rx + self.delta_rx
        
       
        #Internet plan data rollover date/time
        if self.date_and_time.day == 17:
            if ( (self.date_and_time.hour == 18) and (self.date_and_time.minute < 12) ):
                rx_billing_delta = fritztools.format_num(self.total_traffic_in_this_billing_interval_rx)
                tx_billing_delta = fritztools.format_num(self.total_traffic_in_this_billing_interval_tx )
                 
                #Zero interval traffic total counter
                self.total_traffic_in_this_billing_interval_tx = 0
                self.total_traffic_in_this_billing_interval_rx = 0
                
                
                alertText = 'Internet Account Billing Rollover\n\n'
                alertText += 'Total data during last billing interval : Data Sent = %s\t Data Received = %s' %(tx_billing_delta,rx_billing_delta)
                self.emailAlert.set_subject("FritzBox: Billing Roll Over!")
                self.emailAlert.set_text_body(alertText)
                self.emailAlert.send_email()
        
        
	
        
        if self.timer_count >= self.alert_interval_seconds:
            
            #Reuse these delta object variables, since they will be recalculated above each time the method is called.
            self.delta_rx = self.total_traffic_in_this_billing_interval_rx - self.total_traffic_counter_at_last_alert_interval_rx
            self.delta_tx = self.total_traffic_in_this_billing_interval_tx - self.total_traffic_counter_at_last_alert_interval_tx
            self.timer_count = 0
            self.total_traffic_counter_at_last_alert_interval_tx = self.total_traffic_in_this_billing_interval_tx
            self.total_traffic_counter_at_last_alert_interval_rx = self.total_traffic_in_this_billing_interval_rx
            
        
            if ( (self.delta_rx > self.rx_alert_threshold) or (self.delta_tx > self.tx_alert_threshold) ):
                print 'Alert triggered'
                alert_interval_rx = fritztools.format_num(self.delta_rx)
                alert_interval_tx = fritztools.format_num(self.delta_tx)
                
                rx_billing_delta = fritztools.format_num(self.total_traffic_in_this_billing_interval_rx)
                tx_billing_delta = fritztools.format_num(self.total_traffic_in_this_billing_interval_tx)
                alertText = 'Alert Monitoring Interval is {} seconds\n\n'.format(self.alert_interval_seconds)
                alertText += 'Time since last check: {}\n\n'.format(self.delta_time)
                alertText += 'During the last alert monitor interval %s have been received and %s has been transmitted\n\n' % (alert_interval_rx,alert_interval_tx)
                alertText += 'Since start of billing interval : Data Sent = %s\t Data Received = %s\n' %(tx_billing_delta,rx_billing_delta)
                
                self.emailAlert.set_text_body(alertText)
                self.emailAlert.send_email()
            
        self.write_current_traffic_count_to_file()
        self.print_parameters()
            
    def write_current_traffic_count_to_file(self):        
        f = open("internet_traffic.pickle","w") #opens file with name of "test.txt"
        pickle.dump([self.date_and_time, self.timer_count, self.status.bytes_received, self.status.bytes_sent, self.total_traffic_in_this_billing_interval_rx, self.total_traffic_in_this_billing_interval_tx, self.total_traffic_counter_at_last_alert_interval_rx, self.total_traffic_counter_at_last_alert_interval_tx], f)
        f.close()
        
    def read_last_traffic_count_from_file(self):
        if os.path.isfile("./internet_traffic.pickle"):
            with open("internet_traffic.pickle","r") as f:
                data = pickle.load(f)
                self.last_date_and_time = data[0]
                self.timer_count = data[1]
                self.last_fritzbox_traffic_counter_rx_32bit = data[2]
                self.last_fritzbox_traffic_counter_tx_32bit = data[3]
                self.total_traffic_in_this_billing_interval_rx = data[4]
                self.total_traffic_in_this_billing_interval_tx = data[5]
                self.total_traffic_counter_at_last_alert_interval_rx = data[6]
                self.total_traffic_counter_at_last_alert_interval_tx = data[7]
               
                f.close()
               
        else:
            #May be first time the script has run so no previous record
            print 'internet_traffic.pickle file did not exist'
            self.last_date_and_time = self.date_and_time
            self.timer_count = 0
            self.last_fritzbox_traffic_counter_rx_32bit = self.status.bytes_received
            self.last_fritzbox_traffic_counter_tx_32bit = self.status.bytes_sent
            self.total_traffic_in_this_billing_interval_rx = 0
            
            
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
    #root_dir = '/media/files/files/Seafile/Development/ShellScripts/checkFritzBox'
    
    arguments = _get_cli_arguments()
    print os.getcwd()
    #os.chdir(root_dir)
    print os.getcwd()
    app = FritzMonitorInternet(address=arguments.address, port=arguments.port, tx_alert_threshold_bytes=arguments.tx_threshold, rx_alert_threshold_bytes=arguments.rx_threshold, alert_interval=int(arguments.alert_interval))
    
    #app.set_alert_parameters(tx_alert_threshold_bytes = 50000, rx_alert_threshold_bytes = 100000)
    app.calculate_traffic_delta()
    
